import os
import re
import time
import queue
import logging
import subprocess
import concurrent.futures

import tools.io_utils as io_utils
from procedure.post_process import check_class_name


class ChatUniTestRunner():
    # project_url = ""
    cd_cmd: list
    gen_folder: str
    phase_type: str
    logger: logging.Logger

    def __init__(self, phs_tp, tmp_fd):
        # self.project_url = prj_url
        self.gen_folder = f"{tmp_fd}/{phs_tp}-test"
        self.phase_type = phs_tp.upper()
        self.logger = logging.getLogger(__name__)
        return
    
    def running_task(self, project_info, case_list):
        prj_url = project_info["project-url"]
        self.cd_cmd = ["cd", prj_url, '&&']
        case_select = True if len(case_list) > 0 else False
        task_ids = set()
        time_record = {}

        for tinfo in project_info["focal-methods"]:
            if case_select and tinfo["id"] not in case_list:
                continue
            method_name = tinfo["method-name"].split("(")[0]
            task_id = f"{tinfo["class"]}#{method_name}"
            task_ids.add(task_id)

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
        result = subprocess.run(script, shell=True, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        self.logger.info("Output: " + result.stdout)
        if result.returncode != 0:
            self.logger.error(f"Error occurred at {select_method}, info:\n{result.stderr}")
        return

    def _process_classes_hits(self, project_source, project_target):
        io_utils.copy_dir(project_source, project_target)
        # Traverse all files under gen_folder
        dir_list = queue.Queue()
        dir_list.put(project_target)
        delete_list = []
        code_set = set()

        while not dir_list.empty():
            current_dir = dir_list.get()
            paths = os.listdir(current_dir)
            for path in paths:
                full_path = os.path.join(current_dir, path)
                if os.path.isdir(full_path):
                    dir_list.put(full_path)
                elif path.endswith(".java"):
                    code = io_utils.load_text(full_path)
                    pass_flag = True
                    for line in code.splitlines():
                        if line not in code_set:
                            code_set.add(line)
                            pass_flag = False
                    
                    if pass_flag:
                        self.logger.info(f"Deleting file {full_path}, as it contains no unique code")
                    else:
                        file_name = re.sub(r"[0-9]+_[0-9]+_", "", path)
                        count = 2
                        while os.path.exists(os.path.join(current_dir, file_name)):
                            file_name = re.sub(r"[0-9]+_[0-9]+_", f"{count}_", path)
                            count += 1
                        target_file = os.path.join(current_dir, file_name)
                        class_name = file_name.replace(".java", "")
                        if class_name is None:
                            self.logger.error(f"Invalid class name in {path}")
                            continue
                        code = check_class_name(code, class_name)
                        io_utils.write_text(target_file, code)
                    os.remove(full_path)
        return

    def _process_classes_chatunitest(self, project_source, project_target):
        dir_list = queue.Queue()
        dir_list.put(project_source)
        while not dir_list.empty():
            current_dir = dir_list.get()
            paths = os.listdir(current_dir)
            for path in paths:
                full_path = os.path.join(current_dir, path)
                if os.path.isdir(full_path):
                    dir_list.put(full_path)
                elif path.endswith(".java"): # check file name and copy file
                    file_name = re.sub(r"[0-9]+_[0-9]+_", "", path)
                    count = 2
                    while os.path.exists(os.path.join(project_target, file_name)):
                        file_name = re.sub(r"[0-9]+_[0-9]+_", f"{count}_", path)
                        count += 1
                    target_file = os.path.join(project_target, file_name)
                    # Check and modify class name
                    class_name = file_name.replace(".java", "")
                    if class_name is None:
                        self.logger.error(f"Invalid class name in {path}")
                        continue
                    code = io_utils.load_text(full_path)
                    code = check_class_name(code, class_name)
                    self.logger.info(f"Copying file {full_path} to {target_file}")
                    io_utils.write_text(target_file, code)
        return

    def process_test_classes(self, result_folder):
        repetition = 1
        target_foler = f"{result_folder}/rep_{repetition}"
        while os.path.exists(target_foler):
            repetition += 1
            target_foler = f"{result_folder}/rep_{repetition}"
        io_utils.check_path(target_foler)

        project_folders = os.listdir(self.gen_folder)
        for project_folder in project_folders:
            project_source = f"{self.gen_folder}/{project_folder}/"
            project_target = f"{target_foler}/{project_folder}/test_classes/"
            io_utils.check_path(project_target)
            if self.phase_type == "HITS":
                self._process_classes_hits(project_source, project_target)
            else:
                self._process_classes_chatunitest(project_source, project_target)
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
        return
    
    """
    TODO: check whether generated tests covered target method
    Extract test cases that cover the target method and assemble them into a test class
    """
    def process_test_classes(self):
        # 
        pass


def running_chatunitest(dataset_info, task_setting, phase_type, workspace, tmp_folder, result_folder):
    projects = task_setting.PROJECTS
    case_list = task_setting.CASES_LIST
    project_select = True if len(projects) > 0 else False
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
        chatunitest_runner = ChatUniTestRunner(phase_type, tmp_folder)
        time_record = chatunitest_runner.running_task(project_info, case_list)
        logger.info(f"finished processing project: {pname}")
        return time_record

    with concurrent.futures.ThreadPoolExecutor(max_workers=mworkers) as executor:
        futures = []
        for pj_name, p_info in dataset_info.items():
            if project_select and pj_name not in projects:
                continue
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
    # save time record
    io_utils.write_json(time_file, time_record_sum)
    # process test classes
    chatunitest_runner = ChatUniTestRunner(phase_type, tmp_folder)
    chatunitest_runner.process_test_classes(result_folder)
    return


def running_baselines(baseline, dataset_info, task_setting):
    baseline_path = baseline.BASELINE_PATH
    selected_baselines = baseline.BASELINES
    chatunitest_data = baseline.CHATUNITEST_DATA
    logger = logging.getLogger(__name__)
    root_path = os.getcwd().replace("\\", "/")
    tmp_folder = f"{baseline_path}/tmp"
    
    # HITS script
    if "HITS" in selected_baselines:
        logger.info("Using HITS generation...")
        hits_result = f"{baseline_path}/HITS"
        workspace = f"{root_path}/{chatunitest_data}"
        running_chatunitest(dataset_info, task_setting, "HITS", workspace, tmp_folder,hits_result)

    # ChatUniTest script
    if "ChatUniTest" in selected_baselines:
        logger.info("Using ChatUniTest generation...")
        chatunitest_result = f"{baseline_path}/ChatUniTest"
        workspace = f"{root_path}/{chatunitest_data}"
        running_chatunitest(dataset_info, task_setting, "ChatUniTest", workspace, tmp_folder,chatunitest_result)
    
    # ChatTester script
    if "ChatTester" in selected_baselines:
        logger.info("Using ChatTester generation...")
        chattester_result = f"{baseline_path}/ChatTester"
        workspace = f"{root_path}/{chatunitest_data}"
        running_chatunitest(dataset_info, task_setting, "ChatTester", workspace, tmp_folder,chattester_result)
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