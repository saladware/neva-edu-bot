from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode


async def get_bot(token: str, *, skip_updates: bool = False) -> Bot:
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    if skip_updates:
        await bot.delete_webhook(drop_pending_updates=True)
    return bot
