"""Safe file storage for invoices/photos: type sniffing, size limits, HEIC→JPEG, thumbnails."""
import hashlib
import io
import logging
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

from .config import get_settings

log = logging.getLogger("storage")
settings = get_settings()

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_OK = True
except Exception:  # pragma: no cover
    HEIF_OK = False

ALLOWED = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "application/pdf": ".pdf",
}
IMAGE_MAX_EDGE = 3000   # downscale huge phone photos (keeps text legible, saves SD/SSD space)
THUMB_EDGE = 480


def sniff(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"hevc", b"heim", b"heis",
                                                b"mif1", b"msf1", b"avif"):
        return "image/heic"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return None


@dataclass
class StoredFile:
    stored_path: str
    thumb_path: str | None
    content_type: str
    size_bytes: int
    sha256: str
    original_filename: str
    abs_path: Path


def _root() -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings.upload_dir


def abs_path(rel: str) -> Path:
    root = _root().resolve()
    p = (root / rel).resolve()
    if root not in p.parents:
        raise HTTPException(400, "Invalid path")
    return p


def _safe_name(name: str | None) -> str:
    name = Path(name or "upload").name
    return "".join(c for c in name if c.isprintable() and c not in '\\/:*?"<>|')[:150] or "upload"


async def save_upload(file: UploadFile) -> StoredFile:
    limit = settings.max_upload_mb * 1024 * 1024
    buf = io.BytesIO()
    while chunk := await file.read(1024 * 1024):
        buf.write(chunk)
        if buf.tell() > limit:
            raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB)")
    data = buf.getvalue()
    if not data:
        raise HTTPException(400, "Empty file")
    ctype = sniff(data[:32])
    if ctype not in ALLOWED:
        raise HTTPException(415, "Only JPEG, PNG, WEBP, HEIC images and PDF files are allowed")

    original = _safe_name(file.filename)
    if ctype.startswith("image/"):
        data, ctype = _normalise_image(data, ctype)

    sub = datetime.now().strftime("%Y/%m")
    stem = uuid.uuid4().hex
    rel = f"{sub}/{stem}{ALLOWED[ctype]}"
    dest = abs_path(rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    thumb_rel = f"{sub}/{stem}_thumb.jpg"
    thumb_ok = make_thumbnail(dest, ctype, abs_path(thumb_rel))
    return StoredFile(stored_path=rel, thumb_path=thumb_rel if thumb_ok else None, content_type=ctype,
                      size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                      original_filename=original, abs_path=dest)


def _normalise_image(data: bytes, ctype: str) -> tuple[bytes, str]:
    """Fix EXIF rotation, convert HEIC to JPEG, downscale very large photos, strip metadata."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        if ctype == "image/heic":
            raise HTTPException(415, "Could not read HEIC image") from e
        raise HTTPException(415, "Unreadable image") from e
    needs_resize = max(img.size) > IMAGE_MAX_EDGE
    if needs_resize:
        img.thumbnail((IMAGE_MAX_EDGE, IMAGE_MAX_EDGE), Image.LANCZOS)
    out = io.BytesIO()
    if ctype in ("image/jpeg", "image/heic"):
        # always re-encode: applies rotation and drops EXIF (GPS location etc.)
        img.convert("RGB").save(out, "JPEG", quality=88, optimize=True)
        return out.getvalue(), "image/jpeg"
    if not needs_resize:
        return data, ctype
    img.save(out, "PNG" if ctype == "image/png" else "WEBP", **({"optimize": True} if ctype == "image/png" else {"quality": 88}))
    return out.getvalue(), ctype


def make_thumbnail(src: Path, ctype: str, dest: Path) -> bool:
    try:
        if ctype == "application/pdf":
            if not shutil.which("pdftoppm"):
                return False
            with tempfile.TemporaryDirectory() as td:
                subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "60", "-jpeg",
                                str(src), f"{td}/p"], check=True, timeout=30,
                               capture_output=True)
                pages = sorted(Path(td).glob("p*.jpg"))
                if not pages:
                    return False
                img = Image.open(pages[0])
                img.load()
        else:
            img = Image.open(src)
        img.thumbnail((THUMB_EDGE, THUMB_EDGE))
        img.convert("RGB").save(dest, "JPEG", quality=80)
        return True
    except Exception as e:
        log.warning("thumbnail failed for %s: %s", src, e)
        return False


def delete_files(*rels: str | None) -> None:
    for rel in rels:
        if not rel:
            continue
        try:
            abs_path(rel).unlink(missing_ok=True)
        except Exception as e:  # pragma: no cover
            log.warning("could not delete %s: %s", rel, e)
