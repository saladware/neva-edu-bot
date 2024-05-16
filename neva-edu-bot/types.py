from datetime import datetime
from typing import NamedTuple


class NewsPost(NamedTuple):
    title: str
    description: str
    posted_at: datetime
    important: bool
    link: str
    category: str
    keywords: list[str]
