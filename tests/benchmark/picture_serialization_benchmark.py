import time
from unittest.mock import MagicMock, patch

from docling_core.transforms.serializer.markdown import SerializationResult
from docling_core.types.doc import DoclingDocument, PictureItem

from docling_lib.converter import CustomMarkdownPictureSerializer


class MockPicture:
    def __init__(self, self_ref):
        self.self_ref = self_ref
        self.image = None


# We can mock the original O(N) loop to compare
def original_find_idx(doc, item):
    idx = -1
    if hasattr(doc, "pictures") and doc.pictures:
        for i, pic in enumerate(doc.pictures):
            if pic.self_ref == item.self_ref:
                idx = i
                break
    return idx


def run_benchmark(num_pictures=2000):
    doc = MagicMock(spec=DoclingDocument)
    pictures = [MockPicture(f"#/pictures/{i}") for i in range(num_pictures)]
    doc.pictures = pictures

    # Setup the serializer
    serializer = CustomMarkdownPictureSerializer(vlm_enabled=False)

    # Pre-create all items and mocks to eliminate Pydantic and MagicMock overhead
    items = [PictureItem(self_ref=pic.self_ref) for pic in pictures]
    mock_doc_serializer = MagicMock()

    # Let's measure with our optimized version
    start = time.perf_counter()
    with patch(
        "docling_core.transforms.serializer.markdown.MarkdownPictureSerializer.serialize"
    ) as mock_super_serialize:
        mock_super_serialize.return_value = SerializationResult(
            text="![image](placeholder)", span_source=[]
        )
        for item in items:
            _ = serializer.serialize(
                item=item, doc_serializer=mock_doc_serializer, doc=doc
            )
    elapsed_opt = time.perf_counter() - start

    # Now let's measure with a simulated original O(N) loop
    start = time.perf_counter()
    with patch(
        "docling_core.transforms.serializer.markdown.MarkdownPictureSerializer.serialize"
    ) as mock_super_serialize:
        mock_super_serialize.return_value = SerializationResult(
            text="![image](placeholder)", span_source=[]
        )
        for item in items:
            # simulate what the old code did
            idx = original_find_idx(doc, item)
            _ = mock_super_serialize(
                item=item, doc_serializer=mock_doc_serializer, doc=doc
            )
    elapsed_orig = time.perf_counter() - start

    print(f"Number of pictures: {num_pictures}")
    print(f"Original O(N^2) total time: {elapsed_orig:.4f}s")
    print(f"Optimized O(N) total time:  {elapsed_opt:.4f}s")
    print(f"Speedup: {elapsed_orig / elapsed_opt:.2f}x")


if __name__ == "__main__":
    run_benchmark(1000)
    run_benchmark(3000)
    run_benchmark(5000)
