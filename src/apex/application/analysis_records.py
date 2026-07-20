"""Schema-versioned analysis record persistence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from apex.application.methodology_identity import METHODOLOGY_PATH, METHODOLOGY_VERSION

ANALYSIS_RECORD_SCHEMA_VERSION = 1
ANALYSIS_RECORD_DB_SCHEMA_VERSION = 3


def build_analysis_record(
    payload: Mapping[str, Any],
    *,
    provider: str = "configured-provider",
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    """Wrap a serialized analysis or scan payload with reproducibility metadata."""

    timestamp = recorded_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("analysis record timestamp must be timezone-aware")
    normalized_payload = _json_roundtrip(payload)
    source_type = "scan" if "results" in normalized_payload else "analysis"
    subject = _subject(normalized_payload)
    configuration_id = str(normalized_payload.get("configuration_id", "unknown"))
    scanner_type = normalized_payload.get("scanner_type")
    content_hash = _stable_hash(normalized_payload)
    identity = _stable_hash(
        {
            "source_type": source_type,
            "subject": subject,
            "generated_at": normalized_payload.get("generated_at"),
            "configuration_id": configuration_id,
            "scanner_type": scanner_type,
            "content_hash": content_hash,
        }
    )
    return {
        "schema_version": ANALYSIS_RECORD_SCHEMA_VERSION,
        "analysis_id": identity,
        "recorded_at": timestamp.isoformat(),
        "source_type": source_type,
        "provider": provider,
        "subject": subject,
        "configuration_id": configuration_id,
        "methodology_version": str(
            normalized_payload.get("methodology_version", METHODOLOGY_VERSION)
        ),
        "methodology_path": str(normalized_payload.get("methodology_path", METHODOLOGY_PATH)),
        "scanner_type": scanner_type,
        "content_hash": content_hash,
        "payload": normalized_payload,
    }


def write_analysis_record(path: Path, record: Mapping[str, Any], *, append: bool = True) -> None:
    """Write one analysis record as deterministic JSON or append-only JSONL."""

    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(_json_roundtrip(record), sort_keys=True, ensure_ascii=False) + "\n"
    if append:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
        return
    path.write_text(
        json.dumps(_json_roundtrip(record), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_analysis_record_sqlite(path: Path, record: Mapping[str, Any]) -> None:
    """Store one analysis record in a deterministic local SQLite database."""

    normalized = _json_roundtrip(record)
    _validate_record(normalized)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection, connection:
        _ensure_sqlite_schema(connection)
        connection.execute(
            """
            INSERT INTO analysis_records (
                analysis_id,
                schema_version,
                source_type,
                provider,
                subject,
                configuration_id,
                scanner_type,
                content_hash,
                recorded_at,
                payload_json,
                record_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(analysis_id) DO UPDATE SET
                schema_version=excluded.schema_version,
                source_type=excluded.source_type,
                provider=excluded.provider,
                subject=excluded.subject,
                configuration_id=excluded.configuration_id,
                scanner_type=excluded.scanner_type,
                content_hash=excluded.content_hash,
                recorded_at=excluded.recorded_at,
                payload_json=excluded.payload_json,
                record_json=excluded.record_json
            """,
            (
                normalized["analysis_id"],
                normalized["schema_version"],
                normalized["source_type"],
                normalized["provider"],
                normalized["subject"],
                normalized["configuration_id"],
                normalized.get("scanner_type"),
                normalized["content_hash"],
                normalized["recorded_at"],
                json.dumps(normalized["payload"], sort_keys=True, ensure_ascii=False),
                json.dumps(normalized, sort_keys=True, ensure_ascii=False),
            ),
        )
        _register_opportunities(connection, normalized)


def reconcile_pending_opportunities_sqlite(
    path: Path,
    symbol: str,
    candles: tuple[Any, ...],
) -> int:
    """Reconcile pending setups using closed future candles with conservative ambiguity."""

    if not path.exists() or not candles:
        return 0
    normalized_symbol = symbol.upper()
    updated = 0
    with closing(sqlite3.connect(path)) as connection, connection:
        _ensure_sqlite_schema(connection)
        rows = connection.execute(
            """
            SELECT opportunity_id, direction, generated_at, expiry_at, entry_low, entry_high,
                   entry_preferred, stop_price, targets_json, filled_at, mfe_r, mae_r
            FROM opportunity_outcomes
            WHERE symbol = ? AND status IN ('waiting_entry', 'filled')
            """,
            (normalized_symbol,),
        ).fetchall()
        for row in rows:
            result = _evaluate_opportunity_row(row, candles)
            if result is None:
                continue
            connection.execute(
                """
                UPDATE opportunity_outcomes
                SET status=?, outcome=?, filled_at=?, resolved_at=?, observed_until=?,
                    mfe_r=?, mae_r=?
                WHERE opportunity_id=?
                """,
                (*result, row[0]),
            )
            updated += 1
    return updated


def load_analysis_record_sqlite(path: Path, analysis_id: str) -> dict[str, Any] | None:
    """Load one stored analysis record by stable identity."""

    if not path.exists():
        return None
    with closing(sqlite3.connect(path)) as connection, connection:
        _ensure_sqlite_schema(connection)
        row = connection.execute(
            "SELECT record_json FROM analysis_records WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchone()
    if row is None:
        return None
    return cast(dict[str, Any], json.loads(row[0]))


def list_analysis_record_metadata_sqlite(
    path: Path, *, limit: int = 100
) -> tuple[dict[str, Any], ...]:
    """List recent record metadata without loading full payload blobs."""

    if limit <= 0:
        raise ValueError("analysis record metadata limit must be positive")
    if not path.exists():
        return ()
    with closing(sqlite3.connect(path)) as connection, connection:
        _ensure_sqlite_schema(connection)
        rows = connection.execute(
            """
            SELECT
                analysis_id,
                schema_version,
                source_type,
                provider,
                subject,
                configuration_id,
                scanner_type,
                content_hash,
                recorded_at
            FROM analysis_records
            ORDER BY recorded_at DESC, analysis_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return tuple(
        {
            "analysis_id": row[0],
            "schema_version": row[1],
            "source_type": row[2],
            "provider": row[3],
            "subject": row[4],
            "configuration_id": row[5],
            "scanner_type": row[6],
            "content_hash": row[7],
            "recorded_at": row[8],
        }
        for row in rows
    )


def _subject(payload: Mapping[str, Any]) -> str:
    symbol = payload.get("symbol")
    if isinstance(symbol, str) and symbol:
        return symbol
    if "results" in payload:
        return "scan"
    return "unknown"


def _stable_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json_roundtrip(payload: Mapping[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(payload, sort_keys=True, default=str)))


def _ensure_sqlite_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_record_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS opportunity_outcomes (
            opportunity_id TEXT PRIMARY KEY,
            analysis_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            expiry_at TEXT NOT NULL,
            entry_low REAL NOT NULL,
            entry_high REAL NOT NULL,
            entry_preferred REAL NOT NULL,
            stop_price REAL NOT NULL,
            targets_json TEXT NOT NULL,
            status TEXT NOT NULL,
            outcome TEXT,
            filled_at TEXT,
            resolved_at TEXT,
            observed_until TEXT,
            mfe_r REAL NOT NULL DEFAULT 0,
            mae_r REAL NOT NULL DEFAULT 0,
            source_type TEXT,
            opportunity_category TEXT,
            sequence_role TEXT,
            actionability_state TEXT,
            methodology_status TEXT,
            setup_expiry_seconds INTEGER,
            FOREIGN KEY(analysis_id) REFERENCES analysis_records(analysis_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opportunity_outcomes_pending
        ON opportunity_outcomes(symbol, status, generated_at)
        """
    )
    connection.execute(
        """
        INSERT INTO analysis_record_metadata (key, value)
        VALUES ('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(ANALYSIS_RECORD_DB_SCHEMA_VERSION),),
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_records (
            analysis_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            provider TEXT NOT NULL,
            subject TEXT NOT NULL,
            configuration_id TEXT NOT NULL,
            scanner_type TEXT,
            content_hash TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            record_json TEXT NOT NULL
        )
        """
    )
    _ensure_opportunity_outcome_columns(connection)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_analysis_records_subject ON analysis_records(subject)"
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_records_recorded_at
        ON analysis_records(recorded_at)
        """
    )


def _ensure_opportunity_outcome_columns(connection: sqlite3.Connection) -> None:
    columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(opportunity_outcomes)").fetchall()
    }
    additions = {
        "source_type": "TEXT",
        "opportunity_category": "TEXT",
        "sequence_role": "TEXT",
        "actionability_state": "TEXT",
        "methodology_status": "TEXT",
        "setup_expiry_seconds": "INTEGER",
    }
    for name, declaration in additions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE opportunity_outcomes ADD COLUMN {name} {declaration}")


def _validate_record(record: Mapping[str, Any]) -> None:
    required = (
        "analysis_id",
        "schema_version",
        "source_type",
        "provider",
        "subject",
        "configuration_id",
        "content_hash",
        "recorded_at",
        "payload",
    )
    missing = [field for field in required if field not in record]
    if missing:
        raise ValueError(f"analysis record missing required fields: {', '.join(missing)}")
    if not isinstance(record["payload"], dict):
        raise ValueError("analysis record payload must be a mapping")


def _register_opportunities(connection: sqlite3.Connection, record: Mapping[str, Any]) -> None:
    payload = cast(Mapping[str, Any], record["payload"])
    for analysis in _record_analyses(payload):
        symbol = str(analysis.get("symbol") or payload.get("symbol") or "").upper()
        generated_at = str(analysis.get("generated_at") or payload.get("generated_at") or "")
        if not symbol or not generated_at:
            continue
        try:
            generated = datetime.fromisoformat(generated_at)
        except ValueError:
            continue

        for opportunity in _canonical_opportunities(analysis):
            setup = opportunity.get("setup")
            if not isinstance(setup, Mapping):
                setup = opportunity
            entry = setup.get("entry")
            stop = setup.get("stop_loss")
            targets = setup.get("take_profits")
            if (
                not isinstance(entry, Mapping)
                or not isinstance(stop, Mapping)
                or not isinstance(targets, list)
            ):
                continue
            try:
                entry_low = float(entry["lower"])
                entry_high = float(entry["upper"])
                entry_preferred = float(entry["preferred"])
                stop_price = float(stop["price"])
            except (KeyError, TypeError, ValueError):
                continue

            expiry_seconds = int(setup.get("setup_expiry_seconds") or 3600)
            expiry_at = datetime.fromtimestamp(
                generated.timestamp() + expiry_seconds,
                tz=UTC,
            ).isoformat()
            candidate_id = str(
                opportunity.get("candidate_id")
                or setup.get("candidate_id")
                or opportunity.get("opportunity_id")
                or "unknown"
            )
            opportunity_id = _canonical_opportunity_id(
                opportunity,
                setup=setup,
                symbol=symbol,
                generated_at=generated_at,
                candidate_id=candidate_id,
            )
            verdict = opportunity.get("methodology_verdict")
            methodology_status = (
                str(verdict.get("status"))
                if isinstance(verdict, Mapping) and verdict.get("status") is not None
                else None
            )
            connection.execute(
                """
                INSERT INTO opportunity_outcomes (
                    opportunity_id, analysis_id, symbol, candidate_id, direction, generated_at,
                    expiry_at, entry_low, entry_high, entry_preferred, stop_price, targets_json,
                    status, source_type, opportunity_category, sequence_role,
                    actionability_state, methodology_status, setup_expiry_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting_entry', ?, ?, ?, ?, ?, ?)
                ON CONFLICT(opportunity_id) DO UPDATE SET
                    candidate_id=excluded.candidate_id,
                    direction=excluded.direction,
                    expiry_at=excluded.expiry_at,
                    entry_low=excluded.entry_low,
                    entry_high=excluded.entry_high,
                    entry_preferred=excluded.entry_preferred,
                    stop_price=excluded.stop_price,
                    targets_json=excluded.targets_json,
                    opportunity_category=COALESCE(
                        excluded.opportunity_category,
                        opportunity_outcomes.opportunity_category
                    ),
                    sequence_role=COALESCE(
                        excluded.sequence_role,
                        opportunity_outcomes.sequence_role
                    ),
                    actionability_state=COALESCE(
                        excluded.actionability_state,
                        opportunity_outcomes.actionability_state
                    ),
                    methodology_status=COALESCE(
                        excluded.methodology_status,
                        opportunity_outcomes.methodology_status
                    ),
                    setup_expiry_seconds=COALESCE(
                        excluded.setup_expiry_seconds,
                        opportunity_outcomes.setup_expiry_seconds
                    )
                """,
                (
                    opportunity_id,
                    record["analysis_id"],
                    symbol,
                    candidate_id,
                    str(opportunity.get("direction") or setup.get("direction") or ""),
                    generated_at,
                    expiry_at,
                    entry_low,
                    entry_high,
                    entry_preferred,
                    stop_price,
                    json.dumps(targets, sort_keys=True),
                    str(record.get("source_type") or "analysis"),
                    _optional_text(opportunity.get("category")),
                    _optional_text(opportunity.get("sequence_role")),
                    _optional_text(
                        opportunity.get("actionability_state")
                        or setup.get("actionability_state")
                        or setup.get("entry_status")
                    ),
                    methodology_status,
                    expiry_seconds,
                ),
            )


def _record_analyses(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = payload.get("results")
    if isinstance(raw, list):
        return tuple(item for item in raw if isinstance(item, Mapping))
    return (payload,)


def _canonical_opportunities(
    analysis: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    portfolio = analysis.get("opportunity_portfolio")
    if isinstance(portfolio, Mapping):
        primary = portfolio.get("opportunities")
        if isinstance(primary, list):
            return _deduplicate_opportunities(primary)
        combined: list[object] = []
        for key in (
            "current_opportunities",
            "nearby_opportunities",
            "follow_up_opportunities",
            "runner_opportunities",
        ):
            value = portfolio.get(key)
            if isinstance(value, list):
                combined.extend(value)
        if combined:
            return _deduplicate_opportunities(combined)

    legacy: list[Mapping[str, Any]] = []
    for key in ("setup", "developing_setup"):
        setup = analysis.get(key)
        if isinstance(setup, Mapping):
            legacy.append(setup)
    return tuple(legacy)


def _deduplicate_opportunities(values: list[object]) -> tuple[Mapping[str, Any], ...]:
    result: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, Mapping):
            continue
        identity = str(value.get("opportunity_id") or value.get("candidate_id") or "")
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        result.append(value)
    return tuple(result)


def _canonical_opportunity_id(
    opportunity: Mapping[str, Any],
    *,
    setup: Mapping[str, Any],
    symbol: str,
    generated_at: str,
    candidate_id: str,
) -> str:
    canonical = opportunity.get("opportunity_id")
    if canonical is not None and str(canonical).strip():
        return str(canonical).strip()
    return _stable_hash(
        {
            "symbol": symbol,
            "candidate_id": candidate_id,
            "generated_at": generated_at,
            "category": opportunity.get("category"),
            "sequence_role": opportunity.get("sequence_role"),
            "direction": opportunity.get("direction") or setup.get("direction"),
            "entry": setup.get("entry"),
            "stop_loss": setup.get("stop_loss"),
        }
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _evaluate_opportunity_row(
    row: tuple[Any, ...], candles: tuple[Any, ...]
) -> tuple[str, str | None, str | None, str | None, str | None, float, float] | None:
    (
        _,
        direction,
        generated_at,
        expiry_at,
        entry_low,
        entry_high,
        preferred,
        stop,
        targets_json,
        filled_at,
        previous_mfe,
        previous_mae,
    ) = row
    generated = datetime.fromisoformat(generated_at)
    expiry = datetime.fromisoformat(expiry_at)
    relevant = tuple(
        candle for candle in candles if candle.is_closed and candle.close_time > generated
    )
    if not relevant:
        return None
    filled = datetime.fromisoformat(filled_at) if filled_at else None
    risk = abs(float(preferred) - float(stop))
    mfe_r, mae_r = float(previous_mfe), float(previous_mae)
    target_prices = tuple(float(item["price"]) for item in json.loads(targets_json))
    status, outcome, resolved = "waiting_entry", None, None
    for candle in relevant:
        if candle.open_time > expiry:
            status = "resolved"
            outcome = "expired_after_fill" if filled else "missed_entry"
            resolved = candle.open_time.isoformat()
            break
        if filled is None and candle.low <= entry_high and candle.high >= entry_low:
            filled = candle.open_time
        if filled is None:
            continue
        if direction == "long":
            mfe_r = max(mfe_r, (candle.high - preferred) / risk)
            mae_r = min(mae_r, (candle.low - preferred) / risk)
            stop_hit = candle.low <= stop
            target_hit = next(
                (price for price in reversed(target_prices) if candle.high >= price), None
            )
        else:
            mfe_r = max(mfe_r, (preferred - candle.low) / risk)
            mae_r = min(mae_r, (preferred - candle.high) / risk)
            stop_hit = candle.high >= stop
            target_hit = next(
                (price for price in reversed(target_prices) if candle.low <= price), None
            )
        # If stop and target occur in one bar, assume stop first; intrabar order is unknowable.
        if stop_hit:
            status, outcome, resolved = "resolved", "stop", candle.close_time.isoformat()
            break
        if target_hit is not None:
            status, outcome, resolved = (
                "resolved",
                f"target:{target_hit}",
                candle.close_time.isoformat(),
            )
            break
        status = "filled"
    return (
        status,
        outcome,
        filled.isoformat() if filled else None,
        resolved,
        relevant[-1].close_time.isoformat(),
        round(mfe_r, 6),
        round(mae_r, 6),
    )
