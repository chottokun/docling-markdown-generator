import asyncio
import time
from pathlib import Path
import os

# Mock content (1MB)
CONTENT = b"0" * (1024 * 1024)
NUM_FILES = 100
OUT_DIR = Path("tests/benchmark_data")

def setup():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

def cleanup():
    if OUT_DIR.exists():
        for f in OUT_DIR.glob("*"):
            try:
                f.unlink()
            except:
                pass
        try:
            OUT_DIR.rmdir()
        except:
            pass

async def sync_write(filename, content):
    out_path = OUT_DIR / filename
    # Simulate network latency
    await asyncio.sleep(0.01)
    with open(out_path, 'wb') as f:
        f.write(content)

async def async_write(filename, content):
    out_path = OUT_DIR / filename
    # Simulate network latency
    await asyncio.sleep(0.01)
    await asyncio.to_thread(out_path.write_bytes, content)

async def run_test(func, name):
    setup()
    start = time.perf_counter()
    tasks = [func(f"file_{i}.bin", CONTENT) for i in range(NUM_FILES)]
    await asyncio.gather(*tasks)
    duration = time.perf_counter() - start
    print(f"{name}: {duration:.4f}s")
    cleanup()
    return duration

async def main():
    print(f"Running benchmark with {NUM_FILES} files of {len(CONTENT)/1024/1024}MB each...")
    # Warm up
    await run_test(sync_write, "Warmup")

    d1 = await run_test(sync_write, "Sync I/O (Baseline)")
    d2 = await run_test(async_write, "Async I/O (to_thread)")

    print(f"Improvement: {(d1 - d2) / d1 * 100:.2f}%")

if __name__ == "__main__":
    asyncio.run(main())
