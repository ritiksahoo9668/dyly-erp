import logging

from celery import shared_task

logger = logging.getLogger("erp.master.tasks")


@shared_task(name="master.process_import_job", bind=True, max_retries=0)
def process_import_job_task(self, job_id: int) -> str:
    """Process one Master Excel ImportJob in the background."""
    from .import_engine import process_import_job

    logger.info("Starting ImportJob %s (task=%s)", job_id, self.request.id)
    process_import_job(job_id)
    logger.info("Finished ImportJob %s", job_id)
    return f"import-job-{job_id}-done"
