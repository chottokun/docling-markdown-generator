import time
from unittest.mock import MagicMock
from docling_lib.converter import EnhancedMarkdownSerializer

def run_benchmark(iterations=10000):
    mock_doc = MagicMock()

    # Warmup
    for _ in range(1000):
        _ = EnhancedMarkdownSerializer(doc=mock_doc, table_format="html")

    start = time.perf_counter()
    for _ in range(iterations):
        _ = EnhancedMarkdownSerializer(doc=mock_doc, table_format="html")
    elapsed = time.perf_counter() - start
    print(f"Time for {iterations} initializations: {elapsed:.4f}s")
    return elapsed

if __name__ == "__main__":
    run_benchmark()
