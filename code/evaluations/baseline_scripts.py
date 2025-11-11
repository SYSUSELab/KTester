import os
import re
import time
import queue
import logging
import subprocess
import concurrent.futures

import tools.io_utils as io_utils
from tools.code_analysis import JavaCodeEditor
from procedure.post_process import check_class_name
from tools.execute_test import JavaRunner, CoverageExtractor


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
    tmp_folder = ""

    def __init__(self, dfolder, tmp_fd, dep_fd):
        self.data_folder = dfolder
        self.tmp_folder = tmp_fd
        self.dependency_fd = dep_fd
        
        self.logger = logging.getLogger(__name__)
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

    def set_java_runner(self, project_url):
        java_runner = JavaRunner(project_url, self.dependency_fd)
        test_dependencies = f"libs/*;target/test-classes;target/classes;{self.dependency_fd}/*"
        java_runner.test_base_cmd = [
            'java', 
            "--add-opens", "java.base/java.lang=ALL-UNNAMED",
            "--add-opens", "java.base/java.net=ALL-UNNAMED",
            "--add-opens", "java.desktop/java.awt=ALL-UNNAMED",
            # "--add-opens", "java.base/java.util=ALL-UNNAMED",
            # "--add-opens", "java.base/sun.reflect.annotation=ALL-UNNAMED",
            # "--add-opens", "java.base/java.text=ALL-UNNAMED",
            '-cp', test_dependencies, 
            'org.junit.platform.console.ConsoleLauncher', 
            '--disable-banner', 
            '--disable-ansi-colors',
            '--fail-if-no-tests',
        ]
        return java_runner

    def _parse_error_line(self, feedback:str, class_path:str):
        '''
        Parse the compilation feedback to get the error line number and error message.
        '''
        error_lines = []
        split_str = class_path.replace("/", "\\")
        errors = feedback.split(f"{split_str}:")
        for error in errors:
            if str(error).find(": error: ")==-1: continue
            splits = error.split(": error: ")
            try:
                line = int(splits[0]) - 1
                error_lines.append(line)
            except:
                continue
        return error_lines

    def _extend_removing_lines(self, error_lines: list, case_positions):
        starts = case_positions[0]
        ends = case_positions[1]
        count = len(starts)
        extend = set(error_lines)

        for line in error_lines:
            for i in range(count):
                if line >= starts[i] and line <= ends[i]:
                    extend.update(range(starts[i], ends[i]+1))
                    break
        self.logger.info(f"Extending removing lines: {extend}")
        return list(extend)

    """
    check whether generated tests covered target method
    Extract test cases that cover the target method and assemble them into a test class
    """
    def process_test_classes(self, result_folder, dataset_info):
        for pname, pinfo in dataset_info.items():
            project_source = f"{self.tmp_folder}/{pname}/evosuite-tests/"
            project_target = f"{result_folder}/{pname}/test_classes/"
            project_url = pinfo["project-url"]
            io_utils.check_path(project_target)
            self.logger.info(f"project source:{project_source}, project target:{project_target}, project url:{project_url}")
            # 1. prepare task dictionary
            # {"test_class": {"ids":{"id":method_name}, "package":package, "running_path": running_path}}
            task_dict = {}
            for tinfo in pinfo["focal-methods"]:
                id = tinfo["id"]
                method_name = tinfo["method-name"]
                test_class = tinfo["class"].split('.')[-1] + "_ESTest"
                if test_class not in task_dict:
                    running_path = "/".join(tinfo["test-path"].split('/')[:-1])
                    pkgname = tinfo["package"]
                    task_dict[test_class] = {"ids": {id: method_name}, "package": pkgname, "running_path": running_path}
                else:
                    task_dict[test_class]["ids"][id] = method_name
            # 2. copy test classes
            dir_list = queue.Queue()
            dir_list.put(project_source)
            while not dir_list.empty():
                current_dir = dir_list.get()
                paths = os.listdir(current_dir)
                for path in paths:
                    full_path = os.path.join(current_dir, path)
                    if os.path.isdir(full_path):
                        dir_list.put(full_path)
                    elif path.endswith(".java") and path.find("Original") == -1:
                        if path.endswith("scaffolding.java"):
                            self.logger.info(f"Copying file {full_path} to {project_target}")
                            io_utils.copy_file(full_path, project_target)
                        class_name = path.removesuffix(".java").removesuffix("_scaffolding")
                        running_path = f"{project_url}/{task_dict[class_name]['running_path']}/{path}"
                        io_utils.copy_file(full_path, running_path)
            # set running environment
            java_runner = self.set_java_runner(project_url)
            coverage_extractor = CoverageExtractor()
            for test_class, tinfo in task_dict.items():
                code_editor = JavaCodeEditor()
                running_path = f"{tinfo['running_path']}/{test_class}.java"
                code_path= f"{project_url}/{running_path}"
                self.logger.info(f"code path: {code_path}")
                if not os.path.exists(code_path): continue
                pkgname = tinfo['package']
                class_fqn = f"{pkgname}.{test_class}"
                code = io_utils.load_text(code_path)
                code_editor.parse(code)
                # 3. remove uncompiled test cases
                java_runner.compile_test(running_path.replace(".java", "_scaffolding.java"))
                cflag, feedback = java_runner.compile_test(running_path)
                while not cflag:
                    error_lines = self._parse_error_line(feedback, running_path)
                    case_positions = code_editor.get_test_case_position()
                    error_lines = self._extend_removing_lines(error_lines, case_positions)
                    code_editor.remove_lines(error_lines)
                    code = code_editor.get_code()
                    io_utils.write_text(code_path, code)
                    cflag, feedback = java_runner.compile_test(running_path)
                # 4. extract test methods and class framework
                starts, ends, mnames = code_editor.get_test_case_position()
                framework_start = code_editor.get_code([[0, starts[0]-1]])
                framework_end = code_editor.get_code([ends[-1]+1,code_editor.get_length()-1])
                # 5. check which test methods cover the target method
                task_method_position = {}
                for id in tinfo["ids"]: task_method_position[id] = []
                for i in range(len(mnames)):
                    mname = f"{class_fqn}#{mnames[i]}"
                    eflag = java_runner.run_selected_mehods([mname])
                    if not eflag: continue
                    html_report = "target/jacoco-report/"
                    java_runner.generate_report_single(html_report)
                    for id, tmname in tinfo["ids"].items():
                        html_path = f"{project_url}/{html_report}{pkgname}/{test_class.removesuffix('_ESTest')}.html"
                        coverage = coverage_extractor.extract_single_coverage(html_path, tmname)
                        if coverage and coverage[0] > 0:
                            task_method_position[id].append([starts[i], ends[i]])
                    java_runner.delete_jacoco_exec()
                # 6. assemble test methods into a new test class
                for id, tmname in tinfo["ids"].items():
                    position = task_method_position[id]
                    test_cases = code_editor.get_code(position)
                    new_code = framework_start + "\n" + test_cases + "\n" + framework_end
                    new_code = check_class_name(new_code, f"{id}_Test")
                    file_name = f"{project_target}/{id}_Test.java"
                    self.logger.info(f"Writing new test class to {file_name}")
                    io_utils.write_text(file_name, new_code)


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


