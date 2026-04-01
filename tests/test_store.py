"""Tests for the time-sharded TIDET store (writer + reader)."""

import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from afatads.config import StoreConfig
from afatads.model import (
    CoordSystem,
    TargetCategory,
    TargetLocation,
    TargetPriority,
    TargetStatus,
    TidetEvent,
)
from afatads.store import TidetReader, TidetWriter


def _event(target: str = "AB1234", year: int = 2026, month: int = 4,
           day: int = 1, hour: int = 12) -> TidetEvent:
    return TidetEvent(
        target_number=target,
        dtg=datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc),
        category=TargetCategory.ARMOR,
        priority=TargetPriority.IMMEDIATE,
        status=TargetStatus.CONFIRMED,
        location=TargetLocation(
            coord_system=CoordSystem.MGRS,
            raw_coordinate="33UUP1234567890",
        ),
    )


def test_write_creates_sharded_path():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = StoreConfig(root_dir=tmp)
        writer = TidetWriter(cfg)
        evt = _event()
        path = writer.write(evt)
        assert path.exists()
        assert path.suffix == ".txt"
        # Check sharding: yyyy/mm/dd
        rel = path.relative_to(tmp)
        parts = rel.parts
        assert parts[0] == "2026"
        assert parts[1] == "04"
        assert parts[2] == "01"
        assert parts[3].endswith("_tidet.txt")


def test_roundtrip_via_store():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = StoreConfig(root_dir=tmp)
        writer = TidetWriter(cfg)
        reader = TidetReader(cfg)

        evt = _event()
        writer.write(evt)

        loaded = list(reader.iter_all())
        assert len(loaded) == 1
        assert loaded[0].target_number == "AB1234"
        assert loaded[0].category == TargetCategory.ARMOR


def test_iter_date():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = StoreConfig(root_dir=tmp)
        writer = TidetWriter(cfg)
        reader = TidetReader(cfg)

        writer.write(_event(day=1))
        writer.write(_event(day=2))
        writer.write(_event(day=1, hour=14))

        apr1 = list(reader.iter_date(date(2026, 4, 1)))
        apr2 = list(reader.iter_date(date(2026, 4, 2)))
        assert len(apr1) == 2
        assert len(apr2) == 1


def test_iter_range():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = StoreConfig(root_dir=tmp)
        writer = TidetWriter(cfg)
        reader = TidetReader(cfg)

        for d in (1, 2, 3, 5, 10):
            writer.write(_event(day=d))

        ranged = list(reader.iter_range(date(2026, 4, 2), date(2026, 4, 5)))
        assert len(ranged) == 3  # days 2, 3, 5 — range is inclusive


def test_find_by_target():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = StoreConfig(root_dir=tmp)
        writer = TidetWriter(cfg)
        reader = TidetReader(cfg)

        writer.write(_event(target="AA0001"))
        writer.write(_event(target="BB0002"))
        writer.write(_event(target="AA0001", day=2))

        found = reader.find_by_target("AA0001")
        assert len(found) == 2


def test_count_and_dates():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = StoreConfig(root_dir=tmp)
        writer = TidetWriter(cfg)
        reader = TidetReader(cfg)

        writer.write(_event(day=1))
        writer.write(_event(day=3))
        writer.write(_event(day=3, hour=14))

        assert reader.count() == 3
        dates = reader.dates_available()
        assert dates == [date(2026, 4, 1), date(2026, 4, 3)]
