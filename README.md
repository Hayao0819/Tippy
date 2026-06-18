# ComicFuz-Down-Plus

Downloads manga, books, and magazines from Comic Fuz (comic-fuz.com): it calls the
site's Protobuf API, decrypts the page images, and saves them as JPEG.

## Install

```bash
uv sync          # or: pip install -r requirements.txt
```

`protoc` is required (`fuz_pb2.py` is generated on first run):
`sudo apt install protobuf-compiler` / `brew install protobuf`.

## Usage

```bash
python fuz_down.py -m 183        # whole series (by manga ID)
python fuz_down.py -m 68516      # single chapter
python fuz_down.py -b 25120      # book
python fuz_down.py -z 25812      # magazine
```

`-m` takes either a series or chapter ID and figures out which. IDs come from the
URL, e.g. `comic-fuz.com/manga/183` → `183`.

Downloads go to `./out/<title-or-id>/`; override with `-o`. Add `--pdf`
(`--pdf-level chapter|volume|series`) to build PDFs, or `--compress-images` to
shrink them. Paid content needs `-u <email> -p`. Run `python fuz_down.py -h` for
all flags.
