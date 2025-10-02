"""
Unit tests for client.py.

These tests validate that the query_string function can handle
basic TCP connections and responses correctly.
"""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import socket
import threading
import pytest
from client import query_string


def dummy_server(port, response=b"STRING EXISTS\n"):
    """Simple echo-like server for testing the client."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(1)
    conn, _ = sock.accept()
    data = conn.recv(1024)
    conn.sendall(response)
    conn.close()
    sock.close()


def test_query_string_success(tmp_path):
    port = 45678
    t = threading.Thread(target=dummy_server, args=(port,), daemon=True)
    t.start()

    found, ms, raw = query_string("127.0.0.1", port, "apple")
    assert found is True
    assert b"STRING EXISTS" in raw