def running_utgen(dataset_info, dataset_folder, workspace, tmp_folder, dep_folder, result_folder):
    tmp_folder = f"{tmp_folder}/UTGen-test"
    for _, p_info in dataset_info.items():
        p_info['project-url'] = f"{dataset_folder}/{p_info['project-url']}"
    utgen_runner = UTGenRunner(workspace, tmp_folder, dep_folder)
    # utgen_runner.prepare_dataset(dataset_info)
    utgen_runner.process_test_classes(result_folder, dataset_info)


def running_baselines(baseline, dataset_info, task_setting, file_structure):
    baseline_path = baseline.BASELINE_PATH
    selected_baselines = baseline.BASELINES
    chatunitest_data = baseline.CHATUNITEST_DATA
    utgen_data = baseline.UTGEN_DATA
    dependency_path = file_structure.DEPENDENCY_PATH
    dataset_path = file_structure.DATASET_PATH
    logger = logging.getLogger(__name__)
    root_path = os.getcwd().replace("\\", "/")
    dep_folder = f"{root_path}/{dependency_path}"
    tmp_folder = f"{root_path}/{baseline_path}/tmp"
    
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
    
    # UTGen script
    if "UTGen" in selected_baselines:
        logger.info("Using UTGen generation...")
        utgen_result = f"{baseline_path}/UTGen"
        running_utgen(dataset_info, dataset_path, utgen_data, tmp_folder, dep_folder, utgen_result)
    return


if __name__ == "__main__":
    # test runners
    # import sys
    # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from settings import BaseLine, FileStructure
    utgen_data_folder = BaseLine.UTGEN_DATA
    dataset_file = f"{FileStructure.DATASET_PATH}/dataset_info.json"
    dataset = io_utils.load_json(dataset_file)
    # utgen_runner = UTGenRunner(utgen_data_folder)
    # utgen_runner.prepare_dataset(dataset)
    pass