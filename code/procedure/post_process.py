import os
import re
import copy
from sys import flags
import jpype
import logging
from enum import Enum

from tools import io_utils
from tools.llm_api import LLMCaller
from tools.code_analysis import ASTParser
from tools.execute_test import JavaRunner
from tools.prompt_generator import PromptGenerator


def check_class_name(init_class:str, tcname:str, pcname:str=None):
    class_name = re.findall(r'class ([\w$]*)(<.*>)?( extends [\w]+)?', init_class)[0][0]
    new_class = copy.copy(init_class)
    if class_name != tcname:
        new_class = new_class.replace(class_name, tcname)
    package_name = re.findall(r'package\s+([\w\.]+);', init_class)[0]
    if pcname and package_name != pcname:
        new_class = new_class.replace(package_name, pcname)
    return new_class


def insert_test_case(init_class:str, insert_code:str):
    init_class = init_class.strip()
    insert_code = insert_code.lstrip()
    TestClassEditor = jpype.JClass("editcode.TestClassUpdator")
    added_class = str(TestClassEditor.main([init_class, insert_code]))
    return added_class


class RuleError(Enum):
    UNRESLOVE_SYMBOL = 1
    UNREPORTED_EXCEPTION = 2
    PRIVATE_ACCESS = 3
    OTHER = 4


class VerifyResult(Enum):
    PASS = "pass"
    COMPILE_ERROR = "compilation"
    EXECUTE_ERROR = "execution"


