import os
import re
# import queue
import shutil
import logging
import subprocess


import tools.io_utils as io_utils
from procedure.post_process import check_class_name
from evaluations.coverage_test import ProjectTestRunner, CoverageCalculator


class HITSRunner(ProjectTestRunner):
    def __init__(self, project_info, dependency_dir, testclass_path, report_path):
        super().__init__(project_info, dependency_dir, testclass_path, report_path)

    def run_project_test(self, compile=True):
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


class UTGenRunner(ProjectTestRunner):
    def __init__(self, project_info, dependency_dir, testclass_path, report_path):
        super().__init__(project_info, dependency_dir, testclass_path, report_path)
        test_dependencies = f"libs/*;target/test-classes;target/classes;{self.dependency_fd}/*"
        self.test_base_cmd = [
            'java', 
            "--add-opens", "java.base/java.lang=ALL-UNNAMED",
            "--add-opens", "java.base/java.net=ALL-UNNAMED",
            "--add-opens", "java.desktop/java.awt=ALL-UNNAMED",
            # "--add-opens", "java.base/java.util=ALL-UNNAMED",
            # "--add-opens", "java.base/java.lang.reflect=ALL-UNNAMED",
            # "--add-opens", "java.base/sun.reflect.annotation=ALL-UNNAMED",
            # "--add-opens", "java.base/java.text=ALL-UNNAMED",
            # "--add-opens", "java.desktop/java.awt.font=ALL-UNNAMED",
            '-cp', test_dependencies, 
            'org.junit.platform.console.ConsoleLauncher', 
            '--disable-banner', 
            '--disable-ansi-colors',
            '--fail-if-no-tests',
        ]
        self.logger = logging.getLogger(__name__)

    def run_project_test(self, compile=True):
        project_name = self.project_info["project-name"]
        project_url = self.project_info["project-url"]
        test_objects = self.project_info["focal-methods"]
        self.test_result = {}

        self.logger.info(f"Running tests for project: {project_name}")
        for tobject in test_objects:
            testid = tobject["id"]
            method = tobject["method-name"]
            test_path = tobject["test-path"]
            test_folder = "/".join(test_path.split('/')[:-1])
            test_class = tobject["test-class"]
            simple_class = tobject["class"].split('.')[-1]
            scaffold_class = f"{simple_class}_ESTest_scaffolding"
            class_path = f"{self.testclass_path}{test_class.split('.')[-1]}.java"
            scaffold_path = f"{self.testclass_path}{scaffold_class}.java"
            class_target_path = f"{project_url}/{test_path}"
            scaffold_target_path = f"{project_url}/{test_folder}/{scaffold_class}.java"
            data_id = f"{tobject['class']}#{method}"
            self.test_result[data_id] = {}
            try:
                io_utils.copy_file(class_path, class_target_path)
                io_utils.copy_file(scaffold_path, scaffold_target_path)
            except FileNotFoundError:
                self.test_result[data_id].update({
                    "error_type": "compile error",
                    "test_cases": 0,
                    "passed_cases": 0,
                    "note": "test class not found"
                })
                continue

            if compile:
                sflag, _ = self.compile_test(scaffold_target_path)
                cflag, _ = self.compile_test(class_target_path)
                if not (cflag and sflag):
                    self.test_result[data_id]["error_type"] = "compile error"
                    continue
            eflag, feedback = self.run_singal_unit_test(test_class)
            if eflag:
                passed_test = self.deal_execution_feedback(data_id, feedback)
            else:
                self.test_result[data_id]["error_type"] = "execution error"
                continue
            html_report = f"{self.report_path}/jacoco-report-html/{testid}/"
            csv_report = f"{self.report_path}/jacoco-report-csv/{testid}.csv"
            if not self.generate_report_single(html_report, csv_report):
                self.test_result[data_id]["error_type"] = "report error"
                continue
            self.delete_jacoco_exec()
            if len(passed_test)>0:
                passed_test = [f"{test_class}#{method}" for method in passed_test]
                if not self.run_selected_mehods(passed_test): continue
                correct_html_report = f"{self.report_path}/jacoco-report-html/{testid}_correct/"
                correct_csv_report = f"{self.report_path}/jacoco-report-csv/{testid}_correct.csv"
                self.generate_report_single(correct_html_report, correct_csv_report)
                self.delete_jacoco_exec()
            else:
                self.test_result[data_id].update({"correct_inst_cov": 0.0, "correct_bran_cov": 0.0})
        return self.test_result        


