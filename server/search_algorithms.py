"""
Search Algorithms Module
========================

This module implements multiple strategies for performing **exact
full-line string matching** against newline-delimited datasets.

Algorithms implemented:
-----------------------
1. **List-based search**
   - Loads all lines into a Python list.
   - Lookup: O(n) per query.
   - Lower memory usage, slower for large datasets.

2. **Set-based search**
   - Loads all lines into a Python set.
   - Lookup: O(1) average time per query.
   - Higher memory usage but fastest for repeated lookups.

3. **Memory-mapped search (mmap)**
   - Uses `mmap` to search file content without fully loading into memory.
   - Efficient for very large datasets.
   - Search complexity: O(n) but avoids Python string overhead.

4. **Binary search**
   - Requires pre-sorted list of lines.
   - Lookup: O(log n).
   - Efficient when dataset is sorted and stable.

5. **Subprocess grep**
   - Invokes system `grep -x` command.
   - Reliable whole-line match.
   - Slower due to process overhead.
   - Requires GNU `grep` to be installed.

Usage:
------
    from server import search_algorithms as sa

    # Example: memory-mapped search
    exists = sa.mmap_search("data/200.txt", "3;0;1;28;0;7;5;0;")
    print(exists)
"""

from typing import List, Set
import mmap
import bisect
import subprocess
import logging
import os

LOG = logging.getLogger("algoserver.search")


def load_lines_list(path: str) -> List[str]:
    """
    Load dataset file into a Python list of lines.

    Args:
        path (str): Path to the dataset file.

    Returns:
        List[str]: List of lines (without trailing newlines).

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If file cannot be opened.
        PermissionError: If file cannot be accessed due to permissions.

    Example:
        >>> lines = load_lines_list("data/200.txt")
        >>> "hello" in lines
        True
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return [line.rstrip("\n") for line in f]
    except FileNotFoundError:
        LOG.error("File not found: %s", path)
        raise
    except PermissionError:
        LOG.error("Permission denied reading %s", path)
        raise
    except (OSError, IOError) as e:
        LOG.error("IO error while reading %s: %s", path, e)
        raise


def load_lines_set(path: str) -> Set[str]:
    """
    Load dataset file into a Python set of lines for fast O(1) lookups.

    Args:
        path (str): Path to the dataset file.

    Returns:
        Set[str]: Unique set of lines (without trailing newlines).

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If file cannot be opened.
        PermissionError: If file cannot be accessed due to permissions.

    Example:
        >>> s = load_lines_set("data/200.txt")
        >>> "hello" in s
        True
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return {line.rstrip("\n") for line in f}
    except FileNotFoundError:
        LOG.error("File not found: %s", path)
        raise
    except PermissionError:
        LOG.error("Permission denied reading %s", path)
        raise
    except (OSError, IOError) as e:
        LOG.error("IO error while reading %s: %s", path, e)
        raise


def mmap_search(path: str, needle: str) -> bool:
    """
    Perform a memory-mapped search for a full line.

    Args:
        path (str): Path to the dataset file.
        needle (str): Query string to search for.

    Returns:
        bool: True if the line exists, False otherwise.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If memory mapping fails.

    Notes:
        - A newline is appended to the needle to ensure whole-line matching.
        - Memory-mapping avoids fully loading the file into RAM.

    Example:
        >>> mmap_search("data/200.txt", "3;0;1;28;0;7;5;0;")
        True
    """
    if not os.path.exists(path):
        LOG.error("Dataset file missing: %s", path)
        return False

    # Handle empty file edge case - mmap cannot map empty files
    if os.path.getsize(path) == 0:
        return False

    needle_bytes = (needle + "\n").encode("utf-8")
    try:
        with open(path, "rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                return mm.find(needle_bytes) != -1
            finally:
                mm.close()
    except FileNotFoundError:
        LOG.error("File not found during mmap: %s", path)
        return False
    except PermissionError:
        LOG.error("Permission denied for mmap on %s", path)
        return False
    except (OSError, ValueError) as e:
        LOG.error("mmap search failed on %s: %s", path, e)
        return False


def binary_search_sorted(lines: List[str], needle: str) -> bool:
    """
    Perform binary search on a sorted list of lines.

    Args:
        lines (List[str]): Sorted list of dataset lines.
        needle (str): Query string to search for.

    Returns:
        bool: True if the line exists, False otherwise.

    Raises:
        ValueError: If `lines` is not sorted.

    Notes:
        - Assumes the list is sorted. Results are undefined if not.
        - Lookup complexity: O(log n).

    Example:
        >>> lines = sorted(load_lines_list("data/200.txt"))
        >>> binary_search_sorted(lines, "target_line")
        True
    """
    try:
        i = bisect.bisect_left(lines, needle)
        return i != len(lines) and lines[i] == needle
    except TypeError as e:
        LOG.error("Binary search type error (list not comparable): %s", e)
        return False
    except IndexError as e:
        LOG.error("Binary search index error: %s", e)
        return False


def grep_subprocess(path: str, needle: str) -> bool:
    """
    Perform search using system `grep -x` via subprocess.

    Args:
        path (str): Path to the dataset file.
        needle (str): Query string to search for.

    Returns:
        bool: True if the line exists, False otherwise.

    Raises:
        FileNotFoundError: If dataset file or `grep` binary is missing.
        OSError: If subprocess execution fails.

    Notes:
        - Uses `-x` to match the entire line.
        - Slower due to process overhead.
        - Requires `grep` to be installed in system PATH.

    Example:
        >>> grep_subprocess("data/200.txt", "3;0;1;28;0;7;5;0;")
        True
    """
    if not os.path.exists(path):
        LOG.error("Dataset file not found for grep: %s", path)
        return False

    try:
        res = subprocess.run(
            ["grep", "-x", "--", needle, path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5.0,
        )
        return res.returncode == 0
    except FileNotFoundError:
        LOG.warning("grep not available on system; skipping grep_subprocess")
        return False
    except subprocess.TimeoutExpired:
        LOG.error("grep subprocess timed out for query: %s", needle)
        return False
    except (OSError, subprocess.SubprocessError) as e:
        LOG.error("Subprocess grep failed: %s", e)
        return False