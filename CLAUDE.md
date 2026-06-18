# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

ComicFuz-Down-Plus downloads manga, books, and magazines from Comic Fuz
(comic-fuz.com). It calls the site's Protocol Buffers API, decrypts the
AES-256-CBC encrypted page images, and writes JPEGs — optionally bundling them
into PDFs and re-compressing them.

## Architecture

The code is a package, `fuzdown/`, driven by a thin `fuz_down.py` entry point
(`fuzdown.cli:main`).

```
fuzdown/
  cli.py            # argparse + command dispatch (manga / book / magazine)
  api_client.py     # FuzAPIClient: auth, session, viewer endpoints, page scraping
  downloader.py     # ContentDownloader: download chapter/book/magazine/series
  models.py         # Chapter, Volume, Series, BookIssue, MagazineIssue (dataclasses)
  pdf_generator.py  # PDFGenerator: images → PDF at chapter/volume/series level
  image_optimizer.py# ImageOptimizer: JPEG/PNG re-compression, WebP conversion
  utils.py          # b64_to_10, decrypt_image, extract_volume_number, cache paths
  proto/            # fuz.proto, build_proto.py, generated fuz_pb2.py
fuz_down.py         # entry point
```

`fuzdown.cli:main` is also exposed as the `fuz-down` console script (pyproject).

## Key behaviors

- **ID auto-detection** (`ContentDownloader.try_download_chapter_or_series`):
  `-m <id>` is tried as a chapter ID first; on failure it is treated as a series
  ID and the manga page is scraped (`FuzAPIClient.get_chapters_from_manga` parses
  `__NEXT_DATA__`) to download every chapter into `ch_<id>_<title>/` subdirs.
- **Image pipeline**: download `.enc` from `img.comic-fuz.com` → decrypt with the
  per-image key/IV from the API response (`utils.decrypt_image`) → save JPEG.
  Filenames come from `b64_to_10` decoding Comic Fuz's base64 variant.
- **Threading**: `ContentDownloader` runs a single worker draining a bounded
  `Queue(n_jobs)`; each queued item is a started `Thread` that the worker joins,
  which caps concurrent downloads. `_download_pages` dispatches and waits.
- **Metadata**: every download writes `index.protobuf` and `index.json`.
- **Auth** (`FuzAPIClient.get_session`): guest (no token), credential login
  (extracts `fuz_session_key` from the sign-in cookie), or a cached token file
  validated against `/v1/web_mypage`. Default cache: `~/.cache/comicfuz-down/`.

## Protobuf

`fuz_pb2.py` is generated and gitignored. `fuzdown/__init__` calls
`ensure_proto_built()` on import, which runs `protoc` only when `fuz_pb2.py` is
missing or older than `fuz.proto`. `protoc` must be installed. Never hand-edit
`fuz_pb2.py`; edit `fuzdown/proto/fuz.proto` instead.

## Commands

```bash
uv sync                              # or: pip install -r requirements.txt
python fuz_down.py -m 183            # whole series
python fuz_down.py -m 68516          # single chapter
python fuz_down.py -b 25120          # book
python fuz_down.py -z 25812          # magazine
python -m fuzdown.proto.build_proto  # rebuild fuz_pb2.py manually
```

See README.md for the full flag list.

## API endpoints

`api.comic-fuz.com`: `/v1/sign_in`, `/v1/web_mypage`, `/v1/manga_viewer`,
`/v1/book_viewer_2`, `/v1/magazine_viewer_2`. Images: `img.comic-fuz.com`.

## Scope note

Only the protobuf + AES path exists. There is no image descrambling and no
JSON/scramble "new API" support in this codebase — ignore any older notes that
describe them.
