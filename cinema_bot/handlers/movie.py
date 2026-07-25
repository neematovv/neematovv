import logging
from aiogram import Router, Bot, F
from aiogram.filters import StateFilter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.db_manager import db_manager
from handlers.subscription import check_user_subscription, get_subscription_keyboard as build_sub_kb
from utils.states import SearchStates
from utils.config import config

logger = logging.getLogger(__name__)
movie_router = Router()

def build_movie_caption(movie: dict, episodes: list, movie_code: str) -> str:
    """Build standardized Uzbek HTML movie caption with Unicode box characters."""
    bot_username = config.BOT_USERNAME.replace("@", "").strip()
    channel_username = config.CHANNEL_USERNAME.replace("@", "").strip()
    total_episodes = len(episodes)
    status_icon = "✅" if movie.get('status', 'Tugallangan') == "Tugallangan" else "🔄"
    return (
        f"🎬 <b>{movie['title']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"├ <b>Holati:</b> {total_episodes} ta qism\n"
        f"├ <b>Sifat:</b> {movie.get('quality', '1080p HD')}\n"
        f"├ <b>Janri:</b> {movie['genre']}\n"
        f"├ <b>Davlat:</b> {movie.get('country', 'Noma\'lum')}\n"
        f"├ <b>Tili:</b> {movie.get('language', 'O\'zbek tili')}\n"
        f"├ <b>Yili:</b> {movie['year']}\n"
        f"├ <b>Davomiyligi:</b> {total_episodes} qism\n"
        f"└ {status_icon} <b>IMDb:</b> {movie.get('status', 'Tugallangan')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>Bot:</b> @{bot_username}\n"
        f"🆔 <b>Kino ID:</b> <code>{movie_code}</code>\n"
        f"🔗 <b>Link:</b> https://t.me/{bot_username}?start={movie_code}"
    )

