import asyncio
import tempfile
import time
from pathlib import Path

from starlette.concurrency import run_in_threadpool


async def baseline(file_path, iterations):
    start = time.perf_counter()
    for _ in range(iterations):
        if not await run_in_threadpool(file_path.exists) or not await run_in_threadpool(
            file_path.is_file
        ):
            pass
    return time.perf_counter() - start


def _is_valid_file(path: Path) -> bool:
    return path.exists() and path.is_file()


async def optimized(file_path, iterations):
    start = time.perf_counter()
    for _ in range(iterations):
        if not await run_in_threadpool(_is_valid_file, file_path):
            pass
    return time.perf_counter() - start


async def main():
    with tempfile.NamedTemporaryFile() as tmp:
        file_path = Path(tmp.name)
        iterations = 1000

        print(f"Running benchmark with {iterations} iterations...")

        # Warmup
        await baseline(file_path, 100)
        await optimized(file_path, 100)

        t1 = await baseline(file_path, iterations)
        print(f"Baseline (2 calls): {t1:.4f}s")

        t2 = await optimized(file_path, iterations)
        print(f"Optimized (1 call): {t2:.4f}s")

        improvement = (t1 - t2) / t1 * 100
        print(f"Improvement: {improvement:.2f}%")


if __name__ == "__main__":
    asyncio.run(main())
