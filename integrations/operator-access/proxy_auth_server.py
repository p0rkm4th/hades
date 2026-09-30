"""Private Nginx auth_request endpoint for the optional Agent Zero UI route."""

from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from integrations.automation.phase3_lldap_authority import Phase3LldapAuthority
from session_auth import (
    OperatorAuthorizationError,
    agent_zero_cookie,
    authorize_request,
    webui_cookie,
)


def make_handler(*, webui_endpoint: str, directory_authority: Phase3LldapAuthority):
    class Handler(BaseHTTPRequestHandler):
        server_version = "HADES-Operator-Auth/1"
        sys_version = ""

        def do_GET(self) -> None:  # noqa: N802
            if self.client_address[0] not in {"127.0.0.1", "::1"}:
                self.send_error(404)
                return
            try:
                if self.path == "/health":
                    cookie = ""
                    response_header = ""
                elif self.path == "/webui-cookie":
                    cookie = webui_cookie(self.headers)
                    response_header = "X-Hades-WebUI-Cookie"
                elif self.path == "/authorize":
                    authorize_request(
                        self.headers,
                        webui_endpoint=webui_endpoint,
                        directory_authority=directory_authority,
                    )
                    cookie = agent_zero_cookie(self.headers)
                    response_header = "X-Hades-Agent-Zero-Cookie"
                else:
                    self.send_error(404)
                    return
            except (OperatorAuthorizationError, ValueError):
                self.send_response(401)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(204)
            self.send_header("Cache-Control", "no-store")
            if cookie and response_header:
                self.send_header(response_header, cookie)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            self.send_error(404)

        def log_message(self, _format: str, *_args: object) -> None:
            # Do not log session-bearing request metadata.
            return

    return Handler


def main() -> None:
    webui_endpoint = os.environ.get("HADES_OPERATOR_WEBUI_ENDPOINT", "http://127.0.0.1:3001")
    directory_endpoint = os.environ.get("HADES_OPERATOR_LLDAP_ENDPOINT", "http://127.0.0.1:17170")
    config_path = os.environ.get("HADES_OPERATOR_AUTHORITY_CONFIG", "")
    password_path = os.environ.get("HADES_OPERATOR_READER_PASSWORD_FILE", "")
    if not config_path or not password_path:
        raise SystemExit("Operator live directory authority inputs are required")
    authority = Phase3LldapAuthority(
        Path(config_path), Path(password_path), directory_endpoint, timeout=4.0
    )
    server = ThreadingHTTPServer(
        (os.environ.get("HADES_OPERATOR_AUTH_BIND", "127.0.0.1"), int(os.environ.get("HADES_OPERATOR_AUTH_PORT", "8645"))),
        make_handler(webui_endpoint=webui_endpoint, directory_authority=authority),
    )
    server.daemon_threads = True
    server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()
