import asyncio

from aiogram import Bot

from .parser import BaseNewsParser
from .types import NewsPost


class Service:
    def __init__(self, bot: Bot, chat_id: str, parser: BaseNewsParser) -> None:
        self.chat_id = chat_id
        self.bot = bot
        self.current_posts: list[NewsPost] = []
        self.parser = parser

    @staticmethod
    def get_unpublished_posts(
        old_posts: list[NewsPost], actual_posts: list[NewsPost]
    ) -> list[NewsPost]:
        return [post for post in actual_posts if post not in old_posts]

    async def send_post(self, post: NewsPost):
        def hash_tagged(value: str):
            return "#" + value.strip().replace(" ", "_")

        await self.bot.send_message(
            chat_id=self.chat_id,
            text=f'{"⚠️ " if post.important else ""}<a href="{post.link}"><b>{post.title}</b></a>\n\n{post.description}\n\n{post.posted_at:%d.%m.%Y %H:%M}\n\n{hash_tagged(post.category)} {" ".join(map(hash_tagged, post.keywords))}',
        )

    async def start(self):
        while True:
            actual_posts = await self.parser.parse()
            unpublished_posts = self.get_unpublished_posts(
                self.current_posts, actual_posts
            )
            self.current_posts = actual_posts
            for post in sorted(unpublished_posts, key=lambda post: post.posted_at):
                await self.send_post(post)
                await asyncio.sleep(0.5)
            await asyncio.sleep(30)
