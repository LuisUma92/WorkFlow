# tests/latexzettel/test_server_main_characterization.py
"""
Characterization tests for latexzettel.server.main:main() (LZK-0001 RPC server).

Goal: pin the EXACT current behaviour of the stdio JSONL main loop (wire
protocol is a contract consumed by the Neovim plugin) before refactoring it
to reduce cyclomatic complexity. These tests must pass against the UNCHANGED
implementation; any oddity found is documented with a
"characterizes current behaviour (possible bug: ...)" comment rather than
fixed here.

`latexzettel.server.routers` imports `latexzettel.api.analysis`, which
imports numpy at module level. numpy is not a listed project dependency, so
this whole module is skipped when numpy is unavailable (mirrors the
precedent in tests/latexzettel/test_rpc_smoke.py).
"""
from __future__ import annotations

import io
import json
import sys
from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

pytest.importorskip("numpy")

import latexzettel.server.main as server_main  # noqa: E402
from latexzettel.server.routers import CancelledError, CancelToken, ServerContext  # noqa: E402
from latexzettel.server.protocols import ProtocolError  # noqa: E402


# =============================================================================
# Helpers
# =============================================================================


def _lines(*objs_or_strs: Any) -> str:
    """Join raw request lines (already-serialized strings) with '\n'."""
    return "\n".join(objs_or_strs) + "\n"


def _req(**fields: Any) -> str:
    return json.dumps(fields)


def _parse_stdout(raw: str) -> list[dict]:
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


@dataclass
class _RunResult:
    stdout_lines: list[dict]
    raw_stdout: str
    raw_stderr: str
    engine: MagicMock


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    *,
    stdin_text: str,
    routes: dict,
    init_global_db_raises: Optional[Exception] = None,
    env: Optional[dict] = None,
) -> _RunResult:
    monkeypatch.setattr(server_main, "ROUTES", routes)
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))

    engine = MagicMock(name="fake_engine")
    monkeypatch.setattr(server_main, "get_global_engine", lambda: engine)

    if init_global_db_raises is not None:

        def _fake_init_global_db(*, engine):  # noqa: ANN001
            raise init_global_db_raises

        monkeypatch.setattr(server_main, "init_global_db", _fake_init_global_db)
    else:
        monkeypatch.setattr(server_main, "init_global_db", lambda *, engine: None)

    if env:
        for k, v in env.items():
            monkeypatch.setenv(k, v)

    server_main.main()

    captured = capsys.readouterr()
    return _RunResult(
        stdout_lines=_parse_stdout(captured.out),
        raw_stdout=captured.out,
        raw_stderr=captured.err,
        engine=engine,
    )


def _init_handler(ctx: ServerContext, params: dict, token: CancelToken) -> dict:
    ctx.initialized = True
    return {"capabilities": {"methods": ["initialize"]}}


# =============================================================================
# Startup: DB init
# =============================================================================


def test_main_exits_2_when_db_init_fails(monkeypatch, capsys):
    monkeypatch.setattr(server_main, "ROUTES", {})
    monkeypatch.setattr(server_main, "get_global_engine", lambda: MagicMock())

    def _boom(*, engine):  # noqa: ANN001
        raise RuntimeError("db is on fire")

    monkeypatch.setattr(server_main, "init_global_db", _boom)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    with pytest.raises(SystemExit) as exc_info:
        server_main.main()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "DB init failed on startup: db is on fire" in captured.err


# =============================================================================
# Line-level parsing errors: swallowed silently (stderr only, no stdout, loop continues)
# =============================================================================


def test_main_swallows_blank_malformed_and_non_object_lines_then_continues(monkeypatch, capsys):
    stdin_text = _lines(
        "",  # blank line -> ProtocolError("Empty line")
        "{not valid json",  # malformed JSON
        "[1, 2, 3]",  # valid JSON, not an object
        _req(v=1, id="ok1", method="initialize"),
    )
    result = _run_main(
        monkeypatch,
        capsys,
        stdin_text=stdin_text,
        routes={"initialize": _init_handler},
    )

    # Only the well-formed request produces a response line.
    assert result.stdout_lines == [
        {
            "v": 1,
            "id": "ok1",
            "ok": True,
            "result": {"capabilities": {"methods": ["initialize"]}},
        }
    ]
    assert result.raw_stderr.count("Protocol error (no id):") == 3
    assert "Empty line" in result.raw_stderr
    assert "Invalid JSON" in result.raw_stderr
    assert "Request must be a JSON object" in result.raw_stderr


