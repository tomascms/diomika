"""Unit tests for audit log retention and cleanup."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from core.audit_retention import AuditRetentionPolicy, get_retention_policy


class TestAuditRetentionPolicy:
    """Test audit log retention policies."""

    @pytest.fixture
    def dev_policy(self):
        """Create development retention policy."""
        return AuditRetentionPolicy(environment="development")

    @pytest.fixture
    def staging_policy(self):
        """Create staging retention policy."""
        return AuditRetentionPolicy(environment="staging")

    @pytest.fixture
    def prod_policy(self):
        """Create production retention policy."""
        return AuditRetentionPolicy(environment="production")

    def test_retention_days_by_environment(self, dev_policy, staging_policy, prod_policy):
        """Test that retention days vary by environment."""
        assert dev_policy.retention_days == 30
        assert staging_policy.retention_days == 90
        assert prod_policy.retention_days == 365

    def test_cutoff_date_calculation(self, dev_policy):
        """Test cutoff date calculation."""
        cutoff = dev_policy.get_cutoff_date()
        now = datetime.utcnow()

        # Should be approximately 30 days ago
        diff = (now - cutoff).days
        assert 29 <= diff <= 31

    def test_cutoff_date_is_in_past(self, dev_policy, staging_policy, prod_policy):
        """Test that cutoff date is always in the past."""
        now = datetime.utcnow()

        assert dev_policy.get_cutoff_date() < now
        assert staging_policy.get_cutoff_date() < now
        assert prod_policy.get_cutoff_date() < now

    def test_count_expired_logs_returns_int(self, dev_policy):
        """Test that count_expired_logs returns integer."""
        with patch("core.audit_retention.get_db") as mock_db:
            mock_db.return_value.execute.return_value.fetchone.return_value = (0,)

            count = dev_policy.count_expired_logs()

            assert isinstance(count, int)
            assert count >= 0

    def test_count_expired_logs_handles_none(self, dev_policy):
        """Test that count_expired_logs handles None result."""
        with patch("core.audit_retention.get_db") as mock_db:
            mock_db.return_value.execute.return_value.fetchone.return_value = None

            count = dev_policy.count_expired_logs()

            assert count == 0

    def test_archive_expired_logs_returns_count(self, dev_policy):
        """Test that archive_expired_logs returns number archived."""
        with patch("core.audit_retention.get_db") as mock_db:
            mock_result = MagicMock()
            mock_result.rowcount = 0  # No more rows to archive
            mock_db.return_value.execute.return_value = mock_result

            archived = dev_policy.archive_expired_logs()

            assert isinstance(archived, int)

    def test_delete_expired_logs_returns_count(self, dev_policy):
        """Test that delete_expired_logs returns number deleted."""
        with patch("core.audit_retention.get_db") as mock_db:
            mock_result = MagicMock()
            mock_result.rowcount = 0  # No more rows to delete
            mock_db.return_value.execute.return_value = mock_result

            deleted = dev_policy.delete_expired_logs()

            assert isinstance(deleted, int)

    def test_cleanup_without_archive(self, dev_policy):
        """Test cleanup skips archiving when archive=False."""
        with patch("core.audit_retention.get_db") as mock_db:
            mock_result = MagicMock()
            mock_result.rowcount = 0
            mock_result.fetchone.return_value = (10,)
            mock_db.return_value.execute.return_value = mock_result
            mock_db.return_value.execute.return_value.fetchone.return_value = (10,)

            result = dev_policy.cleanup_expired_logs(archive=False)

            assert "expired" in result
            assert "archived" in result
            assert "deleted" in result
            assert result["archived"] == 0

    def test_cleanup_with_archive(self, dev_policy):
        """Test cleanup includes archiving when archive=True."""
        with patch("core.audit_retention.get_db") as mock_db:
            mock_result = MagicMock()
            mock_result.rowcount = 0
            mock_result.fetchone.return_value = (10,)
            mock_db.return_value.execute.return_value = mock_result
            mock_db.return_value.execute.return_value.fetchone.return_value = (10,)

            result = dev_policy.cleanup_expired_logs(archive=True)

            assert "archived" in result

    def test_cleanup_returns_dict_with_counts(self, dev_policy):
        """Test cleanup returns proper result dictionary."""
        with patch("core.audit_retention.get_db") as mock_db:
            mock_result = MagicMock()
            mock_result.rowcount = 0
            mock_result.fetchone.return_value = (0,)
            mock_db.return_value.execute.return_value = mock_result

            result = dev_policy.cleanup_expired_logs()

            assert isinstance(result, dict)
            assert "expired" in result
            assert "archived" in result
            assert "deleted" in result

    def test_retention_stats_returns_dict(self, dev_policy):
        """Test that get_retention_stats returns dictionary."""
        with patch("core.audit_retention.get_db") as mock_db:
            mock_db.return_value.execute.return_value.fetchall.return_value = []
            mock_db.return_value.execute.return_value.fetchone.return_value = (0,)

            stats = dev_policy.get_retention_stats()

            assert isinstance(stats, dict)
            assert "total_logs" in stats
            assert "total_archived" in stats
            assert "action_distribution" in stats
            assert "result_distribution" in stats
            assert "age_distribution" in stats
            assert "retention_days" in stats

    def test_global_instance(self):
        """Test global retention policy instance."""
        with patch("core.audit_retention.get_settings") as mock_settings:
            mock_settings.return_value.environment = "production"

            policy1 = get_retention_policy()
            policy2 = get_retention_policy()

            assert policy1 is policy2

    def test_global_instance_custom_environment(self):
        """Test global instance with custom environment."""
        policy = get_retention_policy(environment="staging")

        assert policy.environment == "staging"
        assert policy.retention_days == 90

    def test_batch_processing_large_dataset(self, dev_policy):
        """Test batch processing for large datasets."""
        with patch("core.audit_retention.get_db") as mock_db:
            # Simulate 5000 rows to delete in batches of 1000
            call_count = [0]

            def side_effect(*args, **kwargs):
                call_count[0] += 1
                mock_result = MagicMock()
                # Return 1000 rows for first 5 calls, then 0
                mock_result.rowcount = 1000 if call_count[0] <= 5 else 0
                return mock_result

            mock_db.return_value.execute.side_effect = side_effect

            deleted = dev_policy.delete_expired_logs(batch_size=1000)

            # Should process in 5 batches
            assert deleted == 5000
