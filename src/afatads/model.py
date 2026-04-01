"""Shared domain model for TIDET events.

Defines the canonical representation used on-disk and in-memory.
The on-disk format is JSON — preserves all original fields but
organises them into a typed, queryable structure.
"""

from __future__ import annotations

import enum
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TargetCategory(str, enum.Enum):
    """High-level target taxonomy (MIL-STD-6016 / STANAG 5516 aligned)."""
    ARMOR = "ARMOR"
    ARTILLERY = "ARTILLERY"
    AIR_DEFENSE = "AIR_DEFENSE"
    INFANTRY = "INFANTRY"
    LOGISTICS = "LOGISTICS"
    COMMAND_CONTROL = "C2"
    ELECTRONIC_WARFARE = "EW"
    ENGINEER = "ENGINEER"
    NBC = "NBC"
    NAVAL = "NAVAL"
    AIR = "AIR"
    MISSILE = "MISSILE"
    UNKNOWN = "UNKNOWN"


class TargetPriority(str, enum.Enum):
    IMMEDIATE = "IMMEDIATE"
    PRIORITY = "PRIORITY"
    ROUTINE = "ROUTINE"


class TargetStatus(str, enum.Enum):
    KNOWN = "KNOWN"
    SUSPECTED = "SUSPECTED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    ENGAGED = "ENGAGED"
    DESTROYED = "DESTROYED"


class CoordSystem(str, enum.Enum):
    MGRS = "MGRS"
    GEODETIC = "GEODETIC"
    UTM = "UTM"


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TargetLocation:
    """Target geo-position.  Stores both raw coordinate text and, when
    available, geodetic lat/lon for downstream consumers."""
    coord_system: CoordSystem
    raw_coordinate: str
    latitude: float | None = None
    longitude: float | None = None
    altitude_m: float | None = None
    cep_m: float | None = None  # Circular Error Probable (metres)


@dataclass(frozen=True)
class SourceInfo:
    """How the target was detected / reported."""
    source_type: str          # e.g. "HUMINT", "SIGINT", "RADAR", "VISUAL"
    source_unit: str = ""     # unit designator, e.g. "1-82 FA"
    reliability: str = ""     # A–F (NATO source reliability)
    credibility: str = ""     # 1–6 (NATO information credibility)


# ---------------------------------------------------------------------------
# Root aggregate — a single TIDET event
# ---------------------------------------------------------------------------

