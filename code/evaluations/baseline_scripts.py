import concurrent
import os

import time
import logging
import subprocess
import concurrent.futures
from venv import logger

import tools.io_utils as io_utils


class ChatUniTestRunner():
    # project_url = ""
    cd_cmd: list
    gen_folder: str
    phase_type: str
    logger: logging.Logger

    def __init__(self, phs_tp):
        # self.project_url = prj_url
        self.gen_folder = "/tmp/" + phs_tp + "-test"
        self.phase_type = phs_tp.upper()
        self.logger = logging.getLogger(__name__)
        return
    
    def running_task(self, project_info):
        prj_url = project_info["project-url"]
        self.cd_cmd = ["cd", prj_url, '&&']
        task_ids = set()
        time_record = {}

        for test_info in project_info["focal-methods"]:
            task_ids.add(test_info["id"].replace("_", "#").replace("#2", ""))
        for task_id in task_ids:
            start_time = time.time()
            self.generate_test4method(task_id)
            end_time = time.time()
            time_record[task_id] = end_time - start_time
        return time_record

    def generate_test4method(self, select_method:str):
        # mvn chatunitest:method -DphaseType <method> -D testOutput /tmp/<method>-test -DselectMethod <class>#<method>
        # TODO: use full name for generation
        gen_cmd = ["mvn", "chatunitest:method", f"-DtestOutput={self.gen_folder}", f"-DselectMethod={select_method}"]
        if self.phase_type != "CHATUNITEST":
            gen_cmd.append(f"-DphaseType={self.phase_type}")
            if self.phase_type == "HITS":
                gen_cmd.append("-DtestNumber=3")
        script = self.cd_cmd + gen_cmd
        self.logger.info("Command: " + " ".join(script))
        result = subprocess.run(script, shell=True, capture_output=True, text=True, encoding="utf-8")
        self.logger.info("Output: " + result.stdout)
        if result.returncode != 0:
            self.logger.error(f"Error occurred at {select_method}, info:\n{result.stderr}")
        return

class UTGenRunner():
    data_folder = ""

    def __init__(self, dfolder):
        self.data_folder = dfolder
        return
    
    def prepare_dataset(self, dataset):
        csv_file = f"{self.data_folder}/projects_binary/classes.csv"
        csv_header = ["project", "class"]
        csv_data = []
        extracted_classes = set()
        for pname,pinfo in dataset.items():
            for minfo in pinfo["focal-methods"]:
                class_name = minfo["class"]
                if class_name not in extracted_classes:
                    csv_data.append([pname, class_name])
                    extracted_classes.add(class_name)
        io_utils.write_csv(csv_file, csv_data, csv_header)
        pass
    
    def process_test_classes(self):
        pass


def running_chatunitest(dataset_info, phase_type, workspace, result_folder):
    mworkers = len(dataset_info)
    logger = logging.getLogger(__name__)
    time_file = f"{result_folder}/time_record.json"
    if os.path.exists(time_file):
        time_record_sum = io_utils.load_json(time_file)
    else:
        time_record_sum = {"details": {}}

    def run4project(project_info):
        pname = project_info["project-name"]
        logger.info(f"Processing project: {pname}")
        chatunitest_runner = ChatUniTestRunner(phase_type)
        time_record = chatunitest_runner.running_task(project_info)
        logger.info(f"finished processing project: {pname}")
        return time_record

    with concurrent.futures.ThreadPoolExecutor(max_workers=mworkers) as executor:
        futures = []
        for _, p_info in dataset_info.items():
            project_path = f"{workspace}/{p_info['project-url']}"
            project_info = p_info.copy()
            project_info["project-url"] = project_path
            future = executor.submit(run4project, project_info)
            futures.append(future)
        for future in concurrent.futures.as_completed(futures):
            try:
                record = future.result()
                time_record_sum["details"].update(record)
            except Exception as e:
                logger.error(f"Error processing test case: {e}")
    io_utils.write_json(time_file, time_record_sum)
    pass


def running_baselines(baseline, dataset_info):
    baseline_path = baseline.BASELINE_PATH
    selected_baselines = baseline.BASELINES
    chatunitest_data = baseline.CHATUNITEST_DATA
    logger = logging.getLogger(__name__)

    root_path = os.getcwd().replace("\\", "/")
    
    # HITS script
    if "HITS" in selected_baselines:
        logger.info("Using HITS generation...")
        hits_result = f"{baseline_path}/HITS"
        workspace = f"{root_path}/{chatunitest_data}"
        running_chatunitest(dataset_info, "HITS", workspace, hits_result)

    # ChatUniTest script
    if "ChatUniTest" in selected_baselines:
        logger.info("Using ChatUniTest generation...")
        chatunitest_result = f"{baseline_path}/ChatUniTest"
        workspace = f"{root_path}/{chatunitest_data}"
        running_chatunitest(dataset_info, "ChatUniTest", workspace, chatunitest_result)
    
    # ChatTester script
    if "ChatTester" in selected_baselines:
        logger.info("Using ChatTester generation...")
        chattester_result = f"{baseline_path}/ChatTester"
        workspace = f"{root_path}/{chatunitest_data}"
        running_chatunitest(dataset_info, "ChatTester", workspace, chattester_result)
    return


if __name__ == "__main__":
    # test runners
    # import sys
    # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from settings import BaseLine, FileStructure
    utgen_data_folder = BaseLine.UTGEN_DATA
    dataset_file = f"{FileStructure.DATASET_PATH}/dataset_info.json"
    dataset = io_utils.load_json(dataset_file)
    utgen_runner = UTGenRunner(utgen_data_folder)
    utgen_runner.prepare_dataset(dataset)
    pass