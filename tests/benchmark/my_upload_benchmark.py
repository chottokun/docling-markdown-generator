import asyncio
import time
import tempfile
import os
from pathlib import Path
from starlette.concurrency import run_in_threadpool
import shutil

# Mocking parts of the server
MAX_UPLOAD_SIZE = 200 * 1024 * 1024
CHUNK_SIZE = 64 * 1024 # 64KB to exaggerate overhead

class MockFile:
    def __init__(self, size):
        self.size = size
        self.read_pos = 0
        self.data = b"0" * size

    def read(self, size=-1):
        if self.read_pos >= self.size:
            return b""
        if size == -1:
            chunk = self.data[self.read_pos:]
            self.read_pos = self.size
            return chunk
        end = min(self.read_pos + size, self.size)
        chunk = self.data[self.read_pos:end]
        self.read_pos = end
        return chunk

    def close(self):
        pass

class MockUploadFile:
    def __init__(self, file):
        self.file = file
        self.filename = "test.pdf"

    async def read(self, size: int = -1) -> bytes:
        return await run_in_threadpool(self.file.read, size)

    async def close(self):
        await run_in_threadpool(self.file.close)

# Current implementation in server.py (with smaller chunks for test)
async def current_impl(file: MockUploadFile, tmp_file, MAX_UPLOAD_SIZE):
    total_size = 0
    try:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE:
                raise Exception("Payload Too Large")
            await run_in_threadpool(tmp_file.write, chunk)
    finally:
        await run_in_threadpool(tmp_file.close)

# Optimization: Single blocking call
async def opt_single_blocking(file: MockUploadFile, tmp_file, MAX_UPLOAD_SIZE):
    def _save():
        total_size = 0
        while True:
            # Read directly from the underlying file (blocking)
            chunk = file.file.read(CHUNK_SIZE)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE:
                raise Exception("Payload Too Large")
            tmp_file.write(chunk)
        tmp_file.close()

    await run_in_threadpool(_save)

async def run_benchmark(file_size_mb, concurrent_reqs):
    file_size = file_size_mb * 1024 * 1024
    upload_dir = Path("benchmark_temp")
    upload_dir.mkdir(exist_ok=True)

    print(f"--- Benchmarking {file_size_mb}MB file, {concurrent_reqs} concurrent requests, CHUNK={CHUNK_SIZE/1024}KB ---")

    # Baseline
    start = time.perf_counter()
    tasks = []
    for _ in range(concurrent_reqs):
        mock_file = MockFile(file_size)
        mock_upload = MockUploadFile(mock_file)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, dir=upload_dir)
        tasks.append(current_impl(mock_upload, tmp_file, MAX_UPLOAD_SIZE))
    await asyncio.gather(*tasks)
    duration_current = time.perf_counter() - start
    print(f"Current impl: {duration_current:.4f}s")

    # Single blocking call
    start = time.perf_counter()
    tasks = []
    for _ in range(concurrent_reqs):
        mock_file = MockFile(file_size)
        mock_upload = MockUploadFile(mock_file)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, dir=upload_dir)
        tasks.append(opt_single_blocking(mock_upload, tmp_file, MAX_UPLOAD_SIZE))
    await asyncio.gather(*tasks)
    duration_opt = time.perf_counter() - start
    print(f"Single blocking call: {duration_opt:.4f}s")

    improvement = (duration_current - duration_opt) / duration_current * 100
    print(f"Improvement: {improvement:.2f}%")

    shutil.rmtree(upload_dir)

if __name__ == "__main__":
    asyncio.run(run_benchmark(50, 5))
