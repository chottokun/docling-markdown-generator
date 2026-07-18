import sys
from types import ModuleType


def mock_docling():
    """
    doclingがインストールされていない環境向けのスタブを注入する。
    実際のdoclingがインストール済みの場合は何もしない。
    """
    # 実際のdoclingがインポート可能かチェック
    try:
        import importlib.util

        spec = importlib.util.find_spec("docling")
        if spec is not None and spec.origin is not None:
            # 実際のdoclingがインストール済み → モック不要
            return
    except (ModuleNotFoundError, ValueError):
        pass

    # doclingが未インストールの場合のみスタブを注入
    if "docling" in sys.modules:
        return

    # Mock docling and other missing dependencies
    def create_mock_module(name):
        if name in sys.modules:
            return sys.modules[name]
        m = ModuleType(name)
        sys.modules[name] = m
        return m

    torch = create_mock_module("torch")
    torch.cuda = create_mock_module("torch.cuda")
    torch.cuda.is_available = lambda: False
    torch.cuda.synchronize = lambda: None
    torch.device = lambda x: x
    torch.zeros = lambda *args, **kwargs: None

    docling = create_mock_module("docling")
    docling_dm = create_mock_module("docling.datamodel")
    docling_base = create_mock_module("docling.datamodel.base_models")
    docling_base.InputFormat = type(
        "InputFormat",
        (),
        {
            "PDF": "pdf",
            "DOCX": "docx",
            "PPTX": "pptx",
            "XLSX": "xlsx",
            "HTML": "html",
            "IMAGE": "image",
            "MD": "md",
            "EMAIL": "email",
            "EPUB": "epub",
            "LATEX": "latex",
            "XML_XBRL": "xml_xbrl",
            "VTT": "vtt",
        },
    )
    docling_acc = create_mock_module("docling.datamodel.accelerator_options")
    docling_acc.AcceleratorDevice = type(
        "AcceleratorDevice", (), {"AUTO": "auto", "CPU": "cpu"}
    )
    docling_acc.AcceleratorOptions = type(
        "AcceleratorOptions", (), {"__init__": lambda self, *args, **kwargs: None}
    )

    docling_pipe = create_mock_module("docling.datamodel.pipeline_options")
    docling_pipe.PdfPipelineOptions = type("PdfPipelineOptions", (), {})
    docling_doc = create_mock_module("docling.datamodel.document")
    docling_doc.ConversionResult = type("ConversionResult", (), {})

    # フォーマットオプション用のダミークラスファクトリ
    def _fmt_opt(name):
        return type(name, (), {"__init__": lambda self, *args, **kwargs: None})

    docling_conv = create_mock_module("docling.document_converter")
    docling_conv.DocumentConverter = _fmt_opt("DocumentConverter")
    docling_conv.PdfFormatOption = _fmt_opt("PdfFormatOption")
    docling_conv.PowerpointFormatOption = _fmt_opt("PowerpointFormatOption")
    docling_conv.WordFormatOption = _fmt_opt("WordFormatOption")
    docling_conv.ExcelFormatOption = _fmt_opt("ExcelFormatOption")
    docling_conv.HTMLFormatOption = _fmt_opt("HTMLFormatOption")
    docling_conv.ImageFormatOption = _fmt_opt("ImageFormatOption")
    docling_conv.MarkdownFormatOption = _fmt_opt("MarkdownFormatOption")
    docling_conv.EmailFormatOption = _fmt_opt("EmailFormatOption")
    docling_conv.EpubFormatOption = _fmt_opt("EpubFormatOption")
    docling_conv.LatexFormatOption = _fmt_opt("LatexFormatOption")
    docling_conv.XBRLFormatOption = _fmt_opt("XBRLFormatOption")

    # docling_coreは実際にインストール済みのためモック不要
    # （モックするとtest_table_serialization.pyなど実際のdocling_coreを使うテストが壊れる）
