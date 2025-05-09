import os
import re
import sys
import time
import jpype
import logging
import argparse

import tools.io_utils as utils
import procedure.generate_prompt as GP
from settings import FileStructure as FS, TaskSettings as TS
from tools.llm_api import LLMCaller
from tools.code_analysis import ASTParser

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-L','--log_level', type=str, default='info', help='log level: info, debug, warning, error, critical')
    parser.add_argument('-F','--log_file', help="storage file of output info", default=None)

    args = parser.parse_args()
    log_level = {
        'info': logging.INFO,
        'debug': logging.DEBUG,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }
    args.log_level = log_level[args.log_level]
    return args


def generate_testclass_framework(dataset_info: dict):
    prompt_path = FS.PROMPT_PATH
    response_path = FS.RESPONSE_PATH
    gen_path = FS.TESTCLASSS_PATH
    projects = TS.PROJECTS
    save_res = TS.SAVE_INTER_RESULT
    select = True if len(projects)>0 else False
    llm_caller = LLMCaller()
    logger = logging.getLogger(__name__)

    for pj_name, pj_info in dataset_info.items():
        if select and pj_name not in projects: continue
        logger.info(f"Generating test class framework for project {pj_name}...")
        project_prompt = prompt_path.replace("<project>", pj_name)
        project_response = response_path.replace("<project>", pj_name)
        gen_folder = gen_path.replace("<project>", pj_name)
        if not os.path.exists(gen_folder):
            os.makedirs(gen_folder)
        for test_info in pj_info["focused-methods"]:
            id = test_info["id"]
            prompt = utils.load_text(f"{project_prompt}/{id}/init_prompt.md")
            code, response = llm_caller.get_response(prompt)
            class_name = test_info["test-class"].split('.')[-1]
            check_class_name(code, class_name)
            test_class_path = f"{gen_folder}/{class_name}.java"
            utils.write_text(test_class_path, code)
            if save_res:
                response_path = f"{project_response}/{id}/init_response.md"
                utils.write_text(response_path, response)
    return

def generate_testcase(dataset_info: dict):
    prompt_path = FS.PROMPT_PATH
    response_path = FS.RESPONSE_PATH
    gen_path = FS.TESTCLASSS_PATH
    prompt_list = TS.PROMPT_LIST
    projects = TS.PROJECTS
    save_res = TS.SAVE_INTER_RESULT
    select = True if len(projects)>0 else False
    llm_caller = LLMCaller()
    logger = logging.getLogger(__name__)

    for pj_name, pj_info in dataset_info.items():
        if select and pj_name not in projects: continue
        logger.info(f"Generating test cases for project {pj_name}...")
        project_prompt = prompt_path.replace("<project>", pj_name)
        project_response = response_path.replace("<project>", pj_name)
        gen_folder = gen_path.replace("<project>", pj_name)
        for test_info in pj_info["focused-methods"]:
            class_name = test_info["test-class"].split('.')[-1]
            id = test_info["id"]
            save_path = f"{gen_folder}/{class_name}.java"
            init_class = utils.load_text(f"{gen_folder}/{class_name}.java")
            for prompt_name in prompt_list:
                prompt = utils.load_text(f"{project_prompt}/{id}/{prompt_name}_prompt.md")
                prompt = prompt.replace('<initial_class>', init_class)
                code, response = llm_caller.get_response(prompt)
                logger.debug("get response")
                init_class = insert_test_case(init_class, code)
                logger.debug("insert test case")
            utils.write_text(save_path, init_class)
            if save_res:
                response_path = f"{project_response}/{id}/{prompt_name}_response.md"
                utils.write_text(response_path, response)
    return

def check_class_name(init_class:str, tcname:str):
    class_name = re.findall(r'class (\w*)(<.*>)?( extends [\w]+)?', init_class)[0][0]
    if class_name != tcname:
        init_class = init_class.replace(class_name, tcname)
    return

def insert_test_case(init_class:str, insert_code:str):
    init_class = init_class.strip()
    insert_code = insert_code.lstrip()
    insert_ast = ASTParser()
    insert_ast.parse(insert_code)
    lines = init_class.splitlines()
    # insert import lines
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('import '):
            last_import_idx = i
    existing_imports = set(re.findall(r'import .*;', init_class, re.MULTILINE))
    additional_imports = insert_ast.get_additional_imports(existing_imports)
    if len(additional_imports) > 0:
        lines = lines[:last_import_idx+1] + additional_imports + lines[last_import_idx+1:]
    # insert test case
    add_test_case = insert_ast.get_test_cases()
    lines = lines[:-1] + add_test_case + [lines[-1]]
    added_class = '\n'.join(lines)
    return added_class


# todo: a complete procedure for singal case in dataset
def run():
    '''
    procedure:
    1. setup & teerdowm generation
        - 2.1 context collection: code search / static analysis
        - 2.2 prompt combination
        - 2.3 testclass structure generation
    2. test function generation
        - 3.1 prompt combination
        - 3.2 generate test function
    3. package & save test class
        - 4.1 code repair (?)
    '''
    dataset_path = FS.DATASET_PATH
    dataset_info = utils.load_json(f"{dataset_path}/dataset_info.json")
    logger = logging.getLogger(__name__)
    
    logger.info("Running: Generate unit test...")
    start_time = time.time()
    GP.generate_init_prompts(FS, dataset_info)
    GP.generate_test_case_prompts(FS, TS, dataset_info)
    generate_testclass_framework(dataset_info)
    generate_testcase(dataset_info)
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"Elapsed time: {elapsed_time:.2f} seconds")
    return


if __name__ == '__main__':
    args = get_args()
    if args.log_file:
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=args.log_level,
            filename=args.log_file)
        sys.stdout = utils.StreamToLogger(logging.getLogger("STDOUT"), logging.INFO)
        sys.stderr = utils.StreamToLogger(logging.getLogger("STDERR"), logging.ERROR)
    else:
        logging.basicConfig(
            level=args.log_level, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    jpype.startJVM(jpype.getDefaultJVMPath(), '-Xmx4g', "-Djava.class.path=./Java/project-index-builder.jar")
    run()
    jpype.shutdownJVM()