import os
import time
from collections import defaultdict
from functools import wraps, partial
import threading

import tools.io_utils as io_utils
from settings import TimeRecord as TR

time_path = f"{TR.TIME_RECORD_PATH}/{TR.TIME_FILE_NAME}"
start_record = TR.START_RECORD


class TimeRecorder:
    """
    A decorator to record and report the execution time of functions.
    """
    records = defaultdict(lambda: defaultdict(list))  # {id: {func_name: time}}

    def __init__(self, func):
        self.func = func
        wraps(func)(self)

    def __get__(self, instance, owner):
        """
        Enable the decorator to support binding as an instance method.
        When the decorated attribute is accessed via an instance, return a partial
        so that the first positional argument of self.__call__ is the instance (i.e., the method's self).
        """
        if instance is None:
            return self
        return partial(self.__call__, instance)

    def __call__(self, *args, **kwargs):
        global start_record
        if not start_record:
            return self.func(*args, **kwargs)

        # get task id from arguments
        func_args = self.func.__code__.co_varnames
        id_value = None
        if "task_info" in kwargs:
            id_value = kwargs["task_info"]["id"]
        elif "task_info" in func_args:
            tidx = func_args.index("task_info")
            if len(args) > tidx:
                id_value = args[tidx]["id"]

        if id_value is None:
            print(f"Agent [TimeRecorder] can't find task id in func {self.func.__name__}")
            return self.func(*args, **kwargs)

        start = time.time()
        result = self.func(*args, **kwargs)
        duration = time.time() - start

        
        lock = threading.Lock()
        with lock:
            TimeRecorder.records[id_value].update({self.func.__name__: duration})

        return result

    @staticmethod
    def update_records():
        """
        Get all the records stored in the class.
        Update the records loaded from time_path and write back to the file.
        """
        if not start_record: return
        old_records: dict
        if os.path.exists(time_path):
            old_records = io_utils.load_json(time_path)
        else:
            old_records = {"details":{}}
        new_records = old_records.copy()
        for id_value in TimeRecorder.records:
            new_records["details"][id_value].update(TimeRecorder.records[id_value])
        io_utils.write_json(time_path, new_records)
        return