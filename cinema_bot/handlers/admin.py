import asyncio
import logging
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from database.db_manager import db_manager
from utils.config import config
from utils.states import AdminStates

logger = logging.getLogger(__name__)
admin_router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in config.admin_list

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Bot Statistikasi", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Reklama Tarqatish", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="➕ Yangi Kino/Serial Qo'shish", callback_data="admin_add_movie")],
        [InlineKeyboardButton(text="🎞️ Qism (Epizod) Qo'shish", callback_data="admin_add_episode")],
        [InlineKeyboardButton(text="❌ Kinoni O'chirish", callback_data="admin_del_movie")],
        [InlineKeyboardButton(text="✏️ Kino/Serialni Tahrirlash", callback_data="admin_edit_movie")],
        [InlineKeyboardButton(text="🖼 Poster Qo'shish", callback_data="admin_add_poster")],
        [InlineKeyboardButton(text="🎥 Trailer Qo'shish", callback_data="admin_add_trailer")],
        [InlineKeyboardButton(text="🗑 Epizodni O'chirish", callback_data="admin_del_episode")],
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin_settings")]
    ])

@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ruxsat yo'q. Faqat adminlar uchun.")
        return
    await message.answer("🛠️ <b>Admin Panel</b>", parse_mode="HTML", reply_markup=admin_menu_kb())

@admin_router.callback_query(F.data == "admin_menu_home")
async def callback_admin_home(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("🛠️ <b>Admin Panel</b>", parse_mode="HTML", reply_markup=admin_menu_kb())

# ===== 1. STATISTIKA =====
@admin_router.callback_query(F.data == "admin_stats")
async def display_admin_stats(callback: CallbackQuery):
    await callback.answer()
    total_users = await db_manager.get_user_count()
    today_users = await db_manager.get_today_users()
    total_searches = await db_manager.get_total_searches()
    total_movies = await db_manager.get_movie_count()
    total_episodes = await db_manager.get_total_episode_count()
    most_viewed = await db_manager.get_most_viewed_movie()
    today_views = await db_manager.get_today_views()
    avg_eps = await db_manager.get_avg_episodes_per_movie()
    db_size_kb = await db_manager.get_db_size_kb()
    db_ping = await db_manager.ping()
    text = (
        "📊 <b>Bot Statistikasi</b>\n\n"
        f"👥 <b>Foydalanuvchilar:</b> {total_users}\n"
        f"🆕 <b>Bugungi foydalanuvchilar:</b> {today_users}\n"
        f"🎬 <b>Kinolar/Seriallar:</b> {total_movies}\n"
        f"🎞 <b>Epizodlar:</b> {total_episodes}\n"
        f"📈 <b>O'rtacha epizod/kino:</b> {avg_eps}\n"
        f"👁 <b>Ko'rishlar:</b> {total_searches}\n"
        f"📅 <b>Bugungi ko'rishlar:</b> {today_views}\n"
        f"🏆 <b>Eng ko'p ko'rilgan:</b> {most_viewed}\n"
        f"💾 <b>Ma'lumotlar bazasi:</b> {db_size_kb} KB\n"
        f"⏱ <b>Database Ping:</b> {db_ping}ms"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu_home")]])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

# ===== 2. REKLAMA TARQATISH =====
@admin_router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()
    await callback.message.edit_text("📢 Reklama xabarini yuboring (matn, rasm yoki video):")

@admin_router.message(AdminStates.waiting_for_broadcast)
async def capture_broadcast(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id if message.photo else None
    video_id = message.video.file_id if message.video else None
    text = message.caption or message.text or ""
    await state.update_data(text=text, photo=photo_id, video=video_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Tarqatish", callback_data="bc_confirm")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_menu_home")]
    ])
    await message.answer("⚠️ Reklama tarqatilsinmi?", reply_markup=kb)

