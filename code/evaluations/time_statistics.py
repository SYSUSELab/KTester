from math import sqrt
import os
import logging

import tools.io_utils as io_utils


"""
{"statistics":{
    "agerage_total": 123.45,
    "average_detail": {
        "task1": 1.23, ...
    },
    "median_time": 7.89,
    "min_time": 4.56,
    "max_time": 10.11,
    "std_time": 2.34
"""
def process_time_file(time_file):
    time_record = io_utils.load_json(time_file)
    details:dict = time_record.get("details", {})
    rec_num = len(details)
    subtask_count = {}
    subtask_time = {}
    time_list = []
    for _, record in details.items():
        if isinstance(record, float):
            time_list.append(record)
        elif isinstance(record, dict):
            single_time = 0.0
            for task, time in record.items():
                if task in subtask_count:
                    subtask_count[task] += 1
                    subtask_time[task] += time
                else:
                    subtask_count[task] = 1
                    subtask_time[task] = time
                single_time += time
            time_list.append(single_time)

    average_total = sum(time_list) / rec_num
    time_list.sort()
    min_time = time_list[0]
    max_time = time_list[-1]
    average_detail = {task: round(subtask_time[task] / subtask_count[task], 2) for task in subtask_count}
    median_time = sorted(time_list)[rec_num // 2]
    std_time = sqrt(sum((x - average_total) ** 2 for x in time_list) / rec_num)
    time_record["statistics"] = {
        "average_total": round(average_total, 2),
        "average_detail": average_detail,
        "median_time": round(median_time, 2),
        "min_time": round(min_time, 2),
        "max_time": round(max_time, 2),
        "std_time": round(std_time, 2)
    }
    io_utils.write_json(time_file, time_record)
    return


"""
Calculate time statistics from a list of time records.
"""
def calculate_time_statistics(time_record):
    time_record_path = time_record.TIME_RECORD_PATH
    logger = logging.getLogger(__name__)

    time_files = [f"{time_record_path}/{file}" for file in os.listdir(time_record_path)]
    for time_file in time_files:
        logger.info(f"Processing time file: {time_file}")
        process_time_file(time_file)
    return
