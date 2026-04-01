"""GTCS client orchestrator.

Manages one or more endpoint transports, dispatches received TIDET
events to the writer, and exposes lifecycle (start / stop / run-once).
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import AsyncIterator

from afatads.config import ClientConfig
from afatads.endpoints.rest import RestTransport
from afatads.endpoints.tcp import TcpTransport
from afatads.endpoints.udp import UdpTransport
from afatads.model import TidetEvent
from afatads.store import TidetWriter

log = logging.getLogger(__name__)


class GtcsClient:
    """Orchestrates GTCS transports → TIDET writer pipeline."""

    def __init__(self, cfg: ClientConfig) -> None:
        self._cfg = cfg
        self._writer = TidetWriter(cfg.store)
        self._transports: list[TcpTransport | UdpTransport | RestTransport] = []
        self._tasks: list[asyncio.Task] = []
        self._event_count = 0

        for ep in cfg.enabled_endpoints:
            ep = ep.lower().strip()
            if ep == "tcp":
                self._transports.append(TcpTransport(cfg.tcp))
            elif ep == "udp":
                self._transports.append(UdpTransport(cfg.udp))
            elif ep == "rest":
                self._transports.append(RestTransport(cfg.rest))
            else:
                log.warning("Unknown endpoint type: %s", ep)

    async def run(self) -> None:
        """Run all transports until cancelled or SIGINT/SIGTERM."""
        loop = asyncio.get_running_loop()

        # Graceful shutdown on signals (Unix-only; ignored on Windows)
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop)
            except NotImplementedError:
                pass  # Windows — handled by KeyboardInterrupt

        log.info("Starting GTCS client — %d transport(s), store=%s",
                 len(self._transports), self._writer.root)

        self._tasks = [
            asyncio.create_task(self._consume(t))
            for t in self._transports
        ]

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass
        finally:
            log.info("GTCS client stopped — %d events ingested", self._event_count)

    def stop(self) -> None:
        for t in self._transports:
            t.stop()
        for task in self._tasks:
            task.cancel()

    @property
    def event_count(self) -> int:
        return self._event_count

    # ---------------------------------------------------------------
    async def _consume(self, transport: TcpTransport | UdpTransport | RestTransport) -> None:
        name = type(transport).__name__
        log.info("Transport %s starting", name)
        try:
            async for event in transport.stream():
                path = self._writer.write(event)
                self._event_count += 1
                log.info("[%s] %s → %s  (TGT %s)",
                         name, event.event_id[:8], path.name, event.target_number)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Transport %s crashed", name)
