"""Time-sharded on-disk store for TIDET events.

Layout:  ``<root>/<yyyy>/<mm>/<dd>/<timestamp>_tidet.txt``

Each file is a single JSON document (human-readable, self-contained).
The writer creates the directory tree on demand; the reader walks it
with optional date-range filtering.
"""

from __future__ import annotations

import json
import logging
import pathlib
from datetime import date, datetime, timezone
from typing import Iterator

from afatads.config import StoreConfig
from afatads.model import TidetEvent

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class TidetWriter:
    """Writes TIDET events to time-sharded files."""

    def __init__(self, cfg: StoreConfig) -> None:
        self._root = pathlib.Path(cfg.root_dir)
        self._indent = cfg.indent_json

    def write(self, event: TidetEvent) -> pathlib.Path:
        """Persist a single event.  Returns the written file path."""
        dt = event.dtg
        day_dir = self._root / f"{dt.year:04d}" / f"{dt.month:02d}" / f"{dt.day:02d}"
        day_dir.mkdir(parents=True, exist_ok=True)

        ts = dt.strftime("%Y%m%dT%H%M%S") + f"_{event.event_id[:8]}"
        fpath = day_dir / f"{ts}_tidet.txt"

        payload = event.to_json(indent=self._indent)
        fpath.write_text(payload, encoding="utf-8")
        log.debug("Wrote %s", fpath)
        return fpath

    @property
    def root(self) -> pathlib.Path:
        return self._root


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

class TidetReader:
    """Reads TIDET events from the time-sharded store."""

    def __init__(self, cfg: StoreConfig) -> None:
        self._root = pathlib.Path(cfg.root_dir)

    # -- bulk iteration --

    def iter_all(self) -> Iterator[TidetEvent]:
        """Yield every event in chronological order."""
        yield from self._walk(self._root)

    def iter_date(self, d: date) -> Iterator[TidetEvent]:
        """Yield events for a single calendar date."""
        day_dir = self._root / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.day:02d}"
        if day_dir.is_dir():
            yield from self._walk(day_dir)

    def iter_range(self, start: date, end: date) -> Iterator[TidetEvent]:
        """Yield events within [start, end] inclusive."""
        current = start
        from datetime import timedelta
        while current <= end:
            yield from self.iter_date(current)
            current += timedelta(days=1)

    # -- single-event retrieval --

    def read_file(self, path: str | pathlib.Path) -> TidetEvent:
        text = pathlib.Path(path).read_text(encoding="utf-8")
        return TidetEvent.from_json(text)

    # -- queries --

    def find_by_target(self, target_number: str) -> list[TidetEvent]:
        return [e for e in self.iter_all()
                if e.target_number.upper() == target_number.upper()]

    def count(self) -> int:
        return sum(1 for _ in self._root.rglob("*_tidet.txt"))

    def dates_available(self) -> list[date]:
        """Return sorted list of dates that have stored events."""
        dates: set[date] = set()
        for f in self._root.rglob("*_tidet.txt"):
            try:
                parts = f.relative_to(self._root).parts  # yyyy/mm/dd/file
                if len(parts) >= 3:
                    dates.add(date(int(parts[0]), int(parts[1]), int(parts[2])))
            except (ValueError, IndexError):
                continue
        return sorted(dates)

    # -- internal --

    @staticmethod
    def _walk(directory: pathlib.Path) -> Iterator[TidetEvent]:
        for fpath in sorted(directory.rglob("*_tidet.txt")):
            try:
                text = fpath.read_text(encoding="utf-8")
                yield TidetEvent.from_json(text)
            except Exception:
                log.exception("Bad TIDET file: %s", fpath)

    @property
    def root(self) -> pathlib.Path:
        return self._root