@admin_router.callback_query(F.data == "bc_confirm")
async def fire_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    await callback.answer()
    await callback.message.edit_text("⏳ Reklama tarqatilmoqda...")
    users = await db_manager.get_all_users()
    sent, blocked, failed = 0, 0, 0
    for uid in users:
        try:
            if data.get('photo'):
                await bot.send_photo(chat_id=uid, photo=data['photo'], caption=data.get('text', ''))
            elif data.get('video'):
                await bot.send_video(chat_id=uid, video=data['video'], caption=data.get('text', ''))
            else:
                await bot.send_message(chat_id=uid, text=data.get('text', ''))
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            if "blocked" in str(e).lower(): blocked += 1
            else: failed += 1
    await callback.message.answer(f"📊 <b>Tarqatish yakunlandi:</b>\n\n✅ Yuborildi: {sent}\n🚫 Bloklangan: {blocked}\n❌ Xatolik: {failed}", parse_mode="HTML")
    logger.info(f"Admin broadcast sent. Total: {sent}, Blocked: {blocked}, Failed: {failed}")

# ===== 3. YANGI KINO/SERIAL QO'SHISH (8 steps) =====
def category_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎬 Kinolar"), KeyboardButton(text="📺 Seriallar")],
        [KeyboardButton(text="🧸 Multfilmlar"), KeyboardButton(text="🎥 Trillerlar")],
        [KeyboardButton(text="🇰🇷 Koreys Dramalari"), KeyboardButton(text="🌍 Boshqalar")]
    ], resize_keyboard=True)

@admin_router.callback_query(F.data == "admin_add_movie")
async def start_add_movie(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_movie_code)
    await callback.answer()
    await callback.message.edit_text("🔑 <b>1/8:</b> Kino/Serial kodini kiriting (bo'shliqsiz, noyob):", parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_movie_code)
async def add_movie_code(message: Message, state: FSMContext):
    code = message.text.strip().replace(" ", "")
    await state.update_data(movie_code=code)
    await state.set_state(AdminStates.waiting_for_movie_title)
    await message.answer("🎬 <b>2/8:</b> Kino/Serial nomini kiriting:", parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_movie_title)
async def add_movie_title(message: Message, state: FSMContext):
    await state.update_data(movie_title=message.text.strip())
    await state.set_state(AdminStates.waiting_for_movie_description)
    await message.answer("📝 <b>3/8:</b> Kino/Serial tavsifini kiriting:", parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_movie_description)
async def add_movie_description(message: Message, state: FSMContext):
    await state.update_data(movie_desc=message.text.strip())
    await state.set_state(AdminStates.waiting_for_movie_genre)
    await message.answer("🎭 <b>4/8:</b> Kino/Serial janrini kiriting:", parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_movie_genre)
async def add_movie_genre(message: Message, state: FSMContext):
    await state.update_data(movie_genre=message.text.strip())
    await state.set_state(AdminStates.waiting_for_movie_year)
    await message.answer("📅 <b>5/8:</b> Kino/Serial yilini kiriting (faqat raqam):", parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_movie_year)
