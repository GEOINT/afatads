"""REST / HTTP polling transport for TIDET events using standard urllib."""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
import urllib.parse
import ssl as _ssl
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from afatads.config import RestEndpointConfig
from afatads.model import TidetEvent, parse_tidet_wire

log = logging.getLogger(__name__)


class RestTransport:
    """Async HTTP polling client for TIDET REST endpoints using standard urllib."""

    def __init__(self, cfg: RestEndpointConfig) -> None:
        self._cfg = cfg
        self._running = False
        self._last_poll: datetime | None = None
        self._seen_ids: set[str] = set()

    async def stream(self) -> AsyncIterator[TidetEvent]:
        self._running = True
        loop = asyncio.get_running_loop()

        while self._running:
            try:
                # Run the blocking poll in a thread pool
                events = await loop.run_in_executor(None, self._poll_sync)
                for evt in events:
                    yield evt
            except Exception as exc:
                log.error("REST poll error: %s", exc)
            
            if not self._running:
                break

            try:
                await asyncio.sleep(self._cfg.poll_interval_s)
            except asyncio.CancelledError:
                break

    def stop(self) -> None:
        self._running = False

    def _poll_sync(self) -> list[TidetEvent]:
        url = self._cfg.base_url.rstrip("/") + self._cfg.path
        params: dict[str, str] = {}
        if self._last_poll:
            params["since"] = self._last_poll.isoformat()

        if params:
            url += "?" + urllib.parse.urlencode(params)

        self._last_poll = datetime.now(timezone.utc)
        
        headers = self._auth_headers()
        req = urllib.request.Request(url, headers=headers)
        
        ssl_ctx = None
        if self._cfg.tls_cert or self._cfg.tls_ca or not self._cfg.verify_ssl:
            ssl_ctx = self._build_ssl()

        try:
            with urllib.request.urlopen(req, timeout=self._cfg.timeout_s, context=ssl_ctx) as resp:
                body_raw = resp.read()
                body = json.loads(body_raw.decode("utf-8"))
        except Exception as e:
            log.error("Failed to poll %s: %s", url, e)
            return []

        results: list[TidetEvent] = []
        items: list[Any] = body if isinstance(body, list) else body.get("events", [])
        for item in items:
            try:
                if isinstance(item, str):
                    evt = parse_tidet_wire(item)
                elif isinstance(item, dict):
                    evt = TidetEvent.from_dict(item)
                else:
                    continue

                if evt.event_id in self._seen_ids:
                    continue
                self._seen_ids.add(evt.event_id)
                evt.network = f"rest://{url}"
                results.append(evt)
            except Exception:
                log.exception("Failed to parse REST TIDET item")

        return results

    def _auth_headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._cfg.auth_type == "bearer" and self._cfg.token:
            h["Authorization"] = f"Bearer {self._cfg.token}"
        elif self._cfg.auth_type == "basic" and self._cfg.username:
            import base64
            cred = base64.b64encode(
                f"{self._cfg.username}:{self._cfg.password}".encode()
            ).decode()
            h["Authorization"] = f"Basic {cred}"
        return h

    def _build_ssl(self) -> _ssl.SSLContext:
        ctx = _ssl.create_default_context(
            cafile=self._cfg.tls_ca or None,
        )
        if self._cfg.tls_cert and self._cfg.tls_key:
            ctx.load_cert_chain(self._cfg.tls_cert, self._cfg.tls_key)
        if not self._cfg.verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
        return ctx
