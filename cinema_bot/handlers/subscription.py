from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db_manager import db_manager
from utils.config import config
import logging

logger = logging.getLogger(__name__)
subscription_router = Router()

async def check_user_subscription(bot: Bot, user_id: int) -> bool:
    if user_id in config.admin_list:
        return True
    channels = await db_manager.get_required_channels()
    if not channels:
        return True
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["channel_id"], user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            logger.error(f"Obuna tekshiruvi xatosi ({ch.get('channel_username', ch['channel_id'])}): {e}")
            return False
    return True

async def get_missing_channels(bot: Bot, user_id: int) -> list:
    channels = await db_manager.get_required_channels()
    missing = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["channel_id"], user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                missing.append(ch)
        except Exception:
            missing.append(ch)
    return missing

async def get_subscription_keyboard(bot: Bot, user_id: int) -> InlineKeyboardMarkup:
    missing = await get_missing_channels(bot, user_id)
    kb = []
    for ch in missing:
        username = ch.get("channel_username", "")
        if username:
            url = f"https://t.me/{username.lstrip('@')}"
        else:
            url = f"https://t.me/c/{str(ch['channel_id']).replace('-100', '')}"
        kb.append([InlineKeyboardButton(text=f"📢 {username}" if username else f"📢 {ch['channel_title'] or ch['channel_id']}", url=url)])
    kb.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub_status")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@subscription_router.callback_query(F.data == "check_sub_status")
async def process_check_subscription(callback: CallbackQuery, bot: Bot):
    if await check_user_subscription(bot, callback.from_user.id):
        try:
            await callback.answer("Obuna tasdiqlandi! Xush kelibsiz 🎉", show_alert=True)
            await callback.message.delete()
        except Exception:
            pass
        from handlers.user import send_main_menu
        await send_main_menu(callback.message)
    else:
        await callback.answer("❌ Siz hali barcha kanallarga obuna bo'lmagansiz! Iltimos avval kanallarga qo'shiling.", show_alert=True)
