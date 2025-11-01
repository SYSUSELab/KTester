import os
import re
import logging

import tools.io_utils as utils
from tools.execute_test import JavaRunner, CoverageExtractor
from tools.code_analysis import ASTParser


class ProjectTestRunner(JavaRunner):
    project_info: dict
    testclass_path: str
    report_path: str
    test_result: dict

    def __init__(self, project_info, dep_fd, tc_path, rpt_path):
        self.project_info = project_info
        self.testclass_path = tc_path.replace("<project>",project_info["project-name"])
        self.report_path = rpt_path.replace("<project>",project_info["project-name"])
        super().__init__(project_info["project-url"], dep_fd)
        self.logger = logging.getLogger(__name__)
        return

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
                self.test_result[data_id].update({
                    "error_type": "compile error",
                    "test_cases": 0,
                    "passed_cases": 0,
                    "note": "test class not found"
                })
                continue

            if compile:
                cflag, _ = self.compile_test(test_path)
                if not cflag:
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

    def deal_execution_feedback(self, data_id, feedback):
        cases = int(re.findall(r"([0-9]+) tests started", feedback)[0])
        passed = int(re.findall(r"([0-9]+) tests successful", feedback)[0])
        self.test_result[data_id]["test_cases"] = cases
        self.test_result[data_id]["passed_cases"] = passed
        passed_tests = re.findall(r"([$\w]+)\(\)\s+\u2714", feedback, re.MULTILINE)
        return passed_tests


class CoverageCalculator(CoverageExtractor):
    report_path: str
    project_info: dict
    astparser: ASTParser
    error_type = {
        "compile error": 1,
        "execution error": 2,
        "report error": 3,
    }

    def __init__(self, project_info, rpt_path):
        project_name = project_info.get("project-name","")
        self.report_path = rpt_path.replace("<project>", project_name)
        self.project_info = project_info
        self.astparser = ASTParser()
        super().__init__()
        pass

    def get_testclass_path(self, tinfo):
        return tinfo["test-path"]

    def generate_project_summary(self, test_result:dict, filter=False):
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
                "bran_cov": <branch coverage>,
                "correct_inst_cov": <instraction coverage>,
                "correct_bran_cov": <branch coverage>,
            },
            "compile_pass_rate": compiled/total,
            "execution_pass_rate": successed/total,
            "average_instruction_coverage": <average instruction coverage>,
            "average_branch_coverage": <average branch coverage>,
            "average_correct_instruction_coverage": <average instruction coverage>,
            "average_correct_branch_coverage": <average branch coverage>,
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
                    class_path = project_path + '/' + self.get_testclass_path(test)
                    self.astparser.parse(utils.load_text(class_path))
                    test_cases = len(self.astparser.get_test_cases())
                    summary[data_id].update({"test_cases": test_cases, "passed_cases": 0})
            else:
                package = test["package"]
                classname = test["class"].split(".")[-1]
                html_path = f"{self.report_path}/jacoco-report-html/{testid}/{package}/{classname}.html"
                cov_score = self.extract_single_coverage(html_path, method)
                data_id = f"{test['class']}#{method}"
                if cov_score: 
                    summary[data_id].update({"inst_cov": cov_score[0], "bran_cov": cov_score[1]})
                else: 
                    summary[data_id].update({"inst_cov": "<missing>", "bran_cov": "<missing>"})
                if "correct_inst_cov" not in summary[data_id]:
                    html_path = f"{self.report_path}/jacoco-report-html/{testid}_correct/{package}/{classname}.html"
                    cov_score = self.extract_single_coverage(html_path, method)
                    if cov_score:
                        summary[data_id].update({"correct_inst_cov": cov_score[0], "correct_bran_cov": cov_score[1]})
                        if filter:
                            inst_cov = summary[data_id]["inst_cov"]
                            bran_cov = summary[data_id]["bran_cov"]
                            if inst_cov>0 and cov_score[0]==inst_cov and cov_score[1]==bran_cov:
                                summary[data_id]["passed_cases"] = summary[data_id]["test_cases"]
                    else:
                        summary[data_id].update({"correct_inst_cov": "<missing>", "correct_bran_cov": "<missing>"})
        self.count_general_metrics(summary)
        return summary

    def count_general_metrics(self, summary:dict):
        case_num = 0
        compile_num = 0
        pass_num = 0
        cov_num  = 0
        inst_cov = 0.0
        bran_cov = 0.0
        correct_inst_cov = 0.0
        correct_bran_cov = 0.0

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
                if "correct_inst_cov" in item and item["correct_inst_cov"] != "<missing>":
                    correct_inst_cov += item["correct_inst_cov"]
                    correct_bran_cov += item["correct_bran_cov"]
        summary.update({
            "compile_pass_rate": compile_num/case_num if case_num > 0 else 0,
            "execution_pass_rate": pass_num/case_num if case_num > 0 else 0,
            "average_instruction_coverage": inst_cov/cov_num if cov_num > 0 else 0.0,
            "average_branch_coverage": bran_cov/cov_num if cov_num > 0 else 0.0,
            "average_correct_instruction_coverage": correct_inst_cov/cov_num if cov_num > 0 else 0.0,
            "average_correct_branch_coverage": correct_bran_cov/cov_num if cov_num > 0 else 0.0,
        })
        return

    def calculate_total_result(self, new_result:dict, result_file):
        exist_result = {}
        if os.path.exists(result_file):
            exist_result = utils.load_json(result_file)
        exist_result.update(new_result)
        metrics = ["compile_pass_rate", "execution_pass_rate", 
                  "average_instruction_coverage", "average_branch_coverage",
                  "average_correct_instruction_coverage", "average_correct_branch_coverage"]
        for metric in metrics:
            exist_result.pop(metric, None)
        self.count_general_metrics(exist_result)
        utils.write_json(result_file, exist_result)


