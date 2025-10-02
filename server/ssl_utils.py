"""
SSL utilities for the Algorithmic Sciences TCP String Search Server.

This module provides helpers to enable TLS encryption for the server.
It creates SSL contexts and optionally wraps sockets, depending on
configuration values.

Features:
    - Create hardened SSLContext objects.
    - Disable insecure TLS versions (TLSv1.0, TLSv1.1).
    - Support self-signed certificates for testing.
    - Optional wrapping of sockets if SSL is enabled.

Usage:
    from server.ssl_utils import wrap_socket_if_needed

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    secure_socket = wrap_socket_if_needed(server_socket, True, "cert.pem", "key.pem")
"""

from typing import Optional
import ssl
import socket
import logging

LOG = logging.getLogger("algoserver.ssl")


def create_server_ssl_context(certfile: str, keyfile: str) -> ssl.SSLContext:
    """Create an SSL context for server-side TLS.

    Args:
        certfile (str): Path to PEM-formatted SSL certificate file.
        keyfile (str): Path to PEM-formatted SSL private key file.

    Returns:
        ssl.SSLContext: Configured SSL context for a server.

    Notes:
        - Uses `ssl.PROTOCOL_TLS_SERVER`, which automatically selects the
          highest available TLS version.
        - TLSv1.0 and TLSv1.1 are explicitly disabled for security reasons.
        - Does not enforce client certificate verification (self-signed certs allowed).

    Example:
        >>> ctx = create_server_ssl_context("cert.pem", "key.pem")
        >>> isinstance(ctx, ssl.SSLContext)
        True
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)

    # Harden context by disabling legacy protocols
    ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
    return ctx


def wrap_socket_if_needed(
    sock: socket.socket,
    ssl_enabled: bool,
    certfile: Optional[str],
    keyfile: Optional[str],
) -> socket.socket:
    """Wrap a socket with SSL if enabled in configuration.

    Args:
        sock (socket.socket): The raw TCP socket to wrap.
        ssl_enabled (bool): Whether SSL/TLS is enabled.
        certfile (Optional[str]): Path to certificate file (if SSL enabled).
        keyfile (Optional[str]): Path to key file (if SSL enabled).

    Returns:
        socket.socket: Either the raw socket (if SSL disabled), or
        an SSL-wrapped socket (if enabled).

    Raises:
        RuntimeError: If SSL is enabled but certificate or key file is missing.

    Example:
        >>> import socket
        >>> s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        >>> secure_sock = wrap_socket_if_needed(s, False, None, None)
        >>> isinstance(secure_sock, socket.socket)
        True
    """
    if not ssl_enabled:
        return sock

    if not certfile or not keyfile:
        raise RuntimeError("SSL enabled but certfile/keyfile missing in config")

    ctx = create_server_ssl_context(certfile, keyfile)
    return ctx.wrap_socket(sock, server_side=True)
