import time
import shutil
from pathlib import Path
import os

OUT_DIR = Path("tests/benchmark_cleanup_data")
NUM_FILES = 2000

def setup():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(NUM_FILES):
        (OUT_DIR / f"file_{i}.bin").write_bytes(b"0")

def cleanup_old():
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

def cleanup_new():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

def measure(func, name):
    setup()
    start = time.perf_counter()
    func()
    end = time.perf_counter()
    # print(f"{name}: {end - start:.6f}s")
    return end - start

if __name__ == "__main__":
    print(f"Benchmarking cleanup with {NUM_FILES} files...")
    # Warmup
    measure(cleanup_old, "Warmup Old")
    measure(cleanup_new, "Warmup New")

    t1 = sum(measure(cleanup_old, f"Old {i}") for i in range(10)) / 10
    t2 = sum(measure(cleanup_new, f"New {i}") for i in range(10)) / 10

    print(f"Average Old: {t1:.6f}s")
    print(f"Average New: {t2:.6f}s")
    if t1 > 0:
        print(f"Improvement: {(t1 - t2) / t1 * 100:.2f}%")
    else:
        print("Baseline too fast to measure improvement.")
