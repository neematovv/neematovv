import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiohttp import web
from utils.config import config
from database.db_manager import db_manager
from handlers.user import user_router
from handlers.movie import movie_router
from handlers.subscription import subscription_router
from handlers.admin import admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Render serverni uyg'oq tutish uchun kichik veb-sahifa funksiyasi
async def handle_home(request):
    return web.Response(text="Bot is running smoothly!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_home)
    
    # Render avtomatik ravishda PORT muhit o'zgaruvchisini taqdim etadi
    port = int(os.environ.get("PORT", 8080))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    logger.info(f"Veb-server {port}-portda ishga tushmoqda...")
    await site.start()

async def main():
    await db_manager.init_db()

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    # Linear Router sequence logic execution layers
    dp.include_router(admin_router)
    dp.include_router(subscription_router)
    dp.include_router(user_router)
    dp.include_router(movie_router)

    logger.info("Kino Bot (O'zbek tili) ishga tushmoqda...")
    
    # Veb-serverni fonda (background) ishga tushiramiz
    asyncio.create_task(start_web_server())
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Critical execution error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution gracefully terminated.")
