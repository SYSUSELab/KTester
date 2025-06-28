import os
import re
import logging
import subprocess
from typing import List, Tuple
from bs4 import BeautifulSoup


class JavaRunner:
    cd_cmd: list
    dependency_fd: str
    logger: logging.Logger
    
    def __init__(self, project_url:str, dep_fd=None):
        self.cd_cmd = ['cd', project_url, '&&']
        self.dependency_fd = dep_fd
        self.logger = logging.getLogger(__name__)
        return
    
    def compile_test(self, class_path):
        compile_cmd = ["javac", "-cp", "@dependencies.txt","-d","target/test-classes", class_path]
        script = self.cd_cmd + compile_cmd
        self.logger.info(" ".join(compile_cmd))
        result = subprocess.run(script, capture_output=True, text=True, shell=True, encoding="utf-8")
        if result.returncode!= 0:
            self.logger.error(f"error occured in compile test class, info:\n{result.stderr}")
            return (False, result.stderr)
        return (True, "")

    def run_singal_unit_test(self, testclass, coverage:bool=True):
        """
        return code of JUnit test:
        - -1: Execution error occured
        - 0: All tests passed
        - 1: Failures occured in test cases
        - 2: No tests
        """
        self.logger.info(f"Running single unit test, testclass: {testclass}")
        test_dependencies = f"libs/*;target/test-classes;target/classes;{self.dependency_fd}/*"
        java_agent = f"-javaagent:{self.dependency_fd}/jacocoagent.jar=destfile=target/jacoco.exec"
        if coverage:
            test_cmd = ['java', '-cp', test_dependencies, java_agent, 'org.junit.platform.console.ConsoleLauncher', '--disable-banner', '--disable-ansi-colors', '--fail-if-no-tests', '--select-class', testclass]
        else:
            test_cmd = ['java', '-cp', test_dependencies, 'org.junit.platform.console.ConsoleLauncher', '--disable-banner', '--disable-ansi-colors', '--fail-if-no-tests', '--select-class', testclass]
        script = self.cd_cmd + test_cmd
        result = subprocess.run(script, capture_output=True, text=True, shell=True, encoding="utf-8", errors='ignore')
        self.logger.info(f"return code: {result.returncode}")
        if result.returncode == 0:
            self.logger.info(f"test execution info: {result.stdout}")
            return (True, result.stdout)
        elif result.returncode != -1:
            test_info = f"{result.stderr}\n{result.stdout}"
            self.logger.info(f"test case failed in {testclass}, info:\n{test_info}")
            flag = True if len(re.findall(r"([0-9]+) tests started", test_info))>0 else False
            return (flag, test_info)
        else:
            test_info = f"{result.stderr}\n{result.stdout}"
            self.logger.error(f"error occured in execute test class {testclass}, info:\n{test_info}")
            return (False, test_info)

    def run_selected_mehods(self, methods:list[str]):
        test_dependencies = f"libs/*;target/test-classes;target/classes;{self.dependency_fd}/*"
        java_agent = f"-javaagent:{self.dependency_fd}/jacocoagent.jar=destfile=target/jacoco.exec"
        test_cmd = ['java', '-cp', test_dependencies, java_agent, 'org.junit.platform.console.ConsoleLauncher', '--disable-banner', '--disable-ansi-colors']
        for method in methods:
            test_cmd += ['--select-method', method]
        script = self.cd_cmd + test_cmd
        self.logger.info(f"Running selected methods: {methods}")
        result = subprocess.run(script, capture_output=True, text=True, shell=True, encoding="utf-8", errors='ignore')
        if result.returncode == -1: 
            test_info = f"{result.stderr}\n{result.stdout}"
            self.logger.error(f"error occured in execute:{' '.join(script)}\n info:\n{test_info}")
            return False
        else:
            self.logger.info(f"test execution info: {result.stdout}")
        return True
    
    def generate_report_single(self, html_report, csv_report=None):
        # generate report
        jacoco_cli = f"{self.dependency_fd}/jacococli.jar"
        report_cmd = ['java', '-jar', jacoco_cli, "report", "target/jacoco.exec", '--classfiles', 'target/classes', '--sourcefiles', 'src/main/java', "--html", html_report]
        if csv_report is not None:
            report_cmd += ["--csv", csv_report]
        script = self.cd_cmd + report_cmd

        result = subprocess.run(script, capture_output=True, text=True, shell=True, encoding="utf-8", errors='ignore')
        if result.returncode!= 0:
            self.logger.error(f"error occured in generate report, info:\n{result.stderr}")
            return False
        return True

    def delete_jacoco_exec(self):
        jacoco_path = f"{self.cd_cmd[1]}/target/jacoco.exec"
        if os.path.exists(jacoco_path):
            os.remove(jacoco_path)
        return


class CoverageExtractor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

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

    def extract_single_coverage(self, html_path, method):
        self.logger.info(f"Extracting coverage for class: {html_path}, method: {method}")
        coverage_score = None
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
                # coverage_score = {"inst_cov": instruction_cov, "bran_cov": branch_cov}
                coverage_score = (instruction_cov, branch_cov)
                break
        return coverage_score

    def extract_uncovered_line(self):
        # get html file with function body
        # get line span
        # get coverage label
        return

    # def jacoco_missing_lines(report_root, package, class_name) -> Tuple[List[Tuple[int, str]], List[Tuple[int, str]]]:
    #     html_path = os.path.join(report_root, package, f"{class_name}.java.html")
    #     with open(html_path, "r") as file:
    #         soup = BeautifulSoup(file, 'lxml-xml')

    #     def get_id(_span):
    #         return int(_span['id'][1:])  # since the 'id' has format 'L{id}', e.g., 'L15', means line 15

    #     def _case_filter(_str: str):
    #         return re.match(r"case .*:", _str.strip()) is not None

    #     missing_lines = [(get_id(_span), _span.string)
    #                     for _span in soup.find_all("span", class_=re.compile(r"nc(.)*"))]
    #     branch_lines = [(get_id(_span), _span.string)
    #                     for _span in soup.find_all("span", class_=re.compile(r"pc b[np]c"))]
    #     # missing_cases = [get_id(_span) for _span in soup.find_all("span",
    #     #                                                           class_=re.compile(r"pc b[np]c"),
    #     #                                                           string=_case_filter)]
    #     # e.g. for missing cases: case 10: System.out.println("10"); This line will be yellow

    #     return missing_lines, branch_lines