import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock
from docling_core.types.doc import DoclingDocument
from fastapi import Request

from docling_lib.converter import is_cuda_compatible, PDFConverter, DocumentConversionOptions
from docling_lib.server import rate_limiter, _rate_limit_data


# 1. Benchmark for is_cuda_compatible
def benchmark_cuda_compatibility(iterations=1000):
    print("\n[1] Benchmarking CUDA Compatibility Verification...")
    start_time = time.perf_counter()
    for _ in range(iterations):
        _ = is_cuda_compatible()
    duration = time.perf_counter() - start_time
    print(f"CUDA verification for {iterations} calls: {duration:.6f} seconds")
    return duration


# 2. Benchmark for _save_images single-image threadpool overhead
def benchmark_save_images_overhead(iterations=100):
    print("\n[2] Benchmarking Save Images Threadpool Overhead (Single Image)...")
    converter = PDFConverter(options=DocumentConversionOptions())

    # Create mock document with exactly 1 picture
    mock_doc = MagicMock(spec=DoclingDocument)
    mock_picture = MagicMock()
    mock_picture.image.pil_image.save = lambda path: None
    mock_doc.pictures = [mock_picture]

    images_dir = Path("tests/benchmark_save_images_data")
    images_dir.mkdir(exist_ok=True)

    start_time = time.perf_counter()
    for _ in range(iterations):
        converter._save_images(mock_doc, images_dir)
    duration = time.perf_counter() - start_time
    print(f"Saving single image {iterations} times: {duration:.6f} seconds")

    if images_dir.exists():
        import shutil
        shutil.rmtree(images_dir, ignore_errors=True)

    return duration


# 3. Benchmark/simulation of rate limiter memory leak/growth
async def benchmark_rate_limiter_memory_growth(num_clients=5000):
    print("\n[3] Benchmarking Rate Limiter Memory Growth...")
    _rate_limit_data.clear()

    # We simulate a series of requests from unique client IPs
    print(f"Processing requests from {num_clients} unique IP addresses...")

    # Simulate FastAPI Request
    def create_mock_request(ip):
        mock_req = MagicMock(spec=Request)
        mock_req.client.host = ip
        mock_req.headers = {}
        return mock_req

    start_time = time.perf_counter()
    for i in range(num_clients):
        req = create_mock_request(f"192.168.1.{i}")
        await rate_limiter(req)

    duration = time.perf_counter() - start_time
    print(f"Rate limiting processing for {num_clients} requests: {duration:.6f} seconds")
    print(f"Number of client records currently in memory: {len(_rate_limit_data)}")

    return duration, len(_rate_limit_data)


async def main():
    print("=================== REFACTORING PERFORMANCE BENCHMARK ===================")
    benchmark_cuda_compatibility(iterations=50)
    benchmark_save_images_overhead(iterations=100)
    await benchmark_rate_limiter_memory_growth(num_clients=2000)
    print("=========================================================================")


if __name__ == "__main__":
    asyncio.run(main())
