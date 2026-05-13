import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Request
from typing import Optional

from app.database import get_db
from app.schemas import VideoListItem, VideoDetail, VideoReplace, VideoUpdate

router = APIRouter(prefix="/videos", tags=["videos"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MAX_VIDEO_SIZE_BYTES = int(os.getenv("MAX_VIDEO_SIZE_MB", "200")) * 1024 * 1024
MAX_THUMBNAIL_SIZE_BYTES = int(os.getenv("MAX_THUMBNAIL_SIZE_MB", "5")) * 1024 * 1024
CHUNK_SIZE_BYTES = 1024 * 1024

VIDEO_ALLOWED_EXTENSIONS = {".mp4", ".webm", ".ogg", ".mov", ".m4v"}
VIDEO_ALLOWED_MIME_TYPES = {
    "video/mp4",
    "video/webm",
    "video/ogg",
    "video/quicktime",
    "video/x-m4v",
}
THUMBNAIL_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
THUMBNAIL_ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _validate_upload(
    file: UploadFile,
    *,
    field_name: str,
    allowed_extensions: set[str],
    allowed_mime_types: set[str],
    max_size_bytes: int,
) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail=f"El archivo de {field_name} requiere un nombre válido")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Extensión no permitida para {field_name}")

    if file.content_type not in allowed_mime_types:
        raise HTTPException(status_code=400, detail=f"Tipo de archivo no permitido para {field_name}")

    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size > max_size_bytes:
        max_size_mb = max_size_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"El archivo de {field_name} excede {max_size_mb}MB")

    return ext


def _save_file(file: UploadFile, subfolder: str, extension: str) -> str:
    folder = os.path.join(UPLOAD_DIR, subfolder)
    os.makedirs(folder, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{extension}"
    path = os.path.join(folder, filename)
    file.file.seek(0)
    with open(path, "wb") as f:
        while chunk := file.file.read(CHUNK_SIZE_BYTES):
            f.write(chunk)
    file.file.seek(0)
    return filename


def _build_url(request: Request, subfolder: str, filename: str | None) -> str | None:
    if not filename:
        return None
    return str(request.url_for("uploads", path=f"{subfolder}/{filename}"))


def _to_video_detail(row, request: Request) -> VideoDetail:
    return VideoDetail(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        channel=row["channel"],
        duration=row["duration"],
        views=row["views"],
        video_url=_build_url(request, "videos", row["video_filename"]),
        thumbnail_url=_build_url(request, "thumbnails", row["thumbnail_filename"]),
        created_at=row["created_at"],
    )


def _to_video_list_item(row, request: Request) -> VideoListItem:
    return VideoListItem(
        id=row["id"],
        title=row["title"],
        channel=row["channel"],
        duration=row["duration"],
        views=row["views"],
        thumbnail_url=_build_url(request, "thumbnails", row["thumbnail_filename"]),
    )


@router.get("", response_model=list[VideoListItem])
def list_videos(request: Request):
    conn = get_db()
    rows = conn.execute("SELECT id, title, channel, duration, views, thumbnail_filename FROM videos ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_to_video_list_item(r, request) for r in rows]


@router.get("/search", response_model=list[VideoListItem])
def search_videos(request: Request, title: str = Query(..., min_length=1)):
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="El título de búsqueda no puede estar vacío")

    conn = get_db()
    rows = conn.execute(
        """
        SELECT id, title, channel, duration, views, thumbnail_filename
        FROM videos
        WHERE LOWER(title) LIKE ?
        ORDER BY created_at DESC
        """,
        (f"%{clean_title.lower()}%",),
    ).fetchall()
    conn.close()

    return [_to_video_list_item(r, request) for r in rows]


@router.get("/{video_id}", response_model=VideoDetail)
def get_video(video_id: int, request: Request):
    conn = get_db()
    r = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    if not r:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    return _to_video_detail(r, request)


@router.post("", response_model=VideoDetail, status_code=201)
def create_video(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    channel: str = Form("Usuario"),
    duration: str = Form("0:00"),
    video: UploadFile = File(...),
    thumbnail: Optional[UploadFile] = File(None),
):
    video_ext = _validate_upload(
        video,
        field_name="video",
        allowed_extensions=VIDEO_ALLOWED_EXTENSIONS,
        allowed_mime_types=VIDEO_ALLOWED_MIME_TYPES,
        max_size_bytes=MAX_VIDEO_SIZE_BYTES,
    )
    thumbnail_ext = None
    if thumbnail:
        thumbnail_ext = _validate_upload(
            thumbnail,
            field_name="thumbnail",
            allowed_extensions=THUMBNAIL_ALLOWED_EXTENSIONS,
            allowed_mime_types=THUMBNAIL_ALLOWED_MIME_TYPES,
            max_size_bytes=MAX_THUMBNAIL_SIZE_BYTES,
        )

    video_filename = _save_file(video, "videos", video_ext)
    thumbnail_filename = _save_file(thumbnail, "thumbnails", thumbnail_ext) if thumbnail and thumbnail_ext else None

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO videos (title, description, channel, duration, video_filename, thumbnail_filename) VALUES (?, ?, ?, ?, ?, ?)",
        (title, description, channel, duration, video_filename, thumbnail_filename)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()

    return _to_video_detail(row, request)


@router.patch("/{video_id}", response_model=VideoDetail)
def update_video(video_id: int, data: VideoUpdate, request: Request):
    conn = get_db()
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Video no encontrado")

    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE videos SET {set_clause} WHERE id = ?", (*updates.values(), video_id))
        conn.commit()

    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    return _to_video_detail(row, request)


@router.put("/{video_id}", response_model=VideoDetail)
def replace_video(video_id: int, data: VideoReplace, request: Request):
    conn = get_db()
    row = conn.execute("SELECT id FROM videos WHERE id = ?", (video_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Video no encontrado")

    conn.execute(
        "UPDATE videos SET title = ?, description = ?, channel = ?, duration = ? WHERE id = ?",
        (data.title, data.description, data.channel, data.duration, video_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    return _to_video_detail(row, request)


@router.delete("/{video_id}", status_code=204)
def delete_video(video_id: int):
    conn = get_db()
    row = conn.execute("SELECT video_filename, thumbnail_filename FROM videos WHERE id = ?", (video_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Video no encontrado")

    # Eliminar archivos del disco
    video_path = os.path.join(UPLOAD_DIR, "videos", row["video_filename"])
    if os.path.exists(video_path):
        os.remove(video_path)
    if row["thumbnail_filename"]:
        thumb_path = os.path.join(UPLOAD_DIR, "thumbnails", row["thumbnail_filename"])
        if os.path.exists(thumb_path):
            os.remove(thumb_path)

    conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    conn.commit()
    conn.close()