# =============================================================================
# Missing/invalid required fields (v/id/method)
# =============================================================================


def test_main_missing_v_and_method_but_valid_id_yields_invalid_request(monkeypatch, capsys):
    # characterizes current behaviour: only the FIRST missing field ('v') is
    # reported even though 'method' is also missing.
    stdin_text = _lines(_req(id="x1"))
    result = _run_main(monkeypatch, capsys, stdin_text=stdin_text, routes={})

    assert result.stdout_lines == [
        {
            "v": 1,  # falls back to PROTOCOL_VERSION since 'v' was absent
            "id": "x1",
            "ok": False,
            "error": {"code": "INVALID_REQUEST", "message": "Missing field 'v'", "data": {}},
        }
    ]


def test_main_invalid_v_type_falls_back_to_protocol_version_in_error(monkeypatch, capsys):
    # characterizes current behaviour (possible bug: server reports its own
    # PROTOCOL_VERSION as 'v' in the error envelope rather than echoing back
    # the client's malformed value or omitting it).
    stdin_text = _lines(_req(v="not-an-int", id="x3"))
    result = _run_main(monkeypatch, capsys, stdin_text=stdin_text, routes={})

    assert result.stdout_lines == [
        {
            "v": 1,
            "id": "x3",
            "ok": False,
            "error": {
                "code": "INVALID_REQUEST",
                "message": "Missing field 'method'",
                "data": {},
            },
        }
    ]


def test_main_method_wrong_type_yields_invalid_request(monkeypatch, capsys):
    stdin_text = _lines(_req(v=1, id="x2", method=123))
    result = _run_main(monkeypatch, capsys, stdin_text=stdin_text, routes={})

    assert result.stdout_lines == [
        {
            "v": 1,
            "id": "x2",
            "ok": False,
            "error": {
                "code": "INVALID_REQUEST",
                "message": "Field 'method' must be string",
                "data": {},
            },
        }
    ]


def test_main_v_wrong_type_with_id_and_method_present_yields_invalid_request(monkeypatch, capsys):
    # All required fields present so _require_fields passes; _get_v itself
    # raises because 'v' is not an int.
    stdin_text = _lines(_req(v="bad", id="x4", method="m"))
    result = _run_main(monkeypatch, capsys, stdin_text=stdin_text, routes={})

    assert result.stdout_lines == [
        {
            "v": 1,
            "id": "x4",
            "ok": False,
            "error": {
                "code": "INVALID_REQUEST",
                "message": "Field 'v' must be int",
                "data": {},
            },
        }
    ]


def test_main_params_none_defaults_to_empty_dict(monkeypatch, capsys):
    received: list[dict] = []

    stdin_text = _lines(
        _req(v=1, id="init", method="initialize"),
        _req(v=1, id="p1", method="echo", params=None),
    )
    result = _run_main(
        monkeypatch,
        capsys,
        stdin_text=stdin_text,
        routes={
            "initialize": _init_handler,
            "echo": lambda c, p, t: received.append(p) or {"got": p},
        },
    )

    assert received == [{}]
    assert result.stdout_lines[1] == {
        "v": 1,
        "id": "p1",
        "ok": True,
        "result": {"got": {}},
    }


def test_main_params_wrong_type_yields_invalid_request(monkeypatch, capsys):
    stdin_text = _lines(_req(v=1, id="p2", method="echo", params="oops"))
    result = _run_main(monkeypatch, capsys, stdin_text=stdin_text, routes={})

    assert result.stdout_lines == [
        {
            "v": 1,
            "id": "p2",
            "ok": False,
            "error": {
                "code": "INVALID_REQUEST",
                "message": "Field 'params' must be an object",
                "data": {},
            },
        }
    ]


