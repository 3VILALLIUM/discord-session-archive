from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class RouteSpec:
    path: str
    method: str
    description: str


def list_routes() -> list[RouteSpec]:
    """Return the API surface for the scaffold app."""
    return [
        RouteSpec(path="/health", method="GET", description="Basic liveness check."),
        RouteSpec(path="/ready", method="GET", description="Readiness and policy posture check."),
        RouteSpec(path="/routes", method="GET", description="List available route specs."),
    ]


def health() -> dict[str, Any]:
    """Liveness probe endpoint payload."""
    return {
        "status": "ok",
        "service": "discord-audio-transcription",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def readiness() -> dict[str, Any]:
    """Readiness probe payload with policy-oriented defaults."""
    return {
        "status": "ready",
        "policy": {
            "mip_opt_out_required": True,
            "privacy_gate_required": True,
        },
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def routes_payload() -> dict[str, Any]:
    """Serializable route metadata payload."""
    return {
        "routes": [route.__dict__ for route in list_routes()],
    }
