"""CI prerequisite check: a missing integration database must fail, not skip."""
import asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.db.session import engine


async def main():
    if make_url(settings.DATABASE_URL).database != "saha_test":
        raise RuntimeError("Integration checks require the dedicated saha_test database")
    async with engine.connect() as connection:
        if (await connection.execute(text("SELECT current_database()"))).scalar_one() != "saha_test":
            raise RuntimeError("Connected to an unexpected database")
        for query in ("SELECT 1 FROM open_projects LIMIT 1", "SELECT 1 FROM project_tasks LIMIT 1", "SELECT 1 FROM project_references LIMIT 1",
                      "SELECT 1 FROM post_media LIMIT 1", "SELECT 1 FROM post_reactions LIMIT 1",
                      "SELECT 1 FROM space_private_records LIMIT 1", "SELECT 1 FROM chat_identities LIMIT 1",
                      "SELECT 1 FROM encrypted_chat_rooms LIMIT 1", "SELECT 1 FROM research_collections LIMIT 1"):
            await connection.execute(text(query))
    await engine.dispose()
    redis = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=5, socket_timeout=5)
    try:
        await redis.ping()
    finally:
        await redis.aclose()
    print("Dedicated test database schema and Redis connection verified")


if __name__ == "__main__":
    asyncio.run(main())