def test_main_id_wrong_type_is_dropped_silently(monkeypatch, capsys):
    # 'id' is a list -> _get_id raises, but the outer handler cannot build an
    # id-bearing error envelope, so it just logs to stderr and emits nothing.
    stdin_text = _lines(_req(v=1, id=[1, 2], method="x"))
    result = _run_main(monkeypatch, capsys, stdin_text=stdin_text, routes={})

    assert result.stdout_lines == []
    assert "Protocol error (no id): Field 'id' must be string or int" in result.raw_stderr


# =============================================================================
# Version mismatch: responds AND terminates the read loop (break)
# =============================================================================


def test_main_version_mismatch_responds_and_breaks_loop(monkeypatch, capsys):
    stdin_text = _lines(
        _req(v=99, id="vmis", method="initialize"),
        # This second line would succeed if reached; the break must prevent that.
        _req(v=1, id="never", method="initialize"),
    )
    result = _run_main(
        monkeypatch, capsys, stdin_text=stdin_text, routes={"initialize": _init_handler}
    )

    assert result.stdout_lines == [
        {
            "v": 99,
            "id": "vmis",
            "ok": False,
            "error": {
                "code": "VERSION_MISMATCH",
                "message": "Protocol version mismatch: client=99, server=1",
                "data": {"server_protocol_version": 1},
            },
        }
    ]
    # dispose() still runs after the break.
    result.engine.dispose.assert_called_once()


# =============================================================================
# Not-initialized gate
# =============================================================================


def test_main_not_initialized_rejects_non_initialize_non_cancel_method(monkeypatch, capsys):
    stdin_text = _lines(_req(v=1, id="r1", method="other"))
    result = _run_main(
        monkeypatch, capsys, stdin_text=stdin_text, routes={"other": lambda c, p, t: {}}
    )

    assert result.stdout_lines == [
        {
            "v": 1,
            "id": "r1",
            "ok": False,
            "error": {
                "code": "NOT_INITIALIZED",
                "message": "Server not initialized. Call method 'initialize' first.",
                "data": {"required_method": "initialize"},
            },
        }
    ]


def test_main_cancel_bypasses_not_initialized_gate(monkeypatch, capsys):
    stdin_text = _lines(_req(v=1, id="c1", method="cancel", params={"id_to_cancel": "nope"}))
    result = _run_main(
        monkeypatch,
        capsys,
        stdin_text=stdin_text,
        routes={"cancel": lambda c, p, t: {"cancelled": True}},
    )

    assert result.stdout_lines == [
        {"v": 1, "id": "c1", "ok": True, "result": {"cancelled": True}}
    ]


# =============================================================================
# Unknown method / successful dispatch
# =============================================================================


def test_main_unknown_method_yields_method_not_found(monkeypatch, capsys):
    stdin_text = _lines(
        _req(v=1, id="init", method="initialize"),
        _req(v=1, id="r2", method="does_not_exist"),
    )
    result = _run_main(
        monkeypatch, capsys, stdin_text=stdin_text, routes={"initialize": _init_handler}
    )

    assert result.stdout_lines[1] == {
        "v": 1,
        "id": "r2",
        "ok": False,
        "error": {
            "code": "METHOD_NOT_FOUND",
            "message": "Unknown method 'does_not_exist'",
            "data": {},
        },
    }


def test_main_successful_dispatch_returns_ok_envelope(monkeypatch, capsys):
    stdin_text = _lines(
        _req(v=1, id="init", method="initialize"),
        _req(v=1, id="r3", method="echo"),
    )
    result = _run_main(
        monkeypatch,
        capsys,
        stdin_text=stdin_text,
        routes={
            "initialize": _init_handler,
            "echo": lambda c, p, t: {"pong": True, "unicode": "ñ"},
        },
    )

    assert result.stdout_lines[1] == {
        "v": 1,
        "id": "r3",
        "ok": True,
        "result": {"pong": True, "unicode": "ñ"},
    }
    # stdout is NDJSON with ensure_ascii=False: literal unicode, not \u escapes.
    assert "ñ" in result.raw_stdout
    assert "\\u00f1" not in result.raw_stdout


