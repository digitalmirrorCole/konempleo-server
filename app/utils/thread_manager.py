from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4


class ThreadPoolManager:
    """
    Class that simplifies the work of multiple tasks in the background and
    returns a simple status when required.
    """

    def __init__(self, max_workers=5):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks = {}

    def submit_task(self, func, *args, **kwargs):
        """
        Adds a task to the executor and if there is a worker available it will
        start the task right away.
        """
        task_id = str(uuid4())
        self.tasks[task_id] = "Queued"
        _ = self.executor.submit(self._run_task, task_id, func, *args,
                                 **kwargs)
        return task_id

    def _run_task(self, task_id, func, *args, **kwargs):
        self.tasks[task_id] = "Processing"
        try:
            func(*args, **kwargs)
            self.tasks[task_id] = "Completed"
        except Exception as e:
            self.tasks[task_id] = f"Failed: {str(e)}"

    def get_task_status(self, task_id):
        """
        Returns the status of a given task.
        """
        return self.tasks.get(task_id, "Not Found")
