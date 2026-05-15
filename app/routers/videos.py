import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from typing import Optional

from app.database import get_db
from app.schemas import VideoListItem, VideoDetail, VideoUpdate

router = APIRouter(prefix="/videos", tags=["videos"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")


def _save_file(file: UploadFile, subfolder: str) -> str:
    folder = os.path.join(UPLOAD_DIR, subfolder)
    os.makedirs(folder, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(folder, filename)
    with open(path, "wb") as f:
        f.write(file.file.read())
    return filename


def _build_url(request: Request, subfolder: str, filename: str | None) -> str | None:
    if not filename:
        return None
    return f"{request.base_url}uploads/{subfolder}/{filename}"


@router.get("", response_model=list[VideoListItem])
def list_videos(request: Request):
    conn = get_db()
    rows = conn.execute("SELECT id, title, channel, duration, views, thumbnail_filename FROM videos ORDER BY created_at DESC").fetchall()
    conn.close()
    return [
        VideoListItem(
            id=r["id"], title=r["title"], channel=r["channel"],
            duration=r["duration"], views=r["views"],
            thumbnail_url=_build_url(request, "thumbnails", r["thumbnail_filename"])
        ) for r in rows
    ]


@router.get("/{video_id}", response_model=VideoDetail)
def get_video(video_id: int, request: Request):
    conn = get_db()
    r = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    if not r:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    return VideoDetail(
        id=r["id"], title=r["title"], description=r["description"],
        channel=r["channel"], duration=r["duration"], views=r["views"],
        video_url=_build_url(request, "videos", r["video_filename"]),
        thumbnail_url=_build_url(request, "thumbnails", r["thumbnail_filename"]),
        created_at=r["created_at"]
    )


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
    video_filename = _save_file(video, "videos")
    thumbnail_filename = _save_file(thumbnail, "thumbnails") if thumbnail else None

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO videos (title, description, channel, duration, video_filename, thumbnail_filename) VALUES (?, ?, ?, ?, ?, ?)",
        (title, description, channel, duration, video_filename, thumbnail_filename)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()

    return VideoDetail(
        id=row["id"], title=row["title"], description=row["description"],
        channel=row["channel"], duration=row["duration"], views=row["views"],
        video_url=_build_url(request, "videos", row["video_filename"]),
        thumbnail_url=_build_url(request, "thumbnails", row["thumbnail_filename"]),
        created_at=row["created_at"]
    )


@router.put("/{video_id}", response_model=VideoDetail)
def update_video(
    video_id: int,
    request: Request,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    channel: Optional[str] = Form(None),
    duration: Optional[str] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
):
    conn = get_db()
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Video no encontrado")

    # Diccionario manual con los campos modificados
    updates = {}
    if title is not None: updates['title'] = title
    if description is not None: updates['description'] = description
    if channel is not None: updates['channel'] = channel
    if duration is not None: updates['duration'] = duration

    # Si llegó un thumbnail nuevo, lo guardamos
    if thumbnail:
        thumbnail_filename = _save_file(thumbnail, "thumbnails")
        updates['thumbnail_filename'] = thumbnail_filename

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE videos SET {set_clause} WHERE id = ?", (*updates.values(), video_id))
        conn.commit()

    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    return VideoDetail(
        id=row["id"], title=row["title"], description=row["description"],
        channel=row["channel"], duration=row["duration"], views=row["views"],
        video_url=_build_url(request, "videos", row["video_filename"]),
        thumbnail_url=_build_url(request, "thumbnails", row["thumbnail_filename"]),
        created_at=row["created_at"]
    )


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
