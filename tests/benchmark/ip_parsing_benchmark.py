import time
import ipaddress
from unittest.mock import patch
import docling_lib.server
from docling_lib.server import _is_trusted_proxy

# A custom implementation of the baseline is_trusted_proxy to compare against the optimized one in the server.
def _is_trusted_proxy_baseline(ip_str: str | None, trusted_proxies) -> bool:
    if not ip_str:
        return False

    ip_str = ip_str.strip()

    for proxy in trusted_proxies:
        if proxy == "*":
            return True
        if proxy == ip_str:
            return True

        try:
            net = ipaddress.ip_network(proxy, strict=False)
            ip = ipaddress.ip_address(ip_str)
            if ip in net:
                return True
        except ValueError:
            continue

    return False

def run_benchmark():
    trusted_proxies = ["127.0.0.1", "10.0.0.0/8", "2001:db8::/32", "testclient"]
    test_ips = [
        "127.0.0.1",       # Exact match
        "10.1.2.3",        # IPv4 CIDR match
        "192.168.1.1",     # No match (not in range)
        "2001:db8::1234",  # IPv6 CIDR match
        "testclient",      # Literal match
        "invalid_ip",      # Invalid IP
    ]

    iterations = 50000

    print(f"Running IP parsing benchmark with {iterations} iterations...")

    # 1. Benchmark baseline
    start = time.perf_counter()
    for _ in range(iterations):
        for ip in test_ips:
            _is_trusted_proxy_baseline(ip, trusted_proxies)
    baseline_time = time.perf_counter() - start
    print(f"Baseline Time: {baseline_time:.4f}s")

    # 2. Benchmark current _is_trusted_proxy (as-is before changes)
    # We patch TRUSTED_PROXIES in docling_lib.server for the test
    with patch("docling_lib.server.TRUSTED_PROXIES", trusted_proxies):
        start = time.perf_counter()
        for _ in range(iterations):
            for ip in test_ips:
                _is_trusted_proxy(ip)
        current_server_time = time.perf_counter() - start
    print(f"Current Server Time (before or after optimization): {current_server_time:.4f}s")

if __name__ == "__main__":
    run_benchmark()
