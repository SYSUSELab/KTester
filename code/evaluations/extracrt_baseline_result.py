import os
import re
import logging
from unittest import result
from bs4 import BeautifulSoup

import tools.io_utils as io_utils
from evaluations.coverage_test import ProjrctTestRunner, CoverageExtractor


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
    dataset_dir = f"{root_path}/{fstruct.DATASET_PATH}"
    testclass_path = f"{result_folder}/<project>/test_classes/"
    report_path = f"{root_path}/{result_folder}/<project>/reports/"
    dependency_dir = f"{root_path}/{fstruct.DEPENDENCY_PATH}"
    compile_test = task_setting.COMPILE_TEST
    projects = task_setting.PROJECTS
    select = True if len(projects)>0 else False
    logger = logging.getLogger(__name__)
    set_file_structure(report_path, dataset_info)

    # for root, dirs, files in os.walk(result_folder):
    #     for file in files:
    #         if file.endswith(".java"):
    #             file_path = os.path.join(root, file)
    #             new_file_name = re.sub(r"_[0-9]+_[0-9]+", "", file)
    #             new_file_path = os.path.join(root, new_file_name)
    #             if new_file_name == file: continue
    #             logger.info(f"renaming {file_path} to {new_file_path}")
    #             try:
    #                 os.rename(file_path, new_file_path)
    #             except FileExistsError:
    #                 logger.warning(f"file {new_file_path} already exists")
    #                 continue

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
        io_utils.write_json(coverage_file, coverage_data)
    return


def exract_baseline_coverage(file_structure, task_setting, benchmark, dataset_info):
    dataset_path = file_structure.DATASET_PATH
    baseline_path = benchmark.BASELINE_PATH
    selected_baselines = benchmark.BASELINES
    logger = logging.getLogger(__name__)

    # extract HITS coverage
    if "HITS" in selected_baselines:
        logger.info("Extracting HITS coverage...")
        dataset_meta = io_utils.load_json(f"{dataset_path}/dataset_meta.json")
        HITS_result = "../../../paper-repetition/HITS-rep/playground_check_official"
        HITS_save = f"{baseline_path}/HITS"
        extract_coverage_HITS(HITS_result, dataset_info, dataset_meta, HITS_save)
    
    # extract ChatUniTest coverage
    if "ChatUniTest" in selected_baselines:
        logger.info("Extracting ChatUniTest coverage...")
        chatunitest_result = f"{baseline_path}/ChatUniTest"
        extract_coverage_ChatUniTest(chatunitest_result, dataset_info, file_structure, task_setting)
    return