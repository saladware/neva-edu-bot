import re
from abc import ABC, abstractmethod
from datetime import datetime
from http import HTTPStatus
from typing import cast

import dateparser
from aiohttp import ClientSession
from bs4 import BeautifulSoup, Tag

from .types import NewsPost


class BaseNewsParser(ABC):
    @abstractmethod
    async def parse(self) -> list[NewsPost]:
        raise NotImplementedError


class Bs4NewsParser(BaseNewsParser):
    BASE_URL = "http://nevarono.spb.ru"

    @classmethod
    async def fetch_markup(cls) -> str:
        async with (
            ClientSession(cls.BASE_URL) as client,
            client.get("/novosti.html", params={"start": 0}) as response,
        ):
            if not HTTPStatus(response.status).is_success:
                message = "something went wrong while fetching markup"
                raise ValueError(message)
            return await response.text()

    @staticmethod
    def parse_datetime(value: str) -> datetime:
        result = dateparser.parse(value, languages=["ru"])
        if result is None:
            message = "something went wrong while parsing datetime"
            raise ValueError(message)
        return result

    async def parse(self) -> list[NewsPost]:
        markup = await self.fetch_markup()
        soup = BeautifulSoup(markup, "html.parser")

        posts = list[NewsPost]()

        for post_markup in soup.find_all("div", class_="news-item"):
            if not isinstance(post_markup.h2, Tag):
                continue
            title = post_markup.h2.text.strip()
            description = post_markup.find("div", class_="desc").get_text().strip()
            link = self.BASE_URL + post_markup.find("a", "more")["href"]
            posted_at = self.parse_datetime(
                post_markup.find("span", "date").get_text().strip()
            )
            important = "itemIsFeatured" in post_markup["class"]
            category = post_markup.find("div", "info").a.get_text()
            keywords_div = post_markup.find("div", "add").find(
                string=re.compile(".*Клю.*")
            )
            if keywords_div is None:
                keywords = []
            else:
                keywords: list[str] = [
                    cast("str", a.get_text()).strip()
                    for a in keywords_div.parent.find_all("a")
                ]

            post = NewsPost(
                title=title,
                description=description,
                posted_at=posted_at,
                important=important,
                link=link,
                category=category,
                keywords=keywords,
            )
            posts.append(post)

        return posts


if __name__ == "__main__":
    """python -m neva-edu-bot.parser"""

    import asyncio

    asyncio.run(Bs4NewsParser().parse())
