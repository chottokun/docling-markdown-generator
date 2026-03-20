# Docling Markdown Generator

Doclingを使ってドキュメントをMarkdownに変換し、図や表を適切に抽出します。

This project provides a Python library, command-line tool, and a containerized FastAPI server to convert PDF, Word (.docx), PowerPoint (.pptx), and Excel (.xlsx) files into structured Markdown documents. It leverages the latest `docling` (v2.x) library for high-accuracy document layout analysis and extraction.

## Documentation

For more detailed information, please refer to:

- **[Markdown Specification](docs/MARKDOWN_SPEC.md)**: Details on image, table, and document structure.
- **[API Reference](docs/API_REFERENCE.md)**: Full API endpoint details and examples.
- **[Unique Features](docs/FEATURES.md)**: Highlights of security, performance, and robustness improvements beyond standard Docling.
- **[Deployment Guide](docs/DEPLOYMENT.md)**: Environment variables, scaling, and operational advice.

## Features

- **Multi-Format Support**: Extracts text, tables, and figures from PDF, DOCX, PPTX, and XLSX files.
- **Native Conversion**: Powered by Docling v2, no external dependencies like LibreOffice are required for Office file conversion.
- **Advanced Layout Analysis**: Intelligent extraction of tables (Markdown format) and figures (with associated captions).
- **Performance Optimized**: Reuses conversion engines for faster processing of multiple documents.
- **Ready-to-use API**: Includes a FastAPI server for remote conversion requests.
- **Docker Integration**: Easy deployment with Docker and Docker Compose.

## Prerequisites

- Python 3.11 or later.
- [uv](https://github.com/astral-sh/uv) (Recommended for package management).
- Docker and Docker Compose (For server usage).

## Installation

This project uses `uv` for seamless dependency management.

1.  **Create and activate a virtual environment:**
    ```bash
    uv venv
    source .venv/bin/activate  # macOS/Linux
    # .venv\Scripts\activate  # Windows
    ```

2.  **Install the library:**
    ```bash
    uv pip install -e ".[test]"
    ```

## Usage

### Command Line Interface (CLI)

```bash
pdf2md_cli [INPUT_FILE] -o [OUTPUT_DIRECTORY]
```

**Arguments:**

- `INPUT_FILE`: The path to the input file (.pdf, .docx, .pptx, .xlsx).
- `-o, --output-dir`: The directory where the results will be saved. Defaults to `output/`.

**Example:**
```bash
pdf2md_cli sample.pptx -o results/
```

### Running with Docker

The containerized FastAPI server is the easiest way to deploy the conversion service.

1.  **Start the server:**
    ```bash
    docker-compose up --build
    ```
    The server will be available at `http://localhost:8000`.

2.  **API Usage:**
    Send a POST request to `/convert/` with the file.
    ```bash
    curl -X POST -F "file=@/path/to/document.pdf" http://localhost:8000/convert/
    ```
    The API returns a JSON response with a download link for the converted Markdown.

## Development & Testing

We follow a Test-Driven Development (TDD) approach.

- **Run all tests:**
  ```bash
  uv run pytest
  ```
- **Run with coverage:**
  ```bash
  uv run pytest --cov=src
  ```

## License

- **docling**: MIT License
- **docling-core**: MIT License
- **FastAPI**: MIT License

Please ensure compliance with the respective licenses.