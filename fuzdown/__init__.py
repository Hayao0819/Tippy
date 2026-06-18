"""ComicFuz Downloader Plus - a modular downloader for Comic Fuz."""

import sys

from .proto.build_proto import ensure_proto_built

if not ensure_proto_built():
    print("Failed to build protobuf files. Run: python -m fuzdown.proto.build_proto", file=sys.stderr)

from .models import Chapter, Volume, Series, BookIssue, MagazineIssue
from .api_client import FuzAPIClient
from .downloader import ContentDownloader
from .pdf_generator import PDFGenerator
from .image_optimizer import ImageOptimizer
from .utils import get_cache_dir, get_default_token_path

__version__ = "2.0.0"
__all__ = [
    "Chapter",
    "Volume",
    "Series",
    "BookIssue",
    "MagazineIssue",
    "FuzAPIClient",
    "ContentDownloader",
    "PDFGenerator",
    "ImageOptimizer",
    "get_cache_dir",
    "get_default_token_path",
]
