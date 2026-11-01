"""Read-only startup gate: refuse new application code on an incomplete schema."""
import asyncio
import sys

from sqlalchemy import inspect

import app.db.models  # noqa: F401 — register all ORM tables
from app.db.session import Base, engine


def missing_columns(connection):
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    missing = []
    for name, table in Base.metadata.tables.items():
        if name not in tables:
            missing.append(name)
            continue
        installed = {column["name"] for column in inspector.get_columns(name)}
        missing.extend(f"{name}.{column.name}" for column in table.columns if column.name not in installed)
    return missing


async def main():
    try:
        async with engine.connect() as connection:
            missing = await connection.run_sync(missing_columns)
        if missing:
            print("Saha schema is incomplete. Follow docs/OPEN-COLLABORATION-DEPLOYMENT.md before starting this release.", file=sys.stderr)
            print("Missing schema objects: " + ", ".join(missing), file=sys.stderr)
            return 1
        print("Saha schema columns match the installed application models.")
        return 0
    except Exception:
        # Driver exceptions can include connection information; keep credentials
        # out of systemd startup messages and report readiness failure plainly.
        print("Saha could not verify its database schema. Check database availability and configured access; no migrations were run.", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
