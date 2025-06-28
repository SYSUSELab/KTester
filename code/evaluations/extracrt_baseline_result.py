import os
import re
import queue
import shutil
import logging
import subprocess
from bs4 import BeautifulSoup

import tools.io_utils as io_utils
from procedure.post_process import check_class_name
from evaluations.coverage_test import ProjectTestRunner, CoverageCalculator


def check_method_name(method_name, target):
    while len(re.findall(r"<[^<>]*>", target, flags=re.DOTALL))>0:
        target = re.sub(r"<[^<>]*>", "", target, flags=re.DOTALL)
    method_parts = method_name.replace("(", "( ").replace(")", " )").split()
    target_parts = target.replace("(", "( ").replace(")", " )").split()
    if len(method_parts) != len(target_parts):
        return False
    if method_parts[0] != target_parts[0]:
        return False
    for item_m, item_t in zip(method_parts[1:-1], target_parts[1:-1]):
        if item_m == "Object" or item_m == "Object,": continue
        if "." in item_m: item_m = item_m.split(".")[-1]
        if "." in item_t: item_t = item_t.split(".")[-1]
        elif item_m != item_t:
            return False
    return True


def extract_coverage_html(html_path, method):
    logger = logging.getLogger(__name__)
    logger.info(f"Extracting coverage form {html_path}, method: {method}")
    coverage_score = None
    if not os.path.exists(html_path):
        logger.exception(f"report file not found: {html_path}")
        return coverage_score
    with open(html_path, "r") as file:
        soup = BeautifulSoup(file, 'lxml-xml')
    for tr in soup.find_all(name='tbody')[0].find_all(name='tr', recursive=False):
        tds = tr.contents
        try:
            method_name = tds[0].span.string
        except AttributeError:
            method_name = tds[0].a.string
        if check_method_name(method_name, method):
            instruction_cov = float(tds[2].string.replace("%", ""))/100
            branch_cov = float(tds[4].string.replace("%", ""))/100
            coverage_score = {"inst_cov": instruction_cov, "bran_cov": branch_cov}
            break
    return coverage_score


def count_general_metrics(summary:dict):
    # case_num = 0
    # compile_num = 0
    # pass_num = 0
    tfunc_num = 0
    inst_cov = 0.0
    bran_cov = 0.0
    for _, item in summary.items():
        if "inst_cov" in item and not isinstance(item["inst_cov"],str):
            tfunc_num += 1
            inst_cov += item["inst_cov"]
            bran_cov += item["bran_cov"]
    summary.update({
        # "compile_pass_rate": compile_num/case_num if case_num > 0 else 0,
        # "execution_pass_rate": pass_num/case_num if case_num > 0 else 0,
        "average_instruction_coverage": inst_cov/tfunc_num if tfunc_num > 0 else 0.0,
        "average_branch_coverage": bran_cov/tfunc_num if tfunc_num > 0 else 0.0
    })
    return summary


def extract_coverage_HITS(result_folder, dataset_info, dataset_meta, save_path):
    if not os.path.exists(save_path): os.makedirs(save_path)
    logger = logging.getLogger(__name__)

    for meta_info in dataset_meta:
        pj_name = meta_info["project_name"]
        pj_info  = dataset_info[pj_name]
        name_to_idx = meta_info["method_name_to_idx"]
        project_result = f"{result_folder}/{pj_name}/methods"
        project_coverage = {}
        for tinfo in pj_info["focal-methods"]:
            method_name = tinfo["method-name"]
            target_class = tinfo["class"]
            msig = target_class + "." + method_name
            method_idx = name_to_idx[msig]
            package = tinfo["package"]
            class_name = target_class.split(".")[-1]
            coverage_path = f"{project_result}/{method_idx}/full_report/{package}/{class_name}.html"
            coverage_score = extract_coverage_html(coverage_path, method_name)
            if coverage_score is None:
                logger.exception(f"coverage score not found: {coverage_path}")
                coverage_score = {"inst_cov": 0, "bran_cov": 0}
            project_coverage[f"{target_class}#{method_name}"] = coverage_score
        project_coverage = count_general_metrics(project_coverage)
        io_utils.write_json(f"{save_path}/{pj_name}.json", project_coverage)
    return


