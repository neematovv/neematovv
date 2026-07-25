import os
import time
import asyncpg
import logging
from datetime import datetime
from utils.config import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, dsn: str = None):
        self.dsn = dsn or os.environ.get("DATABASE_URL") or config.DATABASE_URL
        self.pool = None

    async def _column_exists(self, table: str, column: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchval(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name=$1 AND column_name=$2",
                table, column
            )
            return row is not None

    async def _add_column_if_missing(self, table: str, column: str, col_def: str):
        if not await self._column_exists(table, column):
            async with self.pool.acquire() as conn:
                await conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"
                )
                logger.info(f"Added column {column} to {table}")

    async def init_db(self):
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=10)

        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    joined_at TEXT NOT NULL
                )
            """)

            await conn.execute("""
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
            await self._add_column_if_missing("movies", "country", "TEXT DEFAULT 'Noma_lum'")
            await self._add_column_if_missing("movies", "language", "TEXT DEFAULT 'O''zbek tili'")
            await self._add_column_if_missing("movies", "quality", "TEXT DEFAULT '1080p HD'")
            await self._add_column_if_missing("movies", "status", "TEXT DEFAULT 'Tugallangan'")
            await self._add_column_if_missing("movies", "trailer_url", "TEXT")
            await self._add_column_if_missing("movies", "category", "TEXT DEFAULT '🎬 Kinolar'")

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id SERIAL PRIMARY KEY,
                    movie_code TEXT NOT NULL,
                    episode_number INTEGER NOT NULL,
                    video_file_id TEXT NOT NULL,
                    FOREIGN KEY (movie_code) REFERENCES movies(code) ON DELETE CASCADE,
                    UNIQUE(movie_code, episode_number)
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_views (
                    id SERIAL PRIMARY KEY,
                    movie_code TEXT NOT NULL,
                    viewed_at TEXT NOT NULL
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id SERIAL PRIMARY KEY,
                    channel_id BIGINT NOT NULL UNIQUE,
                    channel_username TEXT,
                    channel_title TEXT,
                    is_required INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    movie_code VARCHAR(50) NOT NULL,
                    UNIQUE(user_id, movie_code)
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
                await conn.execute(
                    "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING",
                    k, v
                )

            try:
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_views_date ON daily_views(viewed_at)")
            except Exception:
                pass

            logger.info("Database initialized with all extensions.")

    # ===== PING & DB SIZE =====
    async def ping(self) -> float:
        """Check database latency, returns execution time in milliseconds."""
        try:
            start = time.time()
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            elapsed = (time.time() - start) * 1000
            return round(elapsed, 2)
        except Exception as e:
            logger.error(f"ping error: {e}")
            return -1.0

    async def get_db_size_mb(self) -> float:
        """Calculate total size of PostgreSQL database tables in MB."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchval("""
                    SELECT ROUND(SUM(pg_total_relation_size(quote_ident(table_schema || '.' || table_name))) / (1024 * 1024)::numeric, 2)
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """)
                return float(row) if row else 0.0
        except Exception as e:
            logger.error(f"get_db_size_mb error: {e}")
            return 0.0

    async def get_db_size_kb(self) -> float:
        """Calculate total size of PostgreSQL database tables in KB."""
        try:
            mb = await self.get_db_size_mb()
            return round(mb * 1024, 2)
        except Exception as e:
            logger.error(f"get_db_size_kb error: {e}")
            return 0.0

    # ===== SETTINGS =====
    async def get_setting(self, key: str) -> str:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT value FROM settings WHERE key=$1", key
                )
                return row[0] if row else "0"
        except Exception as e:
            logger.error(f"get_setting error: {e}")
            return "0"

    async def set_setting(self, key: str, value: str):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO settings (key, value) VALUES ($1, $2) "
                    "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                    key, value
                )
        except Exception as e:
            logger.error(f"set_setting error: {e}")

    async def get_all_settings(self) -> dict:
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT key, value FROM settings")
                return {r[0]: r[1] for r in rows}
        except Exception as e:
            logger.error(f"get_all_settings error: {e}")
            return {}

    # ===== DAILY VIEWS =====
    async def record_view(self, movie_code: str):
        try:
            async with self.pool.acquire() as conn:
                now = datetime.utcnow().isoformat()
                await conn.execute(
                    "INSERT INTO daily_views (movie_code, viewed_at) VALUES ($1, $2)",
                    movie_code, now
                )
        except Exception as e:
            logger.error(f"record_view error: {e}")

    async def get_today_views(self) -> int:
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) FROM daily_views WHERE viewed_at LIKE $1",
                    f"{today}%"
                )
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_today_views error: {e}")
            return 0

    async def get_today_users(self) -> int:
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COUNT(DISTINCT user_id) FROM users WHERE joined_at LIKE $1",
                    f"{today}%"
                )
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_today_users error: {e}")
            return 0

    async def get_most_viewed_movie(self) -> str:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT title FROM movies ORDER BY views DESC LIMIT 1"
                )
                return row[0] if row else "Noma'lum"
        except Exception as e:
            logger.error(f"get_most_viewed_movie error: {e}")
            return "Noma'lum"

    async def get_avg_episodes_per_movie(self) -> float:
        try:
            async with self.pool.acquire() as conn:
                ep_count = await conn.fetchval("SELECT COUNT(*) FROM episodes")
                mov_count = await conn.fetchval("SELECT COUNT(*) FROM movies")
                if mov_count == 0:
                    return 0.0
                return round(ep_count / mov_count, 1)
        except Exception as e:
            logger.error(f"get_avg_episodes_per_movie error: {e}")
            return 0.0

    # ===== USERS =====
    async def add_user(self, user_id: int, username: str, full_name: str):
        try:
            async with self.pool.acquire() as conn:
                now = datetime.utcnow().isoformat()
                await conn.execute("""
                    INSERT INTO users (user_id, username, full_name, joined_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = excluded.username,
                        full_name = excluded.full_name
                """, user_id, username, full_name, now)
        except Exception as e:
            logger.error(f"add_user error: {e}")

    async def get_user_count(self) -> int:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) FROM users")
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_user_count error: {e}")
            return 0

    async def get_total_searches(self) -> int:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COALESCE(SUM(views), 0) FROM movies")
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_total_searches error: {e}")
            return 0

    # ===== CHANNELS =====
    async def add_channel(self, channel_id: int, channel_username: str, channel_title: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                now = datetime.utcnow().isoformat()
                await conn.execute(
                    "INSERT INTO channels (channel_id, channel_username, channel_title, is_required, created_at) "
                    "VALUES ($1, $2, $3, 1, $4) ON CONFLICT (channel_id) DO NOTHING",
                    channel_id, channel_username, channel_title, now
                )
                return True
        except Exception as e:
            logger.error(f"add_channel error: {e}")
            return False

    async def get_required_channels(self) -> list:
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, channel_id, channel_username, channel_title "
                    "FROM channels WHERE is_required=1 ORDER BY id"
                )
                return [{"id": r[0], "channel_id": r[1], "channel_username": r[2], "channel_title": r[3]} for r in rows]
        except Exception as e:
            logger.error(f"get_required_channels error: {e}")
            return []

    async def get_all_channels(self) -> list:
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, channel_id, channel_username, channel_title, is_required, created_at "
                    "FROM channels ORDER BY id"
                )
                return [{"id": r[0], "channel_id": r[1], "channel_username": r[2], "channel_title": r[3], "is_required": r[4], "created_at": r[5]} for r in rows]
        except Exception as e:
            logger.error(f"get_all_channels error: {e}")
            return []

    async def delete_channel(self, channel_id: int) -> bool:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "DELETE FROM channels WHERE id=$1 RETURNING id", channel_id
                )
                return row is not None
        except Exception as e:
            logger.error(f"delete_channel error: {e}")
            return False

    async def get_all_users(self) -> list:
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT user_id FROM users")
                return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"get_all_users error: {e}")
            return []

    # ===== MOVIES =====
    async def add_movie(self, code: str, title: str, description: str, genre: str, year: int, poster_file_id: str = None, category: str = None, country: str = None) -> bool:
        async with self.pool.acquire() as conn:
            try:
                if category and country:
                    await conn.execute("""
                        INSERT INTO movies (code, title, description, genre, year, poster_file_id, views, category, country)
                        VALUES ($1, $2, $3, $4, $5, $6, 0, $7, $8)
                    """, code, title, description, genre, year, poster_file_id, category, country)
                elif category:
                    await conn.execute("""
                        INSERT INTO movies (code, title, description, genre, year, poster_file_id, views, category)
                        VALUES ($1, $2, $3, $4, $5, $6, 0, $7)
                    """, code, title, description, genre, year, poster_file_id, category)
                elif country:
                    await conn.execute("""
                        INSERT INTO movies (code, title, description, genre, year, poster_file_id, views, country)
                        VALUES ($1, $2, $3, $4, $5, $6, 0, $7)
                    """, code, title, description, genre, year, poster_file_id, country)
                else:
                    await conn.execute("""
                        INSERT INTO movies (code, title, description, genre, year, poster_file_id, views)
                        VALUES ($1, $2, $3, $4, $5, $6, 0)
                    """, code, title, description, genre, year, poster_file_id)
                return True
            except Exception as e:
                logger.error(f"add_movie error: {e}")
                return False

    async def get_movie_by_code(self, code: str) -> dict:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT code, title, description, genre, year, poster_file_id, views, "
                    "country, language, quality, status, trailer_url, category "
                    "FROM movies WHERE LOWER(code)=LOWER($1)",
                    code
                )
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
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT DISTINCT code, title
                    FROM movies
                    ORDER BY title
                """)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"get_all_movies error: {e}")
            return []

    async def increment_views(self, code: str):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE movies SET views = views + 1 WHERE LOWER(code)=LOWER($1)",
                    code
                )
        except Exception as e:
            logger.error(f"increment_views error: {e}")

    async def delete_movie(self, code: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "DELETE FROM movies WHERE LOWER(code)=LOWER($1) RETURNING code",
                    code
                )
                return row is not None
        except Exception as e:
            logger.error(f"delete_movie error: {e}")
            return False

    async def get_movie_count(self) -> int:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) FROM movies")
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_movie_count error: {e}")
            return 0

    async def search_movie(self, query: str) -> list:
        try:
            async with self.pool.acquire() as conn:
                pattern = f"%{query}%"
                rows = await conn.fetch(
                    "SELECT code, title, category FROM movies "
                    "WHERE LOWER(title) LIKE LOWER($1) OR LOWER(code) LIKE LOWER($2) "
                    "ORDER BY title LIMIT 20",
                    pattern, pattern
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"search_movie error: {e}")
            return []

    async def get_categories(self) -> list:
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT DISTINCT category FROM movies "
                    "WHERE category IS NOT NULL AND category != '' ORDER BY category"
                )
                return [r[0] for r in rows]
        except Exception as e:
            logger.error(f"get_categories error: {e}")
            return []

    async def get_movies_by_category(self, category: str, page: int = 1, per_page: int = 20) -> dict:
        try:
            async with self.pool.acquire() as conn:
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM movies WHERE LOWER(category)=LOWER($1)",
                    category
                )
                pages = max(1, (total + per_page - 1) // per_page)
                offset = (page - 1) * per_page
                rows = await conn.fetch(
                    "SELECT code, title FROM movies WHERE LOWER(category)=LOWER($1) "
                    "ORDER BY title LIMIT $2 OFFSET $3",
                    category, per_page, offset
                )
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
            async with self.pool.acquire() as conn:
                await conn.execute(
                    f"UPDATE movies SET {field} = $1 WHERE LOWER(code)=LOWER($2)",
                    value, code
                )
                return True
        except Exception as e:
            logger.error(f"update_movie_field error: {e}")
            return False

    # ===== EPISODE METHODS =====
    async def add_episode(self, movie_code: str, episode_number: int, video_file_id: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO episodes (movie_code, episode_number, video_file_id)
                    VALUES ($1, $2, $3)
                """, movie_code, episode_number, video_file_id)
                return True
        except Exception as e:
            logger.error(f"add_episode error: {e}")
            return False

    async def get_episodes(self, movie_code: str) -> list:
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, episode_number, video_file_id "
                    "FROM episodes WHERE LOWER(movie_code)=LOWER($1) ORDER BY episode_number ASC",
                    movie_code
                )
                return [{"id": r[0], "episode_number": r[1], "video_file_id": r[2]} for r in rows]
        except Exception as e:
            logger.error(f"get_episodes error: {e}")
            return []

    async def get_episode(self, movie_code: str, episode_number: int) -> dict:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id, episode_number, video_file_id "
                    "FROM episodes WHERE LOWER(movie_code)=LOWER($1) AND episode_number=$2",
                    movie_code, episode_number
                )
                if row:
                    return {"id": row[0], "episode_number": row[1], "video_file_id": row[2]}
                return None
        except Exception as e:
            logger.error(f"get_episode error: {e}")
            return None

    async def get_episode_count(self, movie_code: str) -> int:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) FROM episodes WHERE LOWER(movie_code)=LOWER($1)",
                    movie_code
                )
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_episode_count error: {e}")
            return 0

    async def get_total_episode_count(self) -> int:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) FROM episodes")
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"get_total_episode_count error: {e}")
            return 0

    async def delete_episode(self, episode_id: int) -> bool:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "DELETE FROM episodes WHERE id=$1 RETURNING id", episode_id
                )
                return row is not None
        except Exception as e:
            logger.error(f"delete_episode error: {e}")
            return False

    # ===== FAVORITES =====
    async def add_favorite(self, user_id: int, movie_code: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO favorites (user_id, movie_code) VALUES ($1, $2) "
                    "ON CONFLICT (user_id, movie_code) DO NOTHING",
                    user_id, movie_code
                )
                return True
        except Exception as e:
            logger.error(f"add_favorite error: {e}")
            return False

    async def remove_favorite(self, user_id: int, movie_code: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "DELETE FROM favorites WHERE user_id=$1 AND movie_code=$2 RETURNING id",
                    user_id, movie_code
                )
                return row is not None
        except Exception as e:
            logger.error(f"remove_favorite error: {e}")
            return False

    async def is_favorite(self, user_id: int, movie_code: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchval(
                    "SELECT 1 FROM favorites WHERE user_id=$1 AND movie_code=$2",
                    user_id, movie_code
                )
                return row is not None
        except Exception as e:
            logger.error(f"is_favorite error: {e}")
            return False

    async def get_user_favorites(self, user_id: int) -> list:
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT f.movie_code, m.title FROM favorites f "
                    "LEFT JOIN movies m ON LOWER(m.code)=LOWER(f.movie_code) "
                    "WHERE f.user_id=$1 ORDER BY f.id DESC",
                    user_id
                )
                return [{"movie_code": r[0], "title": r[1] or r[0]} for r in rows]
        except Exception as e:
            logger.error(f"get_user_favorites error: {e}")
            return []

    async def get_favorite_count(self, user_id: int) -> int:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchval(
                    "SELECT COUNT(*) FROM favorites WHERE user_id=$1",
                    user_id
                )
                return row if row else 0
        except Exception as e:
            logger.error(f"get_favorite_count error: {e}")
            return 0


db_manager = DatabaseManager()
