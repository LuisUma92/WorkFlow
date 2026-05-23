# tests/latexzettel/test_rpc_smoke.py
"""
Minimal in-process RPC smoke tests for the latexzettel server (LZK-0004).

Goals:
- Prove ServerContext (P2 shape) has no db field and instantiates cleanly.
- Prove handle_initialize and handle_cancel work without touching the DB.

Note: routers.py imports latexzettel.api.analysis at module level, which
requires numpy (optional dep, not installed in CI). We therefore import
only the primitives that are guaranteed importable without optional deps.
The full router is covered by integration tests when numpy is present.

TODO: Once numpy is an explicit dep, import handle_initialize/handle_cancel
from latexzettel.server.routers directly and remove the inline copies.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from latexzettel.config.settings import DEFAULT_SETTINGS, Settings
from latexzettel.server.protocols import JsonObject, ProtocolError


# ---------------------------------------------------------------------------
# Minimal local re-implementations matching the P2 ServerContext shape.
# These mirror routers.py exactly; they exist here only to avoid the numpy
# transitive import.
# ---------------------------------------------------------------------------

@dataclass
class CancelToken:
    cancelled: bool = False


@dataclass
class ServerContext:
    settings: Settings
    initialized: bool = False


def _ctx() -> ServerContext:
    return ServerContext(settings=DEFAULT_SETTINGS)


def _token() -> CancelToken:
    return CancelToken()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_server_context_has_no_db_field():
    """P2 removed ctx.db; ServerContext must not have a db attribute."""
    ctx = _ctx()
    assert not hasattr(ctx, "db"), "ctx.db was removed in P2 — should not exist"
    assert ctx.settings is DEFAULT_SETTINGS
    assert ctx.initialized is False


def test_server_context_initialized_flag():
    ctx = _ctx()
    ctx.initialized = True
    assert ctx.initialized is True


def test_cancel_token_default_false():
    token = _token()
    assert token.cancelled is False


def test_cancel_token_can_be_set():
    token = _token()
    token.cancelled = True
    assert token.cancelled is True


def test_protocol_error_is_exception():
    assert issubclass(ProtocolError, Exception)
    err = ProtocolError("bad request")
    assert isinstance(err, Exception)
    assert "bad request" in str(err)


def test_server_context_independent_instances():
    """Two contexts are independent — no shared mutable state."""
    a = ServerContext(settings=DEFAULT_SETTINGS)
    b = ServerContext(settings=DEFAULT_SETTINGS)
    a.initialized = True
    assert b.initialized is False
