
import sys
import time
import jpype
import logging
import argparse

import tools.io_utils as utils
import procedure.generate_prompt as GenPrompt
import procedure.generate_code as GenCode
import procedure.post_process as Post
from settings import FileStructure as FS, TaskSettings as TS


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
    case_then_code = TS.CASE_THEN_CODE
    prompt_list = TS.PROMPT_LIST
    dataset_info = utils.load_json(f"{dataset_path}/dataset_info.json")
    logger = logging.getLogger(__name__)
    start_time = time.time()
    # check prompt list
    if case_then_code:
        for i in range(len(prompt_list)):
            pname = prompt_list[i]
            if not pname.endswith("4case") and pname!="gencode": 
                prompt_list[i] += "4case"
        if "gencode" not in prompt_list:
            prompt_list.append("gencode")
        TS.PROMPT_LIST = prompt_list
        logger.info(f"prompt list: {TS.PROMPT_LIST}")

    # prompt_gen_start = time.time()
    # GenPrompt.generate_init_prompts(FS, TS, dataset_info)
    # GenPrompt.generate_test_case_prompts(FS, TS, dataset_info)
    # prompt_gen_end = time.time()
    # logger.info(f"time for generate prompts: {prompt_gen_end - prompt_gen_start:.2f} seconds")

    framework_start = time.time()
    GenCode.generate_testclass_framework(FS, TS, dataset_info)
    framework_end = time.time()
    logger.info(f"time for generate test class framework: {framework_end - framework_start:.2f} seconds")

    testcase_start = time.time()
    if case_then_code:
        GenCode.generate_case_then_code(FS, TS, dataset_info)
    else:
        GenCode.generate_testcase_code(FS, TS, dataset_info)
    testcase_end = time.time()
    logger.info(f"time for generate test cases: {testcase_end - testcase_start:.2f} seconds")

    post_start = time.time()
    Post.verify_test_classes(FS, TS, dataset_info)
    post_end = time.time()
    logger.info(f"time for post process: {post_end - post_start:.2f} seconds")
    
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
    jpype.startJVM(jpype.getDefaultJVMPath(), '-Xmx4g', "-Djava.class.path=./Java/project-info-process.jar;./Java/project-index-builder.jar")
    run()
    jpype.shutdownJVM()