def set_file_structure(report_path, dataset_info):
    for pj_name, pj_info in dataset_info.items():
        report_folder = report_path.replace("<project>", pj_name)
        report_csv = f"{report_folder}/jacoco-report-csv/"
        io_utils.check_path(report_csv)
        
        for test_info in pj_info["focal-methods"]:
            id = test_info["id"]
            report_html = f"{report_folder}/jacoco-report-html/{id}/"
            io_utils.check_path(report_html)
    pass


def extract_coverage_ChatUniTest(result_folder, dataset_info, fstruct, task_setting):
    root_path = os.getcwd().replace("\\", "/")
    testclass_path = f"{result_folder}/<project>/test_classes/"
    report_path = f"{root_path}/{result_folder}/<project>/reports/"
    dependency_dir = f"{root_path}/{fstruct.DEPENDENCY_PATH}"
    compile_test = task_setting.COMPILE_TEST
    projects = task_setting.PROJECTS
    select = True if len(projects)>0 else False
    logger = logging.getLogger(__name__)
    set_file_structure(report_path, dataset_info)
    total_result = {}
    calculator: CoverageCalculator

    for pj_name, info in dataset_info.items():
        if select and pj_name not in projects: continue
        # run converage test & generate report
        runner = ProjectTestRunner(info, dependency_dir, testclass_path, report_path)
        test_result = runner.run_project_test(compile_test)
        logger.info(test_result)
        # extract coverage
        calculator = CoverageCalculator(info, report_path)
        coverage_data = calculator.generate_project_summary(test_result)
        total_result.update(coverage_data)
        logger.info(f"report data:\n{coverage_data}")
        coverage_file = f"{report_path}/summary.json".replace("<project>", pj_name)
        io_utils.write_json(coverage_file, coverage_data)

    total_file = report_path.split("<project>")[0] + "summary.json"
    calculator.calculate_total_result(total_result, total_file)
    return


