"""
Unit tests for search_algorithms module.

These tests validate correctness of all implemented search strategies
(set, list, mmap, binary, grep) using a temporary dataset.
"""

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tempfile
import pytest
from server import search_algorithms as sa


@pytest.fixture
def sample_file():
    """Create a temporary dataset file for testing."""
    with tempfile.NamedTemporaryFile("w+", delete=False) as f:
        f.write("apple\nbanana\ncherry\n")
        f.flush()
        yield f.name
    os.remove(f.name)


def test_load_lines_list(sample_file):
    lines = sa.load_lines_list(sample_file)
    assert "apple" in lines
    assert "banana" in lines
    assert "cherry" in lines


def test_load_lines_set(sample_file):
    data = sa.load_lines_set(sample_file)
    assert "banana" in data
    assert "pear" not in data


def test_mmap_search(sample_file):
    assert sa.mmap_search(sample_file, "banana")
    assert not sa.mmap_search(sample_file, "pear")


def test_binary_search_sorted(sample_file):
    lines = sorted(sa.load_lines_list(sample_file))
    assert sa.binary_search_sorted(lines, "cherry")
    assert not sa.binary_search_sorted(lines, "pear")


def test_grep_subprocess(sample_file):
    assert sa.grep_subprocess(sample_file, "apple") is True
    assert sa.grep_subprocess(sample_file, "pear") is False
