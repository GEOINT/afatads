"""YAML-backed configuration for the AFATADS GTCS client."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Config data-classes
# ---------------------------------------------------------------------------

@dataclass
class TcpEndpointConfig:
    host: str = "127.0.0.1"
    port: int = 4011
    reconnect_interval_s: float = 5.0
    recv_buffer: int = 8192
    delimiter: str = "\n"
    tls: bool = False
    tls_cert: str = ""
    tls_key: str = ""
    tls_ca: str = ""


@dataclass
class UdpEndpointConfig:
    host: str = "239.1.1.1"
    port: int = 4012
    multicast: bool = True
    recv_buffer: int = 8192
    interface: str = ""


@dataclass
class RestEndpointConfig:
    base_url: str = "http://127.0.0.1:8080"
    path: str = "/api/tidet"
    poll_interval_s: float = 10.0
    auth_type: str = ""        # "", "basic", "bearer", "cert"
    username: str = ""
    password: str = ""
    token: str = ""
    tls_cert: str = ""
    tls_key: str = ""
    tls_ca: str = ""
    verify_ssl: bool = True
    timeout_s: float = 30.0


@dataclass
class StoreConfig:
    root_dir: str = "./tidet_store"
    indent_json: int = 2


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = ""


@dataclass
class ClientConfig:
    """Top-level configuration object."""
    tcp: TcpEndpointConfig = field(default_factory=TcpEndpointConfig)
    udp: UdpEndpointConfig = field(default_factory=UdpEndpointConfig)
    rest: RestEndpointConfig = field(default_factory=RestEndpointConfig)
    store: StoreConfig = field(default_factory=StoreConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    enabled_endpoints: list[str] = field(default_factory=lambda: ["tcp"])


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _merge(target: dict, source: dict) -> dict:
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _merge(target[k], v)
        else:
            target[k] = v
    return target


def _apply_section(obj: Any, data: dict) -> None:
    for k, v in data.items():
        if hasattr(obj, k):
            setattr(obj, k, v)


def load_config(path: str | pathlib.Path) -> ClientConfig:
    """Load a YAML config file and return a *ClientConfig*."""
    path = pathlib.Path(path)
    with path.open("r", encoding="utf-8") as fh:
        raw: dict = yaml.safe_load(fh) or {}

    cfg = ClientConfig()
    if "tcp" in raw:
        _apply_section(cfg.tcp, raw["tcp"])
    if "udp" in raw:
        _apply_section(cfg.udp, raw["udp"])
    if "rest" in raw:
        _apply_section(cfg.rest, raw["rest"])
    if "store" in raw:
        _apply_section(cfg.store, raw["store"])
    if "logging" in raw:
        _apply_section(cfg.logging, raw["logging"])
    if "enabled_endpoints" in raw:
        cfg.enabled_endpoints = raw["enabled_endpoints"]

    return cfg
