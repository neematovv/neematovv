import os
import aiosqlite
import logging
from datetime import datetime
from utils.config import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def _column_exists(self, db, table: str, column: str) -> bool:
        async with db.execute(f"PRAGMA table_info({table})") as cursor:
            cols = await cursor.fetchall()
            return any(c[1] == column for c in cols)

    async def _add_column_if_missing(self, db, table: str, column: str, col_def: str):
        if not await self._column_exists(db, table, column):
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
            logger.info(f"Added column {column} to {table}")

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")

            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    joined_at TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    code TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    genre TEXT,
                    year INTEGER,
                    poster_file_id TEXT,
                    views INTEGER DEFAULT 0
                )
            """)
            await self._add_column_if_missing(db, "movies", "country", "TEXT DEFAULT 'Noma_lum'")
            await self._add_column_if_missing(db, "movies", "language", "TEXT DEFAULT \"O'zbek tili\"")
            await self._add_column_if_missing(db, "movies", "quality", "TEXT DEFAULT '1080p HD'")
            await self._add_column_if_missing(db, "movies", "status", "TEXT DEFAULT 'Tugallangan'")
            await self._add_column_if_missing(db, "movies", "trailer_url", "TEXT")
            await self._add_column_if_missing(db, "movies", "category", "TEXT DEFAULT '🎬 Kinolar'")

            await db.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    movie_code TEXT NOT NULL,
                    episode_number INTEGER NOT NULL,
                    video_file_id TEXT NOT NULL,
                    FOREIGN KEY (movie_code) REFERENCES movies(code) ON DELETE CASCADE,
                    UNIQUE(movie_code, episode_number)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    movie_code TEXT NOT NULL,
                    viewed_at TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL UNIQUE,
                    channel_username TEXT,
                    channel_title TEXT,
                    is_required INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            defaults = {
                "notifications": "1",
                "broadcast_confirm": "1",
                "auto_stats": "1",
                "maintenance": "0",
                "force_join": "1"
            }
            for k, v in defaults.items():
                await db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (k, v)
                )

            try:
                await db.execute("CREATE INDEX IF NOT EXISTS idx_daily_views_date ON daily_views(viewed_at)")
            except Exception:
                pass

            await db.commit()
            logger.info("Database initialized with all extensions.")

    # ===== SETTINGS =====
    async def get_setting(self, key: str) -> str:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else "0"
        except Exception as e:
            logger.error(f"get_setting error: {e}")
            return "0"

    async def set_setting(self, key: str, value: str):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"set_setting error: {e}")

    async def get_all_settings(self) -> dict:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT key, value FROM settings") as cursor:
                    rows = await cursor.fetchall()
                    return {r[0]: r[1] for r in rows}
        except Exception as e:
            logger.error(f"get_all_settings error: {e}")
            return {}

    # ===== DAILY VIEWS =====
    async def record_view(self, movie_code: str):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                now = datetime.utcnow().isoformat()
                await db.execute(
                    "INSERT INTO daily_views (movie_code, viewed_at) VALUES (?, ?)",
                    (movie_code, now)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"record_view error: {e}")

    async def get_today_views(self) -> int:
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT COUNT(*) FROM daily_views WHERE viewed_at LIKE ?",
                    (f"{today}%",)
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_today_views error: {e}")
            return 0

    async def get_today_users(self) -> int:
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM users WHERE joined_at LIKE ?",
                    (f"{today}%",)
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_today_users error: {e}")
            return 0

    async def get_most_viewed_movie(self) -> str:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT title FROM movies ORDER BY views DESC LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else "Noma'lum"
        except Exception as e:
            logger.error(f"get_most_viewed_movie error: {e}")
            return "Noma'lum"

    async def get_avg_episodes_per_movie(self) -> float:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT COUNT(*) FROM episodes") as c_ep:
                    ep_count = (await c_ep.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM movies") as c_mov:
                    mov_count = (await c_mov.fetchone())[0]
                if mov_count == 0:
                    return 0.0
                return round(ep_count / mov_count, 1)
        except Exception as e:
            logger.error(f"get_avg_episodes_per_movie error: {e}")
            return 0.0

    # ===== USERS =====
    async def add_user(self, user_id: int, username: str, full_name: str):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                now = datetime.utcnow().isoformat()
                await db.execute("""
                    INSERT INTO users (user_id, username, full_name, joined_at)
                    VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET
                        username = excluded.username, full_name = excluded.full_name
                """, (user_id, username, full_name, now))
                await db.commit()
        except Exception as e:
            logger.error(f"add_user error: {e}")

    async def get_user_count(self) -> int:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_user_count error: {e}")
            return 0

    async def get_total_searches(self) -> int:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT COALESCE(SUM(views), 0) FROM movies") as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_total_searches error: {e}")
            return 0

    # ===== CHANNELS =====
    async def add_channel(self, channel_id: int, channel_username: str, channel_title: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                now = datetime.utcnow().isoformat()
                await db.execute(
                    "INSERT OR IGNORE INTO channels (channel_id, channel_username, channel_title, is_required, created_at) VALUES (?, ?, ?, 1, ?)",
                    (channel_id, channel_username, channel_title, now)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"add_channel error: {e}")
            return False

    async def get_required_channels(self) -> list:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT id, channel_id, channel_username, channel_title FROM channels WHERE is_required=1 ORDER BY id"
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [{"id": r[0], "channel_id": r[1], "channel_username": r[2], "channel_title": r[3]} for r in rows]
        except Exception as e:
            logger.error(f"get_required_channels error: {e}")
            return []

    async def get_all_channels(self) -> list:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT id, channel_id, channel_username, channel_title, is_required, created_at FROM channels ORDER BY id"
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [{"id": r[0], "channel_id": r[1], "channel_username": r[2], "channel_title": r[3], "is_required": r[4], "created_at": r[5]} for r in rows]
        except Exception as e:
            logger.error(f"get_all_channels error: {e}")
            return []

    async def delete_channel(self, channel_id: int) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("DELETE FROM channels WHERE id=?", (channel_id,))
                await db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"delete_channel error: {e}")
            return False

    async def get_all_users(self) -> list:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT user_id FROM users") as cursor:
                    rows = await cursor.fetchall()
                    return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"get_all_users error: {e}")
            return []

    # ===== MOVIES =====
    async def add_movie(self, code: str, title: str, description: str, genre: str, year: int, poster_file_id: str = None, category: str = None) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                if category:
                    await db.execute("""
                        INSERT INTO movies (code, title, description, genre, year, poster_file_id, views, category)
                        VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    """, (code, title, description, genre, year, poster_file_id, category))
                else:
                    await db.execute("""
                        INSERT INTO movies (code, title, description, genre, year, poster_file_id, views)
                        VALUES (?, ?, ?, ?, ?, ?, 0)
                    """, (code, title, description, genre, year, poster_file_id))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"add_movie error: {e}")
                return False

    async def get_movie_by_code(self, code: str) -> dict:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT code, title, description, genre, year, poster_file_id, views, country, language, quality, status, trailer_url, category FROM movies WHERE LOWER(code)=LOWER(?)",
                    (code,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {
                            "code": row[0], "title": row[1], "description": row[2],
                            "genre": row[3], "year": row[4], "poster_file_id": row[5],
                            "views": row[6], "country": row[7], "language": row[8],
                            "quality": row[9], "status": row[10], "trailer_url": row[11],
                            "category": row[12]
                        }
                    return None
        except Exception as e:
            logger.error(f"get_movie_by_code error: {e}")
            return None

    async def get_all_movies(self):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT DISTINCT code,title
                    FROM movies
                    ORDER BY title
                """) as cursor:
                    rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"get_all_movies error: {e}")
            return []

    async def increment_views(self, code: str):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("UPDATE movies SET views = views + 1 WHERE LOWER(code)=LOWER(?)", (code,))
                await db.commit()
        except Exception as e:
            logger.error(f"increment_views error: {e}")

    async def delete_movie(self, code: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("DELETE FROM movies WHERE LOWER(code)=LOWER(?)", (code,))
                await db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"delete_movie error: {e}")
            return False

    async def get_movie_count(self) -> int:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT COUNT(*) FROM movies") as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_movie_count error: {e}")
            return 0

    async def search_movie(self, query: str) -> list:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                pattern = f"%{query}%"
                async with db.execute(
                    "SELECT code, title, category FROM movies WHERE LOWER(title) LIKE LOWER(?) OR LOWER(code) LIKE LOWER(?) ORDER BY title LIMIT 20",
                    (pattern, pattern)
                ) as cursor:
                    rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"search_movie error: {e}")
            return []

    async def get_categories(self) -> list:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT DISTINCT category FROM movies WHERE category IS NOT NULL AND category != '' ORDER BY category"
                ) as cursor:
                    rows = await cursor.fetchall()
                return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"get_categories error: {e}")
            return []

    async def get_movies_by_category(self, category: str, page: int = 1, per_page: int = 20) -> dict:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT COUNT(*) FROM movies WHERE LOWER(category)=LOWER(?)",
                    (category,)
                ) as cursor:
                    total = (await cursor.fetchone())[0]
                pages = max(1, (total + per_page - 1) // per_page)
                offset = (page - 1) * per_page
                async with db.execute(
                    "SELECT code, title FROM movies WHERE LOWER(category)=LOWER(?) ORDER BY title LIMIT ? OFFSET ?",
                    (category, per_page, offset)
                ) as cursor:
                    rows = await cursor.fetchall()
                return {"movies": [dict(r) for r in rows], "total": total, "pages": pages, "page": page}
        except Exception as e:
            logger.error(f"get_movies_by_category error: {e}")
            return {"movies": [], "total": 0, "pages": 0, "page": 1}

    async def update_movie_field(self, code: str, field: str, value) -> bool:
        allowed = {"title", "description", "genre", "year", "country", "language", "quality", "status", "poster_file_id", "trailer_url", "category"}
        if field not in allowed:
            logger.error(f"update_movie_field: invalid field {field}")
            return False
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    f"UPDATE movies SET {field} = ? WHERE LOWER(code)=LOWER(?)",
                    (value, code)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"update_movie_field error: {e}")
            return False

    # ===== EPISODE METHODS =====
    async def add_episode(self, movie_code: str, episode_number: int, video_file_id: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO episodes (movie_code, episode_number, video_file_id)
                    VALUES (?, ?, ?)
                """, (movie_code, episode_number, video_file_id))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"add_episode error: {e}")
            return False

    async def get_episodes(self, movie_code: str) -> list:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT id, episode_number, video_file_id FROM episodes WHERE LOWER(movie_code)=LOWER(?) ORDER BY episode_number ASC",
                    (movie_code,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [{"id": r[0], "episode_number": r[1], "video_file_id": r[2]} for r in rows]
        except Exception as e:
            logger.error(f"get_episodes error: {e}")
            return []

    async def get_episode(self, movie_code: str, episode_number: int) -> dict:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT id, episode_number, video_file_id FROM episodes WHERE LOWER(movie_code)=LOWER(?) AND episode_number=?",
                    (movie_code, episode_number)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {"id": row[0], "episode_number": row[1], "video_file_id": row[2]}
                    return None
        except Exception as e:
            logger.error(f"get_episode error: {e}")
            return None

    async def get_episode_count(self, movie_code: str) -> int:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT COUNT(*) FROM episodes WHERE LOWER(movie_code)=LOWER(?)",
                    (movie_code,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_episode_count error: {e}")
            return 0

    async def get_total_episode_count(self) -> int:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT COUNT(*) FROM episodes") as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_total_episode_count error: {e}")
            return 0

    async def delete_episode(self, episode_id: int) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("DELETE FROM episodes WHERE id=?", (episode_id,))
                await db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"delete_episode error: {e}")
            return False

    def get_db_size_kb(self) -> float:
        try:
            return round(os.path.getsize(self.db_path) / 1024, 2) if os.path.exists(self.db_path) else 0.0
        except Exception:
            return 0.0

    def get_db_size_mb(self) -> float:
        return round(self.get_db_size_kb() / 1024, 2)

db_manager = DatabaseManager(config.DATABASE_NAME)