class UTGenCalculator(CoverageCalculator):
    def __init__(self, project_info, rpt_path):
        super().__init__(project_info, rpt_path)
    
    def get_testclass_path(self, tinfo):
        return tinfo["test-path"].split("_")[0] + "_ESTest.java"

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


def extract_coverage_generic(runner_class, result_folder, dataset_info, fstruct, task_setting):
    """通用覆盖率提取函数，用于消除重复代码"""
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
    calculator: CoverageCalculator = CoverageCalculator({}, "")

    for pj_name, info in dataset_info.items():
        if select and pj_name not in projects: continue
        # run converage test & generate report
        runner = runner_class(info, dependency_dir, testclass_path, report_path)
        test_result = runner.run_project_test(compile_test)
        logger.info(test_result)
        # extract coverage
        if runner_class.__name__ == UTGenRunner.__name__:
            calculator = UTGenCalculator(info, report_path)
        else:
            calculator = CoverageCalculator(info, report_path)
        coverage_data = calculator.generate_project_summary(test_result)
        total_result.update(coverage_data)
        logger.info(f"report data:\n{coverage_data}")
        coverage_file = f"{report_path}/summary.json".replace("<project>", pj_name)
        io_utils.write_json(coverage_file, coverage_data)

    total_file = report_path.split("<project>")[0] + "summary.json"
    calculator.calculate_total_result(total_result, total_file)
    return total_result


def exract_baseline_coverage(file_structure, task_setting, benchmark, dataset_info):
    dataset_path = file_structure.DATASET_PATH
    baseline_path = benchmark.BASELINE_PATH
    selected_baselines = benchmark.BASELINES
    repetition_num = task_setting.REPETITION_NUM
    logger = logging.getLogger(__name__)

    root_path = os.getcwd().replace("\\", "/")
    dataset_dir = f"{root_path}/{dataset_path}"
    for _, info in dataset_info.items():
        project_path = f"{dataset_dir}/{info['project-url']}"
        info["project-url"] = project_path

    # extract HITS coverage
    if "HITS" in selected_baselines:
        logger.info("Extracting HITS coverage...")
        HITS_result = f"{baseline_path}/HITS/rep_{repetition_num}"
        extract_coverage_generic(HITSRunner, HITS_result, dataset_info, file_structure, task_setting)
    
    # extract ChatUniTest coverage
    if "ChatUniTest" in selected_baselines:
        logger.info("Extracting ChatUniTest coverage...")
        chatunitest_result = f"{baseline_path}/ChatUniTest/rep_{repetition_num}"
        extract_coverage_generic(ProjectTestRunner, chatunitest_result, dataset_info, file_structure, task_setting)

    # extract ChatTester coverage
    if "ChatTester" in selected_baselines:
        logger.info("Extracting ChatTester coverage...")
        chattester_result = f"{baseline_path}/ChatTester/rep_{repetition_num}"
        extract_coverage_generic(ProjectTestRunner, chattester_result, dataset_info, file_structure, task_setting)

    # extract UTGen coverage
    if "UTGen" in selected_baselines:
        logger.info("Extracting UTGen coverage...")
        utgen_result = f"{baseline_path}/UTGen"
        extract_coverage_generic(UTGenRunner, utgen_result, dataset_info, file_structure, task_setting)
    return