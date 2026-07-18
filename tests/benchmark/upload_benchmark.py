import asyncio
import shutil
import tempfile
import time
from pathlib import Path

from starlette.concurrency import run_in_threadpool

# Simulate a large file
CHUNK_SIZE = 1024 * 1024  # 1MB
FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_UPLOAD_SIZE = 100 * 1024 * 1024
CONCURRENT_REQUESTS = 10


class MockFile:
    def __init__(self, size):
        self.size = size
        self.read_pos = 0
        self.data = b"0" * size

    def read(self, size=-1):
        if self.read_pos >= self.size:
            return b""
        if size == -1:
            chunk = self.data[self.read_pos :]
            self.read_pos = self.size
            return chunk
        end = min(self.read_pos + size, self.size)
        chunk = self.data[self.read_pos : end]
        self.read_pos = end
        # Simulate some I/O wait
        time.sleep(0.01)
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


async def current_impl(file: MockUploadFile, upload_dir: Path):
    total_size = 0
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=upload_dir)
    tmp_path = Path(tmp_file.name)

    def _write_file():
        nonlocal total_size
        try:
            while True:
                chunk = file.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_SIZE:
                    raise Exception("Too large")
                tmp_file.write(chunk)
        finally:
            tmp_file.close()

    try:
        await run_in_threadpool(_write_file)
        return tmp_path
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


async def proposed_impl(file: MockUploadFile, upload_dir: Path):
    total_size = 0
    tmp_file = await run_in_threadpool(
        tempfile.NamedTemporaryFile, delete=False, suffix=".pdf", dir=upload_dir
    )
    tmp_path = Path(tmp_file.name)

    try:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE:
                raise Exception("Too large")

            def _write_chunk(c):
                tmp_file.write(c)

            await run_in_threadpool(_write_chunk, chunk)
    finally:
        await run_in_threadpool(tmp_file.close)
    return tmp_path


async def run_benchmark():
    upload_dir = Path("tests/benchmark_uploads")
    upload_dir.mkdir(exist_ok=True)

    print(
        f"Benchmarking with {CONCURRENT_REQUESTS} concurrent requests of {FILE_SIZE / 1024 / 1024}MB file..."
    )

    # Current Impl
    start = time.perf_counter()
    tasks = []
    for _ in range(CONCURRENT_REQUESTS):
        mock_file = MockFile(FILE_SIZE)
        mock_upload = MockUploadFile(mock_file)
        tasks.append(current_impl(mock_upload, upload_dir))
    paths = await asyncio.gather(*tasks)
    duration_current = time.perf_counter() - start
    print(f"Current implementation: {duration_current:.4f}s")
    for path in paths:
        if path.exists():
            path.unlink()

    # Proposed Impl
    start = time.perf_counter()
    tasks = []
    for _ in range(CONCURRENT_REQUESTS):
        mock_file = MockFile(FILE_SIZE)
        mock_upload = MockUploadFile(mock_file)
        tasks.append(proposed_impl(mock_upload, upload_dir))
    paths = await asyncio.gather(*tasks)
    duration_proposed = time.perf_counter() - start
    print(f"Proposed implementation: {duration_proposed:.4f}s")
    for path in paths:
        if path.exists():
            path.unlink()

    improvement = (duration_current - duration_proposed) / duration_current * 100
    print(f"Improvement: {improvement:.2f}%")

    # Cleanup
    shutil.rmtree(upload_dir)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
