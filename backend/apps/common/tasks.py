import logging

from celery import shared_task

from apps.common.mail import tasks as mail_tasks  # noqa: F401  (registers mail tasks)

logger = logging.getLogger("erp.tasks")


@shared_task(name="common.ping")
def ping() -> str:
    """Infrastructure check used to confirm the Celery worker can execute a task."""

    logger.info("Celery ping task executed")
    return "pong"
