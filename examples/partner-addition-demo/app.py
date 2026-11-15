"""Partner addition demo — HTTP transport (stdlib only, no AWS).

Run locally:

    RIS_API_KEY=ris_demo_not_a_real_key python examples/partner-addition-demo/app.py

The key is read server-side only. It is never written into the HTML, the JSON
responses or the logs. Default bind is loopback.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional, Tuple
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from demo_core import DemoError, DemoService, build_service  # noqa: E402

PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>RIS Addition Agent — Testpartner A</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:34rem;margin:3rem auto;padding:0 1rem}
 label{display:block;margin:.6rem 0 .2rem}
 input{width:100%;padding:.5rem;font-size:1rem}
 button{margin-top:1rem;padding:.6rem 1rem;font-size:1rem;cursor:pointer}
 pre{background:#f4f4f4;padding:.8rem;white-space:pre-wrap;word-break:break-word}
 .muted{color:#666;font-size:.85rem}
</style>
</head>
<body>
<h1>Addition beauftragen</h1>
<p class="muted">Testpartner A · Capability <code>math.add</code></p>

<label for="left">Linker Operand</label>
<input id="left" type="number" value="17">
<label for="right">Rechter Operand</label>
<input id="right" type="number" value="25">

<button id="create">Addition beauftragen</button>
<button id="poll">Status prüfen</button>

<h2>Order</h2>
<pre id="order">—</pre>

<script>
let currentOrderId = null;

const render = (value) => {
  document.getElementById('order').textContent =
    typeof value === 'string' ? value : JSON.stringify(value, null, 2);
};

document.getElementById('create').addEventListener('click', async () => {
  const left = Number(document.getElementById('left').value);
  const right = Number(document.getElementById('right').value);
  const res = await fetch('/api/orders', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({left, right})
  });
  const body = await res.json();
  currentOrderId = body.orderId || null;
  render(body);
});

document.getElementById('poll').addEventListener('click', async () => {
  if (!currentOrderId) { render('Keine Order vorhanden.'); return; }
  const res = await fetch('/api/orders/' + encodeURIComponent(currentOrderId));
  render(await res.json());
});
</script>
</body>
</html>
"""


class DemoHandler(BaseHTTPRequestHandler):
    service: DemoService  # injected by make_server

    server_version = "PartnerAdditionDemo/1.0"

    def log_message(self, fmt, *args):  # keep stdout free of request bodies
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # -- helpers ---------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _route(self) -> Tuple[str, str]:
        parsed = urlparse(self.path)
        return parsed.path, parsed.query

    # -- routes ----------------------------------------------------------
    def do_GET(self):
        path, _ = self._route()
        if path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/health":
            self._json(200, {"status": "ok"})
            return
        if path.startswith("/api/orders/"):
            order_id = path[len("/api/orders/"):]
            try:
                self._json(200, self.service.read_order(order_id))
            except DemoError as exc:
                self._json(exc.status, {"error": str(exc)})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        path, _ = self._route()
        if path != "/api/orders":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            self._json(400, {"error": "body must be valid JSON"})
            return
        try:
            self._json(201, self.service.create_order(body))
        except DemoError as exc:
            self._json(exc.status, {"error": str(exc)})


def make_server(service: DemoService, host: str = "127.0.0.1",
                port: int = 8080) -> ThreadingHTTPServer:
    handler = type("BoundDemoHandler", (DemoHandler,), {"service": service})
    return ThreadingHTTPServer((host, port), handler)


def main(argv: Optional[list] = None) -> int:
    host = os.environ.get("DEMO_HOST", "127.0.0.1")
    port = int(os.environ.get("DEMO_PORT", "8080"))
    if os.environ.get("DEMO_MODE") == "real":
        from app_ports import build_real_service

        service = build_real_service()
        print("mode: real application ports (local SQS)", file=sys.stderr)
    else:
        service = build_service()
        if not os.environ.get("RIS_API_KEY"):
            print("warning: RIS_API_KEY is not set; order creation will fail "
                  "with 503 (no credential is invented).", file=sys.stderr)
    server = make_server(service, host=host, port=port)
    print(f"Partner addition demo on http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
