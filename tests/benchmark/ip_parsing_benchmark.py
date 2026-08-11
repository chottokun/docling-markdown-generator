import time
import docling_lib.server as server
from docling_lib.server import _is_trusted_proxy, _parse_trusted_proxies

def run_benchmark():
    # Keep original list for baseline
    original_proxies = ["10.0.0.0/24", "192.168.1.1", "127.0.0.1"]

    # Configure server TRUSTED_PROXIES as a list
    server.TRUSTED_PROXIES = original_proxies
    _parse_trusted_proxies.cache_clear()

    # Warm up
    _is_trusted_proxy("192.168.1.1")

    iterations = 500000
    print(f"Running benchmark with {iterations} iterations...")

    # 1. Baseline with list (requires conversion every time)
    start = time.perf_counter()
    for _ in range(iterations):
        _is_trusted_proxy("192.168.1.1")
    t_baseline = time.perf_counter() - start
    print(f"Baseline (with tuple conversion): {t_baseline:.6f}s")

    # Configure server TRUSTED_PROXIES as a tuple
    server.TRUSTED_PROXIES = tuple(original_proxies)
    _parse_trusted_proxies.cache_clear()

    # Warm up
    _is_trusted_proxy("192.168.1.1")

    # 2. Optimized with tuple (no conversion needed if optimized)
    start = time.perf_counter()
    for _ in range(iterations):
        _is_trusted_proxy("192.168.1.1")
    t_optimized = time.perf_counter() - start
    print(f"Optimized (without tuple conversion): {t_optimized:.6f}s")

    improvement = (t_baseline - t_optimized) / t_baseline * 100
    print(f"Improvement: {improvement:.2f}%")

if __name__ == "__main__":
    run_benchmark()
