"""
Algorithmic Sciences TCP String Search Server
=============================================

This module implements a multithreaded TCP server that performs exact
full-line string matching against a dataset. It supports multiple
search algorithms, SSL/TLS transport, and configurable behavior.

Features:
---------
- Config-driven (dataset path, SSL, reread-on-query, algorithm, host/port).
- Exact full-line search only (no partial matches).
- Responses: "STRING EXISTS\\n" or "STRING NOT FOUND\\n".
- Optional caching for high performance.
- Detailed DEBUG logs with query, IP, timestamp, and execution time.
- Multithreaded: handles concurrent clients.
- Robust exception handling: network errors, SSL failures, invalid payloads.

Usage:
------
    python3 -m server.main_server --config config.ini
"""

from typing import Tuple, Optional
import argparse
import configparser
import socket
import threading
import logging
import time
import signal
import ssl

from server import search_algorithms as sa
from server.ssl_utils import wrap_socket_if_needed
from server.utils import safe_recv, debug_log

# Configure logger
LOG = logging.getLogger("algoserver")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)

DEFAULT_MAX_PAYLOAD = 1024


class Config:
    """
    Container for server configuration values.

    This class encapsulates server settings loaded from `config.ini`.

    Args:
        cfg (configparser.ConfigParser): Parsed configuration file.

    Attributes:
        linuxpath (str): Path to dataset file containing newline-separated strings.
        reread_on_query (bool): If True, reload dataset from disk on every query.
        ssl_enabled (bool): Whether SSL/TLS transport is enabled.
        ssl_certfile (Optional[str]): Path to SSL certificate file (if SSL enabled).
        ssl_keyfile (Optional[str]): Path to SSL key file (if SSL enabled).
        host (str): Server host/IP address to bind.
        port (int): Port to listen on.
        max_payload (int): Maximum number of bytes to read from a client request.
        default_algorithm (str): Algorithm to use for searching (set, list, mmap, binary).
    """

    def __init__(self, cfg: configparser.ConfigParser):
        s = cfg["server"]
        self.linuxpath: str = s.get("linuxpath", fallback="./200k.txt")
        self.reread_on_query: bool = s.getboolean("REREAD_ON_QUERY", fallback=False)
        self.ssl_enabled: bool = s.getboolean("SSL_ENABLED", fallback=False)
        self.ssl_certfile: Optional[str] = s.get("SSL_CERTFILE", fallback=None)
        self.ssl_keyfile: Optional[str] = s.get("SSL_KEYFILE", fallback=None)
        self.host: str = s.get("HOST", fallback="0.0.0.0")
        self.port: int = s.getint("PORT", fallback=44445)
        self.max_payload: int = s.getint("MAX_PAYLOAD", fallback=DEFAULT_MAX_PAYLOAD)
        self.default_algorithm: str = s.get("DEFAULT_ALGORITHM", fallback="set")


