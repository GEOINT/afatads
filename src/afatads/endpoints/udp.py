"""UDP / multicast transport for GTCS TIDET datagrams.

Binds to a multicast group (or unicast address) and yields parsed
TIDET events from incoming datagrams.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
from typing import AsyncIterator

from afatads.config import UdpEndpointConfig
from afatads.model import TidetEvent, parse_tidet_wire

log = logging.getLogger(__name__)


class _UdpProtocol(asyncio.DatagramProtocol):
    """Minimal protocol that pushes datagrams into an asyncio.Queue."""

    def __init__(self, queue: asyncio.Queue[bytes]) -> None:
        self._queue = queue

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._queue.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        log.error("UDP error: %s", exc)


class UdpTransport:
    """Async UDP/multicast receiver for GTCS datagrams."""

    def __init__(self, cfg: UdpEndpointConfig) -> None:
        self._cfg = cfg
        self._running = False

    async def stream(self) -> AsyncIterator[TidetEvent]:
        self._running = True
        queue: asyncio.Queue[bytes] = asyncio.Queue()

        loop = asyncio.get_running_loop()

        # Build raw socket for multicast support
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self._cfg.port))

        if self._cfg.multicast:
            iface = self._cfg.interface or "0.0.0.0"
            mreq = struct.pack(
                "4s4s",
                socket.inet_aton(self._cfg.host),
                socket.inet_aton(iface),
            )
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            log.info("Joined multicast %s:%d (iface %s)",
                     self._cfg.host, self._cfg.port, iface)

        transport, _ = await loop.create_datagram_endpoint(
            lambda: _UdpProtocol(queue), sock=sock,
        )

        try:
            while self._running:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                raw = data.decode("utf-8", errors="replace").strip()
                if not raw:
                    continue
                try:
                    evt = parse_tidet_wire(raw)
                    evt.network = f"udp://{self._cfg.host}:{self._cfg.port}"
                    yield evt
                except Exception:
                    log.exception("Failed to parse UDP TIDET: %.120s", raw)
        except asyncio.CancelledError:
            pass
        finally:
            transport.close()

    def stop(self) -> None:
        self._running = False