# =============================================================================
# Handler exceptions
# =============================================================================


def test_main_handler_protocol_error_yields_invalid_request(monkeypatch, capsys):
    stdin_text = _lines(
        _req(v=1, id="init", method="initialize"),
        _req(v=1, id="r4", method="bad_call"),
    )

    def _bad_call(c, p, t):  # noqa: ANN001
        raise ProtocolError("nope")

    result = _run_main(
        monkeypatch,
        capsys,
        stdin_text=stdin_text,
        routes={"initialize": _init_handler, "bad_call": _bad_call},
    )

    assert result.stdout_lines[1] == {
        "v": 1,
        "id": "r4",
        "ok": False,
        "error": {"code": "INVALID_REQUEST", "message": "nope", "data": {}},
    }


def test_main_handler_generic_exception_yields_internal_error_without_trace(monkeypatch, capsys):
    stdin_text = _lines(
        _req(v=1, id="init", method="initialize"),
        _req(v=1, id="r5", method="boom"),
    )

    def _boom(c, p, t):  # noqa: ANN001
        raise ValueError("kaboom")

    result = _run_main(
        monkeypatch,
        capsys,
        stdin_text=stdin_text,
        routes={"initialize": _init_handler, "boom": _boom},
    )

    assert result.stdout_lines[1] == {
        "v": 1,
        "id": "r5",
        "ok": False,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "kaboom",
            "data": {"exception": "ValueError"},
        },
    }


def test_main_handler_generic_exception_debug_mode_includes_trace(monkeypatch, capsys):
    stdin_text = _lines(
        _req(v=1, id="init", method="initialize"),
        _req(v=1, id="r6", method="boom"),
    )

    def _boom(c, p, t):  # noqa: ANN001
        raise ValueError("kaboom")

    result = _run_main(
        monkeypatch,
        capsys,
        stdin_text=stdin_text,
        routes={"initialize": _init_handler, "boom": _boom},
        env={"LATEXZETTEL_SERVER_DEBUG": "1"},
    )

    resp = result.stdout_lines[1]
    assert resp["ok"] is False
    assert resp["error"]["code"] == "INTERNAL_ERROR"
    assert resp["error"]["data"]["exception"] == "ValueError"
    assert "kaboom" in resp["error"]["data"]["trace"]


def test_main_handler_cancelled_error_yields_cancelled(monkeypatch, capsys):
    stdin_text = _lines(
        _req(v=1, id="init", method="initialize"),
        _req(v=1, id="r7", method="cancel_me"),
    )

    def _cancel_me(c, p, t):  # noqa: ANN001
        raise CancelledError()

    result = _run_main(
        monkeypatch,
        capsys,
        stdin_text=stdin_text,
        routes={"initialize": _init_handler, "cancel_me": _cancel_me},
    )

    assert result.stdout_lines[1] == {
        "v": 1,
        "id": "r7",
        "ok": False,
        "error": {"code": "CANCELLED", "message": "Request cancelled", "data": {}},
    }


# =============================================================================
# Cancel bookkeeping side-effect: marks a previously-created token
# =============================================================================


def test_main_cancel_marks_previously_created_token(monkeypatch, capsys):
    captured_tokens: list[CancelToken] = []

    def _op1(c, p, t):  # noqa: ANN001
        captured_tokens.append(t)
        return {"started": True}

    stdin_text = _lines(
        _req(v=1, id="init", method="initialize"),
        _req(v=1, id="opid", method="op1"),
        _req(v=1, id="c1", method="cancel", params={"id_to_cancel": "opid"}),
    )
    _run_main(
        monkeypatch,
        capsys,
        stdin_text=stdin_text,
        routes={
            "initialize": _init_handler,
            "op1": _op1,
            "cancel": lambda c, p, t: {"cancelled": True},
        },
    )

    assert len(captured_tokens) == 1
    assert captured_tokens[0].cancelled is True


