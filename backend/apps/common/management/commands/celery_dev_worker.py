"""Run the Celery worker and restart it whenever backend code or templates change.

Development only: production runs ``celery -A config.celery worker`` directly.
"""

import atexit
import os
import subprocess
import threading

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import autoreload

WORKER_COMMAND = ["celery", "-A", "config.celery", "worker", "--loglevel=info"]
WATCH_PATTERNS = ("**/*.py", "**/templates/**/*")
SHUTDOWN_GRACE_SECONDS = 20

_reloading = threading.Event()


def watch_project(sender, **kwargs):
    # The worker's own modules (tasks, services) are not imported in this process, so the
    # default module-based watching would miss them.
    for pattern in WATCH_PATTERNS:
        sender.watch_dir(settings.BASE_DIR, pattern)


def stop_worker(process: subprocess.Popen) -> None:
    _reloading.set()
    if process.poll() is not None:
        return
    process.terminate()  # SIGTERM = Celery warm shutdown; running tasks finish first
    try:
        process.wait(timeout=SHUTDOWN_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_worker(worker_args: list[str]) -> None:
    process = subprocess.Popen([*WORKER_COMMAND, *worker_args])
    atexit.register(stop_worker, process)
    code = process.wait()
    if not _reloading.is_set():
        # The worker died on its own: exit so the failure is visible instead of idling.
        os._exit(code or 1)


class Command(BaseCommand):
    help = "Run the Celery worker with auto-restart on code changes (development only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--queues",
            default="",
            help="Comma-separated queues to consume (default: every declared queue).",
        )
        parser.add_argument("--concurrency", type=int, default=0)

    def handle(self, *args, **options):
        worker_args = []
        if options["queues"]:
            worker_args += ["-Q", options["queues"]]
        if options["concurrency"]:
            worker_args += ["--concurrency", str(options["concurrency"])]
        autoreload.autoreload_started.connect(watch_project)
        autoreload.run_with_reloader(run_worker, worker_args)
