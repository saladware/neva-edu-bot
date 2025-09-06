import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile
from aiohttp import ClientSession

from src.parser import BaseNewsParser
from src.types import NewsPost
from src.storage import Storage

logger = logging.getLogger(__name__)


# Константы для хранения истории постов
MAX_POSTS_COUNT = 100  # Максимальное количество постов в истории
MAX_POST_AGE_DAYS = 3  # Максимальный возраст поста в днях
MAX_STORAGE_SIZE_MB = 10  # Максимальный размер файла истории в МБ


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
        self.parser = parser
        self.storage_path = Path("data") / "sent_posts.json"
        self.storage = Storage(self.storage_path)
        self._rotate_storage_if_needed()
        self.current_posts: list[NewsPost] = self.storage.load(NewsPost)

    def _rotate_storage_if_needed(self) -> None:
        """Создает резервную копию и обновляет файл истории, если он слишком большой"""
        if not self.storage_path.exists():
            return

        # Проверяем размер файла в МБ
        size_mb = self.storage_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_STORAGE_SIZE_MB:
            # Загружаем текущие посты
            current_posts = self.storage.load(NewsPost)

            # Фильтруем и оставляем только актуальные посты
            now = datetime.now()
            current_posts = [
                post
                for post in current_posts
                if (now - post.posted_at).days <= MAX_POST_AGE_DAYS
            ]
            current_posts.sort(key=lambda post: post.posted_at, reverse=True)
            current_posts = current_posts[:MAX_POSTS_COUNT]

            # Создаем резервную копию с временной меткой
            backup_path = self.storage_path.with_suffix(
                f".{datetime.now():%Y%m%d_%H%M%S}.backup.json"
            )
            shutil.copy2(self.storage_path, backup_path)

            # Сохраняем отфильтрованные актуальные посты
            self.storage.save(current_posts)

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
            split_idx = text[:max_length].rfind("\n")
            if split_idx == -1:
                # If no newlines, try to split by dots (end of sentences)
                split_idx = text[:max_length].rfind(".")
                if split_idx == -1:
                    # If no good splitting point, just split at max length
                    split_idx = max_length - 1

            parts.append(text[: split_idx + 1])
            text = text[split_idx + 1 :].lstrip()

        return parts

    async def _download_file(self, url: str) -> tuple[bytes, str] | None:
        """Скачивает файл по URL. Возвращает (содержимое, расширение) или None при ошибке"""
        try:
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if not response.ok:
                        logger.error(f"Failed to download file from {url}: {response.status}")
                        return None
                        
                    # Пытаемся получить имя файла из заголовков
                    content_disposition = response.headers.get('Content-Disposition', '')
                    if 'filename=' in content_disposition:
                        # Извлекаем имя файла из content-disposition
                        filename_part = content_disposition.split('filename=')[-1]
                        # Убираем кавычки, точки с запятой и пробелы
                        filename = filename_part.split(';')[0].strip('"\' ')
                        extension = Path(filename).suffix
                        if extension:
                            return await response.read(), extension
                            
                    # Если не нашли в заголовках, пробуем из последнего сегмента URL
                    extension = Path(url.split('/')[-1]).suffix
                    if not extension:
                        # Если расширения нет, возвращаем как есть
                        extension = ''
                        
                    return await response.read(), extension
                    
        except Exception as e:
            logger.error(f"Failed to download file from {url}: {e}")
            return None

    async def send_post(self, post: NewsPost) -> bool:
        """Отправляет пост в Telegram. Возвращает True если отправка успешна."""
        try:
            # Отправляем основной текст
            message = format_post(post)
            parts = self.split_message(message)
            
            for part in parts:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=part,
                    parse_mode="HTML"
                )

            # Отправляем прикрепленные файлы
            if post.attachments:
                for attachment in post.attachments:
                    # Скачиваем файл
                    result = await self._download_file(attachment.url)
                    if result is None:
                        logger.warning(f"Skipping attachment {attachment.title!r} due to download failure")
                        continue
                    
                    file_content, extension = result
                    try:
                        # Формируем имя файла с расширением
                        filename = attachment.title
                        if extension and not filename.endswith(extension):
                            filename = f"{filename}{extension}"
                            
                        # Отправляем как документ
                        await self.bot.send_document(
                            chat_id=self.chat_id,
                            document=BufferedInputFile(
                                file_content,
                                filename=filename
                            )
                        )
                    except Exception as e:
                        logger.error(f"Failed to send attachment {attachment.title!r}: {e}")
                        continue

            return True
        except TelegramAPIError as e:
            logger.error(f"Failed to send post {post.title!r}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while sending post {post.title!r}: {e}")
            return False

    async def __aenter__(self) -> "Service":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Очистка ресурсов при выходе из контекста"""
        await self.bot.session.close()
        self.storage.cleanup_old_backups()

    async def start(self) -> None:
        try:
            while True:
                try:
                    actual_posts = await self.parser.parse()
                except Exception as e:
                    logger.error(f"Parser error: {e}")
                    await asyncio.sleep(30)
                    continue

                try:
                    unpublished_posts = self.get_unpublished_posts(
                        self.current_posts, actual_posts
                    )
                    if unpublished_posts:
                        successfully_sent_posts: list[NewsPost] = []

                        # Сортируем посты для отправки
                        sorted_posts = sorted(
                            unpublished_posts,
                            key=lambda post: (not post.important, post.posted_at),
                        )

                        # Пытаемся отправить каждый пост
                        for post in sorted_posts:
                            if await self.send_post(post):
                                successfully_sent_posts.append(post)
                                await asyncio.sleep(0.5)
                            else:
                                logger.warning(
                                    f"Skipping post {post.title!r} due to send failure"
                                )

                        if successfully_sent_posts:
                            self.current_posts.extend(successfully_sent_posts)
                            # Оставляем только свежие посты
                            now = datetime.now()
                            self.current_posts = [
                                post
                                for post in self.current_posts
                                if (now - post.posted_at).days <= MAX_POST_AGE_DAYS
                            ]
                            # Сортируем по дате перед сохранением
                            self.current_posts.sort(
                                key=lambda post: post.posted_at, reverse=True
                            )
                            # Ограничиваем количество хранимых постов
                            self.current_posts = self.current_posts[:MAX_POSTS_COUNT]

                            try:
                                self.storage.save(self.current_posts)
                            except Exception as e:
                                logger.error(f"Failed to save posts: {e}")

                except Exception as e:
                    logger.error(f"Error in main loop: {e}")

                await asyncio.sleep(30)

        except asyncio.CancelledError:
            logger.info("Service shutdown initiated")
            raise
        except Exception as e:
            logger.error(f"Fatal error in service: {e}")
            raise
        finally:
            await self.__aexit__(None, None, None)