class HITSRunner(ProjectTestRunner):
    def __init__(self, project_info, dependency_dir, testclass_path, report_path):
        super().__init__(project_info, dependency_dir, testclass_path, report_path)

    def check_testclass_name(self):
        # 遍历 testclass_path下的所有文�?
        dir_list = queue.Queue()
        dir_list.put(self.testclass_path)
        while not dir_list.empty():
            current_dir = dir_list.get()
            paths = os.listdir(current_dir)
            for path in paths:
                full_path = os.path.join(current_dir, path)
                if os.path.isdir(full_path):
                    dir_list.put(full_path)
                elif path.endswith(".java") and "slice" in path:
                    self.logger.info(f"Checking class name in {full_path}")
                    class_name = path.replace(".java", "")
                    if class_name is None:
                        self.logger.error(f"Invalid class name in {file_path}")
                        continue
                    file_path = os.path.join(current_dir, path)
                    code = io_utils.load_text(file_path)
                    code = check_class_name(code, class_name)
                    io_utils.write_text(file_path, code)


    def run_project_test(self, compile_test=True):
        project_name = self.project_info["project-name"]
        project_url = self.project_info["project-url"]
        test_objects = self.project_info["focal-methods"]
        self.test_result = {}
        
        # copy test classes to the project directory
        test_dir = f"{project_url}/src/test/java/"
        compiled_classes = f"{project_url}/target/test-classes/"
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir, ignore_errors=False)
        if os.path.exists(compiled_classes):
            shutil.rmtree(compiled_classes, ignore_errors=False)
        io_utils.copy_dir(self.testclass_path, test_dir)
        self.logger.info(f"Running tests for project: {project_name}")

        for tobject in test_objects:
            # test_class = tobject["test-class"]
            test_path = tobject["test-path"]
            testid = tobject["id"]
            method = tobject["method-name"]
            package = tobject["package"]
            test_folder = "/".join(test_path.split("/")[:-1])

            matched_files = []
            if os.path.exists(f"{project_url}/{test_folder}"):
                for file in os.listdir(f"{project_url}/{test_folder}"):
                    if file.startswith(testid): #and file.find("slice")==-1:
                        class_path = f"{project_url}/{test_folder}/{file}"
                        matched_files.append(class_path)

            data_id = f"{tobject['class']}#{method}"
            self.test_result[data_id] = {}
            if len(matched_files) == 0:
                self.test_result[data_id]["error_type"] = "compile error"
                self.test_result[data_id]["test_cases"] = 1
                self.test_result[data_id]["passed_cases"] = 0
                self.test_result[data_id]["note"] = "test class not found"
                continue
            compiled_files = self.compile_test_group(matched_files)
            if len(compiled_files) == 0:
                self.test_result[data_id]["error_type"] = "compile error"
                self.test_result[data_id]["test_cases"] = len(matched_files)
                self.test_result[data_id]["passed_cases"] = 0
                continue
            eflag, test_info = self.run_test_group(package, testid, data_id)
            if eflag:
                cases = int(re.findall(r"([0-9]+) tests started", test_info)[0])
                passed = int(re.findall(r"([0-9]+) tests successful", test_info)[0])
                self.test_result[data_id]["test_cases"] = cases
                self.test_result[data_id]["passed_cases"] = passed
                passed_cases = self.parse_passed_cases(package, test_info)
            else:
                self.test_result[data_id]["error_type"] = "execution error"
                self.test_result[data_id]["test_cases"] = len(matched_files)
                continue
            html_report = f"{self.report_path}/jacoco-report-html/{testid}/"
            csv_report = f"{self.report_path}/jacoco-report-csv/{testid}.csv"
            if not self.generate_report_single(html_report, csv_report):
                self.test_result[data_id]["error_type"] = "report error"
                continue
            self.delete_jacoco_exec()
            if len(passed_cases) > 0:
                passed_cases_groups = []
                flag = False
                for i in range(0, len(passed_cases), 30):
                    end = min(i+30, len(passed_cases))
                    passed_cases_groups.append(passed_cases[i:end])
                for group in passed_cases_groups:
                    if self.run_selected_mehods(group): flag = True
                if flag == True:
                    correct_html_report = f"{self.report_path}/jacoco-report-html/{testid}_correct/"
                    correct_csv_report = f"{self.report_path}/jacoco-report-csv/{testid}_correct.csv"
                    self.generate_report_single(correct_html_report, correct_csv_report)
                self.delete_jacoco_exec()
            else:
                self.test_result[data_id].update({"correct_inst_cov": 0.0, "correct_bran_cov": 0.0})
        return self.test_result
    
    def compile_test_group(self, class_path):
        sucess = []
        for file in class_path:
            cflag, _ = self.compile_test(file)
            if cflag: sucess.append(file)
        return sucess

    def run_test_group(self, package, testid, data_id):
        """
        Run a group of tests in the specified test class.
        """
        test_dependencies = f"libs/*;target/test-classes;target/classes;{self.dependency_fd}/*"
        java_agent = f"-javaagent:{self.dependency_fd}/jacocoagent.jar=destfile=target/jacoco.exec"
        testid = testid.replace("$", "\\$")
        test_cmd = ['java', '-cp', test_dependencies, java_agent, 'org.junit.platform.console.ConsoleLauncher', '--disable-banner', '--disable-ansi-colors', '--fail-if-no-tests', '--select-package', package, '--include-classname', f".*{testid}.*"]
        script = self.cd_cmd + test_cmd
        self.logger.info(' '.join(test_cmd))
        result = subprocess.run(script, capture_output=True, text=True, shell=True, encoding="utf-8", errors='ignore')
        test_info = result.stdout
        if result.returncode == 0:
            self.logger.info(f"test execution info: {test_info}")
            return (True, test_info)
        elif test_info.find("Test run finished")!=-1:
            test_info = f"{result.stderr}\n{result.stdout}"
            self.logger.warning(f"return code: {result.returncode}")
            self.logger.warning(f"test case failed in {testid}, info:\n{test_info}")
            flag = True if len(re.findall(r"([0-9]+) tests started", test_info))>0 else False
            return (flag, test_info)
        else:
            test_info = f"{result.stderr}\n{result.stdout}"
            self.logger.error(f"error occured in execute test class {testid}, info:\n{test_info}")
            return (False, test_info)

    def parse_passed_cases(self, package, test_info):
        result = []
        current_class = None
        for line in test_info.splitlines():
            line = line.strip()
            class_match = re.findall(r"([\w$]+_Test(?:_slice\d+)?)(?:\s*\u2714)?", line)
            if len(class_match)>0:
                current_class = f"{package}.{class_match[0]}"
                continue
            method_match = re.findall(r"([\w$]+)\(\)\s*\u2714$", line)
            if len(method_match)>0:
                method_name = method_match[0]
                result.append(f"{current_class}#{method_name}")
        return result


