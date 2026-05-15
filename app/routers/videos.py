import os
import re
import shutil
import subprocess
import tempfile
import uuid
import boto3
import imageio_ffmpeg
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional

from app.database import get_db
from app.schemas import VideoListItem, VideoDetail, VideoUpdate

router = APIRouter(prefix="/videos", tags=["videos"])

S3_BUCKET = os.getenv('S3_BUCKET_NAME', 'ourtube-videos-413368290265')
s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'us-east-1'))
PRESIGNED_URL_EXPIRES = int(os.getenv('S3_PRESIGNED_URL_EXPIRES', '3600'))

def _save_file(file: UploadFile, subfolder: str) -> str:
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    s3_key = f"{subfolder}/{filename}"
    s3_client.upload_fileobj(file.file, S3_BUCKET, s3_key)
    return filename


def _format_duration(total_seconds: int) -> str:
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _extract_duration(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "")[1] or ".mp4"
    file.file.seek(0)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            temp_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)

        ffmpeg_executable = imageio_ffmpeg.get_ffmpeg_exe()
        probe = subprocess.run(
            [ffmpeg_executable, "-i", temp_path, "-f", "null", "-"],
            capture_output=True,
            text=True,
        )
        output = (probe.stderr or "") + (probe.stdout or "")
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
        if not match:
            raise ValueError("Duración no encontrada")

        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))
        total_seconds = int(hours * 3600 + minutes * 60 + round(seconds))
        return _format_duration(total_seconds)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo calcular la duración del video: {exc}")
    finally:
        file.file.seek(0)
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def _build_url(subfolder: str, filename: Optional[str]) -> Optional[str]:
    if not filename:
        return None
    return s3_client.generate_presigned_url(
        ClientMethod='get_object',
        Params={'Bucket': S3_BUCKET, 'Key': f"{subfolder}/{filename}"},
        ExpiresIn=PRESIGNED_URL_EXPIRES,
    )

@router.get("", response_model=list[VideoListItem])
def list_videos():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, title, channel, duration, views, thumbnail_filename FROM videos ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        VideoListItem(
            id=r["id"], title=r["title"], channel=r["channel"],
            duration=r["duration"], views=r["views"],
            thumbnail_url=_build_url("imagenes", r["thumbnail_filename"])
        ) for r in rows
    ]

@router.get("/{video_id}", response_model=VideoDetail)
def get_video(video_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos WHERE id = %s", (video_id,))
    r = cur.fetchone()
    cur.close()
    conn.close()
    if not r:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    return VideoDetail(
        id=r["id"], title=r["title"], description=r["description"],
        channel=r["channel"], duration=r["duration"], views=r["views"],
        video_url=_build_url("videos", r["video_filename"]),
        thumbnail_url=_build_url("imagenes", r["thumbnail_filename"]),
        created_at=str(r["created_at"])
    )

@router.post("", response_model=VideoDetail, status_code=201)
def create_video(
    title: str = Form(...),
    description: str = Form(""),
    channel: str = Form("Usuario"),
    video: UploadFile = File(...),
    thumbnail: Optional[UploadFile] = File(None),
):
    duration = _extract_duration(video)
    video_filename = _save_file(video, "videos")
    thumbnail_filename = _save_file(thumbnail, "imagenes") if thumbnail else None

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO videos (title, description, channel, duration, video_filename, thumbnail_filename)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (title, description, channel, duration, video_filename, thumbnail_filename)
    )
    new_id = cur.fetchone()["id"]
    conn.commit()

    cur.execute("SELECT * FROM videos WHERE id = %s", (new_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    return VideoDetail(
        id=row["id"], title=row["title"], description=row["description"],
        channel=row["channel"], duration=row["duration"], views=row["views"],
        video_url=_build_url("videos", row["video_filename"]),
        thumbnail_url=_build_url("imagenes", row["thumbnail_filename"]),
        created_at=str(row["created_at"])
    )

@router.put("/{video_id}", response_model=VideoDetail)
def update_video(
    video_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    channel: Optional[str] = Form(None),
    duration: Optional[str] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
    increment_views: bool = Form(False),
):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos WHERE id = %s", (video_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Video no encontrado")

    updates = {}
    if title is not None: updates['title'] = title
    if description is not None: updates['description'] = description
    if channel is not None: updates['channel'] = channel
    if duration is not None: updates['duration'] = duration
    if thumbnail:
        thumbnail_filename = _save_file(thumbnail, "imagenes")
        updates['thumbnail_filename'] = thumbnail_filename
    if increment_views:
        cur.execute("UPDATE videos SET views = views + 1 WHERE id = %s", (video_id,))
        conn.commit()

    if updates:
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        cur.execute(
            f"UPDATE videos SET {set_clause} WHERE id = %s",
            (*updates.values(), video_id)
        )
        conn.commit()

    cur.execute("SELECT * FROM videos WHERE id = %s", (video_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    return VideoDetail(
        id=row["id"], title=row["title"], description=row["description"],
        channel=row["channel"], duration=row["duration"], views=row["views"],
        video_url=_build_url("videos", row["video_filename"]),
        thumbnail_url=_build_url("imagenes", row["thumbnail_filename"]),
        created_at=str(row["created_at"])
    )

@router.delete("/{video_id}", status_code=204)
def delete_video(video_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT video_filename, thumbnail_filename FROM videos WHERE id = %s", (video_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Video no encontrado")

    # Eliminar archivos de S3
    s3_client.delete_object(Bucket=S3_BUCKET, Key=f"videos/{row['video_filename']}")
    if row["thumbnail_filename"]:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=f"imagenes/{row['thumbnail_filename']}")

    cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))
    conn.commit()
    cur.close()
    conn.close()