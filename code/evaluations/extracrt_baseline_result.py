import os
import re
import logging
from bs4 import BeautifulSoup

import tools.io_utils as io_utils


def check_method_name(method_name, target):
        target = re.sub(r"<[^>]*>", "", target, flags=re.DOTALL)
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


def exract_baseline_coverage(file_structure, dataset_info):
    dataset_path = file_structure.DATASET_PATH
    baseline_path = file_structure.BASELINE_PATH
    logger = logging.getLogger(__name__)
    # extract HITS coverage
    logger.info("Extracting HITS coverage...")
    dataset_meta = io_utils.load_json(f"{dataset_path}/dataset_meta.json")
    HITS_result = "../../../paper-repetition/HITS-rep/playground_check_official"
    HITS_save = f"{baseline_path}/HITS"
    extract_coverage_HITS(HITS_result, dataset_info, dataset_meta, HITS_save)
    return