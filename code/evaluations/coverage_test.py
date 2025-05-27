import os
import re
import subprocess
import logging
from bs4 import BeautifulSoup

import tools.io_utils as utils
from tools.code_analysis import ASTParser


class ProjrctTestRunner:
    project_info: dict
    cd_cmd: list
    testclass_path: str
    report_path: str
    test_result: dict

    def __init__(self, project_info, dep_fd, tc_path, rpt_path):
        self.logger = logging.getLogger(__name__)
        self.project_info = project_info
        self.cd_cmd = ['cd', project_info["project-url"], '&&']
        self.dependency_fd = dep_fd
        self.testclass_path = tc_path.replace("<project>",project_info["project-name"])
        self.report_path = rpt_path.replace("<project>",project_info["project-name"])

    def run_project_test(self, compile=True):
        project_name = self.project_info["project-name"]
        project_url = self.project_info["project-url"]
        test_objects = self.project_info["focal-methods"]
        self.test_result = {}

        self.logger.info(f"Running tests for project: {project_name}")
        for tobject in test_objects:
            test_class = tobject["test-class"]
            test_path = tobject["test-path"]
            testid = tobject["id"]
            method = tobject["method-name"]
            class_path = f"{self.testclass_path}/{test_path.split('/')[-1]}"
            data_id = f"{tobject['class']}#{method}"
            self.test_result[data_id] = {}
            try:
                utils.copy_file(class_path, f"{project_url}/{test_path}")
            except FileNotFoundError:
                self.test_result[data_id]["error_type"] = "compile error"
                self.test_result[data_id]["test_cases"] = 0
                self.test_result[data_id]["passed_cases"] = 0
                self.test_result[data_id]["note"] = "test class not found"
                continue
            if compile and not self.compile_test(test_path):
                self.test_result[data_id]["error_type"] = "compile error"
                continue
            if not self.run_singal_unit_test(data_id, test_class):
                self.test_result[data_id]["error_type"] = "execution error"
                continue
            if not self.generate_report_single(testid):
                self.test_result[data_id]["error_type"] = "report error"
        return self.test_result

    def compile_test(self, class_path):
        compile_cmd = ["javac","-cp","@dependencies.txt","-d","target/test-classes",class_path]
        self.logger.info(" ".join(compile_cmd))
        script = self.cd_cmd + compile_cmd
        result = subprocess.run(script, capture_output=True, text=True, shell=True, encoding="utf-8", errors='ignore')
        if result.returncode!= 0:
            self.logger.error(f"error occured in compile test class, info:\n{result.stderr}")
            return False
        return True

    def get_pass_rate(self, test_info):
        cases = int(re.findall(r"([0-9]+) tests started", test_info)[0])
        passed = int(re.findall(r"([0-9]+) tests successful", test_info)[0])
        return (cases, passed)

    def run_singal_unit_test(self, data_id, testclass):
        self.logger.info(f"Running single unit test, testclass: {testclass}")
        test_dependencies = f"libs/*;target/test-classes;target/classes;{self.dependency_fd}/*"
        java_agent = f"-javaagent:{self.dependency_fd}/jacocoagent.jar=destfile=target/jacoco.exec"
        test_cmd = ['java', '-cp', test_dependencies, java_agent, 'org.junit.platform.console.ConsoleLauncher', '--disable-banner', '--disable-ansi-colors', '--fail-if-no-tests', '--select-class', testclass]
        script = self.cd_cmd + test_cmd
        result = subprocess.run(script, capture_output=True, text=True, shell=True, encoding="utf-8", errors='ignore')
        test_info = result.stdout
        if result.returncode == 0:
            self.logger.info(f"test execution info: {test_info}")
            test_cases, passed_cases = self.get_pass_rate(test_info)
            self.test_result[data_id]["test_cases"] = test_cases
            self.test_result[data_id]["passed_cases"] = passed_cases
            return True
        elif test_info.find("Test run finished")!=-1:
            self.logger.warning(f"return code: {result.returncode}")
            self.logger.warning(f"test case failed in {testclass}, info:\n{result.stderr}\n{test_info}")
            test_cases, passed_cases = self.get_pass_rate(test_info)
            self.test_result[data_id]["test_cases"] = test_cases
            self.test_result[data_id]["passed_cases"] = passed_cases
            if test_cases == 0: return False
            return True
        else:
            self.logger.error(f"error occured in execute test class {testclass}, info:\n{result.stderr}\n{test_info}")
            return False

    def generate_report_single(self, testid):
        # generate report
        jacoco_cli = f"{self.dependency_fd}/jacococli.jar"
        html_report = f"{self.report_path}/jacoco-report-html/{testid}/"
        csv_report = f"{self.report_path}/jacoco-report-csv/{testid}.csv"
        report_cmd = ['java', '-jar', jacoco_cli, "report", "target/jacoco.exec", '--classfiles', 'target/classes', '--sourcefiles', 'src/main/java', "--html", html_report, "--csv", csv_report]
        script = self.cd_cmd + report_cmd

        result = subprocess.run(script, capture_output=True, text=True, shell=True, encoding="utf-8", errors='ignore')
        if result.returncode!= 0:
            self.logger.error(f"error occured in generate report, info:\n{result.stderr}")
            return False
        return True


