import os
import urllib.request
import urllib.error

# Ensure output directory exists
out_dir = "tests/data/real_world"
os.makedirs(out_dir, exist_ok=True)

# List of varied PDF and Office samples
# Includes complex Excel structures, PowerPoint presentations, Word documents, etc.
SampleUrls = {
    "sample1_simple.pdf": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
    "sample2_tables.pdf": "https://file-examples.com/wp-content/storage/2017/10/file-sample_150kB.pdf", 
    "sample3_arxiv.pdf": "https://arxiv.org/pdf/2401.00001.pdf", 
    "sample4_form.pdf": "https://www.irs.gov/pub/irs-pdf/fw4.pdf", 
    "sample5_brochure.pdf": "https://www.orimi.com/pdf-test.pdf", 
    "sample6_large.pdf": "https://www.w3.org/TR/pdf-ua1/W3C-PDF-UA-1.pdf",
    "sample7_financial.xlsx": "https://go.microsoft.com/fwlink/?LinkID=521962", # Complex Financial Sample Excel
    "sample8_word.docx": "https://filesamples.com/samples/document/docx/sample3.docx", # Word document
    "sample9_presentation.pptx": "https://filesamples.com/samples/document/pptx/sample1.pptx" # PowerPoint
}

for filename, url in SampleUrls.items():
    out_path = os.path.join(out_dir, filename)
    if os.path.exists(out_path):
        print(f"Already exists: {filename}")
        continue
    print(f"Downloading {filename} from {url}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            with open(out_path, 'wb') as f:
                f.write(response.read())
        print(f"Successfully downloaded {filename}")
    except urllib.error.URLError as e:
        print(f"Failed to download {filename}: {e}")