async def add_movie_year(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Iltimos, faqat raqam kiriting! Masalan: 2024")
        return
    year = int(message.text.strip())
    await state.update_data(movie_year=year)
    await state.set_state(AdminStates.waiting_for_movie_country)
    await message.answer("🌍 <b>6/8:</b> Davlatni kiriting (masalan: AQSH, Janubiy Koreya, O'zbekiston):", parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_movie_country)
async def add_movie_country(message: Message, state: FSMContext):
    country = message.text.strip()
    await state.update_data(movie_country=country)
    await state.set_state(AdminStates.waiting_for_movie_category)
    await message.answer(
        "📁 <b>7/8:</b> Kategoriyani tanlang:",
        parse_mode="HTML",
        reply_markup=category_reply_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_movie_category)
async def add_movie_category(message: Message, state: FSMContext):
    category = message.text.strip()
    await state.update_data(movie_category=category)
    await state.set_state(AdminStates.waiting_for_poster)
    # Remove category keyboard, go back to normal
    await message.answer("🖼️ <b>8/8:</b> Kino uchun Poster (Rasm) faylini yuklang yoki File ID matnini yuboring:", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())

@admin_router.message(AdminStates.waiting_for_poster)
async def add_movie_poster(message: Message, state: FSMContext, bot: Bot):
    poster_file_id = None
    if message.photo:
        poster_file_id = message.photo[-1].file_id
    elif message.text and len(message.text.strip()) > 5:
        poster_file_id = message.text.strip()
    if not poster_file_id:
        await message.answer("❌ Iltimos, rasm faylini yuklang yoki to'g'ri File ID yuboring!")
        return
    data = await state.get_data()
    ok = await db_manager.add_movie(
        code=data['movie_code'], title=data['movie_title'],
        description=data['movie_desc'], genre=data['movie_genre'],
        year=data['movie_year'], poster_file_id=poster_file_id,
        category=data.get('movie_category'),
        country=data.get('movie_country')
    )
    await state.clear()
    if ok:
        await message.answer(f"✅ <b>{data['movie_title']}</b> muvaffaqiyatli qo'shildi!\n\nEndi <b>🎞️ Qism (Epizod) Qo'shish</b> orqali epizodlarni qo'shing.", parse_mode="HTML")
        logger.info(f"Movie added: {data['movie_code']} - {data['movie_title']}")
    else:
        await message.answer("❌ Xatolik! Bunday kod allaqachon mavjud bo'lishi mumkin.", parse_mode="HTML")

# ===== 4. EPIZOD QO'SHISH =====
@admin_router.callback_query(F.data == "admin_add_episode")
async def start_add_episode(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_episode_movie_code)
    await callback.answer()
    await callback.message.edit_text("🎞️ <b>Epizod Qo'shish</b>\n\nKino/Serial kodini kiriting:", parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_episode_movie_code)
async def episode_movie_code(message: Message, state: FSMContext):
    code = message.text.strip().replace(" ", "")
    movie = await db_manager.get_movie_by_code(code)
    if not movie:
        await message.answer(f"❌ Kod <code>{code}</code> bo'yicha kino topilmadi! Avval kino qo'shing.", parse_mode="HTML")
        await state.clear()
        return
    await state.update_data(ep_movie_code=code, ep_movie_title=movie['title'])
    await state.set_state(AdminStates.waiting_for_episode_number)
    await message.answer(f"🎬 <b>{movie['title']}</b>\n\nEpizod raqamini kiriting (masalan: 1 yoki 12):", parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_episode_number)
async def episode_number(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Iltimos, faqat raqam kiriting!")
        return
    ep_num = int(message.text.strip())
    await state.update_data(ep_number=ep_num)
    await state.set_state(AdminStates.waiting_for_episode_video)
    await message.answer("📹 Video faylni yuklang yoki File ID matnini yuboring:", parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_episode_video)
async def episode_video(message: Message, state: FSMContext, bot: Bot):
    video_id = None
    if message.video:
        video_id = message.video.file_id
    elif message.text and len(message.text.strip()) > 10:
        video_id = message.text.strip()
    if not video_id:
        await message.answer("❌ Iltimos, video fayl yoki to'g'ri File ID yuboring!")
        return
    data = await state.get_data()
    ok = await db_manager.add_episode(data['ep_movie_code'], data['ep_number'], video_id)
    await state.clear()
    if not ok:
        await message.answer("❌ Xatolik! Bu epizod raqami allaqachon mavjud bo'lishi mumkin.", parse_mode="HTML")
        return
    await message.answer(f"✅ <b>{data['ep_movie_title']}</b> — {data['ep_number']}-qism muvaffaqiyatli qo'shildi!", parse_mode="HTML")
    logger.info(f"Episode added: {data['ep_movie_code']} - {data['ep_movie_title']} ep{data['ep_number']}")
    try:
        from handlers.movie import build_movie_caption, build_episode_matrix
        movie = await db_manager.get_movie_by_code(data['ep_movie_code'])
        episodes = await db_manager.get_episodes(data['ep_movie_code'])
        bot_username = config.BOT_USERNAME.replace("@", "").strip()
        caption = build_movie_caption(movie, episodes, data['ep_movie_code'])
        watch_link = f"https://t.me/{bot_username}?start={data['ep_movie_code']}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✨ Tomosha Qilish ✨", url=watch_link)]
        ])
        await bot.send_photo(chat_id=config.CHANNEL_ID, photo=movie['poster_file_id'], caption=caption, parse_mode="HTML", reply_markup=kb)
        logger.info(f"Channel post sent: {data['ep_movie_title']} — {data['ep_number']}-qism")
        await message.answer(
            f"✅ Kanalga post joylandi!\n\n"
            f"🎬 <b>{data['ep_movie_title']}</b> — <b>{data['ep_number']}-Qism</b>\n"
            f"🔘 Tugma: <b>✨ Tomosha Qilish ✨</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Kanalga post yuborish xatosi: {e}")