def test_coverage(fstruct, task_setting, dataset_info: dict):
    root_path = os.getcwd().replace("\\", "/")
    dataset_dir = f"{root_path}/{fstruct.DATASET_PATH}"
    testclass_path = f"{root_path}/{fstruct.TESTCLASSS_PATH}"
    report_path = f"{root_path}/{fstruct.REPORT_PATH}"
    dependency_dir = f"{root_path}/{fstruct.DEPENDENCY_PATH}"
    compile_test = task_setting.COMPILE_TEST
    projects = task_setting.PROJECTS
    model = task_setting.MODEL
    select = True if len(projects)>0 else False
    logger = logging.getLogger(__name__)
    total_result = {}
    calculator: CoverageCalculator = CoverageCalculator({}, "")

    logger.info(f"Start coverage test ...")
    for pj_name, info in dataset_info.items():
        if select and pj_name not in projects: continue
        project_path = f"{dataset_dir}/{info['project-url']}"
        info["project-url"] = project_path
        # run converage test & generate report
        runner = ProjectTestRunner(info, dependency_dir, testclass_path, report_path)
        test_result = runner.run_project_test(compile_test)
        logger.info(test_result)
        # extract coverage
        calculator = CoverageCalculator(info, report_path)
        coverage_data = calculator.generate_project_summary(test_result, filter=True)
        total_result.update(coverage_data)
        logger.info(f"report data:\n{coverage_data}")
        coverage_file = f"{report_path}/summary.json".replace("<project>", pj_name)
        utils.write_json(coverage_file, coverage_data)

    total_file = report_path.split("<project>")[0] + f"summary-{model}.json"
    calculator.calculate_total_result(total_result, total_file)
    return


if __name__ == "__main__":

    project_path = "../dataset/puts/commons-csv"
    test_runner = ProjectTestRunner(None, None, None, None)
    class_path = "org.jacoco.examples"
    class_name = "QrConfig"
    method_name = "toHints(BarcodeFormat)"
    testclass = "org.jacoco.examples.MethodHandleUtilTest"
    test_response = test_runner.run_singal_unit_test(testclass)
    print(test_response)
    pass