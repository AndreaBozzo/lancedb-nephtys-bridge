# pyright: reportMissingImports=false, reportMissingModuleSource=false

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import bridge_service_settings, bridge_settings
from .query import query_stream, serialize_results

logger = logging.getLogger("nephtys-bridge.service")


def _first(
    values: dict[str, list[str]], key: str, default: str | None = None
) -> str | None:
    selected = values.get(key)
    if not selected:
        return default
    return selected[0]


def _bool_param(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def query_response_from_params(
    params: dict[str, list[str]],
) -> tuple[int, dict | list[dict]]:
    bridge = bridge_settings()
    service = bridge_service_settings()
    query_text = _first(params, "q") or _first(params, "query")
    if not query_text:
        return HTTPStatus.BAD_REQUEST, {"error": "missing query parameter 'q'"}

    limit_raw = _first(params, "limit", str(service.default_limit))
    max_age_raw = _first(params, "max_age_seconds")
    try:
        limit = max(1, int(limit_raw or service.default_limit))
    except ValueError:
        return HTTPStatus.BAD_REQUEST, {"error": "invalid limit"}

    try:
        max_age_seconds = int(max_age_raw) if max_age_raw is not None else None
    except ValueError:
        return HTTPStatus.BAD_REQUEST, {"error": "invalid max_age_seconds"}

    content_only_override = _first(params, "content_only")
    if content_only_override is not None:
        content_only = _bool_param(content_only_override, default=False)
    else:
        content_only = not _bool_param(_first(params, "all_namespaces"), default=False)

    rows = query_stream(
        query_text,
        limit=limit,
        content_only=content_only,
        db_path=_first(params, "db_path", bridge.db_path) or bridge.db_path,
        table_name=_first(params, "table", bridge.table_name) or bridge.table_name,
        source_filters=params.get("source", []),
        event_type_filters=params.get("event_type", []),
        symbol_filters=params.get("symbol", []),
        max_age_seconds=max_age_seconds,
    )
    return HTTPStatus.OK, serialize_results(rows)


class BridgeQueryHandler(BaseHTTPRequestHandler):
    server_version = "NephtysBridgeQuery/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            bridge = bridge_settings()
            self._write_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "db_path": bridge.db_path,
                    "table": bridge.table_name,
                    "service": "bridge-query",
                },
            )
            return

        if parsed.path == "/query":
            try:
                status, payload = query_response_from_params(parse_qs(parsed.query))
            except Exception as exc:  # pragma: no cover - defensive server path
                logger.exception("query handler failed: %s", exc)
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "query failed"}
                )
                return

            self._write_json(status, payload)
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:
        logger.info("%s - %s", self.address_string(), format % args)

    def _write_json(self, status: int, payload: dict | list[dict]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    service = bridge_service_settings()
    server = ThreadingHTTPServer((service.host, service.port), BridgeQueryHandler)
    logger.info(
        "Bridge query service listening on http://%s:%d", service.host, service.port
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
