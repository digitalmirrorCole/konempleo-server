from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import asyncio
import inspect


class ThreadPoolManager:
    """
    Class that simplifies the execution of background tasks and provides
    status updates.
    """

    def __init__(self, max_workers=5):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks = {}

    def submit_task(self, func, *args, **kwargs):
        """
        Adds a task to the executor and starts execution if a worker is
        available.
        """
        task_id = str(uuid4())
        self.tasks[task_id] = {"status": "Queued"}

        if inspect.iscoroutinefunction(func):
            future = asyncio.run_coroutine_threadsafe(
                self._run_async_task(task_id, func, *args, **kwargs),
                asyncio.get_event_loop())
        else:
            future = self.executor.submit(self._run_task, task_id, func, *args,
                                          **kwargs)

        self.tasks[task_id]["future"] = future
        return task_id

    async def _run_async_task(self, task_id, func, *args, **kwargs):
        """Runs async functions inside the event loop."""
        self.tasks[task_id]["status"] = "Processing"
        try:
            await func(*args, **kwargs)
            self.tasks[task_id]["status"] = "Completed"
        except Exception as e:
            self.tasks[task_id]["status"] = f"Failed: {str(e)}"

    def _run_task(self, task_id, func, *args, **kwargs):
        """Runs sync functions inside a thread."""
        self.tasks[task_id]["status"] = "Processing"
        try:
            func(*args, **kwargs)
            self.tasks[task_id]["status"] = "Completed"
        except Exception as e:
            self.tasks[task_id]["status"] = f"Failed: {str(e)}"

    def get_task_status(self, task_id):
        """Returns the status of a given task."""
        return self.tasks.get(task_id, {"status": None})["status"]
