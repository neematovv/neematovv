from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.db_manager import db_manager
from handlers.subscription import check_user_subscription, get_subscription_keyboard as build_sub_kb
from utils.config import config
import urllib.parse

user_router = Router()

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎬 Kinolar Ro'yxati"), KeyboardButton(text="👤 Profilim")],
        [KeyboardButton(text="⭐ Saralanganlar"), KeyboardButton(text="❓ Yordam")]
    ], resize_keyboard=True)

async def send_main_menu(message: Message):
    await message.answer(
        text="👋 Xush kelibsiz! Kino nomini yozing yoki pastdagi tugmalardan foydalaning. 🍿",
        reply_markup=get_main_menu_keyboard()
    )

@user_router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    await db_manager.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    args = message.text.split()
    if len(args) > 1:
        clean_code = urllib.parse.unquote(args[1])
        movie = await db_manager.get_movie_by_code(clean_code)
        if not movie:
            await message.answer("❌ Kechirasiz, bunday kod ostida kino yoki serial topilmadi!")
            return
        from handlers.movie import build_episode_matrix, build_movie_caption, build_share_keyboard
        episodes = await db_manager.get_episodes(clean_code)
        await db_manager.increment_views(clean_code)
        caption = build_movie_caption(movie, episodes, clean_code)
        kb = build_episode_matrix(clean_code, episodes, movie) if episodes else build_share_keyboard(clean_code, movie)
        await message.answer(caption, parse_mode="HTML", reply_markup=kb)
        return
    if not await check_user_subscription(bot, message.from_user.id):
        kb = await build_sub_kb(bot, message.from_user.id)
        await message.answer(
            text=f"⚠️ Botdan foydalanish uchun kanallarga obuna bo'ling!",
            reply_markup=kb
        )
        return
    await send_main_menu(message)

@user_router.message(Command("help"))
@user_router.message(F.text == "❓ Yordam")
async def cmd_help(message: Message, bot: Bot):
    if not await check_user_subscription(bot, message.from_user.id): return
    help_text = (
        "📖 <b>Kino Bot Qo'llanmasi</b>\n\n"
        "• Kino kodini yozing yoki • <b>🎬 Kinolar Ro'yxati</b> tugmasini bosing yoki kino kodini yuboring.\n"
        "• Bot bazadan kinoni topib, epizodlar ro'yxatini ko'rsatadi.\n"
        "• Epizod tugmasini bosib, videoni tomosha qiling.\n"
        "• <b>⭐ Saralanganlar</b> orqali sevimli kinolaringizni saqlang.\n"
        "• <b>📢 Do'stlarga Ulashish</b> tugmasi orqali do'stlaringizga yuboring."
    )
    await message.answer(help_text, parse_mode="HTML")

@user_router.message(Command("profile"))
@user_router.message(F.text == "👤 Profilim")
async def view_profile(message: Message, bot: Bot):
    if not await check_user_subscription(bot, message.from_user.id): return
    fav_count = await db_manager.get_favorite_count(message.from_user.id)
    profile_text = (
        "👤 <b>Mening Profilim</b>\n\n"
        f"• <b>ID:</b> <code>{message.from_user.id}</code>\n"
        f"• <b>Ism:</b> {message.from_user.full_name}\n"
        f"• <b>Username:</b> @{message.from_user.username or 'N/A'}\n"
        f"• <b>Holat:</b> Faol Obunachi ✅\n"
        f"• <b>⭐ Saralanganlar:</b> {fav_count} ta kino"
    )
    await message.answer(profile_text, parse_mode="HTML")

# ===== FAVORITES HANDLER =====
@user_router.message(Command("favorites"))
@user_router.message(F.text == "⭐ Saralanganlar")
async def show_favorites(message: Message, bot: Bot):
    if not await check_user_subscription(bot, message.from_user.id):
        kb = await build_sub_kb(bot, message.from_user.id)
        await message.answer("⚠️ Avval kanallarga obuna bo'ling!", reply_markup=kb)
        return
    user_id = message.from_user.id
    favorites = await db_manager.get_user_favorites(user_id)
    if not favorites:
        await message.answer("⭐ Sizning saralanganlaringiz hozircha bo'sh. Kino ko'rish vaqtida ⭐ tugmasini bosib qo'shing!")
        return
    txt = "⭐ <b>Saralanganlarim</b>\n\n"
    keyboard = []
    for fav in favorites:
        txt += f"• {fav['title']}\n"
        keyboard.append([InlineKeyboardButton(text=f"🎬 {fav['title']}", callback_data=f"nav_movie_{fav['movie_code']}")])
    keyboard.append([InlineKeyboardButton(text="❌ Saralanganlarni tozalash", callback_data="fav_clear_all")])
    await message.answer(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@user_router.callback_query(F.data == "fav_clear_all")
async def clear_all_favorites(callback: CallbackQuery):
    user_id = callback.from_user.id
    favorites = await db_manager.get_user_favorites(user_id)
    cleared = 0
    for fav in favorites:
        if await db_manager.remove_favorite(user_id, fav['movie_code']):
            cleared += 1
    await callback.answer(f"✅ {cleared} ta kino saralanganlardan o'chirildi!", show_alert=True)
    await callback.message.edit_text("⭐ Saralanganlar bo'sh. Kino ko'rish vaqtida ⭐ tugmasini bosib qo'shing!")
