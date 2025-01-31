from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import inspect
import threading
import time


class Status(Enum):
    QUEUED = 1
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4


class Task:
    def __init__(self, task_id=None, status="Queued", offer_id=None,
                 future=None, message=""):
        self.task_id = task_id
        self.status = status
        self.message = status
        self.offer_id = offer_id
        self.future = future
        self.start_date = None

    def is_cleanable(self):
        return (self.start_date is not None and
                datetime.now() - self.start_date > timedelta(minutes=5) and
                self.status in [Status.COMPLETED, Status.FAILED]) or \
                (self.start_date is not None and
                 datetime.now() - self.start_date > timedelta(minutes=60))

    def set_status(self, status, message=None):
        self.status = status
        if status == Status.QUEUED:
            self.message = message if message is not None else "Queued"
        elif status == Status.PROCESSING:
            self.message = message if message is not None else "Processing"
            self.start_date = time.time()
        elif status == Status.COMPLETED:
            self.message = message if message is not None else "Completed"
        elif status == Status.FAILED:
            self.message = message if message is not None else "Failed"

    def __dict__(self):
        return {"status": self.status, "message": self.message,
                "offer_id": self.offer_id, "task_id": self.task_id}


class ThreadPoolManager:
    """
    Class that simplifies the execution of background tasks and provides
    status updates.
    """

    def __init__(self, max_workers=5):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks = {}
        self.cleanup_interval = 60 * 5  # Clean tasks every 5min
        threading.Thread(target=self._cleanup_tasks, daemon=True).start()

    def _cleanup_tasks(self):
        """Periodically removes completed tasks."""
        while True:
            time.sleep(self.cleanup_interval)
            for task_id in self.tasks.keys():
                if self.tasks[task_id].is_cleanable():
                    del self.tasks[task_id]

    def submit_task(self, offer_id, func, *args, **kwargs):
        """
        Adds a task to the executor and starts execution if a worker is
        available.
        """
        task_id = str(uuid4())
        self.tasks[task_id] = Task(task_id=task_id, offer_id=offer_id)

        if inspect.iscoroutinefunction(func):
            future = asyncio.run_coroutine_threadsafe(
                self._run_async_task(task_id, func, *args, **kwargs),
                asyncio.get_event_loop())
        else:
            future = self.executor.submit(self._run_task, task_id, func, *args,
                                          **kwargs)
        self.tasks[task_id].future = future
        return task_id

    async def _run_async_task(self, task_id, func, *args, **kwargs):
        """Runs async functions inside the event loop."""
        self.tasks[task_id].set_status(Status.PROCESSING)

        try:
            await func(*args, **kwargs)
            self.tasks[task_id].set_status(Status.COMPLETED)
        except Exception as e:
            self.tasks[task_id].set_status(Status.FAILED,
                                           f"Failed: {str(e)}")

    def _run_task(self, task_id, func, *args, **kwargs):
        """Runs sync functions inside a thread."""
        self.tasks[task_id].set_status(Status.PROCESSING)
        try:
            func(*args, **kwargs)
            self.tasks[task_id].set_status(Status.COMPLETED)
        except Exception as e:
            self.tasks[task_id].set_status(Status.FAILED,
                                           f"Failed: {str(e)}")

    def get_task(self, task_id):
        """Returns the status of a given task."""
        result = self.tasks.get(task_id, {"status": None})
        return result.__dict__() if result is not None else None

    def get_tasks(self):
        result = []
        for task_id in self.tasks.keys():
            result.append(self.tasks[task_id].__dict__())
        return result