def test_main_cancel_of_unknown_id_to_cancel_is_a_noop(monkeypatch, capsys):
    stdin_text = _lines(
        _req(v=1, id="init", method="initialize"),
        _req(v=1, id="c1", method="cancel", params={"id_to_cancel": "ghost"}),
    )
    result = _run_main(
        monkeypatch,
        capsys,
        stdin_text=stdin_text,
        routes={"initialize": _init_handler, "cancel": lambda c, p, t: {"cancelled": True}},
    )

    assert result.stdout_lines[1] == {
        "v": 1,
        "id": "c1",
        "ok": True,
        "result": {"cancelled": True},
    }


# =============================================================================
# Shutdown: engine disposal
# =============================================================================


def test_main_disposes_engine_on_normal_eof(monkeypatch, capsys):
    stdin_text = _lines(_req(v=1, id="init", method="initialize"))
    result = _run_main(
        monkeypatch, capsys, stdin_text=stdin_text, routes={"initialize": _init_handler}
    )
    result.engine.dispose.assert_called_once()


def test_main_swallows_dispose_exception(monkeypatch, capsys):
    stdin_text = _lines(_req(v=1, id="init", method="initialize"))

    monkeypatch.setattr(server_main, "ROUTES", {"initialize": _init_handler})
    engine = MagicMock(name="fake_engine")
    engine.dispose.side_effect = RuntimeError("dispose blew up")
    monkeypatch.setattr(server_main, "get_global_engine", lambda: engine)
    monkeypatch.setattr(server_main, "init_global_db", lambda *, engine: None)
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))

    # Must not raise even though dispose() blows up.
    server_main.main()

    captured = capsys.readouterr()
    assert _parse_stdout(captured.out) == [
        {
            "v": 1,
            "id": "init",
            "ok": True,
            "result": {"capabilities": {"methods": ["initialize"]}},
        }
    ]


# =============================================================================
# Defensive branches (unreachable via real NDJSON input; exercised via
# targeted monkeypatching to pin their exact swallow-and-continue behaviour)
# =============================================================================


def test_main_defensive_exception_while_building_fallback_error_is_swallowed(
    monkeypatch, capsys
):
    """Exercises the innermost `except Exception: resp = None` guard around
    fallback error-envelope construction. Real json.loads() output never has
    a raising .get(), so this is forced via a hostile dict subclass whose
    `in` operator still works (so _require_fields can raise a normal
    ProtocolError first) but whose .get() blows up on the retry.
    """

    class _HostileDict(dict):
        def get(self, *args, **kwargs):
            raise RuntimeError("boom-on-get")

    hostile_msg = _HostileDict({"id": "x"})  # missing 'v' and 'method'
    monkeypatch.setattr(server_main, "_parse_request_line", lambda line: hostile_msg)

    result = _run_main(
        monkeypatch, capsys, stdin_text="irrelevant-single-line\n", routes={}
    )

    assert result.stdout_lines == []


def test_main_cancel_bookkeeping_exception_is_swallowed(monkeypatch, capsys):
    """Exercises the bare `except Exception: pass` guarding cancel-token
    bookkeeping. Forced via a fake CancelToken whose `.cancelled` setter
    raises; the cancel response must still ship despite the failure.
    """

    class _RaisingCancelToken:
        def __init__(self, cancelled: bool = False) -> None:
            object.__setattr__(self, "_cancelled", cancelled)

        def __setattr__(self, name: str, value: Any) -> None:
            if name == "cancelled":
                raise RuntimeError("cannot flip cancelled")
            object.__setattr__(self, name, value)

        @property
        def cancelled(self) -> bool:
            return self._cancelled

    monkeypatch.setattr(server_main, "CancelToken", _RaisingCancelToken)

    stdin_text = _lines(
        _req(v=1, id="init", method="initialize"),
        _req(v=1, id="opid", method="op1"),
        _req(v=1, id="c1", method="cancel", params={"id_to_cancel": "opid"}),
    )
    result = _run_main(
        monkeypatch,
        capsys,
        stdin_text=stdin_text,
        routes={
            "initialize": _init_handler,
            "op1": lambda c, p, t: {"started": True},
            "cancel": lambda c, p, t: {"cancelled": True},
        },
    )

    assert result.stdout_lines[-1] == {
        "v": 1,
        "id": "c1",
        "ok": True,
        "result": {"cancelled": True},
    }
