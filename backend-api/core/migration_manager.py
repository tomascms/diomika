"""Database migration framework - versionado com SQL"""
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import hashlib

from core.database import get_supabase_client

logger = logging.getLogger("diomika-api")

MIGRATIONS_DIR = Path(__file__).parent.parent / "sql"


@dataclass
class Migration:
    """Represents a versioned migration."""
    version: str
    name: str
    path: Path
    checksum: str
    executed_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "name": self.name,
            "checksum": self.checksum,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "error": error,
        }


class MigrationManager:
    """Manages database migrations."""

    def __init__(self):
        self.migrations: List[Migration] = []
        self.migrations_table = "schema_migrations"
        self._ensure_migrations_table()

    def _ensure_migrations_table(self):
        """Create migrations tracking table if not exists."""
        try:
            client = get_supabase_client()
            # Simple check via SQL
            client.sql(f"""
                CREATE TABLE IF NOT EXISTS {self.migrations_table} (
                    version TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    executed_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    execution_time_ms INTEGER,
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_schema_migrations_executed_at
                    ON {self.migrations_table}(executed_at);
            """)
            logger.info("Migrations tracking table ready")
        except Exception as e:
            logger.warning(f"Could not ensure migrations table: {e}")

    def _calculate_checksum(self, content: str) -> str:
        """Calculate SHA256 checksum of migration content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def discover_migrations(self) -> List[Migration]:
        """Discover all SQL migration files."""
        if not MIGRATIONS_DIR.exists():
            logger.warning(f"Migrations directory not found: {MIGRATIONS_DIR}")
            return []

        migrations = []
        for file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            # Skip templates and non-numbered files
            if "TEMPLATE" in file.name or "_" not in file.name[:5]:
                continue

            content = file.read_text()
            version = file.name.split("_")[0]
            name = file.stem
            checksum = self._calculate_checksum(content)

            migration = Migration(
                version=version,
                name=name,
                path=file,
                checksum=checksum,
            )
            migrations.append(migration)

        logger.info(f"Discovered {len(migrations)} migrations")
        return migrations

    def get_executed_migrations(self) -> List[Migration]:
        """Get list of already executed migrations."""
        try:
            client = get_supabase_client()
            result = client.sql(f"SELECT * FROM {self.migrations_table} ORDER BY version ASC")

            migrations = []
            for row in result:
                migration = Migration(
                    version=row["version"],
                    name=row["name"],
                    path=MIGRATIONS_DIR / f"{row['version']}_*.sql",
                    checksum=row["checksum"],
                    executed_at=row["executed_at"],
                    execution_time_ms=row["execution_time_ms"],
                    error=row["error"],
                )
                migrations.append(migration)
            return migrations
        except Exception as e:
            logger.error(f"Could not fetch executed migrations: {e}")
            return []

    def get_pending_migrations(self) -> List[Migration]:
        """Get migrations that haven't been executed yet."""
        all_migrations = self.discover_migrations()
        executed = self.get_executed_migrations()
        executed_versions = {m.version for m in executed}

        pending = [m for m in all_migrations if m.version not in executed_versions]
        return pending

    async def validate_checksum(self, migration: Migration) -> bool:
        """Verify migration checksum hasn't changed."""
        try:
            client = get_supabase_client()
            result = client.sql(
                f"SELECT checksum FROM {self.migrations_table} WHERE version = %s",
                (migration.version,)
            )
            if not result:
                return True  # Not executed yet
            return result[0]["checksum"] == migration.checksum
        except Exception as e:
            logger.error(f"Could not validate checksum: {e}")
            return False

    async def execute_migration(self, migration: Migration) -> bool:
        """Execute a single migration."""
        try:
            start_time = datetime.utcnow()
            content = migration.path.read_text()

            client = get_supabase_client()

            # Execute migration SQL
            client.sql(content)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Record in tracking table
            client.sql(
                f"""
                INSERT INTO {self.migrations_table}
                (version, name, checksum, executed_at, execution_time_ms)
                VALUES (%s, %s, %s, NOW(), %s)
                """,
                (migration.version, migration.name, migration.checksum, int(execution_time))
            )

            logger.info(f"✓ Migration {migration.version} ({migration.name}) executed in {execution_time:.2f}ms")
            migration.executed_at = datetime.utcnow()
            migration.execution_time_ms = int(execution_time)
            return True

        except Exception as e:
            logger.error(f"✗ Migration {migration.version} failed: {e}")
            migration.error = str(e)

            try:
                client = get_supabase_client()
                client.sql(
                    f"""
                    INSERT INTO {self.migrations_table}
                    (version, name, checksum, error)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (migration.version, migration.name, migration.checksum, str(e))
                )
            except:
                pass

            return False

    async def execute_pending_migrations(self) -> dict:
        """Execute all pending migrations."""
        pending = self.get_pending_migrations()
        if not pending:
            logger.info("No pending migrations")
            return {"status": "ok", "executed": 0, "failed": 0}

        logger.info(f"Executing {len(pending)} pending migrations...")
        executed_count = 0
        failed_count = 0

        for migration in pending:
            # Validate checksum
            if not await self.validate_checksum(migration):
                logger.error(f"Checksum mismatch for {migration.version}")
                failed_count += 1
                continue

            if await self.execute_migration(migration):
                executed_count += 1
            else:
                failed_count += 1

        logger.info(f"Migrations complete: {executed_count} executed, {failed_count} failed")
        return {
            "status": "ok" if failed_count == 0 else "partial",
            "executed": executed_count,
            "failed": failed_count,
        }

    def get_migration_status(self) -> dict:
        """Get overall migration status."""
        all_migrations = self.discover_migrations()
        executed = self.get_executed_migrations()
        pending = self.get_pending_migrations()

        return {
            "total": len(all_migrations),
            "executed": len(executed),
            "pending": len(pending),
            "migrations": [
                {
                    "version": m.version,
                    "name": m.name,
                    "status": "executed" if m in executed else "pending",
                    "executed_at": m.executed_at.isoformat() if m.executed_at else None,
                }
                for m in all_migrations
            ],
        }


# Global instance
_migration_manager: Optional[MigrationManager] = None


def get_migration_manager() -> MigrationManager:
    """Get global migration manager."""
    global _migration_manager
    if _migration_manager is None:
        _migration_manager = MigrationManager()
    return _migration_manager
