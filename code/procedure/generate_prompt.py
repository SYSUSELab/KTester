import os
import logging

import tools.io_utils as utils
from tools.code_search import CodeSearcher
from tools.prompt_generator import PromptGenerator

def generate_init_prompts(file_structure, task_setting, dataset_info:dict):
    dataset_dir = file_structure.DATASET_PATH
    code_info_path = file_structure.CODE_INFO_PATH
    prompt_path = file_structure.PROMPT_PATH
    projects = task_setting.PROJECTS
    top_k = task_setting.SIM_TOP_K
    select = True if len(projects)>0 else False
    generator = PromptGenerator('./templates', [])
    logger = logging.getLogger(__name__)

    for pj_name, pj_info in dataset_info.items():
        if select and pj_name not in projects: continue
        logger.info(f"Construct init prompts for project {pj_name}...")
        project_url = pj_info["project-url"]
        project_path = f"{dataset_dir}/{project_url}"
        searcher = CodeSearcher(project_path, pj_name, code_info_path, top_k)
        for test_info in pj_info["focal-methods"]:
            id = test_info["id"]
            prompt_dir = f"{prompt_path}/{id}".replace("<project>", pj_name)
            if not os.path.exists(prompt_dir):
                os.makedirs(prompt_dir)
            # get context
            construct_context = searcher.collect_construct_context(test_info["class"], test_info["method-name"], test_info["source-path"])
            contxet_file = f"{prompt_dir}/init_context.json"
            utils.write_json(contxet_file, construct_context)
            # generate prompt
            test_class_name =  test_info["test-class"].split('.')[-1]
            content = {
                "method_name": test_info["method-name"],
                "class_name": test_info["class"].split('.')[-1],
                "class_code": test_info["class-code"],
                "package_name": test_info["package"],
                "class_name": test_class_name,
                "context_dict": construct_context,
            }
            prompt = generator.generate_single('init', content)
            # save prompt
            result_path = f"{prompt_dir}/init_prompt.md"
            utils.write_text(result_path, prompt)


def generate_test_case_prompts(file_structure, task_setting, dataset_info:dict):
    # dataset_dir, code_info_path, prompt_path:str, gen_prompt_list:list
    dataset_dir = file_structure.DATASET_PATH
    code_info_path = file_structure.CODE_INFO_PATH
    prompt_path = file_structure.PROMPT_PATH
    prompt_list:list = task_setting.PROMPT_LIST
    projects = task_setting.PROJECTS
    top_k = task_setting.SIM_TOP_K
    select = True if len(projects)>0 else False
    logger = logging.getLogger(__name__)
    generator = PromptGenerator('./templates', prompt_list)

    for pj_name, pj_info in dataset_info.items():
        if select and pj_name not in projects: continue
        logger.info(f"Construct test case prompts for project {pj_name}...")
        project_url = pj_info["project-url"]
        project_path = f"{dataset_dir}/{project_url}"
        searcher = CodeSearcher(project_path, pj_name, code_info_path, top_k)
        for test_info in pj_info["focal-methods"]:
            id = test_info["id"]
            prompt_dir = f"{prompt_path}/{id}".replace("<project>", pj_name)
            # get context
            usage_context =searcher.collect_usage_context(test_info["class"], test_info["method-name"])
            contxet_file = f"{prompt_dir}/usage_context.json"
            utils.write_json(contxet_file, usage_context)
            # generate prompt
            content = {
                "method_name": test_info["method-name"],
                "class_name": test_info["class"].split('.')[-1],
                "class_code": test_info["class-code"],
                "context_dict": usage_context,
            }
            prompt_list = generator.generate_group(content)
            # save prompt
            for tmp_name, prompt in prompt_list.items():
                result_path = f"{prompt_dir}/{tmp_name}_prompt.md"
                utils.write_text(result_path, prompt)
    return