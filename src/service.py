import asyncio

from aiogram import Bot

from src.parser import BaseNewsParser
from src.types import NewsPost


def format_post(post: NewsPost) -> str:
    def hash_tagged(value: str) -> str:
        return f"#{value.strip().replace(' ', '_')}"

    parts = [
        f'{["", "⚠️ "][post.important]}<a href="{post.link}"><b>{post.title}</b></a>',
        f"{post.description}\n\n{post.posted_at:%d.%m.%Y %H:%M}",
        " ".join(hash_tagged(i) for i in [post.category, *post.keywords]),
    ]
    return "\n\n".join(parts)


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

    @staticmethod
    def split_message(text: str, max_length: int = 4096) -> list[str]:
        if len(text) <= max_length:
            return [text]
        
        parts: list[str] = []
        while text:
            if len(text) <= max_length:
                parts.append(text)
                break
                
            # Try to split by newlines first
            split_idx = text[:max_length].rfind('\n')
            if split_idx == -1:
                # If no newlines, try to split by dots (end of sentences)
                split_idx = text[:max_length].rfind('.')
                if split_idx == -1:
                    # If no good splitting point, just split at max length
                    split_idx = max_length - 1
            
            parts.append(text[:split_idx + 1])
            text = text[split_idx + 1:].lstrip()
        
        return parts

    async def send_post(self, post: NewsPost) -> None:
        message = format_post(post)
        parts = self.split_message(message)
        
        for part in parts:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=part,
            )

    async def start(self) -> None:
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
