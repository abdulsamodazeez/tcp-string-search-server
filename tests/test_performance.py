"""
Performance Tests for Search Algorithms
========================================

This module validates that search algorithms meet the performance
requirements specified in the task:

- Cache mode (REREAD_ON_QUERY=False): < 0.5 ms/query at 250,000 rows.
- Reread mode (REREAD_ON_QUERY=True): < 40 ms/query at 250,000 rows.

These tests generate temporary datasets of various sizes and measure
average query execution time to ensure compliance with thresholds.

Note: Not all algorithms are expected to pass all thresholds. The tests
document which algorithms meet the specification requirements.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tempfile
import time
import random
import pytest
from server import search_algorithms as sa

# Performance thresholds from specification
CACHE_THRESHOLD_MS = 0.5
REREAD_THRESHOLD_MS = 40.0

# Test dataset sizes
SMALL_SIZE = 1000
MEDIUM_SIZE = 10000
LARGE_SIZE = 250000  # Required benchmark size

# Number of queries to average
NUM_QUERIES = 25


def generate_test_file(size):
    """
    Generate a temporary test file with specified number of lines.
    
    Args:
        size (int): Number of lines to generate.
        
    Returns:
        tuple: (file_path, list_of_lines)
    """
    f = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt')
    lines = []
    for i in range(size):
        # Generate realistic semicolon-delimited data
        line = ";".join(str(random.randint(0, 9)) for _ in range(8))
        f.write(f"{line}\n")
        lines.append(line)
    f.flush()
    f.close()
    return f.name, lines


@pytest.fixture(scope="module")
def small_dataset():
    """Fixture for small dataset (1k lines)."""
    path, lines = generate_test_file(SMALL_SIZE)
    yield path, lines
    os.remove(path)


@pytest.fixture(scope="module")
def medium_dataset():
    """Fixture for medium dataset (10k lines)."""
    path, lines = generate_test_file(MEDIUM_SIZE)
    yield path, lines
    os.remove(path)


@pytest.fixture(scope="module")
def large_dataset():
    """Fixture for large dataset (250k lines) - required for spec compliance."""
    path, lines = generate_test_file(LARGE_SIZE)
    yield path, lines
    os.remove(path)


def measure_cache_performance(path, lines, algorithm):
    """
    Measure performance in cache mode (data loaded once).
    
    Args:
        path (str): Path to test file.
        lines (list): List of lines in file.
        algorithm (str): Algorithm to test.
        
    Returns:
        float: Average milliseconds per query.
    """
    # Prepare queries: mix of existing and non-existing strings
    queries = random.choices(lines, k=NUM_QUERIES - 5)
    queries += [f"nonexistent_{i}" for i in range(5)]
    
    # Pre-load data once (cache mode)
    if algorithm == "set":
        data = sa.load_lines_set(path)
    elif algorithm == "list":
        data = sa.load_lines_list(path)
    elif algorithm == "binary":
        data = sorted(sa.load_lines_list(path))
    
    # Measure query time
    start = time.perf_counter()
    
    for query in queries:
        if algorithm == "set":
            _ = query in data
        elif algorithm == "list":
            _ = query in data
        elif algorithm == "mmap":
            _ = sa.mmap_search(path, query)
        elif algorithm == "binary":
            _ = sa.binary_search_sorted(data, query)
        elif algorithm == "grep":
            _ = sa.grep_subprocess(path, query)
    
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed * 1000.0) / len(queries)
    
    return avg_ms


def measure_reread_performance(path, lines, algorithm):
    """
    Measure performance in reread mode (data reloaded per query).
    
    Args:
        path (str): Path to test file.
        lines (list): List of lines in file.
        algorithm (str): Algorithm to test.
        
    Returns:
        float: Average milliseconds per query.
    """
    queries = random.choices(lines, k=NUM_QUERIES - 5)
    queries += [f"nonexistent_{i}" for i in range(5)]
    
    start = time.perf_counter()
    
    for query in queries:
        if algorithm == "set":
            data = sa.load_lines_set(path)
            _ = query in data
        elif algorithm == "list":
            data = sa.load_lines_list(path)
            _ = query in data
        elif algorithm == "mmap":
            _ = sa.mmap_search(path, query)
        elif algorithm == "binary":
            data = sorted(sa.load_lines_list(path))
            _ = sa.binary_search_sorted(data, query)
        elif algorithm == "grep":
            _ = sa.grep_subprocess(path, query)
    
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed * 1000.0) / len(queries)
    
    return avg_ms


# ============================================================================
# Cache Mode Performance Tests (REREAD_ON_QUERY=False)
# ============================================================================

@pytest.mark.parametrize("algorithm", ["set", "list", "mmap", "binary"])
def test_cache_performance_small(small_dataset, algorithm):
    """Test cache mode performance on small dataset (1k lines)."""
    path, lines = small_dataset
    avg_ms = measure_cache_performance(path, lines, algorithm)
    
    # Should be very fast for small datasets
    assert avg_ms < 10.0, (
        f"{algorithm} cache mode too slow on {SMALL_SIZE} lines: "
        f"{avg_ms:.3f} ms/query (expected < 10 ms)"
    )
    print(f"{algorithm} cache @ {SMALL_SIZE} lines: {avg_ms:.3f} ms/query")


@pytest.mark.parametrize("algorithm", ["set", "list", "mmap", "binary"])
def test_cache_performance_medium(medium_dataset, algorithm):
    """Test cache mode performance on medium dataset (10k lines)."""
    path, lines = medium_dataset
    avg_ms = measure_cache_performance(path, lines, algorithm)
    
    # Should still be reasonably fast
    assert avg_ms < 5.0, (
        f"{algorithm} cache mode too slow on {MEDIUM_SIZE} lines: "
        f"{avg_ms:.3f} ms/query (expected < 5 ms)"
    )
    print(f"{algorithm} cache @ {MEDIUM_SIZE} lines: {avg_ms:.3f} ms/query")


@pytest.mark.parametrize("algorithm", ["set", "binary"])
def test_cache_performance_large_spec_compliance(large_dataset, algorithm):
    """
    Test that optimal algorithms meet cache mode specification at 250k lines.
    
    Requirement: < 0.5 ms/query at 250,000 rows (REREAD_ON_QUERY=False)
    
    Note: Only 'set' and 'binary' are expected to meet this strict requirement.
    """
    path, lines = large_dataset
    avg_ms = measure_cache_performance(path, lines, algorithm)
    
    print(f"\n{algorithm} cache mode @ 250k lines: {avg_ms:.3f} ms/query")
    
    assert avg_ms < CACHE_THRESHOLD_MS, (
        f"{algorithm} FAILS cache mode spec at {LARGE_SIZE} lines: "
        f"{avg_ms:.3f} ms/query (required < {CACHE_THRESHOLD_MS} ms)\n"
        f"Specification: REREAD_ON_QUERY=False must be < 0.5 ms at 250k rows"
    )


@pytest.mark.parametrize("algorithm", ["list", "mmap"])
def test_cache_performance_large_documented(large_dataset, algorithm):
    """
    Document cache mode performance for algorithms not expected to meet strict spec.
    
    This test documents performance but doesn't fail - it shows that these
    algorithms work but may not meet the < 0.5ms requirement.
    """
    path, lines = large_dataset
    avg_ms = measure_cache_performance(path, lines, algorithm)
    
    print(f"\n{algorithm} cache mode @ 250k lines: {avg_ms:.3f} ms/query")
    
    # Document performance but allow slower times
    assert avg_ms < 10.0, (
        f"{algorithm} unreasonably slow at {LARGE_SIZE} lines: "
        f"{avg_ms:.3f} ms/query"
    )


# ============================================================================
# Reread Mode Performance Tests (REREAD_ON_QUERY=True)
# ============================================================================

@pytest.mark.parametrize("algorithm", ["set", "list", "mmap", "binary"])
def test_reread_performance_small(small_dataset, algorithm):
    """Test reread mode performance on small dataset."""
    path, lines = small_dataset
    avg_ms = measure_reread_performance(path, lines, algorithm)
    
    # Should be reasonable even with reread
    assert avg_ms < 100.0, (
        f"{algorithm} reread mode too slow on {SMALL_SIZE} lines: "
        f"{avg_ms:.3f} ms/query (expected < 100 ms)"
    )
    print(f"{algorithm} reread @ {SMALL_SIZE} lines: {avg_ms:.3f} ms/query")


@pytest.mark.parametrize("algorithm", ["list", "mmap"])
def test_reread_performance_large_spec_compliance(large_dataset, algorithm):
    """
    Test that optimal algorithms meet reread mode specification at 250k lines.
    
    Requirement: < 40 ms/query at 250,000 rows (REREAD_ON_QUERY=True)
    
    Note: 'list' and 'mmap' are expected to meet this requirement.
    """
    path, lines = large_dataset
    avg_ms = measure_reread_performance(path, lines, algorithm)
    
    print(f"\n{algorithm} reread mode @ 250k lines: {avg_ms:.3f} ms/query")
    
    assert avg_ms < REREAD_THRESHOLD_MS, (
        f"{algorithm} FAILS reread mode spec at {LARGE_SIZE} lines: "
        f"{avg_ms:.3f} ms/query (required < {REREAD_THRESHOLD_MS} ms)\n"
        f"Specification: REREAD_ON_QUERY=True must be < 40 ms at 250k rows"
    )


@pytest.mark.parametrize("algorithm", ["set", "binary"])
def test_reread_performance_large_documented(large_dataset, algorithm):
    """
    Document reread mode performance for algorithms not optimized for this mode.
    
    Set and binary search require sorting/conversion on each read, making them
    slower in reread mode. This test documents their performance without failing.
    """
    path, lines = large_dataset
    avg_ms = measure_reread_performance(path, lines, algorithm)
    
    print(f"\n{algorithm} reread mode @ 250k lines: {avg_ms:.3f} ms/query")
    
    # Document performance but allow slower times for these algorithms
    assert avg_ms < 200.0, (
        f"{algorithm} unreasonably slow at {LARGE_SIZE} lines: "
        f"{avg_ms:.3f} ms/query"
    )


# ============================================================================
# Edge Cases and Robustness Tests
# ============================================================================

def test_empty_file_performance():
    """Test performance with empty file (edge case)."""
    f = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    f.close()
    
    for algorithm in ["set", "list", "mmap", "binary"]:
        start = time.perf_counter()
        
        if algorithm == "set":
            data = sa.load_lines_set(f.name)
            _ = "test" in data
        elif algorithm == "list":
            data = sa.load_lines_list(f.name)
            _ = "test" in data
        elif algorithm == "mmap":
            _ = sa.mmap_search(f.name, "test")
        elif algorithm == "binary":
            data = sorted(sa.load_lines_list(f.name))
            _ = sa.binary_search_sorted(data, "test")
        
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 50.0, f"{algorithm} too slow on empty file: {elapsed_ms:.3f} ms"
    
    os.remove(f.name)


def test_single_line_performance():
    """Test performance with single-line file (edge case)."""
    f = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    f.write("single_line\n")
    f.flush()
    f.close()
    
    for algorithm in ["set", "list", "mmap", "binary"]:
        start = time.perf_counter()
        
        if algorithm == "set":
            data = sa.load_lines_set(f.name)
            _ = "single_line" in data
        elif algorithm == "list":
            data = sa.load_lines_list(f.name)
            _ = "single_line" in data
        elif algorithm == "mmap":
            _ = sa.mmap_search(f.name, "single_line")
        elif algorithm == "binary":
            data = sorted(sa.load_lines_list(f.name))
            _ = sa.binary_search_sorted(data, "single_line")
        
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 50.0, f"{algorithm} too slow on single line file: {elapsed_ms:.3f} ms"
    
    os.remove(f.name)


def test_long_lines_performance():
    """Test performance with very long lines (edge case)."""
    f = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    long_line = "x" * 10000  # 10k character line
    for i in range(100):
        f.write(f"{long_line}_{i}\n")
    f.flush()
    f.close()
    
    for algorithm in ["set", "list", "mmap"]:
        start = time.perf_counter()
        
        if algorithm == "set":
            data = sa.load_lines_set(f.name)
            _ = f"{long_line}_50" in data
        elif algorithm == "list":
            data = sa.load_lines_list(f.name)
            _ = f"{long_line}_50" in data
        elif algorithm == "mmap":
            _ = sa.mmap_search(f.name, f"{long_line}_50")
        
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert elapsed_ms < 200.0, (
            f"{algorithm} too slow with long lines: {elapsed_ms:.3f} ms"
        )
    
    os.remove(f.name)


def test_nonexistent_queries_performance(medium_dataset):
    """Test performance when all queries return NOT FOUND."""
    path, _ = medium_dataset
    
    # All queries guaranteed not to exist
    queries = [f"definitely_nonexistent_{i}" for i in range(NUM_QUERIES)]
    
    for algorithm in ["set", "list", "mmap", "binary"]:
        if algorithm == "set":
            data = sa.load_lines_set(path)
        elif algorithm == "list":
            data = sa.load_lines_list(path)
        elif algorithm == "binary":
            data = sorted(sa.load_lines_list(path))
        
        start = time.perf_counter()
        
        for query in queries:
            if algorithm == "set":
                _ = query in data
            elif algorithm == "list":
                _ = query in data
            elif algorithm == "mmap":
                _ = sa.mmap_search(path, query)
            elif algorithm == "binary":
                _ = sa.binary_search_sorted(data, query)
        
        elapsed_ms = (time.perf_counter() - start) * 1000.0 / len(queries)
        
        # Should still be fast even when nothing is found
        assert elapsed_ms < 10.0, (
            f"{algorithm} too slow on nonexistent queries: {elapsed_ms:.3f} ms/query"
        )


# ============================================================================
# Comparative Performance Test
# ============================================================================

def test_set_fastest_in_cache_mode(large_dataset):
    """
    Verify that 'set' algorithm is among the fastest for cache mode.
    
    This validates the DEFAULT_ALGORITHM choice in config.
    """
    path, lines = large_dataset
    
    results = {}
    for algorithm in ["set", "list", "mmap", "binary"]:
        avg_ms = measure_cache_performance(path, lines, algorithm)
        results[algorithm] = avg_ms
        print(f"{algorithm}: {avg_ms:.3f} ms")
    
    # Set should be competitive (within 3x of the fastest)
    fastest_ms = min(results.values())
    set_ms = results["set"]
    
    assert set_ms <= fastest_ms * 3.0, (
        f"'set' algorithm not competitive: {set_ms:.3f} ms "
        f"(fastest: {fastest_ms:.3f} ms)"
    )