class CoverageExtractor:
    project_info: dict
    report_path: str
    astparser: ASTParser
    error_type = {
        "compile error": 1,
        "execution error": 2,
        "report error": 3,
    }

    def __init__(self, project_info, rpt_path):
        self.project_info = project_info
        self.report_path = rpt_path.replace("<project>",project_info["project-name"])
        self.astparser = ASTParser()
        self.logger = logging.getLogger(__name__)

    def sig_compare(sig_list_a, sig_list_jacoco):
        if len(sig_list_a) != len(sig_list_jacoco):
            return False
        if len(sig_list_a) == 0:  # length guaranteed to be the same
            return True
        if sig_list_a[0] != sig_list_jacoco[0]:
            return False
        for item_a, item_jacoco in zip(sig_list_a[1:], sig_list_jacoco[1:]):
            if item_jacoco == 'Object':
                continue
            elif item_a != item_jacoco:
                return False
        return True

    def check_method_name(self, method_name, target):
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
            elif not item_t.startswith(item_m):
                return False
        return True

    def extract_single_coverage(self, testid, package, classname, method):
        self.logger.info(f"Extracting coverage for class: {classname}, method: {method}")
        coverage_score = None
        html_path = f"{self.report_path}/jacoco-report-html/{testid}/{package}/{classname}.html"
        if not os.path.exists(html_path):
            self.logger.exception(f"report file not found: {html_path}")
            return coverage_score
        # extract coverage
        with open(html_path, "r") as file:
            soup = BeautifulSoup(file, 'lxml-xml')
        for tr in soup.find_all(name='tbody')[0].find_all(name='tr', recursive=False):
            tds = tr.contents
            try:
                method_name = tds[0].span.string
            except AttributeError:
                method_name = tds[0].a.string
            if self.check_method_name(method_name, method):
                instruction_cov = float(tds[2].string.replace("%", ""))/100
                branch_cov = float(tds[4].string.replace("%", ""))/100
                coverage_score = {"inst_cov": instruction_cov, "bran_cov": branch_cov}
                break
        return coverage_score


    def generate_project_summary(self, test_result:dict):
        """
        result format:
        {   
            "<class_name>#{method_name}": {
                "error_type": <error type>
                "test_cases": number,
                "passed_cases": number,
            },
            "<class_name>#{method_name}": {
                "test_cases": number,
                "passed_cases": number,
                "inst_cov": <instruction coverage>,
                "bran_cov": <branch coverage>
            },
            "compile_pass_rate": compiled/total,
            "execution_pass_rate": successed/total,
            "average_instruction_coverage": <average instruction coverage>,
            "average_branch_coverage": <average branch coverage>
        }
        """
        project_path = self.project_info["project-url"]
        focal_methods = self.project_info["focal-methods"]
        summary = test_result.copy()
        for test in focal_methods:
            testid = test["id"]
            method = test["method-name"]
            data_id = f"{test['class']}#{method}"
            if "error_type" in summary[data_id]:
                if "test_cases" not in summary[data_id]:
                    class_path = project_path + '/' + test["test-path"]
                    self.astparser.parse(utils.load_text(class_path))
                    test_cases = len(self.astparser.get_test_cases())
                    summary[data_id].update({"test_cases": test_cases, "passed_cases": 0})
            else:
                package = test["package"]
                classname = test["class"].split(".")[-1]
                cov_score = self.extract_single_coverage(testid, package, classname, method)
                data_id = f"{test['class']}#{method}"
                if cov_score: 
                    summary[data_id].update(cov_score)
                else: 
                    summary[data_id].update({"inst_cov": "<missing>", "bran_cov": "<missing>"})
        self.count_general_metrics(summary)
        return summary

    def count_general_metrics(self, summary:dict):
        case_num = 0
        compile_num = 0
        pass_num = 0
        cov_num  = 0
        inst_cov = 0.0
        bran_cov = 0.0
        for _, item in summary.items():
            test_cases = item.get("test_cases", 0)
            passed_cases = item.get("passed_cases", 0)
            case_num += test_cases
            cov_num += 1
            if "error_type" in item:
                error_type = self.error_type[item["error_type"]]
                if error_type > 1:
                    compile_num += test_cases
                if error_type > 2:
                    pass_num += passed_cases
            else:
                compile_num += test_cases
                pass_num += passed_cases
                if "inst_cov" in item and item["inst_cov"] != "<missing>":
                    inst_cov += item["inst_cov"]
                    bran_cov += item["bran_cov"]
        summary.update({
            "compile_pass_rate": compile_num/case_num if case_num > 0 else 0,
            "execution_pass_rate": pass_num/case_num if case_num > 0 else 0,
            "average_instruction_coverage": inst_cov/cov_num if cov_num > 0 else 0.0,
            "average_branch_coverage": bran_cov/cov_num if cov_num > 0 else 0.0
        })
        return


