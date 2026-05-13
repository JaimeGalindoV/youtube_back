from pydantic import BaseModel
from typing import Optional


class VideoListItem(BaseModel):
    id: int
    title: str
    channel: str
    duration: str
    views: int
    thumbnail_url: Optional[str] = None


class VideoDetail(BaseModel):
    id: int
    title: str
    description: str
    channel: str
    duration: str
    views: int
    video_url: str
    thumbnail_url: Optional[str] = None
    created_at: str


class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    channel: Optional[str] = None
    duration: Optional[str] = None


class VideoReplace(BaseModel):
    title: str
    description: str
    channel: str
    duration: str
