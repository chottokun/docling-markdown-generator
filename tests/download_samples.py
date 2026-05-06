import os
import asyncio
import httpx

# Ensure output directory exists
out_dir = "tests/data/real_world"
os.makedirs(out_dir, exist_ok=True)

# List of varied PDF and Office samples
# Includes complex Excel structures, PowerPoint presentations, Word documents, etc.
SampleUrls = {
    "sample1_simple.pdf": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
    "sample3_arxiv.pdf": "https://arxiv.org/pdf/2401.00001.pdf", 
    "sample4_form.pdf": "https://www.irs.gov/pub/irs-pdf/fw4.pdf", 
    "sample5_brochure.pdf": "https://www.orimi.com/pdf-test.pdf", 
    "sample7_financial.xlsx": "https://go.microsoft.com/fwlink/?LinkID=521962",
    "sample8_word.docx": "https://filesamples.com/samples/document/docx/sample3.docx",
    "sample10_jp_gov.pdf": "https://www.mext.go.jp/content/20200710-mxt_kouhou01-000008479_1.pdf" # Japanese government document
}

async def download_file(client, filename, url):
    out_path = os.path.join(out_dir, filename)
    if await asyncio.to_thread(os.path.exists, out_path):
        print(f"Already exists: {filename}")
        return

    print(f"Downloading {filename} from {url}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = await client.get(url, headers=headers, follow_redirects=True)
        response.raise_for_status()

        # Use asyncio.to_thread to perform blocking I/O without blocking the event loop
        def _save_to_disk():
            with open(out_path, "wb") as f:
                f.write(response.content)

        await asyncio.to_thread(_save_to_disk)

        print(f"Successfully downloaded {filename}")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")

async def download_all():
    async with httpx.AsyncClient() as client:
        tasks = [download_file(client, filename, url) for filename, url in SampleUrls.items()]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(download_all())