class Searcher:
    """
    Search engine abstraction supporting multiple algorithms.

    This class manages dataset loading and provides an interface for
    full-line search queries. Depending on configuration, data can be
    cached in memory or reloaded on each query.

    Args:
        cfg (Config): Server configuration object.

    Attributes:
        cfg (Config): Configuration used for searches.
        _cached_set (Optional[set[str]]): Cached set of lines (for O(1) lookups).
        _cached_list (Optional[list[str]]): Cached list of lines.
        _cached_sorted (Optional[list[str]]): Cached sorted list (for binary search).
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._cached_set = None
        self._cached_list = None
        self._cached_sorted = None
        if not cfg.reread_on_query:
            self._preload()

    def _preload(self) -> None:
        """
        Preload dataset into memory depending on the configured algorithm.

        Notes:
            - For "set", data is stored as a Python set for O(1) lookups.
            - For "list", data is stored as a list for sequential scans.
            - For "binary", data is sorted and searched via binary search.
            - If dataset file is missing, logs error and skips preload.
        """
        path = self.cfg.linuxpath
        try:
            if self.cfg.default_algorithm == "set":
                self._cached_set = sa.load_lines_set(path)
            elif self.cfg.default_algorithm == "list":
                self._cached_list = sa.load_lines_list(path)
            elif self.cfg.default_algorithm == "binary":
                self._cached_sorted = sorted(sa.load_lines_list(path))
            else:
                self._cached_set = sa.load_lines_set(path)
        except FileNotFoundError:
            LOG.error("Dataset file not found: %s", path)
        except PermissionError:
            LOG.error("Permission denied reading dataset: %s", path)
        except (OSError, IOError) as e:
            LOG.error("Error loading dataset file %s: %s", path, e)

    def search(self, needle: str) -> bool:
        """
        Perform an exact full-line match search.

        Args:
            needle (str): Query string to search for.

        Returns:
            bool: True if the string exists in dataset, False otherwise.

        Raises:
            OSError: If dataset file cannot be accessed during reread mode.

        Notes:
            - In reread mode, file is reloaded for every query.
            - In cached mode, results depend on preloaded structures.
        """
        path = self.cfg.linuxpath
        try:
            if self.cfg.reread_on_query:
                if self.cfg.default_algorithm == "set":
                    return needle in sa.load_lines_set(path)
                elif self.cfg.default_algorithm == "list":
                    return needle in sa.load_lines_list(path)
                elif self.cfg.default_algorithm == "mmap":
                    return sa.mmap_search(path, needle)
                elif self.cfg.default_algorithm == "binary":
                    lines = sorted(sa.load_lines_list(path))
                    return sa.binary_search_sorted(lines, needle)
                else:
                    return sa.mmap_search(path, needle)
            else:
                if self._cached_set is not None:
                    return needle in self._cached_set
                if self._cached_list is not None:
                    return needle in self._cached_list
                if self._cached_sorted is not None:
                    return sa.binary_search_sorted(self._cached_sorted, needle)
                return sa.mmap_search(path, needle)
        except FileNotFoundError:
            LOG.error("Dataset file not found during search: %s", path)
            return False
        except PermissionError:
            LOG.error("Permission denied accessing dataset during search: %s", path)
            return False
        except (OSError, IOError) as e:
            LOG.error("IO error during search for query %r: %s", needle, e)
            return False
        except (TypeError, ValueError) as e:
            LOG.error("Invalid data type in search for query %r: %s", needle, e)
            return False


class TCPServer:
    """
    Multithreaded TCP server for full-line string matching.

    Attributes:
        cfg (Config): Server configuration.
        addr (Tuple[str, int]): Host/port tuple.
        sock (socket.socket): Listening socket.
        searcher (Searcher): Search engine instance.
        should_stop (threading.Event): Shutdown signal flag.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.addr: Tuple[str, int] = (cfg.host, cfg.port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.searcher = Searcher(cfg)
        self.should_stop = threading.Event()

    def start(self) -> None:
        """
        Start the TCP server and accept incoming client connections.

        Notes:
            - Handles SSL wrapping if enabled in configuration.
            - Spawns a new thread for each client.
        """
        LOG.info("Starting server on %s:%d SSL=%s", self.cfg.host, self.cfg.port, self.cfg.ssl_enabled)
        try:
            self.sock.bind(self.addr)
            self.sock.listen(50)
            if self.cfg.ssl_enabled:
                self.sock = wrap_socket_if_needed(self.sock, True, self.cfg.ssl_certfile, self.cfg.ssl_keyfile)
        except PermissionError:
            LOG.error("Permission denied binding to %s:%d", self.cfg.host, self.cfg.port)
            return
        except OSError as e:
            LOG.error("Failed to bind server socket: %s", e)
            return
        except ssl.SSLError as e:
            LOG.error("SSL error during socket setup: %s", e)
            return

        try:
            while not self.should_stop.is_set():
                try:
                    client_sock, client_addr = self.sock.accept()
                    t = threading.Thread(
                        target=self._handle_client, args=(client_sock, client_addr), daemon=True
                    )
                    t.start()
                except socket.timeout:
                    # Expected for non-blocking sockets
                    continue
                except OSError as e:
                    if not self.should_stop.is_set():
                        LOG.warning("Accept error: %s", e)
                    continue
        finally:
            try:
                self.sock.close()
            except OSError:
                pass

    def _handle_client(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        """
        Handle a connected client request.

        Args:
            conn (socket.socket): Connected client socket.
            addr (Tuple[str, int]): Client address (ip, port).

        Behavior:
            - Reads up to MAX_PAYLOAD bytes.
            - Decodes query safely (UTF-8 with replacement).
            - Executes search using Searcher.
            - Logs query and execution time.
            - Sends back a response string.

        Exceptions:
            - Handles network errors (BrokenPipe, Reset).
            - Handles invalid UTF-8 gracefully.
        """
        try:
            start = time.perf_counter()
            raw = safe_recv(conn, self.cfg.max_payload)
            try:
                query = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            except UnicodeDecodeError:
                LOG.warning("Invalid UTF-8 from %s", addr)
                query = ""

            found = self.searcher.search(query)
            exec_ms = (time.perf_counter() - start) * 1000.0
            debug_log(addr, query, exec_ms)

            try:
                if found:
                    conn.sendall(b"STRING EXISTS\n")
                else:
                    conn.sendall(b"STRING NOT FOUND\n")
            except BrokenPipeError:
                LOG.warning("Connection broken before response sent: %s", addr)
            except ConnectionResetError:
                LOG.warning("Connection reset by peer: %s", addr)
            except OSError as e:
                LOG.warning("Socket error sending response to %s: %s", addr, e)

        except socket.timeout:
            LOG.warning("Timeout handling client %s", addr)
        except ConnectionResetError:
            LOG.warning("Connection reset by client %s", addr)
        except BrokenPipeError:
            LOG.warning("Broken pipe with client %s", addr)
        except ssl.SSLError as e:
            LOG.error("SSL error with client %s: %s", addr, e)
        except OSError as e:
            LOG.error("Socket error with client %s: %s", addr, e)
        except UnicodeDecodeError as e:
            LOG.error("Unicode decode error from client %s: %s", addr, e)
        except ValueError as e:
            LOG.error("Value error handling client %s: %s", addr, e)
        finally:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass

    def stop(self) -> None:
        """Stop the server gracefully by closing the listening socket."""
        self.should_stop.set()
        try:
            self.sock.close()
        except OSError:
            pass


def load_config(path: str) -> Config:
    """
    Load server configuration from a file.

    Args:
        path (str): Path to config.ini file.

    Returns:
        Config: Parsed configuration object.
    
    Raises:
        FileNotFoundError: If config file doesn't exist.
        configparser.Error: If config file is malformed.
    """
    cp = configparser.ConfigParser()
    try:
        cp.read(path)
        if not cp.has_section("server"):
            raise configparser.NoSectionError("server")
        return Config(cp)
    except FileNotFoundError:
        LOG.error("Config file not found: %s", path)
        raise
    except configparser.Error as e:
        LOG.error("Config parsing error: %s", e)
        raise


def main() -> None:
    """
    CLI entrypoint for the TCP server.

    Notes:
        - Loads config.ini
        - Registers SIGINT/SIGTERM handlers
        - Starts TCPServer
    """
    parser = argparse.ArgumentParser(description="Algorithmic Sciences String Search Server")
    parser.add_argument("--config", default="config.ini", help="Path to config.ini")
    args = parser.parse_args()
    
    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, configparser.Error):
        LOG.error("Failed to load configuration. Exiting.")
        return
    
    srv = TCPServer(cfg)

    def handle_sig(signum, frame):
        LOG.info("Shutdown signal received")
        srv.stop()

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    srv.start()


if __name__ == "__main__":
    main()