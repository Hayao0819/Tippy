"""Image compression and optimization utilities."""

import logging
from pathlib import Path
from typing import Optional
from PIL import Image


class ImageOptimizer:
    """Re-compress or convert downloaded images to save space."""

    @staticmethod
    def optimize_jpeg(
        image_path: Path,
        quality: int = 85,
        optimize: bool = True
    ) -> Optional[int]:
        """Re-save a JPEG at the given quality. Returns bytes saved, or None on failure."""
        try:
            original_size = image_path.stat().st_size
            img = Image.open(image_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(image_path, 'JPEG', quality=quality, optimize=optimize)
            img.close()

            new_size = image_path.stat().st_size
            reduction = original_size - new_size

            logging.debug(
                f"Optimized {image_path.name}: "
                f"{original_size/1024:.1f}KB → {new_size/1024:.1f}KB "
                f"({reduction/1024:.1f}KB saved, {100*reduction/original_size:.1f}%)"
            )

            return reduction
        except Exception as e:
            logging.error(f"Failed to optimize {image_path}: {e}")
            return None

    @staticmethod
    def optimize_png(
        image_path: Path,
        compress_level: int = 9
    ) -> Optional[int]:
        """Re-save a PNG with maximum compression. Returns bytes saved, or None on failure."""
        try:
            original_size = image_path.stat().st_size
            img = Image.open(image_path)
            img.save(image_path, 'PNG', compress_level=compress_level, optimize=True)
            img.close()

            new_size = image_path.stat().st_size
            reduction = original_size - new_size

            if reduction > 0:
                logging.debug(
                    f"Optimized {image_path.name}: "
                    f"{original_size/1024:.1f}KB → {new_size/1024:.1f}KB "
                    f"({reduction/1024:.1f}KB saved, {100*reduction/original_size:.1f}%)"
                )

            return reduction
        except Exception as e:
            logging.error(f"Failed to optimize {image_path}: {e}")
            return None

    @staticmethod
    def convert_to_webp(
        image_path: Path,
        quality: int = 85,
        delete_original: bool = True
    ) -> Optional[Path]:
        """Convert an image to WebP. Returns the new path, or None on failure."""
        try:
            original_size = image_path.stat().st_size
            img = Image.open(image_path)
            webp_path = image_path.with_suffix('.webp')
            img.save(webp_path, 'WEBP', quality=quality, method=6)  # method=6: slowest, smallest
            img.close()

            new_size = webp_path.stat().st_size
            reduction = original_size - new_size

            logging.debug(
                f"Converted {image_path.name} → {webp_path.name}: "
                f"{original_size/1024:.1f}KB → {new_size/1024:.1f}KB "
                f"({reduction/1024:.1f}KB saved, {100*reduction/original_size:.1f}%)"
            )

            if delete_original:
                image_path.unlink()

            return webp_path
        except Exception as e:
            logging.error(f"Failed to convert {image_path} to WebP: {e}")
            return None

    @classmethod
    def optimize_directory(
        cls,
        directory: Path,
        jpeg_quality: Optional[int] = None,
        optimize_png: bool = False,
        convert_to_webp: bool = False,
        webp_quality: int = 85
    ) -> dict:
        """Optimize every image in a directory, returning {total/optimized/failed/reduction}.

        Pass convert_to_webp to convert all images; otherwise JPEGs are re-compressed when
        jpeg_quality is set and PNGs when optimize_png is set.
        """
        if not directory.exists():
            logging.warning(f"Directory does not exist: {directory}")
            return {}

        image_files = []
        for pattern in ('*.jpeg', '*.jpg', '*.png'):
            image_files.extend(directory.glob(pattern))

        stats = {
            'total_files': len(image_files),
            'optimized_files': 0,
            'total_reduction': 0,
            'failed_files': 0,
        }
        if not image_files:
            logging.debug(f"No images found in {directory}")
            return stats

        logging.info(f"Optimizing {stats['total_files']} images in {directory.name}...")

        for img_path in image_files:
            try:
                if convert_to_webp:
                    if cls.convert_to_webp(img_path, webp_quality, delete_original=True):
                        stats['optimized_files'] += 1
                    else:
                        stats['failed_files'] += 1
                    continue

                if img_path.suffix.lower() in ('.jpg', '.jpeg') and jpeg_quality is not None:
                    reduction = cls.optimize_jpeg(img_path, jpeg_quality)
                elif img_path.suffix.lower() == '.png' and optimize_png:
                    reduction = cls.optimize_png(img_path)
                else:
                    continue

                if reduction is None:
                    stats['failed_files'] += 1
                else:
                    stats['optimized_files'] += 1
                    stats['total_reduction'] += max(reduction, 0)

            except Exception as e:
                logging.error(f"Error processing {img_path}: {e}")
                stats['failed_files'] += 1

        if stats['optimized_files'] > 0:
            logging.info(
                f"✓ Optimized {stats['optimized_files']}/{stats['total_files']} images, "
                f"saved {stats['total_reduction']/1024/1024:.2f}MB"
            )

        if stats['failed_files'] > 0:
            logging.warning(f"Failed to optimize {stats['failed_files']} images")

        return stats
