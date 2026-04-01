"""TCP socket transport for GTCS TIDET streams.

Connects to a GTCS-compatible socket endpoint, reads delimiter-framed
TIDET messages, and yields parsed events.  Supports optional TLS.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
from typing import AsyncIterator

from afatads.config import TcpEndpointConfig
from afatads.model import TidetEvent, parse_tidet_wire

log = logging.getLogger(__name__)


class TcpTransport:
    """Async TCP client for GTCS socket endpoints."""

    def __init__(self, cfg: TcpEndpointConfig) -> None:
        self._cfg = cfg
        self._running = False

    async def stream(self) -> AsyncIterator[TidetEvent]:
        """Connect (with auto-reconnect) and yield TIDET events."""
        self._running = True
        while self._running:
            try:
                ssl_ctx = self._build_ssl() if self._cfg.tls else None
                log.info("Connecting TCP %s:%d", self._cfg.host, self._cfg.port)
                reader, writer = await asyncio.open_connection(
                    self._cfg.host, self._cfg.port, ssl=ssl_ctx,
                )
                log.info("Connected to %s:%d", self._cfg.host, self._cfg.port)

                buf = b""
                delim = self._cfg.delimiter.encode()
                while self._running:
                    chunk = await reader.read(self._cfg.recv_buffer)
                    if not chunk:
                        log.warning("TCP connection closed by remote")
                        break
                    buf += chunk
                    while delim in buf:
                        msg_bytes, buf = buf.split(delim, 1)
                        raw = msg_bytes.decode("utf-8", errors="replace").strip()
                        if not raw:
                            continue
                        try:
                            evt = parse_tidet_wire(raw)
                            evt.network = f"tcp://{self._cfg.host}:{self._cfg.port}"
                            yield evt
                        except Exception:
                            log.exception("Failed to parse TIDET message: %.120s", raw)

                writer.close()
                await writer.wait_closed()

            except OSError as exc:
                log.error("TCP error: %s — retrying in %.1fs",
                          exc, self._cfg.reconnect_interval_s)
            except asyncio.CancelledError:
                self._running = False
                return

            if self._running:
                await asyncio.sleep(self._cfg.reconnect_interval_s)

    def stop(self) -> None:
        self._running = False

    # ----- TLS -----
    def _build_ssl(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context(
            cafile=self._cfg.tls_ca or None,
        )
        if self._cfg.tls_cert and self._cfg.tls_key:
            ctx.load_cert_chain(self._cfg.tls_cert, self._cfg.tls_key)
        return ctx
