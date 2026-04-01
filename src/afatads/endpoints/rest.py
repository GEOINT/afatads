"""REST / HTTP polling transport for TIDET events.

Polls a TAK-Server-compatible REST endpoint at a configurable interval
and yields parsed TIDET events.  Supports Basic, Bearer, and mutual-TLS
authentication.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import aiohttp

from afatads.config import RestEndpointConfig
from afatads.model import TidetEvent, parse_tidet_wire

log = logging.getLogger(__name__)


class RestTransport:
    """Async HTTP polling client for TIDET REST endpoints."""

    def __init__(self, cfg: RestEndpointConfig) -> None:
        self._cfg = cfg
        self._running = False
        self._last_poll: datetime | None = None
        self._seen_ids: set[str] = set()

    async def stream(self) -> AsyncIterator[TidetEvent]:
        self._running = True
        ssl_ctx = self._build_ssl() if (self._cfg.tls_cert or self._cfg.tls_ca) else None

        connector = aiohttp.TCPConnector(ssl=ssl_ctx) if ssl_ctx else None
        timeout = aiohttp.ClientTimeout(total=self._cfg.timeout_s)

        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout,
        ) as session:
            while self._running:
                try:
                    events = await self._poll(session)
                    for evt in events:
                        yield evt
                except aiohttp.ClientError as exc:
                    log.error("REST poll error: %s", exc)
                except asyncio.CancelledError:
                    return

                await asyncio.sleep(self._cfg.poll_interval_s)

    def stop(self) -> None:
        self._running = False

    # ---------------------------------------------------------------
    async def _poll(self, session: aiohttp.ClientSession) -> list[TidetEvent]:
        url = self._cfg.base_url.rstrip("/") + self._cfg.path
        headers = self._auth_headers()
        params: dict[str, str] = {}
        if self._last_poll:
            params["since"] = self._last_poll.isoformat()

        self._last_poll = datetime.now(timezone.utc)

        async with session.get(url, headers=headers, params=params,
                               ssl=self._cfg.verify_ssl) as resp:
            resp.raise_for_status()
            body = await resp.json(content_type=None)

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

    def _build_ssl(self) -> Any:
        import ssl as _ssl
        ctx = _ssl.create_default_context(
            cafile=self._cfg.tls_ca or None,
        )
        if self._cfg.tls_cert and self._cfg.tls_key:
            ctx.load_cert_chain(self._cfg.tls_cert, self._cfg.tls_key)
        if not self._cfg.verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
        return ctx