class CodeRepairer(JavaRunner):
    max_tries: int
    half_tries: int
    url: str
    testclass_path: str
    temp_path: str
    import_dict: dict
    llm_caller: LLMCaller
    prompt_gen: PromptGenerator
    parser: ASTParser
    class_editor: jpype.JClass

    def __init__(self, dependency_fd, project_url, tc_path:str, fix_tries:int, impt_dict:dict):
        super().__init__(project_url, dependency_fd)
        self.max_tries = fix_tries
        self.half_tries = int((fix_tries)/2)
        self.url = project_url
        self.testclass_path = tc_path
        self.temp_path = f"{self.testclass_path}/temp/"
        self.import_dict = impt_dict
        self.llm_caller = LLMCaller()
        self.prompt_gen = PromptGenerator('./templates', [])
        self.parser = ASTParser()
        self.class_editor = jpype.JClass("editcode.TestClassUpdator")
        self.logger = logging.getLogger(__name__)

    def compile_and_execute(self, class_path, test_class):
        passrate = -2.0
        cflag, cfeedback = self.compile_test(class_path)
        if not cflag:
            return (VerifyResult.COMPILE_ERROR, cfeedback, passrate)
        eflag, efeedback = self.run_singal_unit_test(test_class, coverage=False)
        if eflag:
            try:
                cases = int(re.findall(r"([0-9]+) tests started", efeedback)[0])
                passed = int(re.findall(r"([0-9]+) tests successful", efeedback)[0])
                passrate = passed / cases if cases > 0 else -1.0
            except:
                pass
        if not eflag or passrate<0.9:
            passrate = -1.0
            return (VerifyResult.EXECUTE_ERROR, efeedback, passrate)

        return (VerifyResult.PASS, "", passrate)


    def parse_feedback(self, feedback:str, test_class:str):#, method_name:str):
        '''
        Parse the compilation feedback to get the error line number and error message.
        '''
        rule_fixes = []
        llm_fixes = []
        split_str = test_class.replace("/", "\\")
        errors = feedback.split(f"{split_str}:")
        for error in errors:
            if str(error).find(": error: ")==-1: continue
            splits = error.split(": error: ")
            try:
                line = int(splits[0]) - 1
                msg = splits[1]
                if msg.find("cannot find symbol") > -1:
                    rule_fixes.append([line, msg, RuleError.UNRESLOVE_SYMBOL])
                elif msg.find("unreported exception") > -1:
                    rule_fixes.append([line, msg, RuleError.UNREPORTED_EXCEPTION])
                # elif msg.find("private access")>-1 and msg.find(method_name)>-1:
                #     rule_fixes.append([line, msg, RuleError.PRIVATE_ACCESS])
                llm_fixes.append([line, msg])
            except:
                continue
        return [rule_fixes, llm_fixes]

    def repair_by_rules(self, test_class, error_infos):
        '''
        Use the compilation feedback and corresponding test cases as input
        Repair the test cases through rules.
        0. check package name and class name
        1. fix wrong/missing import statements
        2. fix unreported exception
        '''
        self.parser.parse(test_class)
        remove_imports = []
        add_imports = set()
        exception_lines = []
        symbol_pattern = r'symbol:\s+(class|variable) (.*)'
        for line, msg, type in error_infos:
            if type == RuleError.UNRESLOVE_SYMBOL:
                group = re.findall(symbol_pattern, msg)
                if len(group) > 0:
                    symbol = group[0][1]
                    add_import = self.import_dict.get(symbol, [])
                    add_imports.update(add_import)
                if msg.find("import ") > -1:
                    remove_imports.append(line)
            elif type == RuleError.UNREPORTED_EXCEPTION:
                exception_lines.append(line)
                pass
        if len(exception_lines) > 0:
            self.logger.info(f"add exception declaration in lines {exception_lines}")
            self.parser.add_exception(exception_lines)
        if len(remove_imports) > 0:
            self.logger.info(f"remove imports in lines {remove_imports}")
            self.parser.remove_lines(remove_imports)
        if len(add_imports) > 0:
            self.logger.info(f"add imports {add_imports}")
            self.parser.add_imports(list(add_imports))
        new_class = self.parser.get_code()
        return new_class

    def repair_by_LLM(self, test_class, feedback, prompt_path, response_path, context, repair_type:VerifyResult):
        '''
        Use the compilation/execution feedback and corresponding test cases as input
        Repair the test cases through LLM.
        '''
        context = {
            repair_type.value: True,
            "code_to_fix": test_class,
            "feedback": feedback,
            "context_dict": context
        }
        prompt = self.prompt_gen.generate_single("post", context)
        code, response = self.llm_caller.get_response_code(prompt)
        code = str(self.class_editor.main([test_class, code, "true"]))
        io_utils.write_text(prompt_path, prompt)
        io_utils.write_text(response_path, response)
        return code

    def clean_error_cases(self, error_infos:list, code:str):
        '''
        Clean/Comment the error test cases from the test class.
        '''
        self.parser.parse(code)
        start, end = self.parser.get_test_case_position()
        lines = [line for line, _ in error_infos]
        fulL_lines = set(lines)
        for line in lines:
            for i in range(0, len(start)):
                if line >=start[i] and line<=end[i]:
                    fulL_lines.update(range(start[i], end[i]+1))
                    break
        self.logger.info(f"clean error cases in lines {fulL_lines}")
        self.parser.comment_code(fulL_lines)
        return self.parser.get_code()

    def check_test_class(self, ts_info:dict, prompt_path:str, response_path:str, context_path:str):
        '''
        Check if the test class is compileable.
        If not, repair the test cases through rules & LLM.
        '''
        test_path = ts_info["test-path"]
        test_class = ts_info["test-class"]
        class_name = test_path.split('/')[-1]
        class_path = f"{self.testclass_path}/{class_name}"
        target_path = f"{self.url}/{test_path}"
        passrates = []
        io_utils.copy_file(class_path, target_path)
        flag, feedback, passrate = self.compile_and_execute(test_path, test_class)
        passrates.append(passrate)
        count = 0
        fixed_code = io_utils.load_text(class_path)
        context = io_utils.load_json(context_path)
        while flag!=VerifyResult.PASS and count<self.max_tries:
            temp = f"{self.temp_path}/{class_name}".replace(".java", f"_{count}.java")
            io_utils.write_text(temp, fixed_code)
            self.logger.info(f"try to repair test class {class_path}...")
            if flag == VerifyResult.COMPILE_ERROR:
                error_infos = self.parse_feedback(feedback, test_path)
                fixed_code = self.repair_by_rules(fixed_code, error_infos[0])
                io_utils.write_text(target_path, fixed_code)
                flag, feedback, passrate = self.compile_and_execute(test_path, test_class)
            if flag!=VerifyResult.PASS:
                prompt = f"{prompt_path}_{count}.md"
                response = f"{response_path}_{count}.md"
                fixed_code = self.repair_by_LLM(fixed_code, feedback, prompt, response, context, flag)
                io_utils.write_text(target_path, fixed_code)
                flag, feedback, passrate = self.compile_and_execute(test_path, test_class)
                if flag == VerifyResult.COMPILE_ERROR and count>=self.half_tries:
                    error_infos = self.parse_feedback(feedback, test_path)
                    commented_code = self.clean_error_cases(error_infos[-1], fixed_code)
                    io_utils.write_text(target_path, commented_code)
                    cflag, cfeedback, cpassrate = self.compile_and_execute(test_path, test_class)
                    if cpassrate > passrate:
                        flag = cflag
                        feedback = cfeedback
                        passrate = cpassrate
                        fixed_code = commented_code
            passrates.append(passrate)
            count += 1
        
        # while cflag==False:
        # if flag == VerifyResult.COMPILE_ERROR:
        #     error_infos = self.parse_feedback(feedback, test_path)[-1]
        #     fixed_code = self.clean_error_cases(error_infos, fixed_code)
        #     # io_utils.write_text(target_path, fixed_code)
        #     # cflag, feedback = self.compile_test(test_path)
        #     count += 1
        if count > 0:
            temp = f"{self.temp_path}/{class_name}".replace(".java", f"_{count}.java")
            io_utils.write_text(temp, fixed_code)
            # get the test class with max passrate
            max_value = max(passrates)
            max_index = passrates.index(max_value) if max_value>=0 else len(passrates)-1
            if max_index < count:
                index_file = f"{self.temp_path}/{class_name}".replace(".java", f"_{max_index}.java")
                fixed_code = io_utils.load_text(index_file)
                io_utils.write_text(class_path, fixed_code)
        return


def verify_test_classes(file_structure, task_setting, dataset_info):
    '''
    Compile test class to check correctness
    If there are compilation errors, fix the test cases through compilation feedback.
    '''
    root_path = os.getcwd().replace("\\", "/")
    dependency_path = f"{root_path}/{file_structure.DEPENDENCY_PATH}"
    dataset_dir = file_structure.DATASET_PATH
    code_info_path = file_structure.CODE_INFO_PATH
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
        code_info = io_utils.load_json(f"{code_info_path}/json/{pj_name}.json")
        import_dict = code_info["import_dict"]
        code_repair = CodeRepairer(dependency_path, project_path, project_testclass, fix_tries, import_dict)

        for ts_info in pj_info["focal-methods"]:
            tid = ts_info["id"]
            if case_select and tid not in case_list: continue
            context_path = f"{project_prompt}/{tid}/usage_context.json"
            case_prompt_path = f"{project_fix}/{tid}/repair_prompt"
            case_response_path = f"{project_fix}/{tid}/repair_response"
            code_repair.check_test_class(ts_info, case_prompt_path, case_response_path, context_path)
    return


if __name__ == "__main__":
    import os
    import sys 
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    s = '''
    '''
    code_repair = CodeRepairer("", "", 1)
    pass