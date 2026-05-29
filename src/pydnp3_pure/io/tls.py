"""TLS context builder for DNP3 secure communication."""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TlsConfig:
    """TLS configuration for DNP3 channels."""

    ca_cert_path: str | Path
    client_cert_path: str | Path | None = None
    client_key_path: str | Path | None = None
    key_password: str | None = None
    verify_hostname: bool = True
    server_hostname: str | None = None
    min_version: int = ssl.TLSVersion.TLSv1_2


def create_tls_context(config: TlsConfig, server_side: bool = False) -> ssl.SSLContext:
    """Create an SSL context from the given TLS configuration.

    Args:
        config: TLS certificate and key paths
        server_side: True for server (master listening), False for client (outstation connecting)

    Returns:
        Configured ssl.SSLContext with TLS 1.2+ minimum
    """
    if server_side:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    else:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    ctx.load_verify_locations(cafile=str(config.ca_cert_path))

    if config.client_cert_path and config.client_key_path:
        ctx.load_cert_chain(
            certfile=str(config.client_cert_path),
            keyfile=str(config.client_key_path),
            password=config.key_password,
        )

    if server_side:
        ctx.verify_mode = ssl.CERT_REQUIRED
    else:
        ctx.check_hostname = config.verify_hostname
        if not config.verify_hostname:
            ctx.verify_mode = ssl.CERT_NONE

    return ctx
