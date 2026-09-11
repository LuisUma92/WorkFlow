# src/latexzettel/server/main.py
"""
LatexZettel Server (MVP) - JSONL/NDJSON over stdin/stdout

Objetivo:
- Proceso persistente para ser usado por Neovim (modelo 3).
- Protocolo RPC estable y transport-agnostic (stdio hoy, unix domain socket mañana)
  manteniendo exactamente el mismo framing: 1 JSON por línea + '\n' (JSONL).

Requisitos de protocolo (cumplidos):
- NDJSON estricto: 1 JSON completo por línea; stdout solo datos; stderr solo logs.
- Correlación obligatoria: request incluye id; response devuelve el mismo id.
- Envelope RPC estable:
    Request: { "v": ..., "id": ..., "method": "...", "params": { ... } }
    Response OK: { "v": ..., "id": ..., "ok": true, "result": { ... } }
    Response error: { "v": ..., "id": ..., "ok": false, "error": { "code": "...", "message": "...", "data": { ... } } }
- Versionado desde día 1:
    - v en cada mensaje.
    - Si no coincide -> responder error VERSION_MISMATCH y cerrar.
- Handshake initialize:
    - Primer mensaje recomendado method="initialize".
    - Respuesta incluye capabilities y server_version.
- Cancelación:
    - method="cancel" con params { "id_to_cancel": ... }.
    - Best-effort en MVP: marcamos cancelado; handlers deben consultar el token.
- No asumir cliente único:
    - Cada request debe ser autosuficiente.
    - initialize permite fijar config default de sesión (root/db_module), pero cada request
      puede override con params si se desea.
- Compatible con unix socket:
    - El framing es JSONL; para UDS solo cambia el transporte, no el protocolo ni handlers.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Any, Optional, Union

from workflow.db.engine import init_global_db, get_global_engine

from latexzettel.config.settings import DEFAULT_SETTINGS

from latexzettel.server.protocols import JsonObject, ProtocolError
from latexzettel.server.routers import (
    ROUTES,
    CancelledError,
    CancelToken,
    ServerContext,
)

# =============================================================================
# Protocolo
# =============================================================================

PROTOCOL_VERSION = 1
SERVER_NAME = "latexzettel-server"
SERVER_VERSION = "0.1.0"


def _eprint(*args: Any) -> None:
    print(*args, file=sys.stderr, flush=True)


def _write_jsonl(obj: JsonObject) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _error_obj(
    *,
    v: int,
    req_id: str | int,
    code: str,
    message: str,
    data: Optional[JsonObject] = None,
) -> JsonObject:
    err: JsonObject = {"code": code, "message": message, "data": data or {}}
    return {"v": v, "id": req_id, "ok": False, "error": err}


def _ok_obj(*, v: int, req_id: str | int, result: JsonObject) -> JsonObject:
    return {"v": v, "id": req_id, "ok": True, "result": result}


# =============================================================================
# Parsing/validación de requests
# =============================================================================


def _parse_request_line(line: str) -> JsonObject:
    line = line.strip("\n")
    if not line:
        raise ProtocolError("Empty line")
    try:
        msg = json.loads(line)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"Invalid JSON: {e}") from e

    if not isinstance(msg, dict):
        raise ProtocolError("Request must be a JSON object")

    return msg  # type: ignore[return-value]


def _require_fields(msg: JsonObject, fields: list[str]) -> None:
    for f in fields:
        if f not in msg:
            raise ProtocolError(f"Missing field '{f}'")


def _get_v(msg: JsonObject) -> int:
    v = msg.get("v", None)
    if not isinstance(v, int):
        raise ProtocolError("Field 'v' must be int")
    return v


def _get_id(msg: JsonObject) -> str | int:
    req_id = msg.get("id", None)
    if isinstance(req_id, (str, int)):
        return req_id
    raise ProtocolError("Field 'id' must be string or int")


def _get_method(msg: JsonObject) -> str:
    method = msg.get("method", None)
    if not isinstance(method, str):
        raise ProtocolError("Field 'method' must be string")
    return method


def _get_params(msg: JsonObject) -> JsonObject:
    params = msg.get("params", {})
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise ProtocolError("Field 'params' must be an object")
    return params  # type: ignore[return-value]


# =============================================================================
# Request dispatcher
# =============================================================================


def _handle_request(
    ctx: ServerContext,
    msg: JsonObject,
    tokens_by_id: dict[Union[str, int], CancelToken],
) -> Optional[JsonObject]:
    _require_fields(msg, ["v", "id", "method"])
    v = _get_v(msg)
    req_id = _get_id(msg)
    method = _get_method(msg)
    params = _get_params(msg)

    if v != PROTOCOL_VERSION:
        return _error_obj(
            v=v,
            req_id=req_id,
            code="VERSION_MISMATCH",
            message=f"Protocol version mismatch: client={v}, server={PROTOCOL_VERSION}",
            data={"server_protocol_version": PROTOCOL_VERSION},
        )

    if method == "cancel":
        token = CancelToken(cancelled=False)
        resp = ROUTES["cancel"](ctx, params, token)
        return _ok_obj(v=v, req_id=req_id, result=resp)

    if not ctx.initialized and method != "initialize":
        return _error_obj(
            v=v,
            req_id=req_id,
            code="NOT_INITIALIZED",
            message="Server not initialized. Call method 'initialize' first.",
            data={"required_method": "initialize"},
        )

    handler = ROUTES.get(method)
    if handler is None:
        return _error_obj(
            v=v,
            req_id=req_id,
            code="METHOD_NOT_FOUND",
            message=f"Unknown method '{method}'",
        )

    token = tokens_by_id.setdefault(req_id, CancelToken(cancelled=False))

    try:
        result = handler(ctx, params, token)
        return _ok_obj(v=v, req_id=req_id, result=result)
    except CancelledError:
        return _error_obj(
            v=v, req_id=req_id, code="CANCELLED", message="Request cancelled", data={}
        )
    except ProtocolError as e:
        return _error_obj(
            v=v, req_id=req_id, code="INVALID_REQUEST", message=str(e), data={}
        )
    except Exception as e:
        data: JsonObject = {"exception": e.__class__.__name__}
        if os.environ.get("LATEXZETTEL_SERVER_DEBUG", "") in ("1", "true", "yes"):
            data["trace"] = traceback.format_exc()
        return _error_obj(
            v=v, req_id=req_id, code="INTERNAL_ERROR", message=str(e), data=data
        )


# =============================================================================
# Main loop helpers (extracted to keep main() and each helper simple)
# =============================================================================


def _startup_init_db() -> None:
    """Initialize the global DB or exit(2) on failure (unchanged behaviour)."""
    try:
        init_global_db(engine=get_global_engine())
    except Exception as e:
        _eprint(f"[{SERVER_NAME}] DB init failed on startup: {e}")
        sys.exit(2)


def _fallback_error_response(
    msg: JsonObject, e: ProtocolError
) -> Optional[JsonObject]:
    """
    Best-effort INVALID_REQUEST envelope for a ProtocolError raised outside
    handler dispatch (e.g. missing/invalid v, id or method). Returns None
    (after logging to stderr) when no usable id is available.
    """
    try:
        v = msg.get("v", PROTOCOL_VERSION)
        if not isinstance(v, int):
            v = PROTOCOL_VERSION
        req_id = msg.get("id", None)
        if isinstance(req_id, (str, int)):
            return _error_obj(
                v=v,
                req_id=req_id,
                code="INVALID_REQUEST",
                message=str(e),
                data={},
            )
        _eprint(f"[{SERVER_NAME}] Protocol error (no id): {e}")
        return None
    except Exception:
        return None


def _process_line(
    ctx: ServerContext,
    line: str,
    tokens_by_id: dict[Union[str, int], CancelToken],
) -> Optional[tuple[JsonObject, JsonObject]]:
    """
    Parse + dispatch a single NDJSON request line.

    Returns (msg, resp) when there is a response to send, or None when the
    line should be silently skipped (parse error, or no usable id to report
    a fallback error against).
    """
    try:
        msg = _parse_request_line(line)
    except ProtocolError as e:
        _eprint(f"[{SERVER_NAME}] Protocol error (no id): {e}")
        return None

    try:
        resp = _handle_request(ctx, msg, tokens_by_id)
    except ProtocolError as e:
        resp = _fallback_error_response(msg, e)

    if resp is None:
        return None
    return msg, resp


def _is_version_mismatch(resp: JsonObject) -> bool:
    if resp.get("ok") is not False:
        return False
    err = resp.get("error", {})
    return isinstance(err, dict) and err.get("code") == "VERSION_MISMATCH"


def _maybe_mark_cancelled(
    msg: JsonObject, tokens_by_id: dict[Union[str, int], CancelToken]
) -> None:
    """Best-effort bookkeeping: flag a previously-created token as cancelled."""
    try:
        if msg.get("method") != "cancel":
            return
        params = msg.get("params", {})
        if not isinstance(params, dict):
            return
        id_to_cancel = params.get("id_to_cancel")
        if not isinstance(id_to_cancel, (str, int)):
            return
        tok = tokens_by_id.get(id_to_cancel)
        if tok is not None:
            tok.cancelled = True
    except Exception:
        pass


def _shutdown_dispose() -> None:
    try:
        get_global_engine().dispose()
    except Exception:
        pass


# =============================================================================
# Main loop
# =============================================================================


def main() -> None:
    """
    Inicia el server en modo stdio JSONL.

    El cliente debe:
    1) enviar initialize
    2) enviar requests NDJSON
    3) leer responses NDJSON

    stdout: SOLO responses JSONL
    stderr: logs/diagnóstico
    """
    ctx = ServerContext(
        settings=DEFAULT_SETTINGS,
        initialized=False,
    )

    _startup_init_db()

    tokens_by_id: dict[Union[str, int], CancelToken] = {}

    for line in sys.stdin:
        outcome = _process_line(ctx, line, tokens_by_id)
        if outcome is None:
            continue
        msg, resp = outcome

        if _is_version_mismatch(resp):
            _write_jsonl(resp)
            break

        _maybe_mark_cancelled(msg, tokens_by_id)
        _write_jsonl(resp)

    _shutdown_dispose()


if __name__ == "__main__":
    main()
