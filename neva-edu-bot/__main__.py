import asyncio

from .bot import get_bot
from .service import Service
from .parser import Bs4NewsParser
from .config import get_settings


async def main():
    settings = get_settings()
    bot = await get_bot(settings.bot_token)
    service = Service(bot=bot, chat_id=settings.chat_id, parser=Bs4NewsParser())
    await service.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        exit(0)
