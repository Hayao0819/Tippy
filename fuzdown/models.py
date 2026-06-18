"""Data models for Comic Fuz content."""

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


def _safe(name: str) -> str:
    """Make a title usable as a directory/file name."""
    return name.replace('/', '_').replace('\\', '_')


@dataclass
class Chapter:
    chapter_id: int
    manga_id: int
    chapter_main_name: str
    chapter_sub_name: str = ""
    price: int = 0
    images_dir: Optional[Path] = None

    @property
    def display_name(self) -> str:
        if self.chapter_sub_name:
            return f"{self.chapter_main_name} {self.chapter_sub_name}"
        return self.chapter_main_name

    @property
    def is_free(self) -> bool:
        return self.price == 0

    @property
    def safe_name(self) -> str:
        return _safe(self.display_name)


@dataclass
class Volume:
    """A volume (巻) grouping several chapters."""
    volume_number: int
    chapters: List[Chapter] = field(default_factory=list)
    title: str = ""

    @property
    def display_name(self) -> str:
        return self.title or f"Volume {self.volume_number}"

    @property
    def safe_name(self) -> str:
        return _safe(self.display_name)

    def add_chapter(self, chapter: Chapter):
        self.chapters.append(chapter)


@dataclass
class Series:
    manga_id: int
    title: str
    volumes: List[Volume] = field(default_factory=list)
    standalone_chapters: List[Chapter] = field(default_factory=list)

    @property
    def safe_name(self) -> str:
        return _safe(self.title)

    @property
    def all_chapters(self) -> List[Chapter]:
        chapters = [ch for volume in self.volumes for ch in volume.chapters]
        chapters.extend(self.standalone_chapters)
        return chapters

    def add_volume(self, volume: Volume):
        self.volumes.append(volume)

    def add_standalone_chapter(self, chapter: Chapter):
        self.standalone_chapters.append(chapter)


@dataclass
class BookIssue:
    """A book issue (単行本)."""
    book_id: int
    book_issue_id: int
    title: str
    thumbnail_url: str = ""
    images_dir: Optional[Path] = None

    @property
    def safe_name(self) -> str:
        return _safe(self.title)


@dataclass
class MagazineIssue:
    """A magazine issue (雑誌)."""
    magazine_id: int
    magazine_issue_id: int
    title: str
    images_dir: Optional[Path] = None

    @property
    def safe_name(self) -> str:
        return _safe(self.title)
