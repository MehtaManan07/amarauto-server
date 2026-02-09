"""
Google Cloud Storage for product images.
Compresses to WebP (max 1600px, quality 80), uploads to GCS, returns public URLs.
Same blob path stored in drive_file_id for refcount/delete.
"""

import io
import uuid
from typing import Tuple

from google.cloud import storage
from PIL import Image

from app.core.config import config

# Slight compression: max dimension 1600px, WebP quality 80 (~200 products × 5 images)
MAX_PIXEL_DIMENSION = 1600
WEBP_QUALITY = 80

_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _client
    if _client is not None:
        return _client
    _client = storage.Client(project=config.gcp_project_id or None)
    return _client


def _compress_to_webp(image_bytes: bytes, content_type: str) -> bytes:
    """Resize (max 1600px) and convert to WebP at quality 80."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    w, h = img.size
    if w > MAX_PIXEL_DIMENSION or h > MAX_PIXEL_DIMENSION:
        if w >= h:
            new_w = MAX_PIXEL_DIMENSION
            new_h = int(h * MAX_PIXEL_DIMENSION / w)
        else:
            new_h = MAX_PIXEL_DIMENSION
            new_w = int(w * MAX_PIXEL_DIMENSION / h)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    save_kw: dict = {"format": "WEBP", "quality": WEBP_QUALITY}
    if img.mode == "RGBA":
        save_kw["lossless"] = False
    img.save(out, **save_kw)
    return out.getvalue()


def upload_product_image(
    product_id: int,
    image_bytes: bytes,
    content_type: str,
    filename: str,
) -> Tuple[str, str, str]:
    """
    Compress image to WebP, upload to GCS, return (blob_name, url, thumb_url).
    Public read: enable via bucket IAM (e.g. allUsers objectViewer). thumb_url same as url.
    """
    if not config.gcp_bucket_name:
        raise RuntimeError("GCP_BUCKET_NAME must be set for product images.")

    webp_bytes = _compress_to_webp(image_bytes, content_type)
    prefix = (config.gcp_product_images_prefix or "product-images/").strip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    base_name = (filename or "image").rsplit(".", 1)[0] or "image"
    safe_name = f"{base_name}_{uuid.uuid4().hex[:8]}.webp"
    blob_path = f"{prefix}{product_id}/{safe_name}"

    client = _get_client()
    bucket = client.bucket(config.gcp_bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(
        webp_bytes,
        content_type="image/webp",
    )
    # Uniform bucket-level access: do not use object ACLs. Make bucket (or prefix) public via IAM if needed.
    url = f"https://storage.googleapis.com/{config.gcp_bucket_name}/{blob_path}"
    return (blob_path, url, url)


def delete_file(blob_path: str) -> None:
    """Delete an object from GCS by path (same value stored in drive_file_id)."""
    if not config.gcp_bucket_name:
        return
    client = _get_client()
    bucket = client.bucket(config.gcp_bucket_name)
    blob = bucket.blob(blob_path)
    blob.delete()
