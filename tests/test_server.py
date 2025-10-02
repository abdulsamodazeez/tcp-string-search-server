"""
Unit tests for main_server.py (TCPServer and Config).
"""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import socket
import threading
import tempfile
import pytest
from server.main_server import Config, TCPServer
import configparser


@pytest.fixture
def sample_file():
    with tempfile.NamedTemporaryFile("w+", delete=False) as f:
        f.write("dog\ncat\nmouse\n")
        f.flush()
        yield f.name
    os.remove(f.name)


def make_config(path, reread=False):
    """Helper to build Config object dynamically."""
    cp = configparser.ConfigParser()
    cp["server"] = {
        "linuxpath": path,
        "REREAD_ON_QUERY": str(reread),
        "HOST": "127.0.0.1",
        "PORT": "45679",
        "DEFAULT_ALGORITHM": "set",
    }
    return Config(cp)


def test_server_response(sample_file):
    cfg = make_config(sample_file)
    server = TCPServer(cfg)

    t = threading.Thread(target=server.start, daemon=True)
    t.start()

    # Connect as client
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", cfg.port))
    sock.sendall(b"dog")
    data = sock.recv(1024)
    sock.close()

    assert b"STRING EXISTS" in data
    server.stop()
