"""Background job queue for async tasks."""
import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, List
from enum import Enum
import asyncio

from core.cache import get_redis

logger = logging.getLogger("diomika-api")


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Job priority levels."""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    URGENT = 0


class Job:
    """Represents a background job."""

    def __init__(
        self,
        job_type: str,
        data: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: int = 3,
        timeout_seconds: int = 300,
        job_id: Optional[str] = None,
    ):
        self.job_id = job_id or str(uuid.uuid4())
        self.job_type = job_type
        self.data = data
        self.priority = priority
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

        self.status = JobStatus.PENDING
        self.retries = 0
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status.value,
            "priority": self.priority.name,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        job = cls(
            job_type=data["job_type"],
            data=data.get("data", {}),
            priority=JobPriority[data.get("priority", "NORMAL")],
            max_retries=data.get("max_retries", 3),
            timeout_seconds=data.get("timeout_seconds", 300),
            job_id=data.get("job_id"),
        )
        job.status = JobStatus[data.get("status", "PENDING")]
        job.retries = data.get("retries", 0)
        job.result = data.get("result")
        job.error = data.get("error")
        return job


class JobQueue:
    """Queue for managing background jobs."""

    def __init__(self):
        self.job_handlers: Dict[str, Callable] = {}
        self.redis = None

    async def initialize(self):
        """Initialize Redis connection."""
        self.redis = await get_redis()

    async def enqueue(self, job: Job) -> str:
        """Enqueue a job."""
        try:
            queue_key = f"queue:{job.priority.value}"
            job_key = f"job:{job.job_id}"

            # Store job data
            await self.redis.set(job_key, job.to_json(), ex=7*24*3600)  # 7 days TTL

            # Add to queue
            await self.redis.lpush(queue_key, job.job_id)

            logger.info(f"Enqueued job {job.job_id} ({job.job_type}) with priority {job.priority.name}")
            return job.job_id

        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            raise

    async def dequeue(self, priority: JobPriority = JobPriority.NORMAL) -> Optional[Job]:
        """Dequeue a job from the queue."""
        try:
            queue_key = f"queue:{priority.value}"
            job_id = await self.redis.rpop(queue_key)

            if not job_id:
                return None

            job_data = await self.redis.get(f"job:{job_id}")
            if not job_data:
                return None

            job = Job.from_dict(json.loads(job_data))
            return job

        except Exception as e:
            logger.error(f"Failed to dequeue job: {e}")
            return None

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status."""
        try:
            job_data = await self.redis.get(f"job:{job_id}")
            if not job_data:
                return None
            return json.loads(job_data)
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return None

    def register_handler(self, job_type: str, handler: Callable):
        """Register a handler for a job type."""
        self.job_handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")

    async def execute_job(self, job: Job) -> bool:
        """Execute a job."""
        handler = self.job_handlers.get(job.job_type)
        if not handler:
            logger.error(f"No handler for job type: {job.job_type}")
            job.status = JobStatus.FAILED
            job.error = "No handler found"
            return False

        try:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.utcnow()

            logger.info(f"Executing job {job.job_id} ({job.job_type})")

            # Execute with timeout
            result = await asyncio.wait_for(
                handler(job.data),
                timeout=job.timeout_seconds
            )

            job.status = JobStatus.COMPLETED
            job.result = result
            job.completed_at = datetime.utcnow()

            logger.info(f"✓ Job {job.job_id} completed successfully")

            # Store result
            await self.redis.set(f"job:{job.job_id}", job.to_json(), ex=7*24*3600)
            return True

        except asyncio.TimeoutError:
            logger.error(f"Job {job.job_id} timed out after {job.timeout_seconds}s")
            job.error = f"Timeout after {job.timeout_seconds}s"
            return await self._handle_job_failure(job)

        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}")
            job.error = str(e)
            return await self._handle_job_failure(job)

    async def _handle_job_failure(self, job: Job) -> bool:
        """Handle job failure with retries."""
        if job.retries < job.max_retries:
            job.retries += 1
            job.status = JobStatus.RETRYING

            logger.info(f"Retrying job {job.job_id} (attempt {job.retries}/{job.max_retries})")

            # Re-enqueue
            queue_key = f"queue:{job.priority.value}"
            await self.redis.lpush(queue_key, job.job_id)
            await self.redis.set(f"job:{job.job_id}", job.to_json(), ex=7*24*3600)

            return False

        else:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            logger.error(f"Job {job.job_id} failed after {job.max_retries} retries")

            # Store final state
            await self.redis.set(f"job:{job.job_id}", job.to_json(), ex=7*24*3600)
            return False

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        try:
            stats = {}
            for priority in JobPriority:
                queue_key = f"queue:{priority.value}"
                count = await self.redis.llen(queue_key)
                stats[priority.name] = count

            return {
                "queues": stats,
                "total_pending": sum(stats.values()),
            }
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {}

    async def clear_queue(self, priority: Optional[JobPriority] = None):
        """Clear jobs from queue."""
        try:
            if priority:
                queue_key = f"queue:{priority.value}"
                await self.redis.delete(queue_key)
                logger.info(f"Cleared queue: {priority.name}")
            else:
                for p in JobPriority:
                    queue_key = f"queue:{p.value}"
                    await self.redis.delete(queue_key)
                logger.info("Cleared all queues")
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")


# Job type handlers
async def send_email_handler(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for sending emails."""
    logger.info(f"Sending email to {data.get('to')}")
    return {"sent": True, "message_id": str(uuid.uuid4())}


async def generate_report_handler(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for generating reports."""
    logger.info(f"Generating report: {data.get('report_type')}")
    await asyncio.sleep(2)  # Simulate work
    return {"report_id": str(uuid.uuid4()), "status": "completed"}


async def process_webhook_handler(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for processing webhooks."""
    logger.info(f"Processing webhook: {data.get('webhook_type')}")
    return {"processed": True}


async def cleanup_handler(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for cleanup tasks."""
    logger.info("Running cleanup tasks")
    return {"cleaned": True}


# Global queue
_job_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """Get global job queue."""
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue()
    return _job_queue
