# AFATADS Integrator Guide

This guide details how to install, configure, and integrate the AFATADS GTCS client into existing systems.

## 1. Prerequisites

- **Python 3.7+** installed.
- No external libraries are needed. The client only uses the Python Standard Library.

## 2. Installation

The client is designed to be portable and can be used directly from the source directory without formal installation.

### Option A: Direct Usage (No Install)
Simply clone the repository and use the provided wrapper scripts:
- Linux: `afatads.sh`
- Windows (PS): `afatads.ps1`
- Windows (CMD): `afatads.bat`

### Option B: Python Package Installation
If you wish to install it into your system or a virtual environment:

```bash
cd afatads
pip install .
```
*(Requires `setuptools` and `wheel`, but no runtime dependencies will be installed.)*

## 3. Configuration

Configuration is managed via a JSON file. Use the following schema as a reference:

### Top-Level Configuration (`ClientConfig`)

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled_endpoints` | `list[str]` | `["tcp"]` | Which endpoints to start (e.g., `["tcp", "udp", "rest"]`). |
| `tcp` | `object` | `{...}` | TCP endpoint settings. |
| `udp` | `object` | `{...}` | UDP/Multicast endpoint settings. |
| `rest` | `object` | `{...}` | REST polling endpoint settings. |
| `store` | `object` | `{...}` | On-disk TIDET storage settings. |
| `logging` | `object` | `{...}` | Logging level and file path. |

### TCP Endpoint Settings

- `host` (str): Remote GTCS hostname or IP.
- `port` (int): GTCS service port.
- `reconnect_interval_s` (float): Seconds to wait before reconnecting.
- `tls` (bool): Enable TLS for the TCP stream.

### REST Polling Settings

- `base_url` (str): TAK-Server URL (e.g., `http://10.0.0.1:8080`).
- `path` (str): API endpoint path (default: `/api/tidet`).
- `poll_interval_s` (float): Seconds between HTTP GET requests.
- `auth_type` (str): Authentication method (`"bearer"`, `"basic"`, or `""`).
- `token` (str): API token for bearer authentication.

### Storage Settings

- `root_dir` (str): Root path for the time-sharded store.
- `indent_json` (int): Pretty-printing indentation (set to `null` to disable).

## 4. Programmatic Integration

The client library can be imported into your own Python projects.

### Example: Running the Ingest Client

```python
import asyncio
import os
import sys

# Add src to PYTHONPATH if not installed
sys.path.append(os.path.abspath("src"))

from afatads.config import load_config
from afatads.client import GtcsClient

async def main():
    config = load_config("config.json")
    client = GtcsClient(config)
    await client.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

### Example: Querying the Store

```python
from afatads.config import StoreConfig
from afatads.store import TidetReader

# Initialize the reader
store_cfg = StoreConfig(root_dir="./tidet_store")
reader = TidetReader(store_cfg)

# Find all events for a specific target
target_id = "AB1234"
events = reader.find_by_target(target_id)

for evt in events:
    print(f"Target: {evt.target_number} at {evt.dtg}")
    if evt.location:
        print(f"  Coords: {evt.location.raw_coordinate}")
```
