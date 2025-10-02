"""
Streamlit Query Tester for Algorithmic Sciences Server
======================================================

This lightweight web UI allows interactive testing of the TCP server.

Features:
---------
- Input server host, port, and query string.
- Toggle TLS/SSL option.
- Displays server response and round-trip time.
- Handles errors gracefully and shows them in the UI.

Usage:
------
    streamlit run streamlit_app.py
"""

import streamlit as st
import time
import socket
import ssl


def send_query(host: str, port: int, query: str, use_ssl: bool = False) -> tuple[str, float]:
    """
    Send a query to the TCP server and return response + elapsed time.

    Args:
        host (str): Server hostname or IP.
        port (int): Server port.
        query (str): Query string to send.
        use_ssl (bool): If True, wrap socket in SSL/TLS.

    Returns:
        tuple[str, float]:
            - Response string (decoded)
            - Elapsed time in milliseconds
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        sock = ctx.wrap_socket(sock, server_hostname=host)

    start = time.perf_counter()
    sock.connect((host, port))
    sock.sendall(query.encode("utf-8"))
    data = sock.recv(1024)
    elapsed = (time.perf_counter() - start) * 1000.0
    sock.close()
    return data.decode("utf-8", errors="replace").strip(), elapsed


# ---------------- Streamlit UI ----------------
st.title("Algorithmic Sciences - Query Tester")

host = st.text_input("Server Host", value="127.0.0.1")
port = st.number_input("Server Port", value=44445, step=1)
use_ssl = st.checkbox("Use TLS (SSL)", value=False)
query = st.text_input("Query line to search")

if st.button("Search"):
    try:
        response, elapsed = send_query(host, port, query, use_ssl)
        st.success(f"Response: {response}")
        st.info(f"Elapsed time: {elapsed:.3f} ms")
    except Exception as e:
        st.error(f"❌ Error: {e}")
