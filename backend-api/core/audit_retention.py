"""Audit log retention and cleanup policies.

Manages automatic cleanup of old audit logs based on retention policies:
- 90-day retention for development/staging
- 365-day retention for production
- Compliant archival before deletion
- Batch processing for large datasets
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text

from core.database import get_db

logger = logging.getLogger("diomika-audit-retention")


class AuditRetentionPolicy:
    """Manages audit log retention and cleanup."""

    # Default retention periods (in days)
    RETENTION_DEVELOPMENT = 30
    RETENTION_STAGING = 90
    RETENTION_PRODUCTION = 365

    def __init__(self, environment: str = "development"):
        self.environment = environment
        self.retention_days = self._get_retention_days()

    def _get_retention_days(self) -> int:
        """Get retention period based on environment."""
        if self.environment == "production":
            return self.RETENTION_PRODUCTION
        elif self.environment == "staging":
            return self.RETENTION_STAGING
        else:
            return self.RETENTION_DEVELOPMENT

    def get_cutoff_date(self) -> datetime:
        """Get the cutoff date for audit logs to delete."""
        return datetime.utcnow() - timedelta(days=self.retention_days)

    def count_expired_logs(self) -> int:
        """Count audit logs that are older than retention period."""
        cutoff = self.get_cutoff_date()
        db = get_db()

        query = """
        SELECT COUNT(*) as count FROM audit_trail
        WHERE created_at < :cutoff_date
        """

        result = db.execute(text(query), {"cutoff_date": cutoff}).fetchone()
        return result[0] if result else 0

    def archive_expired_logs(self, batch_size: int = 1000) -> int:
        """Archive expired audit logs before deletion.

        Moves logs to archive table for long-term storage.
        Returns number of logs archived.
        """
        cutoff = self.get_cutoff_date()
        db = get_db()
        total_archived = 0

        # Archive in batches to avoid lock contention
        while True:
            query = """
            INSERT INTO audit_archive
            SELECT * FROM audit_trail
            WHERE created_at < :cutoff_date
            LIMIT :batch_size
            """

            result = db.execute(
                text(query),
                {"cutoff_date": cutoff, "batch_size": batch_size},
            )

            if result.rowcount == 0:
                break

            total_archived += result.rowcount
            logger.info(f"Archived {result.rowcount} audit logs (total: {total_archived})")

        db.commit()
        return total_archived

    def delete_expired_logs(self, batch_size: int = 1000) -> int:
        """Delete expired audit logs in batches.

        Returns number of logs deleted.
        """
        cutoff = self.get_cutoff_date()
        db = get_db()
        total_deleted = 0

        while True:
            query = """
            DELETE FROM audit_trail
            WHERE id IN (
                SELECT id FROM audit_trail
                WHERE created_at < :cutoff_date
                LIMIT :batch_size
            )
            """

            result = db.execute(
                text(query),
                {"cutoff_date": cutoff, "batch_size": batch_size},
            )

            if result.rowcount == 0:
                break

            total_deleted += result.rowcount
            logger.info(f"Deleted {result.rowcount} audit logs (total: {total_deleted})")

        db.commit()
        return total_deleted

    def cleanup_expired_logs(self, archive: bool = True, batch_size: int = 1000) -> dict:
        """Run complete cleanup: archive then delete expired logs.

        Args:
            archive: Whether to archive logs before deletion
            batch_size: Batch size for processing

        Returns:
            Dictionary with counts
        """
        logger.info(
            f"Starting audit log cleanup (environment: {self.environment}, retention: {self.retention_days}d)"
        )

        expired_count = self.count_expired_logs()

        if expired_count == 0:
            logger.info("No expired audit logs to clean up")
            return {"expired": 0, "archived": 0, "deleted": 0}

        logger.info(f"Found {expired_count} expired audit logs")

        archived = 0
        if archive:
            archived = self.archive_expired_logs(batch_size)
            logger.info(f"Archived {archived} audit logs")

        deleted = self.delete_expired_logs(batch_size)
        logger.info(f"Deleted {deleted} audit logs")

        return {
            "expired": expired_count,
            "archived": archived,
            "deleted": deleted,
        }

    def get_retention_stats(self) -> dict:
        """Get audit log retention statistics."""
        db = get_db()

        # Count by action
        action_stats = db.execute(
            text("""
            SELECT action, COUNT(*) as count
            FROM audit_trail
            GROUP BY action
            ORDER BY count DESC
            """
            )
        ).fetchall()

        # Count by result
        result_stats = db.execute(
            text("""
            SELECT result, COUNT(*) as count
            FROM audit_trail
            GROUP BY result
            ORDER BY count DESC
            """
            )
        ).fetchall()

        # Age distribution
        age_dist = db.execute(
            text("""
            SELECT
                CASE
                    WHEN created_at >= NOW() - INTERVAL '7 days' THEN 'Last 7 days'
                    WHEN created_at >= NOW() - INTERVAL '30 days' THEN 'Last 30 days'
                    WHEN created_at >= NOW() - INTERVAL '90 days' THEN 'Last 90 days'
                    WHEN created_at >= NOW() - INTERVAL '1 year' THEN 'Last year'
                    ELSE 'Older'
                END as period,
                COUNT(*) as count
            FROM audit_trail
            GROUP BY period
            """
            )
        ).fetchall()

        return {
            "total_logs": db.execute(
                text("SELECT COUNT(*) FROM audit_trail")
            ).fetchone()[0],
            "total_archived": db.execute(
                text("SELECT COUNT(*) FROM audit_archive")
            ).fetchone()[0],
            "action_distribution": dict((row[0], row[1]) for row in action_stats),
            "result_distribution": dict((row[0], row[1]) for row in result_stats),
            "age_distribution": dict((row[0], row[1]) for row in age_dist),
            "oldest_log": db.execute(
                text("SELECT MIN(created_at) FROM audit_trail")
            ).fetchone()[0],
            "newest_log": db.execute(
                text("SELECT MAX(created_at) FROM audit_trail")
            ).fetchone()[0],
            "retention_days": self.retention_days,
            "cutoff_date": self.get_cutoff_date(),
            "environment": self.environment,
        }


# Global instance
_retention_policy: Optional[AuditRetentionPolicy] = None


def get_retention_policy(environment: Optional[str] = None) -> AuditRetentionPolicy:
    """Get global audit retention policy instance."""
    global _retention_policy
    if _retention_policy is None:
        from core.config import get_settings
        settings = get_settings()
        _retention_policy = AuditRetentionPolicy(
            environment=environment or settings.environment
        )
    return _retention_policy