@dataclass
class TidetEvent:
    """Canonical TIDET event representation.

    All original wire-format data is retained in *raw_message*; the
    typed fields provide structured access for queries and analytics.
    """
    # -- identity --
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    target_number: str = ""          # e.g. "AB1234"

    # -- temporal --
    dtg: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # -- spatial --
    location: TargetLocation | None = None

    # -- classification --
    category: TargetCategory = TargetCategory.UNKNOWN
    target_type: str = ""            # free-text refinement, e.g. "T-72B3"
    description: str = ""

    # -- operational --
    priority: TargetPriority = TargetPriority.ROUTINE
    status: TargetStatus = TargetStatus.KNOWN
    source: SourceInfo | None = None

    # -- engagement --
    engagement_method: str = ""      # e.g. "FIRE FOR EFFECT"
    munition_type: str = ""          # e.g. "HE", "DPICM", "FASCAM"
    firing_unit: str = ""

    # -- provenance --
    originator: str = ""             # message originator
    network: str = ""                # which GTCS net / endpoint
    raw_message: str = ""            # verbatim wire-format payload
    remarks: str = ""

    # -- extensibility --
    extra: dict[str, Any] = field(default_factory=dict)

    # -----------------------------------------------------------------------
    # Serialisation helpers
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Produce a JSON-safe dict."""
        d = asdict(self)
        # datetime → ISO-8601
        d["dtg"] = self.dtg.isoformat()
        d["received_at"] = self.received_at.isoformat()
        # enums → values
        if self.location:
            d["location"]["coord_system"] = self.location.coord_system.value
        d["category"] = self.category.value
        d["priority"] = self.priority.value
        d["status"] = self.status.value
        return d

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TidetEvent:
        """Reconstruct from a JSON-safe dict (inverse of *to_dict*)."""
        d = dict(d)  # shallow copy

        d["dtg"] = _parse_dt(d.get("dtg", ""))
        d["received_at"] = _parse_dt(d.get("received_at", ""))

        loc = d.pop("location", None)
        if loc:
            loc["coord_system"] = CoordSystem(loc["coord_system"])
            d["location"] = TargetLocation(**loc)

        src = d.pop("source", None)
        if src:
            d["source"] = SourceInfo(**src)

        d["category"] = TargetCategory(d.get("category", "UNKNOWN"))
        d["priority"] = TargetPriority(d.get("priority", "ROUTINE"))
        d["status"] = TargetStatus(d.get("status", "KNOWN"))

        return cls(**d)

    @classmethod
    def from_json(cls, text: str) -> TidetEvent:
        return cls.from_dict(json.loads(text))


# ---------------------------------------------------------------------------
# Wire-format parsers  (add more as formats are discovered)
# ---------------------------------------------------------------------------

_TIDET_FIELD_MAP: dict[str, str] = {
    "TGTNUM":  "target_number",
    "DTG":     "dtg",
    "MGRS":    "_mgrs",
    "LAT":     "_lat",
    "LON":     "_lon",
    "ALT":     "_alt",
    "CEP":     "_cep",
    "CAT":     "category",
    "TYPE":    "target_type",
    "DESC":    "description",
    "PRI":     "priority",
    "STATUS":  "status",
    "SRCTYPE": "_srctype",
    "SRCUNIT": "_srcunit",
    "SRCREL":  "_srcrel",
    "SRCCRED": "_srccred",
    "ENGMETH": "engagement_method",
    "MUNTYPE": "munition_type",
    "FIRUNIT": "firing_unit",
    "ORIG":    "originator",
    "RMK":     "remarks",
}


def parse_tidet_wire(raw: str) -> TidetEvent:
    """Parse a TIDET key-value wire message.

    Expected format (one field per line, or semicolon-delimited)::

        TGTNUM:AB1234;DTG:201200ZAPR2026;MGRS:33UUP1234567890;...

    Unknown keys are stored in ``extra``.
    """
    raw = raw.strip()
    tokens: list[str] = []
    for line in raw.splitlines():
        tokens.extend(tok.strip() for tok in line.split(";") if tok.strip())

    fields: dict[str, str] = {}
    for tok in tokens:
        if ":" not in tok:
            continue
        key, _, val = tok.partition(":")
        fields[key.strip().upper()] = val.strip()

    kw: dict[str, Any] = {"raw_message": raw, "extra": {}}

    for wire_key, val in fields.items():
        mapped = _TIDET_FIELD_MAP.get(wire_key)
        if mapped and not mapped.startswith("_"):
            kw[mapped] = val
        elif mapped:
            kw[mapped] = val  # will fixup below
        else:
            kw["extra"][wire_key] = val

    # -- fixup typed fields --
    if "dtg" in kw and isinstance(kw["dtg"], str):
        kw["dtg"] = _parse_military_dtg(kw["dtg"])

    # location assembly
    coord_raw = kw.pop("_mgrs", None)
    lat_s = kw.pop("_lat", None)
    lon_s = kw.pop("_lon", None)
    alt_s = kw.pop("_alt", None)
    cep_s = kw.pop("_cep", None)

    if coord_raw:
        kw["location"] = TargetLocation(
            coord_system=CoordSystem.MGRS,
            raw_coordinate=coord_raw,
            latitude=_safe_float(lat_s),
            longitude=_safe_float(lon_s),
            altitude_m=_safe_float(alt_s),
            cep_m=_safe_float(cep_s),
        )
    elif lat_s and lon_s:
        kw["location"] = TargetLocation(
            coord_system=CoordSystem.GEODETIC,
            raw_coordinate=f"{lat_s},{lon_s}",
            latitude=_safe_float(lat_s),
            longitude=_safe_float(lon_s),
            altitude_m=_safe_float(alt_s),
            cep_m=_safe_float(cep_s),
        )

    # source assembly
    srctype = kw.pop("_srctype", None)
    srcunit = kw.pop("_srcunit", "")
    srcrel = kw.pop("_srcrel", "")
    srccred = kw.pop("_srccred", "")
    if srctype:
        kw["source"] = SourceInfo(
            source_type=srctype,
            source_unit=srcunit,
            reliability=srcrel,
            credibility=srccred,
        )

    # enums (graceful fallback)
    for fld, enum_cls in [
        ("category", TargetCategory),
        ("priority", TargetPriority),
        ("status", TargetStatus),
    ]:
        v = kw.get(fld)
        if isinstance(v, str):
            try:
                kw[fld] = enum_cls(v.upper())
            except ValueError:
                kw["extra"][fld + "_raw"] = v
                kw[fld] = enum_cls.UNKNOWN if hasattr(enum_cls, "UNKNOWN") else list(enum_cls)[0]

    return TidetEvent(**kw)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(s: str) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return _parse_military_dtg(s)


def _parse_military_dtg(s: str) -> datetime:
    """Best-effort parse of military Date-Time Group, e.g.
    ``201200ZAPR2026`` → 2026-04-20T12:00Z."""
    s = s.strip().upper()
    if not s:
        return datetime.now(timezone.utc)
    # common patterns
    for fmt in (
        "%d%H%MZ%b%Y",   # 201200ZAPR2026
        "%d%H%M%b%Y",    # 201200APR2026
        "%Y%m%d%H%M%S",  # 20260420120000
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None
