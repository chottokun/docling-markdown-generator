import asyncio
import time

import docling_lib.server
from docling_lib.server import cleanup_expired_rate_limits


async def run_benchmark():
    print("--- Rate Limiter Cleanup Benchmark ---")

    # 1. Simulate a large number of client IPs
    NUM_IPS = 10000
    print(f"Populating {NUM_IPS} client IPs in rate limit storage...")

    docling_lib.server._rate_limit_data.clear()
    now = time.time()
    for i in range(NUM_IPS):
        ip = f"192.168.{i // 256}.{i % 256}"
        # Some are expired, some are active
        if i % 2 == 0:
            docling_lib.server._rate_limit_data[ip].append(now - 1000.0) # expired
        else:
            docling_lib.server._rate_limit_data[ip].append(now - 10.0) # active

    # Measure the non-blocking nature of the async cleanup
    print("\nExecuting asynchronous rate limit cleanup...")
    start_time = time.perf_counter()

    # Create the cleanup task
    task = asyncio.create_task(cleanup_expired_rate_limits(now))

    # Measure how long it takes for control to return to the caller (non-blocking test)
    control_return_time = time.perf_counter() - start_time
    print(f"Time for control to return to caller (async task scheduled): {control_return_time * 1000:.6f} ms")

    # While the task is running in the background, we simulate ongoing event loop activity (other requests)
    event_loop_delays = []
    for _ in range(20):
        t0 = time.perf_counter()
        await asyncio.sleep(0.001)
        event_loop_delays.append(time.perf_counter() - t0)

    await task
    total_cleanup_time = time.perf_counter() - start_time
    print(f"Total time to complete full background cleanup: {total_cleanup_time * 1000:.6f} ms")

    avg_loop_delay = sum(event_loop_delays) / len(event_loop_delays)
    print(f"Average event loop delay/latency during cleanup: {avg_loop_delay * 1000:.6f} ms")

    # Assertions / verification of correctness
    # Half of the IPs (expired ones) should be cleaned up
    remaining_ips = len(docling_lib.server._rate_limit_data)
    print(f"IPs remaining after cleanup: {remaining_ips} (expected ~5000)")

    # Let's compare with a simulated synchronous version of the same cleanup
    # (i.e. if we ran the iteration fully synchronously in a single request context)
    print("\nSimulating old synchronous cleanup (blocking)...")
    docling_lib.server._rate_limit_data.clear()
    for i in range(NUM_IPS):
        ip = f"192.168.{i // 256}.{i % 256}"
        if i % 2 == 0:
            docling_lib.server._rate_limit_data[ip].append(now - 1000.0)
        else:
            docling_lib.server._rate_limit_data[ip].append(now - 10.0)

    sync_start = time.perf_counter()
    # The old synchronous implementation
    for ip in list(docling_lib.server._rate_limit_data.keys()):
        dq = docling_lib.server._rate_limit_data[ip]
        while dq and now - dq[0] >= 60.0: # RATE_LIMIT_WINDOW (default 60)
            dq.popleft()
        if not dq:
            docling_lib.server._rate_limit_data.pop(ip, None)

    sync_duration = time.perf_counter() - sync_start
    print(f"Synchronous cleanup blocking duration: {sync_duration * 1000:.6f} ms")

    improvement_pct = ((sync_duration - control_return_time) / sync_duration) * 100
    print(f"\nImmediate Request Latency Improvement: {improvement_pct:.2f}% (Response time reduced from {sync_duration * 1000:.4f} ms to {control_return_time * 1000:.4f} ms)")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
