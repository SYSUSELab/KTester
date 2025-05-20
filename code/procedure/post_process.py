import re
import jpype
import logging
import subprocess

from tools import io_utils
from tools.llm_api import LLMCaller
from tools.code_analysis import ASTParser
from tools.prompt_generator import PromptGenerator


def check_class_name(init_class:str, tcname:str):
    class_name = re.findall(r'class (\w*)(<.*>)?( extends [\w]+)?', init_class)[0][0]
    if class_name != tcname:
        init_class = init_class.replace(class_name, tcname)
    return


def insert_test_case(init_class:str, insert_code:str):
    init_class = init_class.strip()
    insert_code = insert_code.lstrip()
    TestClassEditor = jpype.JClass("TestClassEditor")
    added_class = str(TestClassEditor.main([init_class, insert_code]))
    return added_class


class CodeRepairer:
    max_tries: int
    url: str
    cd_cmd: list
    llm_caller: LLMCaller
    prompt_gen: PromptGenerator
    logger: logging.Logger

    def __init__(self, project_url, tc_path:str, fix_tries:int):
        self.max_tries = fix_tries
        self.url = project_url
        self.cd_cmd = ['cd', project_url, '&&']
        self.testclass_path = tc_path
        self.temp_path = f"{self.testclass_path}/temp/"
        self.llm_caller = LLMCaller()
        self.prompt_gen = PromptGenerator('./templates', [])
        self.logger = logging.getLogger(__name__)


    def compile_test(self, class_path):
        compile_cmd = ["javac","-cp","@dependencies.txt","-d","target/test-classes",class_path]
        script = self.cd_cmd + compile_cmd
        self.logger.info(" ".join(compile_cmd))
        result = subprocess.run(script, capture_output=True, text=True, shell=True)
        if result.returncode!= 0:
            self.logger.error(f"error occured in compile test class, info:\n{result.stderr}")
            return (False, result.stderr)
        return (True, str(""))


    def parse_feedback(self, feedback:str, test_class:str):
        '''
        Parse the compilation feedback to get the error line number and error message.
        '''
        rule_fixes = []
        llm_fixes = []
        split_str = test_class.replace("/", "\\")
        errors = feedback.split(f"{split_str}:")
        for error in errors:
            if str(error).find("error:")==-1: continue
            splits = error.split(":error: ")
            try:
                line = int(splits[0]) - 1
                msg = splits[1]
                if msg.find("cannot find symbol"):
                    rule_fixes.append([line, msg])    
                llm_fixes.append([line, msg])
            except:
                continue
        return [rule_fixes, llm_fixes]


    def repair_by_rules(self, test_class, error_infos):
        '''
        Use the compilation feedback and corresponding test cases as input
        Repair the test cases through rules.
        '''
        return


    def repair_by_LLM(self, test_class, feedback, prompt_path, response_path, context):
        '''
        Use the compilation feedback and corresponding test cases as input
        Repair the test cases through LLM.
        '''
        context = {
            "code_to_fix": test_class,
            "compilation_feedback": feedback,
            "context_dict": context
        }
        prompt = self.prompt_gen.generate_singal("repair", context)
        code, response = self.llm_caller.get_response_code(prompt)
        io_utils.write_text(prompt_path, prompt)
        io_utils.write_text(response_path, response)
        return code
    
    def clean_error_cases(self, error_infos:list, code:str):
        '''
        Clean the error cases from the test class.
        '''
        parser = ASTParser()
        parser.parse(code)
        start, end = parser.get_test_case_position()
        lines = [line for line, _ in error_infos]
        fulL_lines = set(lines)
        for line in lines:
            for i in range(0, len(start)):
                if line >=start[i] and line<=end[i]:
                    fulL_lines.update(range(start[i], end[i]+1))
                    break
        parser.comment_code(fulL_lines)
        # TODO: delete error test cases
        return parser.get_code()


    def check_test_class(self, ts_info:dict, prompt_path:str, response_path:str, context_path:str):
        '''
        Check if the test class is compileable.
        If not, repair the test cases through rules & LLM.
        '''
        test_path = ts_info["test-path"]
        class_name = test_path.split('/')[-1]
        class_path = f"{self.testclass_path}/{class_name}"
        target_path = f"{self.url}/{test_path}"
        io_utils.copy_file(class_path, target_path)
        cflag, feedback = self.compile_test(test_path)
        count = 0
        fixed_code = io_utils.load_text(class_path)
        context = io_utils.load_json(context_path)
        while not cflag and count<self.max_tries:
            temp = f"{self.temp_path}/{class_name}".replace(".java", f"_{count}.java")
            io_utils.write_text(temp, fixed_code)
            self.logger.info(f"try to repair test class {class_path}...")
            prompt = f"{prompt_path}_{count}.md"
            response = f"{response_path}_{count}.md"
            fixed_code = self.repair_by_LLM(fixed_code, feedback, prompt, response, context)
            io_utils.write_text(target_path, fixed_code)
            cflag, feedback = self.compile_test(test_path)
            count += 1
        
        if not cflag:
            error_infos = self.parse_feedback(feedback, test_path)[-1]
            fixed_code = self.clean_error_cases(error_infos, fixed_code)
        if count > 0:
            io_utils.write_text(class_path, fixed_code)
        return


def verify_test_classes(file_structure, task_setting, dataset_info):
    '''
    Compile test class to check correctness
    If there are compilation errors, fix the test cases through compilation feedback.
    '''
    dataset_dir = file_structure.DATASET_PATH
    prompt_path = file_structure.PROMPT_PATH
    fix_path = file_structure.FIX_PATH
    testclass_path = file_structure.TESTCLASSS_PATH
    projects = task_setting.PROJECTS
    case_list = task_setting.CASES_LIST
    fix_tries = task_setting.FIX_TRIES
    project_select = True if len(projects)>0 else False
    case_select = True if len(case_list)>0 else False
    logger = logging.getLogger(__name__)

    for pj_name, pj_info in dataset_info.items():
        if project_select and pj_name not in projects: continue
        logger.info(f"verify process test classes in {pj_name}...")
        project_path = f"{dataset_dir}/{pj_info['project-url']}"
        project_prompt = prompt_path.replace("<project>",pj_name)
        project_fix = fix_path.replace("<project>",pj_name)
        project_testclass = testclass_path.replace("<project>",pj_name)
        code_repair = CodeRepairer(project_path, project_testclass, fix_tries)

        for ts_info in pj_info["focal-methods"]:
            tid = ts_info["id"]
            if case_select and tid not in case_list: continue
            context_path = f"{project_prompt}/{tid}/usage_context.json"
            case_prompt_path = f"{project_fix}/{tid}/repair_prompt"
            case_response_path = f"{project_fix}/{tid}/repair_response"
            code_repair.check_test_class(ts_info, case_prompt_path, case_response_path, context_path)
    return