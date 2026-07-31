import re
import time

# Regex pattern matching the page break format
PAGE_BREAK_RE = re.compile(r"#_#_DOCLING_DOC_PAGE_BREAK_\d+_(\d+)_#_#")


def _get_page_breaks_emulated(text: str):
    pattern = r"#_#_DOCLING_DOC_PAGE_BREAK_(\d+)_(\d+)_#_#"
    matches = re.finditer(pattern, text)
    for match in matches:
        full_match = match.group(0)
        prev_page_nr = int(match.group(1))
        next_page_nr = int(match.group(2))
        yield (full_match, prev_page_nr, next_page_nr)


def baseline_replace(text_res: str) -> str:
    # Mimic the current looping string replacement
    for full_match, _prev_page_nr, next_page_nr in _get_page_breaks_emulated(
        text=text_res
    ):
        text_res = text_res.replace(
            full_match, f"<!-- PAGE_BREAK: Page {next_page_nr} -->"
        )
    return text_res


def optimized_replace(text_res: str) -> str:
    # Mimic the optimized re.sub approach
    return PAGE_BREAK_RE.sub(r"<!-- PAGE_BREAK: Page \1 -->", text_res)


def main():
    print("--- PAGE BREAK REPLACEMENT BENCHMARK ---")

    # Generate test document with 5000 page breaks
    num_pages = 5000
    parts = []
    for i in range(1, num_pages + 1):
        parts.append(
            f"This is the content of page {i} containing some sample text to simulate document size."
        )
        if i < num_pages:
            parts.append(f"#_#_DOCLING_DOC_PAGE_BREAK_{i}_{i + 1}_#_#")

    test_text = "\n".join(parts)
    print(f"Test document generated: {len(test_text)} characters, {num_pages} pages.")

    # Warmup
    _ = baseline_replace(test_text)
    _ = optimized_replace(test_text)

    # Baseline timing
    start = time.perf_counter()
    res_baseline = baseline_replace(test_text)
    t_baseline = time.perf_counter() - start
    print(f"Baseline (loop replace): {t_baseline:.6f}s")

    # Optimized timing
    start = time.perf_counter()
    res_optimized = optimized_replace(test_text)
    t_optimized = time.perf_counter() - start
    print(f"Optimized (regex sub):  {t_optimized:.6f}s")

    # Assert correctness
    assert res_baseline == res_optimized, (
        "Mismatch between baseline and optimized results!"
    )
    print("Correctness check: PASSED (results are identical)")

    speedup = t_baseline / t_optimized
    improvement = (t_baseline - t_optimized) / t_baseline * 100
    print(f"Speedup: {speedup:.2f}x")
    print(f"Improvement: {improvement:.2f}%")


if __name__ == "__main__":
    main()