# ===== 5. KINONI O'CHIRISH =====
@admin_router.callback_query(F.data == "admin_del_movie")
async def start_delete_movie(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_delete_code)
    await callback.answer()
    await callback.message.edit_text("❌ O'chirish uchun kino kodini kiriting:")

@admin_router.message(AdminStates.waiting_for_delete_code)
async def delete_movie_code(message: Message, state: FSMContext):
    code = message.text.strip().replace(" ", "")
    movie = await db_manager.get_movie_by_code(code)
    if not movie:
        await message.answer(f"❌ Kod <code>{code}</code> bo'yicha kino topilmadi!", parse_mode="HTML")
        await state.clear()
        return
    await state.update_data(del_code=code, del_title=movie['title'])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data="del_confirm_yes")],
        [InlineKeyboardButton(text="❌ Yo'q, bekor qilish", callback_data="admin_menu_home")]
    ])
    await message.answer(f"⚠️ <b>{movie['title']}</b> va uning barcha epizodlarini o'chirmoqchimisiz?", parse_mode="HTML", reply_markup=kb)

@admin_router.callback_query(F.data == "del_confirm_yes")
async def confirm_delete_movie(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.answer()
    ok = await db_manager.delete_movie(data['del_code'])
    await state.clear()
    if ok:
        await callback.message.edit_text(f"✅ <b>{data['del_title']}</b> va barcha epizodlari o'chirildi!", parse_mode="HTML")
        logger.info(f"Movie deleted: {data['del_code']} - {data['del_title']}")
    else:
        await callback.message.edit_text("❌ Xatolik yuz berdi, kino topilmadi.")

# ===== 6. KINO/SERIALNI TAHRIRLASH =====
def build_edit_field_kb(movie_code: str) -> InlineKeyboardMarkup:
    fields = [
        ("🎬 Nomi", "title"),
        ("🎭 Janr", "genre"),
        ("📝 Tavsif", "description"),
        ("🔑 Kod", "code_meta"),
        ("📅 Yil", "year"),
        ("🌍 Davlat", "country"),
        ("🗣 Til", "language"),
        ("📺 Sifat", "quality"),
        ("✅ Status", "status"),
        ("📁 Kategoriya", "category"),
    ]
    kb = []
    for label, field in fields:
        kb.append([InlineKeyboardButton(text=label, callback_data=f"edit_field_{movie_code}_{field}")])
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu_home")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def format_movie_details(movie: dict) -> str:
    country = movie.get('country', "Noma'lum")
    language = movie.get('language', "O'zbek tili")
    desc = movie.get('description', "Yo'q")
    return (
        f"✏️ <b>{movie['title']}</b>\n\n"
        f"🎭 Janr: {movie['genre']}\n"
        f"📝 Tavsif: {desc}\n"
        f"📅 Yil: {movie['year']}\n"
        f"🌍 Davlat: {country}\n"
        f"🗣 Til: {language}\n"
        f"📺 Sifat: {movie.get('quality', '1080p HD')}\n"
        f"✅ Status: {movie.get('status', 'Tugallangan')}\n\n"
        f"Qaysi maydonni tahrirlaysiz?"
    )

@admin_router.callback_query(F.data == "admin_edit_movie")
async def start_edit_movie(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_admin_search)
    await callback.answer()
    await callback.message.edit_text(
        "✏️ <b>Kino/Serialni Tahrirlash</b>\n\nKino nomini yoki kodini yozing:",
        parse_mode="HTML"
    )

@admin_router.message(AdminStates.waiting_for_admin_search)
async def handle_edit_search(message: Message, state: FSMContext):
    query = message.text.strip()
    movie = await db_manager.get_movie_by_code(query)
    if movie:
        await state.update_data(edit_code=movie['code'])
        await state.set_state(AdminStates.waiting_for_edit_field)
        await message.answer(format_movie_details(movie), parse_mode="HTML", reply_markup=build_edit_field_kb(movie['code']))
        return
    results = await db_manager.search_movie(query)
    if not results:
        await message.answer("❌ Hech qanday kino topilmadi. Qaytadan urinib ko'ring:")
        return
    txt = "🔍 <b>Topilgan kinolar:</b>\n\n"
    kb = []
    for r in results:
        txt += f"• <code>{r['code']}</code> — {r['title']}\n"
        kb.append([InlineKeyboardButton(text=r['title'], callback_data=f"edit_choose_{r['code']}")])
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu_home")])
    await message.answer(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@admin_router.callback_query(F.data.startswith("edit_choose_"))
async def edit_choose_movie(callback: CallbackQuery, state: FSMContext):
    code = callback.data.replace("edit_choose_", "")
    await state.update_data(edit_code=code)
    await state.set_state(AdminStates.waiting_for_edit_field)
    await callback.answer()
    movie = await db_manager.get_movie_by_code(code)
    if not movie:
        await callback.message.edit_text("❌ Kino topilmadi.")
        return
    await callback.message.edit_text(format_movie_details(movie), parse_mode="HTML", reply_markup=build_edit_field_kb(code))

@admin_router.callback_query(F.data.startswith("edit_field_"))
async def edit_field_choose(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_", 3)
    if len(parts) < 4:
        await callback.answer("Xatolik", show_alert=True)
        return
    code = parts[2]
    field = parts[3]
    await state.update_data(edit_code=code, edit_field=field)
    await state.set_state(AdminStates.waiting_for_edit_value)
    await callback.answer()
    field_names = {
        "title": "yangi nomini",
        "genre": "yangi janrini",
        "description": "yangi tavsifini",
        "year": "yangi yilini (raqam)",
        "country": "yangi davlatni",
        "language": "yangi tilni",
        "quality": "yangi sifatni",
        "status": "yangi statusni (Tugallangan/Davom etmoqda)",
        "category": "yangi kategoriyasini (🎬 Kinolar, 📺 Seriallar, 🧸 Multfilmlar, 🎥 Trillerlar, 🇰🇷 Koreys Dramalari, 🌍 Boshqalar)",
    }
    label = field_names.get(field, "yangi qiymatini")
    await callback.message.edit_text(f"✏️ <b>{label}</b> kiriting:", parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_edit_value)
async def edit_field_value(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get('edit_code')
    field = data.get('edit_field')
    if not code or not field:
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        await state.clear()
        return
    value = message.text.strip()
    if field == "year":
        if not value.isdigit():
            await message.answer("❌ Iltimos, faqat raqam kiriting! Masalan: 2024")
            return
        value = int(value)
    ok = await db_manager.update_movie_field(code, field, value)
    await state.clear()
    movie = await db_manager.get_movie_by_code(code)
    title = movie['title'] if movie else code
    if ok:
        await message.answer(f"✅ <b>{title}</b> muvaffaqiyatli tahrirlandi!", parse_mode="HTML")
        logger.info(f"Movie edited: {code} - field {field} changed")
    else:
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.", parse_mode="HTML")

# ===== 7. POSTER QO'SHISH =====
async def start_add_media(callback: CallbackQuery, state: FSMContext, state_name, title_text):
    await state.set_state(state_name)
    await callback.answer()
    await callback.message.edit_text(title_text, parse_mode="HTML")

async def get_movie_by_code_input(message: Message, state: FSMContext, code_key: str, title_key: str, next_state, ask_text: str):
    code = message.text.strip().replace(" ", "")
    movie = await db_manager.get_movie_by_code(code)
    if not movie:
        await message.answer(f"❌ Kod <code>{code}</code> bo'yicha kino topilmadi!", parse_mode="HTML")
        await state.clear()
        return
    await state.update_data({code_key: code, title_key: movie['title']})
    await state.set_state(next_state)
    await message.answer(f"🎬 <b>{movie['title']}</b>\n\n{ask_text}", parse_mode="HTML")

@admin_router.callback_query(F.data == "admin_add_poster")
async def start_add_poster(callback: CallbackQuery, state: FSMContext):
    await start_add_media(callback, state, AdminStates.waiting_for_poster_movie_code,
        "🖼 <b>Poster Qo'shish</b>\n\nKino/Serial kodini kiriting:")

@admin_router.message(AdminStates.waiting_for_poster_movie_code)
async def poster_movie_code(message: Message, state: FSMContext):
    await get_movie_by_code_input(message, state, "poster_code", "poster_title",
        AdminStates.waiting_for_poster_upload, "Yangi poster rasmni yuklang:")

@admin_router.message(AdminStates.waiting_for_poster_upload)
async def poster_upload(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("❌ Iltimos, rasm faylini yuklang!")
        return
    file_id = message.photo[-1].file_id
    data = await state.get_data()
    code = data['poster_code']
    ok = await db_manager.update_movie_field(code, "poster_file_id", file_id)
    await state.clear()
    if ok:
        await message.answer(f"✅ <b>{data['poster_title']}</b> uchun poster muvaffaqiyatli o'rnatildi!", parse_mode="HTML")
        logger.info(f"Poster updated: {code} - {data['poster_title']}")
    else:
        await message.answer("❌ Xatolik yuz berdi.", parse_mode="HTML")

# ===== 8. TRAILER QO'SHISH =====
@admin_router.callback_query(F.data == "admin_add_trailer")
async def start_add_trailer(callback: CallbackQuery, state: FSMContext):
    await start_add_media(callback, state, AdminStates.waiting_for_trailer_movie_code,
        "🎥 <b>Trailer Qo'shish</b>\n\nKino/Serial kodini kiriting:")

@admin_router.message(AdminStates.waiting_for_trailer_movie_code)
async def trailer_movie_code(message: Message, state: FSMContext):
    await get_movie_by_code_input(message, state, "trailer_code", "trailer_title",
        AdminStates.waiting_for_trailer_url,
        "YouTube trailer havolasini yuboring:\nMasalan: https://youtube.com/watch?v=...")

@admin_router.message(AdminStates.waiting_for_trailer_url)
async def trailer_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith("http"):
        await message.answer("❌ Iltimos, to'g'ri URL kiriting (http/https bilan boshlansin)!")
        return
    data = await state.get_data()
    code = data['trailer_code']
    ok = await db_manager.update_movie_field(code, "trailer_url", url)
    await state.clear()
    if ok:
        await message.answer(f"✅ <b>{data['trailer_title']}</b> uchun trailer muvaffaqiyatli qo'shildi!\n\nKinoni ko'rishda 🎥 Trailer tugmasi paydo bo'ladi.", parse_mode="HTML")
        logger.info(f"Trailer updated: {code} - {data['trailer_title']}")
    else:
        await message.answer("❌ Xatolik yuz berdi.", parse_mode="HTML")

# ===== 9. EPIZODNI O'CHIRISH =====
@admin_router.callback_query(F.data == "admin_del_episode")
async def start_del_episode(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_ep_del_movie_code)
    await callback.answer()
    await callback.message.edit_text("🗑 <b>Epizodni O'chirish</b>\n\nKino/Serial kodini kiriting:", parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_ep_del_movie_code)
async def del_episode_movie_code(message: Message, state: FSMContext):
    code = message.text.strip().replace(" ", "")
    movie = await db_manager.get_movie_by_code(code)
    if not movie:
        await message.answer(f"❌ Kod <code>{code}</code> bo'yicha kino topilmadi!", parse_mode="HTML")
        await state.clear()
        return
    episodes = await db_manager.get_episodes(code)
    if not episodes:
        await message.answer(f"❌ <b>{movie['title']}</b> da epizodlar mavjud emas.", parse_mode="HTML")
        await state.clear()
        return
    await state.update_data(ep_del_code=code, ep_del_title=movie['title'])
    txt = f"🎬 <b>{movie['title']}</b>\n\nQaysi epizodni o'chirmoqchisiz?\n\n"
    kb = []
    for ep in episodes:
        txt += f"🎞 <b>{ep['episode_number']}-Qism</b>\n"
        kb.append([InlineKeyboardButton(text=f"❌ {ep['episode_number']}-Qismni o'chirish", callback_data=f"ep_del_{ep['id']}_{ep['episode_number']}")])
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu_home")])
    await message.answer(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@admin_router.callback_query(F.data.startswith("ep_del_"))
async def del_episode_confirm(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("Xatolik", show_alert=True)
        return
    ep_id = int(parts[2])
    ep_num = parts[3]
    data = await state.get_data()
    title = data.get('ep_del_title', "Noma'lum")
    await state.update_data(ep_del_id=ep_id, ep_del_num=ep_num)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data="ep_del_yes")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_menu_home")]
    ])
    await callback.answer()
    await callback.message.edit_text(f"⚠️ <b>{title}</b> — <b>{ep_num}-Qism</b> ni o'chirmoqchimisiz?", parse_mode="HTML", reply_markup=kb)

@admin_router.callback_query(F.data == "ep_del_yes")
async def ep_del_execute(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ep_id = data.get('ep_del_id')
    ep_num = data.get('ep_del_num')
    title = data.get('ep_del_title', "Noma'lum")
    await state.clear()
    await callback.answer()
    if not ep_id:
        await callback.message.edit_text("❌ Xatolik yuz berdi.")
        return
    ok = await db_manager.delete_episode(ep_id)
    if ok:
        await callback.message.edit_text(f"✅ <b>{title}</b> — <b>{ep_num}-Qism</b> muvaffaqiyatli o'chirildi!", parse_mode="HTML")
        logger.info(f"Episode deleted: {title} - ep{ep_num}")
    else:
        await callback.message.edit_text("❌ Xatolik yuz berdi, epizod topilmadi.", parse_mode="HTML")

# ===== 10. SOZLAMALAR =====
def settings_kb(settings: dict) -> InlineKeyboardMarkup:
    def toggle_btn(label: str, key: str, current: str) -> InlineKeyboardButton:
        status = "✅ Yoqilgan" if current == "1" else "❌ O'chirilgan"
        return InlineKeyboardButton(text=f"{label}: {status}", callback_data=f"set_toggle_{key}")
    kb = [
        [toggle_btn("📢 Bildirishnomalar", "notifications", settings.get("notifications", "1"))],
        [toggle_btn("📨 Reklama tasdiqlash", "broadcast_confirm", settings.get("broadcast_confirm", "1"))],
        [toggle_btn("📊 Avtomatik statistika", "auto_stats", settings.get("auto_stats", "1"))],
        [toggle_btn("🔧 Xizmat rejimi", "maintenance", settings.get("maintenance", "0"))],
        [toggle_btn("📢 Kanalga majburiy obuna", "force_join", settings.get("force_join", "1"))],
        [InlineKeyboardButton(text="📢 Majburiy Obuna", callback_data="admin_force_sub")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_menu_home")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

@admin_router.callback_query(F.data == "admin_settings")
async def show_settings(callback: CallbackQuery):
    await callback.answer()
    s = await db_manager.get_all_settings()
    txt = "⚙️ <b>Bot Sozlamalari</b>\n\nO'zgartirish uchun tugmani bosing:"
    await callback.message.edit_text(txt, parse_mode="HTML", reply_markup=settings_kb(s))

@admin_router.callback_query(F.data.startswith("set_toggle_"))
async def toggle_setting(callback: CallbackQuery):
    key = callback.data.replace("set_toggle_", "")
    await callback.answer()
    current = await db_manager.get_setting(key)
    new_val = "0" if current == "1" else "1"
    await db_manager.set_setting(key, new_val)
    s = await db_manager.get_all_settings()
    await callback.message.edit_reply_markup(reply_markup=settings_kb(s))
    logger.info(f"Setting changed: {key} -> {new_val}")

# ===== 11. MAJBURIY OBUNA (CHANNEL MANAGEMENT) =====
def force_sub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal Qo'shish", callback_data="add_channel")],
        [InlineKeyboardButton(text="📋 Kanallar", callback_data="list_channels")],
        [InlineKeyboardButton(text="❌ Kanal O'chirish", callback_data="del_channel")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="admin_settings")]
    ])

@admin_router.callback_query(F.data == "admin_force_sub")
async def show_force_sub(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.answer()
    await callback.message.edit_text("📢 <b>Majburiy Obuna</b>\n\nKerakli amalni tanlang:", parse_mode="HTML", reply_markup=force_sub_kb())

@admin_router.callback_query(F.data == "add_channel")
async def start_add_channel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_channel_id)
    await callback.message.edit_text("Kanal username yoki ID sini yuboring.\n\nMasalan: @kanal_nomi yoki -1001234567890")

@admin_router.message(AdminStates.waiting_for_channel_id)
async def process_add_channel(message: Message, state: FSMContext, bot: Bot):
    text = message.text.strip()
    chat_id = None
    username = None
    if text.startswith("@"):
        username = text
        try:
            chat = await bot.get_chat(username)
            chat_id = chat.id
        except Exception:
            await message.answer("❌ Kanal topilmadi yoki bot admin emas!")
            await state.clear()
            return
    else:
        try:
            chat_id = int(text)
        except ValueError:
            await message.answer("❌ Noto'g'ri format! Username (@kanal) yoki ID (-100...) yuboring.")
            await state.clear()
            return
    try:
        chat = await bot.get_chat(chat_id)
        member = await bot.get_chat_member(chat_id, (await bot.get_me()).id)
        if member.status not in ["administrator", "creator"]:
            await message.answer("❌ Bot kanalda admin emas! Avval botni kanalga admin qiling.")
            await state.clear()
            return
        channel_title = chat.title or username or str(chat_id)
        channel_username = chat.username or username or ""
        if not channel_username.startswith("@"):
            channel_username = f"@{channel_username}" if channel_username else ""
        ok = await db_manager.add_channel(chat_id, channel_username, channel_title)
        await state.clear()
        if ok:
            await message.answer(f"✅ <b>{channel_title}</b> muvaffaqiyatli qo'shildi!", parse_mode="HTML")
        else:
            await message.answer("❌ Bu kanal allaqachon qo'shilgan!")
    except Exception as e:
        logger.error(f"add_channel error: {e}")
        await message.answer("❌ Xatolik! Kanal mavjudligini va bot adminligini tekshiring.")
        await state.clear()

@admin_router.callback_query(F.data == "list_channels")
async def list_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.answer()
    channels = await db_manager.get_all_channels()
    if not channels:
        await callback.message.edit_text("📋 <b>Kanallar</b>\n\nHech qanday kanal qo'shilmagan.", parse_mode="HTML", reply_markup=force_sub_kb())
        return
    txt = "📋 <b>Kanallar</b>\n\n"
    for i, ch in enumerate(channels, 1):
        uname = ch.get("channel_username") or f"ID: {ch['channel_id']}"
        txt += f"{i}. {uname}\n"
    txt += "\nJami: " + str(len(channels))
    await callback.message.edit_text(txt, parse_mode="HTML", reply_markup=force_sub_kb())

@admin_router.callback_query(F.data == "del_channel")
async def start_del_channel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.answer()
    channels = await db_manager.get_all_channels()
    if not channels:
        await callback.message.edit_text("❌ Hech qanday kanal mavjud emas.", reply_markup=force_sub_kb())
        return
    txt = "❌ <b>Kanal O'chirish</b>\n\nO'chirmoqchi bo'lgan kanal ID sini yuboring:\n\n"
    for ch in channels:
        txt += f"ID {ch['id']}: {ch.get('channel_username') or ch['channel_title']}\n"
    await state.set_state(AdminStates.waiting_for_channel_del_select)
    await callback.message.edit_text(txt, parse_mode="HTML")

@admin_router.message(AdminStates.waiting_for_channel_del_select)
async def process_del_channel(message: Message, state: FSMContext):
    try:
        ch_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Iltimos, faqat raqam (kanal ID sini) yuboring!")
        return
    channels = await db_manager.get_all_channels()
    ch = next((c for c in channels if c["id"] == ch_id), None)
    if not ch:
        await message.answer("❌ Bunday ID li kanal topilmadi!")
        await state.clear()
        return
    await state.update_data(del_ch_id=ch_id, del_ch_name=ch.get("channel_username") or ch["channel_title"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha", callback_data="del_ch_confirm")],
        [InlineKeyboardButton(text="❌ Yo'q", callback_data="admin_force_sub")]
    ])
    await message.answer(f"⚠️ <b>{ch.get('channel_username') or ch['channel_title']}</b> ni o'chirmoqchimisiz?", parse_mode="HTML", reply_markup=kb)

@admin_router.callback_query(F.data == "del_ch_confirm")
async def confirm_del_channel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    data = await state.get_data()
    await state.clear()
    await callback.answer()
    ok = await db_manager.delete_channel(data["del_ch_id"])
    if ok:
        await callback.message.edit_text(f"✅ <b>{data['del_ch_name']}</b> o'chirildi!", parse_mode="HTML")
    else:
        await callback.message.edit_text("❌ Xatolik yuz berdi.")
