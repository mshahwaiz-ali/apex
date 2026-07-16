"""Persistence safety tests for provider-policy bindings in funded inputs."""

from pathlib import Path

import pytest

from apex.funded.provider_readiness_input import write_funded_readiness_input


def _binding(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "compatible": True,
        "execution_authorized": False,
    }
    payload.update(overrides)
    return payload


def test_authorizing_provider_binding_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="binding cannot authorize execution"):
        write_funded_readiness_input(
            tmp_path / "authorizing.json",
            {
                "execution_authorized": False,
                "provider_policy_binding": _binding(execution_authorized=True),
            },
        )


def test_incompatible_provider_binding_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="binding must be compatible"):
        write_funded_readiness_input(
            tmp_path / "incompatible.json",
            {
                "execution_authorized": False,
                "provider_policy_binding": _binding(compatible=False),
            },
        )
