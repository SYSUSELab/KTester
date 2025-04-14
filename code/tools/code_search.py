import os
import logging

import tools.io_utils as utils


class CodeSearcher:
    project_path: str
    code_info: dict

    def __init__(self, project_path: str, code_info_path: str):
        self.project_path = project_path
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Loading code info from {code_info_path}")
        self.code_info = utils.load_json(code_info_path)


    def _get_test_classes(self, class_url: str):
        """
        搜索Java项目中指定类的测试类
        """
        test_source = f"{self.project_path}/{class_url}".replace("test/", "test-original/")
        content = None
        if os.path.exists(test_source):
            content = utils.load_text(test_source)
        return content

    def _get_class_info(self, class_name: str) -> dict:
        return self.code_info["source"].get(class_name, None)


    def _get_method_info(self, class_info: str, method_name: str) -> dict:
        '''
        get the method info in the class info
        '''
        method_info = next(
            (m_info for method, m_infos in class_info["methods"].items()
             if method_name.startswith(method)
             for m_info in m_infos if m_info["signature"].endswith(method_name)),
            None
        )
        return method_info

    # todo: compress overlong context
    def collect_construct_context(self, class_name, class_url):
        '''
        content in construct context:
        - Class constructor
        - Parameter in constructor, expecially classes defined in the project
        - API documents (optional)
        - Existing test class (optional)
        '''
        class_info = self._get_class_info(class_name)
        if class_info is None:
            raise ValueError(f"Class `{class_name}` not found in code info")
        
        context = {}
        constructor_info = []
        # get the constructor info
        for constructor in class_info["constructors"]:
            ptext = []
            for param in constructor["parameters"]:
                ptype = param["variable_type"]
                pname = param["variable_name"]
                pinfo = self._get_class_info(ptype)
                if pinfo is not None:
                    # todo: add more info for paramater
                    ptext.append(f"{ptype} {pname} ") #: {pinfo['javadoc']}")
                else:
                    ptext.append(f"{ptype} {pname}")
            constructor_info.append(f"params: {'\n'.join(ptext)}\nbody:\n```java\n" + constructor["body"] + "\n```")
        if len(constructor_info) > 0:
            context[f"constructors for class `{class_name}`"] = f"{constructor_info}"
        # get existing test class
        test_url = class_url.replace("main","test").replace(".java", "Test.java")
        test_class = self._get_test_classes(test_url)
        if test_class is not None:
            context["existing test class"] = f"```java\n{test_class}\n```"
        # get api document
        if "javadoc" in class_info:
            context[f"api document of class {class_name}"] = class_info["javadoc"]
        # more context can be added here
        return context


    # todo: compress overlong context
    def collect_usage_context(self, class_name, method_name:str):
        '''
        content in usage context:
        - External variables (unimplemented) and methods called in the focus method
        - Code context for calling focus methods (unimplemented)
        - Parameter & Return Value in the focus method, expecially classes defined in the project
        - API documents (optional)
        - Code summary (optional) (unimplemented)
        '''
        # get the class info and method info
        class_info = self._get_class_info(class_name)
        if class_info is None:
            raise ValueError(f"Class `{class_name}` not found in code info")
        method_info = self._get_method_info(class_info, method_name)
        if method_info is None:
            raise ValueError(f"Method `{method_name}` not found in class `{class_name}`")
        # collect the context
        context = {}
        # api documents
        if "javadoc" in class_info:
            context[f"api document of class {class_name}"] = class_info["javadoc"]
        if "javadoc" in method_info:
            context[f"api document of method {method_name}"] = method_info["javadoc"]
        # parameters in focus method
        ptext = []
        for param in method_info["parameters"]:
            ptype = param["variable_type"]
            pname = param["variable_name"]
            pinfo = self._get_class_info(ptype)
            if pinfo is not None:
                # todo: add more info for paramater
                ptext.append(f"{ptype} {pname} ") #: {pinfo['javadoc']}")
            else:
                ptext.append(f"{ptype} {pname}")
        if len(ptext) > 0: context["parameters"] = '\n'.join(ptext)
        # return type in focus method
        return_type:str = method_info["return_type"]
        if return_type!="void" and not return_type.startswith("java"):
            context["return type"] = return_type
        # calling methods in focus method
        cmtexts = []
        for cmethod in method_info["call_methods"]:
            method_name = cmethod["signature"]
            return_type = cmethod["return_type"]
            cmtexts.append(f"method: {method_name}, return: {return_type}")
        if len(cmtexts) > 0: context["calling methods"] = '\n'.join(cmtexts)
        # add more context here
        return context

    # def search_class_usage(self, target_class: str) -> List[Dict]:
    #     """
    #     Search the variable declaration of the specified class in the Java project and extract the context.
    #     Args:
    #         target_class: Class to seach for.
    #     Returns:
    #         A list containing variable declaration information. Each element is a dictionary containing file path, line number, and context.
    #     """
    #     results = []
    #     return results

    # def search_method_usage(self, target_method: str) -> List[Dict]:
    #     """
    #     Search the usage of the specified method name in the Java project and extract the context.
    #     Args:
    #         target_method: Method to search for.
    #     Returns:
    #         A list containing method usage information. Each element is a dictionary containing file path, line number, and context.
    #     """
    #     results = []
    #     return results


if __name__ == "__main__":
    project_path = "../dataset/puts/commons-csv"
    method_name = "nextToken"
    searcher = CodeSearcher(project_path)
    # results = searcher.search_method_usage(method_name)
    class_name = "CSVFormat" #"Lexer"
    # results = searcher.search_class_usage(class_name)
    class_url = "src/main/java/org/apache/commons/csv/CSVFormat.java"
    results = searcher.collect_construct_context(class_name, class_url)
    print(results)