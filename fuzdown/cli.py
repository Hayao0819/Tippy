"""Command-line interface for ComicFuz Downloader Plus."""

import argparse
import logging
from pathlib import Path

from . import FuzAPIClient, ContentDownloader, PDFGenerator, ImageOptimizer
from .models import Volume
from .utils import get_default_token_path

DEFAULT_OUTPUT_BASE = Path("./out")


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download manga, books, and magazines from Comic Fuz"
    )

    auth = parser.add_argument_group('Authentication')
    auth.add_argument('-t', '--token-file', metavar='<path>', default=None,
                      help="Token file path (default: ~/.cache/comicfuz-down/token.txt)")
    auth.add_argument('-u', '--user-email', metavar='<email>',
                      help="Login email; without it and no saved token, accesses free content only")
    auth.add_argument('-p', '--password', metavar='<password>', nargs='?',
                      help="Password; prompted for if -u is given without one")

    content = parser.add_argument_group('Content Selection')
    content.add_argument('-m', '--manga', metavar='<id>', type=int,
                         help="Manga ID or chapter ID (auto-detected)")
    content.add_argument('-b', '--book', metavar='<id>', type=int, help="Book ID")
    content.add_argument('-z', '--magazine', metavar='<id>', type=int, help="Magazine ID")

    output = parser.add_argument_group('Output Options')
    output.add_argument('-o', '--output-dir', metavar='<path>', default=None,
                        help="Output directory (default: ./out/{title}/, or ./out/{id}/ if no title). "
                             "Supports {id}, {title}, {manga_id}, {chapter_id}, {bookIssueId}, {magazineIssueId}")
    output.add_argument('-f', '--file-format', default="02",
                        help="Filename zero-padding (default: 02 → 00, 01, ...)")

    pdf = parser.add_argument_group('PDF Generation')
    pdf.add_argument('--pdf', action="store_true", help="Build a PDF from the downloaded images")
    pdf.add_argument('--pdf-level', choices=['chapter', 'volume', 'series'], default='chapter',
                     help="One PDF per chapter, per volume, or for the whole series (default: chapter)")

    compress = parser.add_argument_group('Image Compression')
    compress.add_argument('--compress-images', action="store_true", help="Re-compress images after download")
    compress.add_argument('--jpeg-quality', type=int, metavar='<1-100>', default=85,
                          help="JPEG quality (default: 85; lower = smaller)")
    compress.add_argument('--optimize-png', action="store_true", help="Re-compress PNGs at maximum level")
    compress.add_argument('--convert-to-webp', action="store_true", help="Convert images to WebP (replaces originals)")
    compress.add_argument('--webp-quality', type=int, metavar='<1-100>', default=85,
                          help="WebP quality when converting (default: 85)")

    parser.add_argument('-j', '--n-jobs', metavar='<n>', type=int, default=16,
                        help="Parallel download threads (default: 16)")
    parser.add_argument('-v', '--verbose', action="store_true", help="Print debug output")
    return parser


def _compress(images_dir: Path, args):
    if not images_dir:
        return
    ImageOptimizer.optimize_directory(
        images_dir,
        jpeg_quality=None if args.convert_to_webp else args.jpeg_quality,
        optimize_png=args.optimize_png and not args.convert_to_webp,
        convert_to_webp=args.convert_to_webp,
        webp_quality=args.webp_quality,
    )


def _resolve_output_dir(template, default_id, **fields) -> Path:
    if template is None:
        return DEFAULT_OUTPUT_BASE / str(default_id)
    return Path(template.format(id=default_id, **fields))


def _handle_manga(downloader, api_client, args):
    if args.output_dir is None:
        try:
            _, title = api_client.get_chapters_from_manga(args.manga)
        except Exception:
            title = None
        output_dir = DEFAULT_OUTPUT_BASE / str(title or args.manga)
    else:
        output_dir = Path(args.output_dir.format(id=args.manga, manga_id=args.manga, title="manga"))

    chapter, series = downloader.try_download_chapter_or_series(args.manga, output_dir, args.file_format)

    if args.compress_images:
        if chapter:
            _compress(chapter.images_dir, args)
        elif series:
            logging.info("\nCompressing images...")
            for ch in series.all_chapters:
                _compress(ch.images_dir, args)

    if not args.pdf:
        return

    if chapter:
        if args.pdf_level == 'chapter':
            PDFGenerator.create_chapter_pdf(chapter)
        else:
            logging.warning(f"PDF level '{args.pdf_level}' does not apply to a single chapter")
        return

    if not series:
        return

    if args.pdf_level == 'chapter':
        logging.info("\nGenerating per-chapter PDFs...")
        for ch in series.all_chapters:
            PDFGenerator.create_chapter_pdf(ch)
    elif args.pdf_level == 'volume':
        logging.info("\nGenerating per-volume PDFs...")
        if series.volumes:
            for volume in series.volumes:
                PDFGenerator.create_volume_pdf(volume, output_dir)
        else:
            volume = Volume(volume_number=1, chapters=series.standalone_chapters)
            PDFGenerator.create_volume_pdf(volume, output_dir, f"{series.safe_name}_All.pdf")
    elif args.pdf_level == 'series':
        logging.info("\nGenerating series PDF...")
        PDFGenerator.create_series_pdf(series, output_dir)


def _handle_issue(content, args, label):
    if not args.pdf or not content or not content.images_dir:
        return
    logging.info(f"\nGenerating PDF for {label}...")
    images = PDFGenerator._get_images_from_directory(content.images_dir)
    if images:
        PDFGenerator._create_pdf_from_images(images, content.images_dir / f"{content.safe_name}.pdf")


def main():
    args = get_parser().parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
    logging.info("= ComicFuz Downloader Plus =")

    api_client = FuzAPIClient()

    token_file = args.token_file
    if token_file is None and args.user_email:
        token_file = str(get_default_token_path())

    if args.manga or args.book or args.magazine:
        api_client.get_session(
            token_file=token_file if (token_file or args.user_email) else "",
            user_email=args.user_email or "",
            password=args.password or "",
        )

    downloader = ContentDownloader(api_client, n_jobs=args.n_jobs)

    if args.manga:
        _handle_manga(downloader, api_client, args)
    elif args.book:
        output_dir = _resolve_output_dir(args.output_dir, args.book, book_id=args.book, bookIssueId=args.book, title="book")
        book = downloader.download_book(args.book, output_dir, args.file_format)
        if args.compress_images and book:
            _compress(book.images_dir, args)
        _handle_issue(book, args, "book")
    elif args.magazine:
        output_dir = _resolve_output_dir(args.output_dir, args.magazine, magazine_id=args.magazine, magazineIssueId=args.magazine, title="magazine")
        magazine = downloader.download_magazine(args.magazine, output_dir, args.file_format)
        if args.compress_images and magazine:
            _compress(magazine.images_dir, args)
        _handle_issue(magazine, args, "magazine")

    logging.info("\nDone.")


if __name__ == "__main__":
    main()
