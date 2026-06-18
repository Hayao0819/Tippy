"""Content downloader for manga, books, and magazines."""

import re
import json
import logging
from pathlib import Path
from threading import Thread
from queue import Queue
from typing import Optional
from urllib.request import urlopen

from google.protobuf import json_format

from .proto import fuz_pb2
from .api_client import FuzAPIClient
from .models import Chapter, BookIssue, MagazineIssue, Volume, Series
from .utils import b64_to_10, decrypt_image, extract_volume_number


class ContentDownloader:
    """Download and decrypt manga content."""

    def __init__(self, api_client: FuzAPIClient, n_jobs: int = 16):
        self.api_client = api_client
        self.n_jobs = n_jobs
        self.queue: Optional[Queue] = None
        self.worker_thread: Optional[Thread] = None

    def _start_worker(self):
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.queue = Queue(self.n_jobs)
            self.worker_thread = Thread(target=self._worker, daemon=True)
            self.worker_thread.start()

    def _worker(self):
        """Bounded queue that joins each page-download thread, capping in-flight downloads."""
        while True:
            thread = self.queue.get()
            thread.join()
            self.queue.task_done()

    def _download_image_old_api(
        self,
        save_dir: Path,
        file_format: str,
        image: fuz_pb2.ViewerPage.Image,
        overwrite: bool = False
    ):
        """Download an AES-encrypted page and write the decrypted image."""
        if not image.imageUrl:
            logging.debug("Not an image: %s", image)
            return

        name_match = re.match(r'.*/([0-9a-zA-Z_-]+)\.(\w+)\.enc\?.*', image.imageUrl)
        if not name_match or not name_match.group(1):
            logging.debug("Can't parse filename: %s", image)
            return

        filename = f"{format(b64_to_10(name_match.group(1)), file_format)}.{name_match.group(2)}"
        filepath = save_dir / filename

        if not overwrite and filepath.exists():
            logging.debug("File exists, skipping: %s", filepath)
            return

        with urlopen(self.api_client.IMG_HOST + image.imageUrl) as r:
            encrypted_data = r.read()

        decrypted_data = decrypt_image(encrypted_data, image.encryptionKey, image.iv)
        with open(filepath, "wb") as f:
            f.write(decrypted_data)

        logging.debug("Downloaded: %s", filepath)

    def _download_thumbnail(self, save_dir: Path, url: str, overwrite: bool = False):
        """Download thumbnail image."""
        name_match = re.match(r'.*/([0-9a-zA-Z_-]+)\.(\w+)\?.*', url)
        if not name_match or not name_match.group(1):
            logging.warning("Can't parse thumbnail filename: %s", url)
            return

        filename = f"{b64_to_10(name_match.group(1))}.{name_match.group(2)}"
        filepath = save_dir / filename

        if not overwrite and filepath.exists():
            return

        with urlopen(self.api_client.IMG_HOST + url) as r:
            with open(filepath, "wb") as f:
                f.write(r.read())

    def _save_metadata(self, save_dir: Path, data):
        """Write the raw API response as both index.protobuf and index.json."""
        save_dir.mkdir(parents=True, exist_ok=True)
        with open(save_dir / "index.protobuf", "wb") as f:
            f.write(data.SerializeToString())
        with open(save_dir / "index.json", "w") as f:
            json.dump(json_format.MessageToDict(data), f, ensure_ascii=False, indent=4)

    def _download_pages(self, pages, save_dir: Path, file_format: str, overwrite: bool):
        """Dispatch each page to the bounded worker queue and wait for completion."""
        for page in pages:
            t = Thread(
                target=self._download_image_old_api,
                name=page.image.imageUrl,
                args=(save_dir, file_format, page.image, overwrite),
            )
            t.start()
            self.queue.put(t)
        self.queue.join()

    def download_chapter(
        self,
        chapter: Chapter,
        output_dir: Path,
        file_format: str = "02",
        overwrite: bool = False
    ) -> bool:
        """Download one chapter's pages. Returns True on success."""
        self._start_worker()

        try:
            manga_data = self.api_client.get_manga_viewer(chapter.chapter_id)
            logging.info(f"[{chapter.chapter_id}] {manga_data.viewerTitle}")

            save_dir = Path(output_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            chapter.images_dir = save_dir

            self._save_metadata(save_dir, manga_data)
            self._download_pages(manga_data.pages, save_dir, file_format, overwrite)

            logging.info(f"✓ Downloaded chapter: {chapter.display_name}")
            return True

        except Exception as e:
            logging.error(f"Failed to download chapter {chapter.chapter_id}: {e}")
            return False

    def download_book(
        self,
        book_id: int,
        output_dir: Path,
        file_format: str = "02",
        overwrite: bool = False
    ) -> Optional[BookIssue]:
        """Download a book issue, including its cover thumbnail."""
        self._start_worker()

        try:
            book_data = self.api_client.get_book_viewer(book_id)
            book_issue_id = book_data.bookIssue.bookIssueId
            title = book_data.bookIssue.bookIssueName
            logging.info(f"[{book_issue_id}] {title}")

            save_dir = Path(output_dir)
            save_dir.mkdir(parents=True, exist_ok=True)

            book = BookIssue(
                book_id=book_id,
                book_issue_id=book_issue_id,
                title=title,
                thumbnail_url=book_data.bookIssue.thumbnailUrl,
                images_dir=save_dir
            )

            self._save_metadata(save_dir, book_data)
            if book_data.bookIssue.thumbnailUrl:
                self._download_thumbnail(save_dir, book_data.bookIssue.thumbnailUrl, overwrite)
            self._download_pages(book_data.pages, save_dir, file_format, overwrite)

            logging.info(f"✓ Downloaded book: {title}")
            return book

        except Exception as e:
            logging.error(f"Failed to download book {book_id}: {e}")
            return None

    def download_magazine(
        self,
        magazine_id: int,
        output_dir: Path,
        file_format: str = "02",
        overwrite: bool = False
    ) -> Optional[MagazineIssue]:
        """Download a magazine issue."""
        self._start_worker()

        try:
            magazine_data = self.api_client.get_magazine_viewer(magazine_id)
            magazine_issue_id = magazine_data.magazineIssue.magazineIssueId
            title = magazine_data.magazineIssue.magazineIssueName
            logging.info(f"[{magazine_issue_id}] {title}")

            save_dir = Path(output_dir)
            save_dir.mkdir(parents=True, exist_ok=True)

            magazine = MagazineIssue(
                magazine_id=magazine_id,
                magazine_issue_id=magazine_issue_id,
                title=title,
                images_dir=save_dir
            )

            self._save_metadata(save_dir, magazine_data)
            self._download_pages(magazine_data.pages, save_dir, file_format, overwrite)

            logging.info(f"✓ Downloaded magazine: {title}")
            return magazine

        except Exception as e:
            logging.error(f"Failed to download magazine {magazine_id}: {e}")
            return None

    def download_series(
        self,
        manga_id: int,
        output_base_dir: Path,
        file_format: str = "02",
        overwrite: bool = False
    ) -> Optional[Series]:
        """Download every chapter of a series, grouping them into volumes by title."""
        try:
            chapters, manga_title = self.api_client.get_chapters_from_manga(manga_id)
            if not chapters:
                logging.error(f"No chapters found for manga {manga_id}")
                return None

            series = Series(manga_id=manga_id, title=manga_title or f"manga_{manga_id}")

            free_count = sum(1 for ch in chapters if ch.is_free)
            logging.info(f"\nFound {len(chapters)} chapters ({free_count} free, {len(chapters) - free_count} paid)")

            volumes_dict = {}
            for i, chapter in enumerate(chapters, 1):
                status = "FREE" if chapter.is_free else f"¥{chapter.price}"
                logging.info(f"\n[{i}/{len(chapters)}] {chapter.display_name} ({status})")

                chapter_dir = output_base_dir / f"ch_{chapter.chapter_id}_{chapter.safe_name}"
                if not self.download_chapter(chapter, chapter_dir, file_format, overwrite):
                    continue

                volume_num = extract_volume_number(chapter.display_name)
                if volume_num is None:
                    series.add_standalone_chapter(chapter)
                    continue
                if volume_num not in volumes_dict:
                    volumes_dict[volume_num] = Volume(volume_number=volume_num, title=f"{volume_num}巻")
                volumes_dict[volume_num].add_chapter(chapter)

            for vol_num in sorted(volumes_dict):
                series.add_volume(volumes_dict[vol_num])

            logging.info(f"\n✓ Completed! Downloaded {len(series.all_chapters)} chapters")
            return series

        except Exception as e:
            logging.error(f"Failed to download series {manga_id}: {e}")
            return None

    def try_download_chapter_or_series(
        self,
        manga_id: int,
        output_dir: Path,
        file_format: str = "02",
        overwrite: bool = False
    ) -> tuple[Optional[Chapter], Optional[Series]]:
        """Resolve an ambiguous ID: try it as a chapter, then fall back to a series.

        Exactly one element of the returned tuple is set, or both are None on failure.
        """
        try:
            logging.info(f"Attempting to download as chapter ID: {manga_id}")
            chapter = Chapter(chapter_id=manga_id, manga_id=0, chapter_main_name=f"chapter_{manga_id}")
            if self.download_chapter(chapter, output_dir, file_format, overwrite):
                return (chapter, None)
        except Exception as e:
            logging.debug(f"Failed as chapter ID: {e}")

        try:
            logging.info(f"Attempting to download as manga ID: {manga_id}")
            series = self.download_series(manga_id, output_dir, file_format, overwrite)
            if series:
                return (None, series)
        except Exception as e:
            logging.error(f"Failed as manga ID: {e}")
            raise

        return (None, None)
