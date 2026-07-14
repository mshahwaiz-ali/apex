"""Validated account-policy configuration loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from apex.domain.account import AccountPolicy


class AccountPoliciesConfig(BaseModel):
    """Named account-policy presets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    default_policy: str = Field(min_length=1)
    policies: dict[str, AccountPolicy]

    def policy_for(self, name: str | None = None) -> AccountPolicy:
        """Return a named policy or the configured default."""

        selected = name or self.default_policy
        try:
            return self.policies[selected]
        except KeyError as exc:
            raise ValueError(f"unknown account policy: {selected}") from exc


def load_account_policies_config(path: str | Path) -> AccountPoliciesConfig:
    """Load account-policy presets from YAML."""

    raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("account-policy configuration file must contain a mapping")
    config = AccountPoliciesConfig.model_validate(raw)
    if config.default_policy not in config.policies:
        raise ValueError("default account policy must reference a configured policy")
    return config
