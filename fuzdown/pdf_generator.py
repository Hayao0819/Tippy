"""Build PDFs from downloaded chapter/volume/series images."""

import logging
import re
from pathlib import Path
from typing import List, Union

from PIL import Image

from .models import Chapter, Volume, Series


class PDFGenerator:

    @staticmethod
    def _get_images_from_directory(directory: Union[str, Path]) -> List[Path]:
        """Return a directory's images sorted by the leading number in the filename."""
        directory = Path(directory)
        if not directory.exists():
            logging.warning(f"Directory does not exist: {directory}")
            return []

        image_files = []
        for pattern in ('*.jpeg', '*.jpg', '*.png', '*.webp'):
            image_files.extend(directory.glob(pattern))

        def numeric_sort_key(path: Path):
            try:
                return int(path.stem)
            except ValueError:
                match = re.match(r'^(\d+)', path.stem)
                return int(match.group(1)) if match else float('inf')

        image_files.sort(key=numeric_sort_key)
        return image_files

    @staticmethod
    def _create_pdf_from_images(image_paths: List[Path], output_path: Path) -> bool:
        if not image_paths:
            logging.warning(f"No images found to create PDF: {output_path}")
            return False

        logging.info(f"Total images: {len(image_paths)}")
        current_dir = None
        for i, img_path in enumerate(image_paths, 1):
            if img_path.parent != current_dir:
                current_dir = img_path.parent
                logging.info(f"  [{current_dir.name}]")
            logging.info(f"    {i:3d}: {img_path.name}")

        # PDF pages must be RGB; PNG/WebP may carry an alpha channel.
        images = []
        for img_path in image_paths:
            try:
                img = Image.open(img_path)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                images.append(img)
            except Exception as e:
                logging.error(f"Failed to load image {img_path}: {e}")

        if not images:
            logging.error("No valid images to create PDF")
            return False

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            images[0].save(
                str(output_path),
                save_all=True,
                append_images=images[1:],
                resolution=100.0,
                quality=95,
                optimize=False,
            )
            logging.info(f"✓ Created PDF: {output_path} ({len(images)} pages)")
            return True
        except Exception as e:
            logging.error(f"Failed to create PDF {output_path}: {e}")
            return False
        finally:
            for img in images:
                img.close()

    @classmethod
    def create_chapter_pdf(cls, chapter: Chapter, output_filename: str = None) -> bool:
        if not chapter.images_dir:
            logging.error(f"Chapter {chapter.chapter_id} has no images directory")
            return False

        images_dir = Path(chapter.images_dir)
        image_paths = cls._get_images_from_directory(images_dir)
        if not image_paths:
            return False

        output_path = images_dir / (output_filename or f"{chapter.safe_name}.pdf")
        return cls._create_pdf_from_images(image_paths, output_path)

    @classmethod
    def create_volume_pdf(cls, volume: Volume, output_dir: Path, output_filename: str = None) -> bool:
        """Combine every chapter in a volume into one PDF, in chapter-id order."""
        if not volume.chapters:
            logging.warning(f"Volume {volume.volume_number} has no chapters")
            return False

        all_images = []
        for chapter in sorted(volume.chapters, key=lambda c: c.chapter_id):
            if not chapter.images_dir:
                logging.warning(f"Chapter {chapter.chapter_id} has no images directory, skipping")
                continue
            all_images.extend(cls._get_images_from_directory(chapter.images_dir))

        if not all_images:
            logging.error(f"No images found for volume {volume.volume_number}")
            return False

        output_path = Path(output_dir) / (output_filename or f"{volume.safe_name}.pdf")
        logging.info(f"Creating volume PDF: {len(all_images)} images from {len(volume.chapters)} chapters")
        return cls._create_pdf_from_images(all_images, output_path)

    @classmethod
    def create_series_pdf(cls, series: Series, output_dir: Path, output_filename: str = None) -> bool:
        """Combine the whole series (volumes then standalone chapters) into one PDF."""
        all_images = []
        for volume in sorted(series.volumes, key=lambda v: v.volume_number):
            for chapter in sorted(volume.chapters, key=lambda c: c.chapter_id):
                if not chapter.images_dir:
                    logging.warning(f"Chapter {chapter.chapter_id} has no images directory, skipping")
                    continue
                all_images.extend(cls._get_images_from_directory(chapter.images_dir))

        for chapter in sorted(series.standalone_chapters, key=lambda c: c.chapter_id):
            if not chapter.images_dir:
                logging.warning(f"Chapter {chapter.chapter_id} has no images directory, skipping")
                continue
            all_images.extend(cls._get_images_from_directory(chapter.images_dir))

        if not all_images:
            logging.error(f"No images found for series {series.title}")
            return False

        output_path = Path(output_dir) / (output_filename or f"{series.safe_name}.pdf")
        total_chapters = sum(len(v.chapters) for v in series.volumes) + len(series.standalone_chapters)
        logging.info(f"Creating series PDF: {len(all_images)} images from {total_chapters} chapters")
        return cls._create_pdf_from_images(all_images, output_path)
