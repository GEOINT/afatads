"""Tests for the TIDET domain model and wire-format parser."""

from datetime import datetime, timezone

from afatads.model import (
    CoordSystem,
    SourceInfo,
    TargetCategory,
    TargetLocation,
    TargetPriority,
    TargetStatus,
    TidetEvent,
    parse_tidet_wire,
)


# ---------------------------------------------------------------------------
# Round-trip serialisation
# ---------------------------------------------------------------------------

def _make_event() -> TidetEvent:
    return TidetEvent(
        event_id="aabbccdd11223344",
        target_number="AB1234",
        dtg=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        received_at=datetime(2026, 4, 1, 12, 0, 1, tzinfo=timezone.utc),
        location=TargetLocation(
            coord_system=CoordSystem.MGRS,
            raw_coordinate="33UUP1234567890",
            latitude=48.123,
            longitude=11.456,
            altitude_m=500.0,
            cep_m=50.0,
        ),
        category=TargetCategory.ARMOR,
        target_type="T-72B3",
        description="Armored platoon in tree line",
        priority=TargetPriority.IMMEDIATE,
        status=TargetStatus.CONFIRMED,
        source=SourceInfo(
            source_type="RADAR",
            source_unit="1-82 FA",
            reliability="B",
            credibility="2",
        ),
        originator="FIRES-6",
        remarks="Coordinates confirmed by UAS",
    )


def test_roundtrip_json():
    evt = _make_event()
    js = evt.to_json()
    restored = TidetEvent.from_json(js)

    assert restored.event_id == evt.event_id
    assert restored.target_number == evt.target_number
    assert restored.dtg == evt.dtg
    assert restored.location.raw_coordinate == "33UUP1234567890"
    assert restored.location.coord_system == CoordSystem.MGRS
    assert restored.category == TargetCategory.ARMOR
    assert restored.priority == TargetPriority.IMMEDIATE
    assert restored.status == TargetStatus.CONFIRMED
    assert restored.source.source_type == "RADAR"
    assert restored.source.reliability == "B"


def test_roundtrip_dict():
    evt = _make_event()
    d = evt.to_dict()
    assert isinstance(d["dtg"], str)
    restored = TidetEvent.from_dict(d)
    assert restored.target_number == "AB1234"


# ---------------------------------------------------------------------------
# Wire-format parsing
# ---------------------------------------------------------------------------

RAW_WIRE = (
    "TGTNUM:AB1234;DTG:011200ZAPR2026;MGRS:33UUP1234567890;"
    "CAT:ARMOR;TYPE:T-72B3;PRI:IMMEDIATE;STATUS:CONFIRMED;"
    "SRCTYPE:RADAR;SRCUNIT:1-82 FA;SRCREL:B;SRCCRED:2;"
    "DESC:Armored platoon in tree line;ORIG:FIRES-6;RMK:UAS confirmed"
)


def test_parse_wire_basic_fields():
    evt = parse_tidet_wire(RAW_WIRE)
    assert evt.target_number == "AB1234"
    assert evt.category == TargetCategory.ARMOR
    assert evt.target_type == "T-72B3"
    assert evt.priority == TargetPriority.IMMEDIATE
    assert evt.status == TargetStatus.CONFIRMED
    assert evt.originator == "FIRES-6"
    assert evt.description == "Armored platoon in tree line"


def test_parse_wire_location():
    evt = parse_tidet_wire(RAW_WIRE)
    assert evt.location is not None
    assert evt.location.coord_system == CoordSystem.MGRS
    assert evt.location.raw_coordinate == "33UUP1234567890"


def test_parse_wire_source():
    evt = parse_tidet_wire(RAW_WIRE)
    assert evt.source is not None
    assert evt.source.source_type == "RADAR"
    assert evt.source.source_unit == "1-82 FA"
    assert evt.source.reliability == "B"


def test_parse_wire_preserves_raw():
    evt = parse_tidet_wire(RAW_WIRE)
    assert evt.raw_message == RAW_WIRE


def test_parse_wire_unknown_keys_in_extra():
    raw = "TGTNUM:ZZ9999;FOO:bar;BAZ:qux"
    evt = parse_tidet_wire(raw)
    assert evt.target_number == "ZZ9999"
    assert evt.extra["FOO"] == "bar"
    assert evt.extra["BAZ"] == "qux"


def test_parse_wire_multiline():
    raw = "TGTNUM:ML0001\nCAT:INFANTRY\nSTATUS:SUSPECTED"
    evt = parse_tidet_wire(raw)
    assert evt.target_number == "ML0001"
    assert evt.category == TargetCategory.INFANTRY
    assert evt.status == TargetStatus.SUSPECTED


def test_parse_wire_geodetic():
    raw = "TGTNUM:GD0001;LAT:48.123;LON:11.456;ALT:500;CEP:50"
    evt = parse_tidet_wire(raw)
    assert evt.location is not None
    assert evt.location.coord_system == CoordSystem.GEODETIC
    assert evt.location.latitude == 48.123
    assert evt.location.longitude == 11.456
    assert evt.location.altitude_m == 500.0
    assert evt.location.cep_m == 50.0
