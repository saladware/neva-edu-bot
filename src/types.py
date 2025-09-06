from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AttachedFile:
    title: str
    url: str

@dataclass(frozen=True)
class NewsPost:
    title: str
    description: str
    posted_at: datetime
    important: bool
    link: str
    category: str
    keywords: list[str]
    attachments: list[AttachedFile]
