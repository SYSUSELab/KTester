import os
import logging
import jpype
import concurrent.futures
from threading import Lock

import tools.io_utils as io_utils
from tools.llm_api import LLMCaller
from tools.time_agent import TimeRecorder
from procedure.post_process import check_class_name


def insert_test_case(init_class:str, insert_code:str):
    init_class = init_class.strip()
    insert_code = insert_code.lstrip()
    TestClassEditor = jpype.JClass("editcode.TestClassUpdator")
    added_class = str(TestClassEditor.main([init_class, insert_code, init_class.splitlines()[0]]))
    return added_class


def generate_testclass_framework(file_structure, task_setting, dataset_info: dict):
    prompt_path = file_structure.PROMPT_PATH
    response_path = file_structure.RESPONSE_PATH
    gen_path = file_structure.TESTCLASSS_PATH
    projects = task_setting.PROJECTS
    case_list = task_setting.CASES_LIST
    save_res = task_setting.SAVE_INTER_RESULT
    mworkers = task_setting.MAX_WORKERS
    project_select = True if len(projects)>0 else False
    case_select = True if len(case_list)>0 else False
    logger = logging.getLogger(__name__)
    file_lock = Lock() # ensure thread-safe file writing
    llm_callers = [LLMCaller() for _ in range(mworkers)]

    @TimeRecorder
    def process_init_response(llm_caller:LLMCaller, task_info, project_prompt, project_response, gen_folder):
        id = task_info["id"]
        class_name = task_info["test-class"].split('.')[-1]
        test_class_path = f"{gen_folder}/{class_name}.java"
        prompt = io_utils.load_text(f"{project_prompt}/{id}/init_prompt.md")
        code, response = llm_caller.get_response_code(prompt)
        code = check_class_name(code, class_name)
        with file_lock:
            io_utils.write_text(test_class_path, code)
            if save_res:
                res_path = f"{project_response}/{id}/init_response.md"
                io_utils.write_text(res_path, response)
        return id
    
    for pj_name, pj_info in dataset_info.items():
        if project_select and pj_name not in projects: continue
        logger.info(f"Generating test class framework for project {pj_name}...")
        project_prompt = prompt_path.replace("<project>", pj_name)
        project_response = response_path.replace("<project>", pj_name)
        gen_folder = gen_path.replace("<project>", pj_name)
        if not os.path.exists(gen_folder): os.makedirs(gen_folder)
        logger.debug(f"max workers: {mworkers}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=mworkers) as executor:
            futures = []
            api_count = 0
            for test_info in pj_info["focal-methods"]:
                if case_select and test_info["id"] not in case_list: continue
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
                    logger.error(f"Error processing test framework for: {e}")
    return


def generate_testcase_code(file_structure, task_setting, dataset_info: dict):
    prompt_path = file_structure.PROMPT_PATH
    response_path = file_structure.RESPONSE_PATH
    gen_path = file_structure.TESTCLASSS_PATH
    prompt_list = task_setting.PROMPT_LIST
    projects = task_setting.PROJECTS
    case_list = task_setting.CASES_LIST
    save_res = task_setting.SAVE_INTER_RESULT
    mworkers = task_setting.MAX_WORKERS
    project_select = True if len(projects)>0 else False
    case_select = True if len(case_list)>0 else False
    logger = logging.getLogger(__name__)
    file_lock = Lock()
    llm_callers = [LLMCaller() for _ in range(mworkers)]

    @TimeRecorder
    def process_case_response(llm_caller:LLMCaller, task_info, project_prompt, project_response, gen_folder):
        class_name = task_info["test-class"].split('.')[-1]
        id = task_info["id"]
        save_path = f"{gen_folder}/{class_name}.java"
        init_class = io_utils.load_text(save_path)
        for prompt_name in prompt_list:
            prompt = io_utils.load_text(f"{project_prompt}/{id}/{prompt_name}_prompt.md")
            prompt = prompt.replace('<initial_class>', init_class)
            code, response = llm_caller.get_response_code(prompt)
            logger.debug("finish get response")
            init_class = insert_test_case(init_class, code)
            logger.debug("finish insert test case")
            if save_res:
                response_path = f"{project_response}/{id}/{prompt_name}_response.md"
                with file_lock:
                    io_utils.write_text(response_path, response)
        with file_lock:
            io_utils.write_text(save_path, init_class)
        return id

    for pj_name, pj_info in dataset_info.items():
        if project_select and pj_name not in projects: continue
        logger.info(f"Generating test cases for project {pj_name}...")
        project_prompt = prompt_path.replace("<project>", pj_name)
        project_response = response_path.replace("<project>", pj_name)
        gen_folder = gen_path.replace("<project>", pj_name)
        logger.debug(f"max workers: {mworkers}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=mworkers) as executor:
            futures = []
            api_count = 0
            for test_info in pj_info["focal-methods"]:
                if case_select and test_info["id"] not in case_list: continue
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
                    logger.error(f"Error processing test case: {e}")
    return



'''
format of output cases:
[
  {
    "group": "test name",
    "cases": [
      {
        "input": [
          {
            "parameter": "param name",
            "value": "param value"
          }
        ],
        "expected": "expected exception or behavior",
        "description": "test scenario description"
      }
    ]
  }
]
'''
class FormattedTestcase:
    group_cases: dict

    def __init__(self):
        self.group_cases = {}

    def merge_test_cases(self, json_res):
        if json_res is None: return
        new_groups = []
        def extract_group(cur_json):
            if isinstance(cur_json, dict):
                if "cases" in cur_json and \
                    isinstance(cur_json["cases"], list) and \
                    len(cur_json["cases"]) > 0:
                    new_groups.append(cur_json)
                else:
                    for key, value in cur_json.items():
                        extract_group(value)
            elif isinstance(cur_json, list):
                for item in cur_json:
                    extract_group(item)
            return
        extract_group(json_res)
        for new_group in new_groups:
            group_cases = new_group.get("cases", [])
            group_name = new_group.get("group", "unnamed")
            exist_group = self.group_cases.get(group_name, None) # list or None
            if exist_group is None:
                self.group_cases[group_name] = group_cases
            else:
                for new_case in group_cases:
                    case_exists = False
                    for exist_case in exist_group:
                        if len(new_case["input"]) == len(exist_case["input"]):
                            all_params_match = True
                            for new_input, exist_input in zip(new_case["input"], exist_case["input"]):
                                if new_input["parameter"] != exist_input["parameter"] or \
                                new_input["value"] != exist_input["value"]:
                                    all_params_match = False
                                    break
                        if all_params_match:
                            case_exists = True
                            break
                    if not case_exists:
                        exist_group.append(new_case)
                self.group_cases[group_name] = exist_group
        return

    def __str__(self) -> str:
        res = []
        for group_name, cases in self.group_cases.items():
            res.append({
                "group": group_name,
                "cases": cases
            })
        return str(res)

    def to_list(self) -> dict:
        res = []
        for group_name, cases in self.group_cases.items():
            res.append({
                "group": group_name,
                "cases": cases
            })
        return res


def generate_case_then_code(file_structure, task_setting, dataset_info: dict):
    prompt_path = file_structure.PROMPT_PATH
    response_path = file_structure.RESPONSE_PATH
    gen_path = file_structure.TESTCLASSS_PATH
    prompt_list:list = task_setting.PROMPT_LIST
    projects = task_setting.PROJECTS
    case_list = task_setting.CASES_LIST
    save_res = task_setting.SAVE_INTER_RESULT
    mworkers = task_setting.MAX_WORKERS
    project_select = True if len(projects)>0 else False
    case_select = True if len(case_list)>0 else False
    logger = logging.getLogger(__name__)
    file_lock = Lock()
    llm_callers = [LLMCaller() for _ in range(mworkers)]

    @TimeRecorder
    def process_case_response(llm_caller:LLMCaller, task_info, project_prompt, project_response, gen_folder):
        id = task_info["id"]
        response_folder = f"{project_response}/{id}"
        prompt_folder = f"{project_prompt}/{id}"
        # generate test cases in json format
        formatted_cases = FormattedTestcase()
        for prompt_name in prompt_list:
            if prompt_name == "gencode": continue
            prompt = io_utils.load_text(f"{prompt_folder}/{prompt_name}_prompt.md")
            prompt = prompt.replace('<cases_json>', str(formatted_cases))
            case_data, response = llm_caller.get_response_json(prompt)
            logger.debug("finish get response")
            try:
                formatted_cases.merge_test_cases(case_data)
            except Exception as e:
                logger.warning(f"Error while adding test cases for {id} from prompt {prompt_name}: {e}")
            logger.debug("finish insert test case")
            if save_res:
                with file_lock:
                    io_utils.write_text(f"{response_folder}/{prompt_name}_response.md", response)
        with file_lock:
            io_utils.write_json(f"{response_folder}/cases.json", formatted_cases.to_list())
        # generate test code based on test cases
        class_name = task_info["test-class"].split('.')[-1]
        save_path = f"{gen_folder}/{class_name}.java"
        init_class = io_utils.load_text(save_path)
        prompt = io_utils.load_text(f"{prompt_folder}/gencode_prompt.md")
        prompt = prompt.replace('<initial_class>', init_class).replace('<cases_json>', str(formatted_cases))
        code, response = llm_caller.get_response_code(prompt)
        init_class = insert_test_case(init_class, code)
        with file_lock:
            io_utils.write_text(save_path, init_class)
            if save_res:
                io_utils.write_text(f"{response_folder}/gencode_response.md", response)
        return id

    for pj_name, pj_info in dataset_info.items():
        if project_select and pj_name not in projects: continue
        logger.info(f"Generating test cases for project {pj_name}...")
        project_prompt = prompt_path.replace("<project>", pj_name)
        project_response = response_path.replace("<project>", pj_name)
        gen_folder = gen_path.replace("<project>", pj_name)
        logger.debug(f"max workers: {mworkers}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=mworkers) as executor:
            futures = []
            api_count = 0
            for test_info in pj_info["focal-methods"]:
                if case_select and test_info["id"] not in case_list: continue
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
                    logger.error(f"Error processing test case: {e}")
    return


if __name__ == "__main__":
    import sys
    sys.path.append(os.path.abspath("../"))
    import json
    test_group_1 = json.loads("""
    """)
    test_group_2 = json.loads("""
""")
    format_case = FormattedTestcase()
    format_case.merge_test_cases(test_group_1)
    format_case.merge_test_cases(test_group_2)
    print(format_case)