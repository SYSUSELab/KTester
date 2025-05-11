import os
import sys
import time
import jpype
import logging
import argparse
import concurrent.futures
from threading import Lock

import tools.io_utils as utils
import procedure.generate_prompt as GenPrompt
import procedure.post_process as Post
from settings import FileStructure as FS, TaskSettings as TS
from tools.llm_api import LLMCaller

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
    mworkers = TS.MAX_WORKERS
    select = True if len(projects)>0 else False
    logger = logging.getLogger(__name__)
    file_lock = Lock() # ensure thread-safe file writing
    llm_callers = [LLMCaller() for _ in range(mworkers)]

    def process_init_response(llm_caller:LLMCaller, test_info, project_prompt, project_response, gen_folder):
        id = test_info["id"]
        prompt = utils.load_text(f"{project_prompt}/{id}/init_prompt.md")
        code, response = llm_caller.get_response(prompt)
        class_name = test_info["test-class"].split('.')[-1]
        Post.check_class_name(code, class_name)
        test_class_path = f"{gen_folder}/{class_name}.java"
        with file_lock:
            utils.write_text(test_class_path, code)
            if save_res:
                res_path = f"{project_response}/{id}/init_response.md"
                utils.write_text(res_path, response)
        return id
    
    for pj_name, pj_info in dataset_info.items():
        if select and pj_name not in projects: continue
        logger.info(f"Generating test class framework for project {pj_name}...")
        project_prompt = prompt_path.replace("<project>", pj_name)
        project_response = response_path.replace("<project>", pj_name)
        gen_folder = gen_path.replace("<project>", pj_name)
        if not os.path.exists(gen_folder):
            os.makedirs(gen_folder)
        logger.debug(f"max workers: {mworkers}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=mworkers) as executor:
            futures = []
            api_count = 0
            for test_info in pj_info["focused-methods"]:
                future = executor.submit(
                    process_init_response, 
                    llm_callers[api_count],
                    test_info, 
                    project_prompt, 
                    project_response, 
                    gen_folder
                )
                futures.append(future)
                api_count = (api_count+1) % mworkers
            # wait for all tasks complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    id = future.result()
                    logger.info(f"Completed test class framework generation for {id}")
                except Exception as e:
                    logger.error(f"Error processing test framework for {id}: {e}")

    return

def generate_testcase(dataset_info: dict):
    prompt_path = FS.PROMPT_PATH
    response_path = FS.RESPONSE_PATH
    gen_path = FS.TESTCLASSS_PATH
    prompt_list = TS.PROMPT_LIST
    projects = TS.PROJECTS
    save_res = TS.SAVE_INTER_RESULT
    mworkers = TS.MAX_WORKERS
    select = True if len(projects)>0 else False
    logger = logging.getLogger(__name__)
    file_lock = Lock()
    llm_callers = [LLMCaller() for _ in range(mworkers)]

    def process_case_response(llm_caller:LLMCaller, test_info, project_prompt, project_response, gen_folder):
        class_name = test_info["test-class"].split('.')[-1]
        id = test_info["id"]
        save_path = f"{gen_folder}/{class_name}.java"
        init_class = utils.load_text(save_path)
        for prompt_name in prompt_list:
            prompt = utils.load_text(f"{project_prompt}/{id}/{prompt_name}_prompt.md")
            prompt = prompt.replace('<initial_class>', init_class)
            code, response = llm_caller.get_response(prompt)
            logger.debug("finish get response")
            init_class = Post.insert_test_case(init_class, code)
            logger.debug("finish insert test case")
            if save_res:
                response_path = f"{project_response}/{id}/{prompt_name}_response.md"
                with file_lock:
                    utils.write_text(response_path, response)
        with file_lock:
            utils.write_text(save_path, init_class)
        return id

    for pj_name, pj_info in dataset_info.items():
        if select and pj_name not in projects: continue
        logger.info(f"Generating test cases for project {pj_name}...")
        project_prompt = prompt_path.replace("<project>", pj_name)
        project_response = response_path.replace("<project>", pj_name)
        gen_folder = gen_path.replace("<project>", pj_name)
        logger.debug(f"max workers: {mworkers}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=mworkers) as executor:
            futures = []
            api_count = 0
            for test_info in pj_info["focused-methods"]:
                future = executor.submit(
                    process_case_response, 
                    llm_callers[api_count],
                    test_info, 
                    project_prompt, 
                    project_response, 
                    gen_folder
                )
                futures.append(future)
                api_count = (api_count+1) % mworkers
            # wait for all tasks complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    id = future.result()
                    logger.info(f"Completed test case generation for {id}")
                except Exception as e:
                    logger.error(f"Error processing test framework for {id}: {e}")
                    
    return


# TODO: a complete procedure for singal case in dataset
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
    start_time = time.time()

    prompt_gen_start = time.time()
    GenPrompt.generate_init_prompts(FS, TS, dataset_info)
    GenPrompt.generate_test_case_prompts(FS, TS, dataset_info)
    prompt_gen_end = time.time()
    logger.info(f"time for generate prompts: {prompt_gen_end - prompt_gen_start:.2f} seconds")

    framework_start = time.time()
    generate_testclass_framework(dataset_info)
    framework_end = time.time()
    logger.info(f"time for generate test class framework: {framework_end - framework_start:.2f} seconds")

    testcase_start = time.time()
    generate_testcase(dataset_info)
    testcase_end = time.time()
    logger.info(f"time for generate test cases: {testcase_end - testcase_start:.2f} seconds")
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"total elapsed time: {elapsed_time:.2f} seconds")
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
    jpype.startJVM(jpype.getDefaultJVMPath(), '-Xmx4g', "-Djava.class.path=./Java/project-info-extract.jar;./Java/project-index-builder.jar")
    run()
    jpype.shutdownJVM()