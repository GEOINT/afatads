"""Tests for configuration loading."""

import tempfile
import json
from pathlib import Path

from afatads.config import load_config


def test_load_defaults():
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"enabled_endpoints": ["tcp"]}, f)
        f.flush()
        cfg = load_config(f.name)

    assert cfg.tcp.host == "127.0.0.1"
    assert cfg.tcp.port == 4011
    assert cfg.enabled_endpoints == ["tcp"]


def test_load_overrides():
    data = {
        "enabled_endpoints": ["tcp", "rest"],
        "tcp": {"host": "10.0.0.5", "port": 9999},
        "rest": {"base_url": "https://tak.example.mil", "auth_type": "bearer", "token": "abc"},
        "store": {"root_dir": "/data/tidet"},
        "logging": {"level": "DEBUG"},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        cfg = load_config(f.name)

    assert cfg.tcp.host == "10.0.0.5"
    assert cfg.tcp.port == 9999
    assert cfg.rest.base_url == "https://tak.example.mil"
    assert cfg.rest.auth_type == "bearer"
    assert cfg.store.root_dir == "/data/tidet"
    assert cfg.logging.level == "DEBUG"
    assert "rest" in cfg.enabled_endpoints