def build_episode_matrix(movie_code: str, episodes: list, movie: dict = None) -> InlineKeyboardMarkup:
    """Build episode button matrix. Auto-wraps episodes, share button alone on last row."""
    kb_buttons = []
    for ep in episodes:
        kb_buttons.append(
            InlineKeyboardButton(
                text=f"🍿 {ep['episode_number']}-Qism",
                callback_data=f"ep_{movie_code}_{ep['episode_number']}"
            )
        )
    keyboard = [kb_buttons[i:i+5] for i in range(0, len(kb_buttons), 5)]
    if movie and movie.get('trailer_url'):
        keyboard.append([InlineKeyboardButton(text="🎥 Trailer", url=movie['trailer_url'])])
    bot_username = config.BOT_USERNAME.replace("@", "").strip()
    share_url = f"https://t.me/{bot_username}?start={movie_code}"
    keyboard.append([InlineKeyboardButton(text="📢 Do'stlarga Ulashish", url=share_url)])
    # Add favorites button
    keyboard.append([InlineKeyboardButton(text="⭐ Saralanganlarga qo'shish", callback_data=f"fav_add_{movie_code}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_category_keyboard(categories: list = None) -> InlineKeyboardMarkup:
    """Build dynamic category selection keyboard."""
    if not categories:
        categories = ["🎬 Kinolar", "📺 Seriallar", "🎞 Multfilmlar", "🎌 Anime", "🇰🇷 Koreys Dramalari", "🌍 Boshqalar"]
    keyboard = []
    row = []
    for cat in categories:
        row.append(InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_movie_page_keyboard(category: str, page: int, pages: int, movies: list) -> InlineKeyboardMarkup:
    """Build movie list with pagination for a category."""
    keyboard = []
    row = []
    for m in movies:
        row.append(InlineKeyboardButton(text=f"🎬 {m['title']}", callback_data=f"nav_movie_{m['code']}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"pg_{category}_{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page}/{pages}", callback_data="noop"))
    if page < pages:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"pg_{category}_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton(text="🔙 Kategoriyalar", callback_data="back_categories")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_share_keyboard(movie_code: str, movie: dict = None) -> InlineKeyboardMarkup:
    """Build keyboard for movies with no episodes (just share + optional trailer)."""
    bot_username = config.BOT_USERNAME.replace("@", "").strip()
    share_url = f"https://t.me/{bot_username}?start={movie_code}"
    kb_buttons = []
    if movie and movie.get('trailer_url'):
        kb_buttons.append([InlineKeyboardButton(text="🎥 Treylerni Ko'rish", url=movie['trailer_url'])])
    # If no episodes exist, show "Kinoni Ko'rish" button that alerts
    kb_buttons.append([InlineKeyboardButton(text="🎬 Kinoni Ko'rish", callback_data=f"movie_not_ready_{movie_code}")])
    kb_buttons.append([InlineKeyboardButton(text="📢 Do'stlarga Ulashish", url=share_url)])
    # Add favorites button
    kb_buttons.append([InlineKeyboardButton(text="⭐ Saralanganlarga qo'shish", callback_data=f"fav_add_{movie_code}")])
    return InlineKeyboardMarkup(inline_keyboard=kb_buttons)

@movie_router.message(F.text == "🎬 Kino Izlash")
async def init_search_flow(message: Message, bot: Bot, state: FSMContext):
    if not await check_user_subscription(bot, message.from_user.id):
        return
    await state.set_state(SearchStates.waiting_for_query)
    await message.answer("🔍 Qidirmoqchi bo'lgan **Kino kodini** yoki nomini yozing:")

@movie_router.message(F.text == "🎬 Kinolar Ro'yxati")
async def show_movie_catalog(message: Message, bot: Bot):
    if not await check_user_subscription(bot, message.from_user.id):
        kb = await build_sub_kb(bot, message.from_user.id)
        await message.answer("⚠️ Avval kanallarga obuna bo'ling!", reply_markup=kb)
        return
    categories = await db_manager.get_categories()
    if not categories:
        await message.answer("📁 Kechirasiz, hozirda bot bazasida hech qanday kino yoki serial mavjud emas!")
        return
    await message.answer(
        "🎬 <b>Kategoriyalar</b>\n\nKerakli kategoriyani tanlang:",
        parse_mode="HTML",
        reply_markup=build_category_keyboard(categories)
    )

@movie_router.callback_query(F.data.startswith("cat_"))
async def select_category(callback: CallbackQuery):
    category = callback.data.replace("cat_", "", 1)
    await callback.answer()
    result = await db_manager.get_movies_by_category(category, page=1)
    if not result["movies"]:
        await callback.message.edit_text("Bu kategoriyada hozircha kino mavjud emas.")
        return
    await callback.message.edit_text(
        f"📂 <b>{category}</b>",
        parse_mode="HTML",
        reply_markup=build_movie_page_keyboard(category, result["page"], result["pages"], result["movies"])
    )

@movie_router.callback_query(F.data.startswith("pg_"))
async def paginate_movies(callback: CallbackQuery):
    parts = callback.data.split("_", 2)
    if len(parts) < 3:
        await callback.answer("Xatolik", show_alert=True)
        return
    category = parts[1]
    page = int(parts[2])
    await callback.answer()
    result = await db_manager.get_movies_by_category(category, page=page)
    if not result["movies"]:
        await callback.answer("Bu sahifada kino mavjud emas.", show_alert=True)
        return
    await callback.message.edit_text(
        f"📂 <b>{category}</b>",
        parse_mode="HTML",
        reply_markup=build_movie_page_keyboard(category, result["page"], result["pages"], result["movies"])
    )

@movie_router.callback_query(F.data == "back_categories")
async def back_to_categories(callback: CallbackQuery):
    await callback.answer()
    categories = await db_manager.get_categories()
    if not categories:
        await callback.message.edit_text("📁 Kechirasiz, hozirda bot bazasida hech qanday kino yoki serial mavjud emas!")
        return
    await callback.message.edit_text(
        "🎬 <b>Kategoriyalar</b>\n\nKerakli kategoriyani tanlang:",
        parse_mode="HTML",
        reply_markup=build_category_keyboard(categories)
    )

@movie_router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()

@movie_router.message(SearchStates.waiting_for_query)
@movie_router.message(F.text, StateFilter(None))
async def process_movie_search(message: Message, bot: Bot, state: FSMContext):
    menu_buttons = {"🎬 Kinolar Ro'yxati", "🎬 Kino Izlash", "👤 Profilim", "❓ Yordam", "⭐ Saralanganlar"}
    if message.text in menu_buttons:
        await state.clear()
        from handlers.user import view_profile, cmd_help, show_favorites
        if message.text == "👤 Profilim":
            await view_profile(message, bot)
        elif message.text == "❓ Yordam":
            await cmd_help(message, bot)
        elif message.text == "🎬 Kino Izlash":
            await init_search_flow(message, bot, state)
        elif message.text == "🎬 Kinolar Ro'yxati":
            await show_movie_catalog(message, bot)
        elif message.text == "⭐ Saralanganlar":
            await show_favorites(message, bot)
        return
    if not await check_user_subscription(bot, message.from_user.id):
        kb = await build_sub_kb(bot, message.from_user.id)
        await message.answer("⚠️ Avval kanallarga obuna bo'ling!", reply_markup=kb)
        return
    query = message.text.strip()
    await state.clear()
    loading = await message.answer("⏳ <i>Qidirilmoqda...</i>", parse_mode="HTML")
    movie = await db_manager.get_movie_by_code(query)
    if movie:
        episodes = await db_manager.get_episodes(query)
        await db_manager.increment_views(query)
        await db_manager.record_view(query)
        await loading.delete()
        caption = build_movie_caption(movie, episodes, query)
        kb = build_episode_matrix(query, episodes, movie) if episodes else build_share_keyboard(query, movie)
        await message.answer(caption, parse_mode="HTML", reply_markup=kb)
        return
    results = await db_manager.search_movie(query)
    await loading.delete()
    if not results:
        await message.answer("❌ Kechirasiz, bunday kino yoki serial topilmadi! Kino kodini yoki nomini to'liq yozib ko'ring.")
        return
    txt = f"🔍 <b>Qidiruv natijalari:</b> <code>{query}</code>\n\n"
    keyboard = []
    row = []
    for r in results:
        row.append(InlineKeyboardButton(text=f"🎬 {r['title']}", callback_data=f"nav_movie_{r['code']}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    await message.answer(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@movie_router.message(F.chat.type.in_({"group", "supergroup"}), F.text)
async def group_movie_code_catcher(message: Message, bot: Bot):
    code = message.text.strip()
    if " " in code or len(code) < 2:
        return
    movie = await db_manager.get_movie_by_code(code)
    if not movie:
        return
    episodes = await db_manager.get_episodes(code)
    bot_username = config.BOT_USERNAME.replace("@", "").strip()
    watch_url = f"https://t.me/{bot_username}?start={code}"
    caption = build_movie_caption(movie, episodes, code)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Tomosha Qilish ✨", url=watch_url)]
    ])
    try:
        await message.reply(caption, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error(f"Guruhda kino kodiga javob berish xatosi: {e}")

@movie_router.callback_query(F.data.startswith("ep_"))
async def callback_play_episode(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.message.answer("❌ Xatolik yuz berdi.")
        return
    movie_code = parts[1]
    ep_number = int(parts[2])
    episode = await db_manager.get_episode(movie_code, ep_number)
    if not episode or not episode.get("video_file_id"):
        await callback.message.answer("❌ Bu epizod uchun video topilmadi.")
        return
    movie = await db_manager.get_movie_by_code(movie_code)
    title = movie['title'] if movie else movie_code
    caption = f"🎬 <b>{title}</b> — <b>{ep_number}-Qism</b>"
    try:
        await bot.send_video(
            chat_id=callback.from_user.id,
            video=episode["video_file_id"],
            caption=caption,
            parse_mode="HTML",
            supports_streaming=True
        )
    except Exception as e:
        logger.error(f"Video jo'natish xatosi: {e}")
        await callback.message.answer("❌ Videoni yuborishda xatolik yuz berdi.")

@movie_router.callback_query(F.data.startswith("nav_movie_"))
async def open_movie(callback: CallbackQuery):
    movie_code = callback.data.replace("nav_movie_", "")
    await callback.message.delete()
    movie = await db_manager.get_movie_by_code(movie_code)
    if not movie:
        await callback.answer("Kino topilmadi", show_alert=True)
        return
    episodes = await db_manager.get_episodes(movie_code)
    await db_manager.increment_views(movie_code)
    await db_manager.record_view(movie_code)
    caption = build_movie_caption(movie, episodes, movie_code)
    keyboard = build_episode_matrix(movie_code, episodes, movie)
    await callback.message.answer(caption, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

# ===== SMART TRAILER & MOVIE SELECTION =====
@movie_router.callback_query(F.data.startswith("movie_not_ready_"))
async def movie_not_ready(callback: CallbackQuery):
    await callback.answer(
        "Ushbu kino hali ma'lumotlar bazasiga joylanmagan yoki premyera qilinmagan!",
        show_alert=True
    )

# ===== FAVORITES SYSTEM =====
@movie_router.callback_query(F.data.startswith("fav_add_"))
async def add_to_favorites(callback: CallbackQuery):
    movie_code = callback.data.replace("fav_add_", "")
    user_id = callback.from_user.id
    is_fav = await db_manager.is_favorite(user_id, movie_code)
    if is_fav:
        await callback.answer("Bu kino allaqachon saralanganlarda mavjud!", show_alert=True)
        return
    ok = await db_manager.add_favorite(user_id, movie_code)
    if ok:
        await callback.answer("⭐ Saralanganlarga qo'shildi!", show_alert=True)
        # Update the button to show remove option
        try:
            movie = await db_manager.get_movie_by_code(movie_code)
            episodes = await db_manager.get_episodes(movie_code)
            caption = build_movie_caption(movie, episodes, movie_code)
            if episodes:
                kb = build_episode_matrix(movie_code, episodes, movie)
            else:
                kb = build_share_keyboard(movie_code, movie)
            # Replace the last button row with remove favorite
            kb.inline_keyboard[-1] = [InlineKeyboardButton(text="❌ Saralanganlardan o'chirish", callback_data=f"fav_remove_{movie_code}")]
            await callback.message.edit_reply_markup(reply_markup=kb)
        except Exception as e:
            logger.error(f"Favorites button update error: {e}")
    else:
        await callback.answer("Xatolik yuz berdi!", show_alert=True)

@movie_router.callback_query(F.data.startswith("fav_remove_"))
async def remove_from_favorites(callback: CallbackQuery):
    movie_code = callback.data.replace("fav_remove_", "")
    user_id = callback.from_user.id
    ok = await db_manager.remove_favorite(user_id, movie_code)
    if ok:
        await callback.answer("❌ Saralanganlardan o'chirildi!", show_alert=True)
        # Update the button back to add
        try:
            movie = await db_manager.get_movie_by_code(movie_code)
            episodes = await db_manager.get_episodes(movie_code)
            if episodes:
                kb = build_episode_matrix(movie_code, episodes, movie)
            else:
                kb = build_share_keyboard(movie_code, movie)
            await callback.message.edit_reply_markup(reply_markup=kb)
        except Exception as e:
            logger.error(f"Favorites button update error: {e}")
    else:
        await callback.answer("Xatolik yuz berdi!", show_alert=True)
