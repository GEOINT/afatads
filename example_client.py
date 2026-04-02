"""
Example script demonstrating how to use the AFATADS GTCS client library.
This script creates a dummy TIDET event and writes it to the local store.
"""

import os
import sys
from datetime import datetime, timezone

# Add src to PYTHONPATH if not installed
sys.path.append(os.path.abspath("src"))

from afatads.model import (
    TidetEvent, TargetLocation, CoordSystem, 
    TargetCategory, TargetPriority, TargetStatus
)
from afatads.config import StoreConfig
from afatads.store import TidetWriter, TidetReader

def main():
    # 1. Setup storage configuration
    store_dir = "./example_store"
    cfg = StoreConfig(root_dir=store_dir, indent_json=4)
    writer = TidetWriter(cfg)
    
    # 2. Create a dummy TIDET event
    event = TidetEvent(
        target_number="ZZ9999",
        dtg=datetime.now(timezone.utc),
        location=TargetLocation(
            coord_system=CoordSystem.MGRS,
            raw_coordinate="18STN0543210987",
            latitude=38.8895,
            longitude=-77.0353
        ),
        category=TargetCategory.COMMAND_CONTROL,
        target_type="HQ BUNKERS",
        description="High-value target identified via OSINT",
        priority=TargetPriority.IMMEDIATE,
        status=TargetStatus.CONFIRMED,
        originator="INTEL-CELL-1"
    )
    
    print(f"Created event for target: {event.target_number}")
    
    # 3. Write to disk
    path = writer.write(event)
    print(f"Event written to: {path}")
    
    # 4. Read it back
    reader = TidetReader(cfg)
    found_events = reader.find_by_target("ZZ9999")
    
    print(f"\nFound {len(found_events)} events for target ZZ9999:")
    for evt in found_events:
        print(f"  - Event ID: {evt.event_id}")
        print(f"  - Category: {evt.category}")
        print(f"  - Description: {evt.description}")
        print(f"  - Coordinates: {evt.location.raw_coordinate if evt.location else 'N/A'}")

if __name__ == "__main__":
    main()
