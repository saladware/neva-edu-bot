import asyncio
import sys

from src.bot import get_bot
from src.config import get_settings
from src.parser import Bs4NewsParser
from src.service import Service


async def main() -> None:
    settings = get_settings()
    bot = await get_bot(settings.bot_token)
    service = Service(bot=bot, chat_id=settings.chat_id, parser=Bs4NewsParser())
    await service.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
