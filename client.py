"""
TCP Client for Algorithmic Sciences Server
==========================================

This client connects to the Algorithmic Sciences TCP server, sends a query
string, and measures round-trip response time.

Features:
---------
- Supports both plain TCP and TLS (SSL) connections.
- Validates payload size against server limits.
- Handles server errors gracefully.
- Prints server response and execution latency.

Usage:
------
    python3 client.py --host 127.0.0.1 --port 44445 --string "target_line"
    python3 client.py --host 127.0.0.1 --port 44445 --string "target_line" --ssl
"""

from typing import Tuple, Optional
import argparse
import socket
import time
import ssl
import logging

# Constants
DEFAULT_MAX = 1024
LOG = logging.getLogger("algoserver.client")


def query_string(
    host: str,
    port: int,
    s: str,
    use_ssl: bool = False,
    certfile: Optional[str] = None
) -> Tuple[bool, float, bytes]:
    """
    Send a query string to the server and receive a response.

    Args:
        host (str): Server IP or hostname.
        port (int): TCP port of the server.
        s (str): Query string to check for existence.
        use_ssl (bool, optional): If True, use TLS for connection.
        certfile (Optional[str], optional): Path to trusted CA certificate file.

    Returns:
        Tuple[bool, float, bytes]:
            - bool: True if response contains "STRING EXISTS".
            - float: Round-trip time in milliseconds.
            - bytes: Raw server response.

    Raises:
        ValueError: If payload exceeds maximum allowed size.
        socket.error: If connection or send/receive fails.

    Example:
        >>> query_string("127.0.0.1", 44445, "line_123")
        (True, 1.23, b'STRING EXISTS\\n')
    """
    addr = (host, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    if use_ssl:
        try:
            ctx = ssl.create_default_context()
            if certfile:
                ctx.load_verify_locations(certfile)
            else:
                # Allow self-signed certs (testing only)
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            sock = ctx.wrap_socket(sock, server_hostname=host)
        except ssl.SSLError as e:
            LOG.error("SSL context creation failed: %s", e)
            return (False, 0.0, b"")
        except FileNotFoundError:
            LOG.error("SSL certificate file not found: %s", certfile)
            return (False, 0.0, b"")

    try:
        sock.connect(addr)
        payload = s.encode("utf-8")
        if len(payload) > DEFAULT_MAX:
            raise ValueError("Payload exceeds max size")

        start = time.perf_counter()
        sock.sendall(payload)
        data = sock.recv(DEFAULT_MAX)
        elapsed = (time.perf_counter() - start) * 1000.0
        return (b"STRING EXISTS" in data, elapsed, data)
    except ConnectionRefusedError:
        LOG.error("Connection refused by server at %s:%d", host, port)
        return (False, 0.0, b"")
    except socket.timeout:
        LOG.error("Connection timed out to %s:%d", host, port)
        return (False, 0.0, b"")
    except ConnectionResetError:
        LOG.error("Connection reset by server at %s:%d", host, port)
        return (False, 0.0, b"")
    except BrokenPipeError:
        LOG.error("Broken pipe connecting to %s:%d", host, port)
        return (False, 0.0, b"")
    except ssl.SSLError as e:
        LOG.error("SSL error: %s", e)
        return (False, 0.0, b"")
    except socket.gaierror as e:
        LOG.error("Address resolution error for %s: %s", host, e)
        return (False, 0.0, b"")
    except ValueError as e:
        LOG.error("Value error: %s", e)
        return (False, 0.0, b"")
    except OSError as e:
        LOG.error("Socket error: %s", e)
        return (False, 0.0, b"")
    finally:
        try:
            sock.close()
        except OSError:
            pass


def main() -> None:
    """CLI entry point for the TCP client."""
    parser = argparse.ArgumentParser(description="Algorithmic Sciences TCP Client")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=44445, help="Server port")
    parser.add_argument("--string", required=True, help="Query string to search")
    parser.add_argument("--ssl", action="store_true", help="Enable TLS/SSL")
    parser.add_argument("--cert", help="Optional CA certificate file")
    args = parser.parse_args()

    found, ms, raw = query_string(args.host, args.port, args.string, args.ssl, args.cert)
    if raw:
        print(f"Response: {raw.decode('utf-8', errors='replace').strip()}")
        print(f"Elapsed: {ms:.3f} ms")
    else:
        print("❌ No response from server (check logs).")


if __name__ == "__main__":
    main()