def test_coverage(fstruct, task_setting, dataset_info: dict):
    root_path = os.getcwd().replace("\\", "/")
    dataset_dir = f"{root_path}/{fstruct.DATASET_PATH}"
    testclass_path = f"{root_path}/{fstruct.TESTCLASSS_PATH}"
    report_path = f"{root_path}/{fstruct.REPORT_PATH}"
    dependency_dir = f"{root_path}/{fstruct.DEPENDENCY_PATH}"
    compile_test = task_setting.COMPILE_TEST
    projects = task_setting.PROJECTS
    select = True if len(projects)>0 else False
    logger = logging.getLogger(__name__)

    for pj_name, info in dataset_info.items():
        if select and pj_name not in projects: continue
        project_path = f"{dataset_dir}/{info['project-url']}"
        info["project-url"] = project_path
        # run converage test & generate report
        runner = ProjrctTestRunner(info, dependency_dir, testclass_path, report_path)
        test_result = runner.run_project_test(compile_test)
        logger.info(test_result)
        # extract coverage
        extractor = CoverageExtractor(info, report_path)
        coverage_data = extractor.generate_project_summary(test_result)
        logger.info(f"report data:\n{coverage_data}")
        coverage_file = f"{report_path}/summary.json".replace("<project>", pj_name)
        utils.write_json(coverage_file, coverage_data)
    return

# test
if __name__ == "__main__":

    project_path = "../dataset/puts/commons-csv"
    test_runner = ProjrctTestRunner(project_path)
    class_path = "org.jacoco.examples"
    class_name = "QrConfig"
    method_name = "toHints(BarcodeFormat)"
    testclass = "org.jacoco.examples.MethodHandleUtilTest"
    test_response = test_runner.run_singal_unit_test(testclass)
    print(test_response)
    pass
