# AFATADS GTCS Client

A high-performance, **zero external dependency** AFATADS GTCS client for TIDET event ingestion and retrieval.

## Features

- **Zero External Dependencies**: Uses only the Python Standard Library.
- **Python 3.7+ Compatibility**: Runs on all modern Python versions (3.7 to 3.13+).
- **Cross-Platform**: Tested on Windows and Linux.
- **Multiple Transports**:
  - **TCP**: Delimiter-framed TIDET streams (with optional TLS).
  - **UDP**: Multicast/Unicast datagrams.
  - **REST**: Polling of TAK-Server or compatible HTTP endpoints.
- **Time-Sharded Storage**: Efficiently stores TIDET events in a `yyyy/mm/dd` directory structure.
- **CLI Tool**: Powerful command-line interface for ingestion, reading, and status checks.

## Quick Start

### 1. Configure the Client

Copy `config.example.json` to `config.json` and edit it with your GTCS endpoint details:

```bash
cp config.example.json config.json
# Or on Windows
copy config.example.json config.json
```

### 2. Run the Client

**Linux:**
```bash
./afatads.sh ingest -c config.json
```

**Windows (PowerShell):**
```powershell
.\afatads.ps1 ingest -c config.json
```

**Windows (Command Prompt):**
```cmd
afatads.bat ingest -c config.json
```

### 3. Read Stored Events

```bash
./afatads.sh read -c config.json --all
```

## CLI Commands

- `ingest`: Connect to GTCS endpoints and start ingesting TIDET events to disk.
- `read`: Retrieve events from the local store.
  - `--all`: Dump all events.
  - `--date YYYY-MM-DD`: Events for a specific day.
  - `--target AB1234`: Search for events by target number.
- `status`: Show storage statistics and date ranges.

## Example Configuration

```json
{
  "enabled_endpoints": ["tcp", "rest"],
  "tcp": {
    "host": "127.0.0.1",
    "port": 4011
  },
  "store": {
    "root_dir": "./tidet_store",
    "indent_json": 2
  }
}
```

## License
MIT
