import os

import subprocess

from bs4 import BeautifulSoup
import utils


class ProjrctTestRunner:
    project_info: dict
    cd_cmd: list

    def __init__(self, project_info, dep_fd, rpt_path):
        self.project_info = project_info
        self.cd_cmd = ['cd', project_info["project-url"], '&&']
        self.dependency_fd = dep_fd
        self.report_path = rpt_path.replace("<project>",project_info["project-name"])

        if not os.path.exists(self.report_path):
            os.mkdir(self.report_path)
            os.mkdir(f"{self.report_path}/jacoco-report-html")
            os.mkdir(f"{self.report_path}/jacoco-report-csv")


    def run_project_test(self, compile_test=True):
        # TODO: improve this parameter
        project_name = self.project_info["project-name"]
        # if compile_test:
        #     print(f"Compiling test classes in: {project_name}")
        #     compile_cmd = ['mvn', 'compiler:testCompile']
        #     script = self.cd_cmd + compile_cmd
        #     subprocess.run(script, shell=True)

        print(f"Running tests for project: {project_name}")
        test_objects = self.project_info["focused-methods"]
        failed_tests = {}
        for tobject in test_objects:
            test_class = tobject["test-class"]
            test_path = tobject["test-path"]
            testid = tobject["id"]
            if not self.compile_test(test_path):
                failed_tests[testid] = "compile error"
                continue
            if not self.run_singal_unit_test(test_class):
                failed_tests[testid] = "execution error"
                continue
            if not self.generate_report_single(testid):
                failed_tests[testid] = "report error"
        return failed_tests

    def compile_test(self, class_path):
        compile_cmd = ["javac","-cp","@dependencies.txt","-d","target/test-classes",class_path]
        script = self.cd_cmd + compile_cmd
        result = subprocess.run(script, capture_output=True, text=True, shell=True)
        if result.returncode!= 0:
            print(f"error occured in compile test class, info:\n{result.stderr}")
            return False
        return True

    def run_singal_unit_test(self, testclass):
        print(f"Running single unit test, testclass: {testclass}")
        test_dependencies = f"libs/*;target/test-classes;target/classes;{self.dependency_fd}/*"
        java_agent = f"-javaagent:{self.dependency_fd}/jacocoagent.jar=destfile=target/jacoco.exec"
        test_cmd = ['java', '-cp', test_dependencies, java_agent, 'org.junit.platform.console.ConsoleLauncher', '--select-class', testclass]
        script = self.cd_cmd + test_cmd
        result = subprocess.run(script, capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            print(f"error occured in execute test class {testclass}, info:\n{result.stderr}")
            return False
        return True

    def generate_report_single(self, testid):
        # generate report
        jacoco_cli = f"{self.dependency_fd}/jacococli.jar"
        html_report = f"{self.report_path}/jacoco-report-html/{testid}/"
        csv_report = f"{self.report_path}/jacoco-report-csv/{testid}.csv"
        report_cmd = ['java', '-jar', jacoco_cli, "report", "target/jacoco.exec", "--classfiles", "target/classes", "--html", html_report, "--csv", csv_report]
        script = self.cd_cmd + report_cmd
        result = subprocess.run(script, capture_output=True, text=True, shell=True)

        if result.returncode!= 0:
            print(f"error occured in generate report, info:\n{result.stderr}")
            return False
        return True


class CoverageExtractor:

    project_info: dict

    def __init__(self, project_info, rpt_path):
        self.project_info = project_info
        self.report_path = rpt_path.replace("<project>",project_info["project-name"])

    def extract_single_coverage(self, testid, package, classname, method):
        # extract coverage
        print(f"Extracting coverage for class: {classname}, method: {method}")
        coverage_score = None
        html_path = f"{self.report_path}/jacoco-report-html/{testid}/{package}/{classname}.html"
        if not os.path.exists(html_path):
            print(f"report file not found: {html_path}")
            return coverage_score
        
        with open(html_path, "r") as file:
            soup = BeautifulSoup(file, 'lxml-xml')
        for tr in soup.find_all(name='tbody')[0].find_all(name='tr', recursive=False):
            tds = tr.contents
            try:
                method_name = tds[0].span.string
            except AttributeError:
                method_name = tds[0].a.string
            if method_name != method: continue
            instruction_cov = float(tds[2].string.replace("%", ""))/100
            branch_cov = float(tds[4].string.replace("%", ""))/100
            coverage_score = {"inst_cov": instruction_cov, "bran_cov": branch_cov}
            break
        # return coverage results
        return coverage_score

    # {"<class_name>#{method_name}":{"inst_cov":"","bran_cov":""}}
    def extract_coverage_project(self, failed_tests:dict):
        focused_methods = self.project_info["focused-methods"]
        coverage = {}
        for test in focused_methods:
            testid = test["id"]
            method = test["method-name"]
            if testid in failed_tests:
                error_info = failed_tests[testid]
                coverage[f"{test['class']}#{method}"] = {
                    "inst_cov": error_info, "bran_cov": error_info}
            else:
                package = test["package"]
                classname = test["class"].split(".")[-1]
                cov_score = self.extract_single_coverage(testid, package, classname, method)
                data_id = f"{test['class']}#{method}"
                if cov_score: 
                    coverage[data_id] = cov_score
                else: 
                    coverage[data_id] = {
                    "inst_cov": "<missing>", "bran_cov": "<misding>"}
        return coverage


def test_coverage(datset_dir, dependency_dir, report_path):
    dataset_info = utils.load_json(f"{datset_dir}/dataset_info.json")
    if not os.path.exists(report_path):
        os.mkdir(report_path)
    for pj_name, info in dataset_info.items():
        project_path = f"{datset_dir}/{info['project-url']}"
        info["project-url"] = project_path
        # run converage test & generate report
        runner = ProjrctTestRunner(info, dependency_dir, report_path)
        failed_tests = runner.run_project_test()
        # extract coverage
        extractor = CoverageExtractor(info, report_path)
        coverage_data = extractor.extract_coverage_project(failed_tests)
        print(coverage_data)
        coverage_file = f"{report_path}/coverage.json".replace("<project>", pj_name)
        utils.write_json(coverage_file, coverage_data)
    return


if __name__ == "__main__":
    # import settings as ST
    # dataset_dir = f"{ST.ROOT_PATH}/{ST.DATASET_PATH}"
    # jacoco_dir = f"{ST.ROOT_PATH}/{ST.DEPENDENCY_PATH}"
    # report_path = f"{ST.ROOT_PATH}/{ST.REPORT_PATH}"

    project_path = "../dataset/puts/commons-csv"
    test_runner = ProjrctTestRunner(project_path)
    class_path = "org.jacoco.examples"
    class_name = "QrConfig"
    method_name = "toHints(BarcodeFormat)"
    testclass = "org.jacoco.examples.MethodHandleUtilTest"
    test_response = test_runner.run_singal_unit_test(testclass)
    print(test_response)
    pass
