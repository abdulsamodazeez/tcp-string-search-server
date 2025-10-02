from typing import Tuple
import logging
import time
import socket

LOG = logging.getLogger("algoserver")

def now_iso() -> str:
    """Return current time in ISO format (UTC)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def debug_log(remote_addr, query, exec_ms):
    """Emit a PDF-compliant DEBUG line."""
    LOG.debug(
        "query=%s ip=%s time=%s exec_ms=%.3f",
        query,
        f"{remote_addr[0]}:{remote_addr[1]}",
        now_iso(),
        exec_ms,
    )


def safe_recv(sock: socket.socket, max_len: int) -> bytes:
    """Receive up to max_len bytes and strip trailing NULs."""
    data = sock.recv(max_len)
    # strip trailing \x00
    return data.rstrip(b'\x00')