def run_HITS_coverage(fstruct, task_setting, result_folder, dataset_info):
    root_path = os.getcwd().replace("\\", "/")
    testclass_path = f"{result_folder}/<project>/test-classes/"
    report_path = f"{root_path}/{result_folder}/<project>/reports/"
    dependency_dir = f"{root_path}/{fstruct.DEPENDENCY_PATH}"
    compile_test = task_setting.COMPILE_TEST
    projects = task_setting.PROJECTS
    select = True if len(projects)>0 else False
    logger = logging.getLogger(__name__)
    set_file_structure(report_path, dataset_info)
    total_result = {}
    calculator: CoverageCalculator

    for pj_name, info in dataset_info.items():
        if select and pj_name not in projects: continue
        runner = HITSRunner(info, dependency_dir, testclass_path, report_path)
        runner.check_testclass_name()
        test_result = runner.run_project_test(compile_test)
        logger.info(test_result)
        # extract coverage
        calculator = CoverageCalculator(info, report_path)
        coverage_data = calculator.generate_project_summary(test_result)
        total_result.update(coverage_data)
        logger.info(f"report data:\n{coverage_data}")
        coverage_file = f"{report_path}/summary.json".replace("<project>", pj_name)
        io_utils.write_json(coverage_file, coverage_data)

    total_file = report_path.split("<project>")[0] + "summary.json"
    calculator.calculate_total_result(total_result, total_file)
    return


def exract_baseline_coverage(file_structure, task_setting, benchmark, dataset_info):
    dataset_path = file_structure.DATASET_PATH
    baseline_path = benchmark.BASELINE_PATH
    selected_baselines = benchmark.BASELINES
    logger = logging.getLogger(__name__)

    root_path = os.getcwd().replace("\\", "/")
    dataset_dir = f"{root_path}/{dataset_path}"
    for _, info in dataset_info.items():
        project_path = f"{dataset_dir}/{info['project-url']}"
        info["project-url"] = project_path

    # extract HITS coverage
    if "HITS" in selected_baselines:
        logger.info("Extracting HITS coverage...")
        # dataset_meta = io_utils.load_json(f"{dataset_path}/dataset_meta.json")
        # HITS_result = "../../../paper-repetition/HITS-rep/playground_check_official"
        # HITS_save = f"{baseline_path}/HITS/gpt3.5"
        # extract_coverage_HITS(HITS_result, dataset_info, dataset_meta, HITS_save)

        # run HITS coverage test
        HITS_result = f"{baseline_path}/HITS/gpt4o"
        run_HITS_coverage(file_structure, task_setting, HITS_result, dataset_info)
    
    # extract ChatUniTest coverage
    if "ChatUniTest" in selected_baselines:
        logger.info("Extracting ChatUniTest coverage...")
        chatunitest_result = f"{baseline_path}/ChatUniTest"
        extract_coverage_ChatUniTest(chatunitest_result, dataset_info, file_structure, task_setting)

    # extract ChatTester coverage
    if "ChatTester" in selected_baselines:
        logger.info("Extracting ChatTester coverage...")
        chattester_result = f"{baseline_path}/ChatTester"
        extract_coverage_ChatUniTest(chattester_result, dataset_info, file_structure, task_setting)
    return