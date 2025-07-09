import os
import re
import copy
import json
import jpype
import logging

import tools.io_utils as utils


class SnippetReader:
    project_path: str
    cache:dict # {"<file_path>": ["line1", "line2"]}
    def __init__(self, pj_path):
        self.project_path = pj_path
        self.cache = {}
        pass

    def _get_contents(self, file_path):
        lines = self.cache.get(file_path)
        if lines is None:
            content:str = utils.load_text(file_path)
            lines = content.splitlines()
            self.cache[file_path] = lines
        return lines

    def read_single_line(self, file_path, line):
        line = max(0, line)
        lines = self._get_contents(file_path)
        return lines[min(line, len(lines)-1)]

    def read_lines(self, file_path, start_line, end_line):
        start_line = max(0, start_line if start_line is not None else 0)
        lines = self._get_contents(file_path)
        end_line = min(max(start_line, end_line) + 1, len(lines))
        return lines[start_line:end_line]

    def read_incoherent_lines(self, file_path, read_lines:list):
        extracted_contents = []
        for line in read_lines:
            if isinstance(line,int):
                extracted_contents.append(self.read_single_line(file_path, line))
            elif isinstance(line,list):
                extracted_contents += (self.read_lines(file_path, line[0], line[1]))
        return extracted_contents


class CodeSearcher:
    project_path: str
    index_path: str
    top_k: str
    code_info: dict
    snippet_reader: SnippetReader

    def __init__(self, project_path: str, code_info_path: str, index_path:str, top_k):
        self.project_path = project_path
        self.index_path = index_path
        self.top_k = top_k
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Loading code info from {code_info_path}")
        self.code_info = utils.load_json(code_info_path)

    # todo: will be replaced by _get_class_info
    def _get_test_classes(self, class_url: str):
        """
        find the test class for the given class
        """
        test_source = f"{self.project_path}/{class_url}".replace("test/", "test-original/")
        content = None
        if os.path.exists(test_source):
            content = utils.load_text(test_source)
        return content

    def _get_class_info(self, class_name: str, istest=False) -> dict:
        if istest:
            return self.code_info["test"].get(class_name, None)
        else:
            return self.code_info["source"].get(class_name, None)

    def _get_method_info(self, class_info: str, method_name: str) -> dict:
        '''
        get the method info in the class info
        '''
        method_info = next(
            (m_info for method, m_infos in class_info["methods"].items()
             if method_name.find(method) != -1
             for m_info in m_infos if m_info["signature"].endswith(method_name)),
            None
        )
        return method_info

    def _extract_snippet(self, context:dict):
        full_context = {}
        for key, value in context.items():
            finds = re.findall(r"(<position:\[([^>]*)\]>)", value, re.DOTALL)
            if len(finds) > 0:
                new_value = copy.copy(value)
                for find in finds:
                    pivot = find[0]
                    position = find[1].split(", ")
                    file_path = position[0]
                    start_line = int(position[1])
                    end_line = int(position[2])
                    snippet = '\n'.join(self.snippet_reader.read_lines(file_path, start_line, end_line))
                    new_value = new_value.replace(pivot, snippet)
                full_context[key] = new_value
            else:
                full_context[key] = value
        return full_context


    class DependentClassInfo:
        """
        "class_fqn": {
            "APIdoc": "xxxxx",
            "dep_field": ["decalaration"],
            "dep_func": ["apidoc + sig + body(?)"]
            "rel_func": ["apidoc(?) + sig + annotation + body(?)"]
        }
        """
        class_dict:dict
        def __init__(self):
            self.class_dict = {}
            pass
        def update_str(self, class_name, key, value):
            if class_name not in self.class_dict:
                self.class_dict[class_name] = {key:value}
            else:
                self.class_dict[class_name][key] = value

        def update_list(self, class_name, key, value):
            if class_name not in self.class_dict:
                self.class_dict[class_name] = {key:set([value])}
            elif key not in self.class_dict[class_name]:
                self.class_dict[class_name][key] = set([value])
            else:
                self.class_dict[class_name][key].add(value)

        def __str__(self):
            class_info = []
            for class_name, info in self.class_dict.items():
                pcontext = f"class `{class_name}`:\n\t"
                if "javadoc" in info:
                    pcontext += f"class document: " + info['javadoc']+ "\n\t"
                if "dep_field" in info:
                    pcontext += f"dependent fields:\n\t\t" + '\n\t\t'.join(info['dep_field']) + "\n\t"
                if "dep_func" in info:
                    pcontext += f"dependent functions:\n\t\t" + ';\n\t\t'.join(info['dep_func']) + ";\n\t"
                if "rel_func" in info:
                    pcontext += f"related functions:\n\t\t" + ';\n\t\t'.join(info['rel_func']) +";"
                class_info.append(pcontext)
            return '\n'.join(class_info)


    # todo: compress overlong context
    def collect_construct_context(self, class_name, method_name:str, class_url):
        '''
        content in construct context:
        - API documents (optional)
        - Class constructor
        - Parameter in constructor, expecially classes defined in the project        
        - Existing test class (optional)
        '''
        class_info = self._get_class_info(class_name)
        if class_info is None:
            raise ValueError(f"Class `{class_name}` not found in code info")
        method_info = self._get_method_info(class_info, method_name)
        if method_info is None:
            raise ValueError(f"Method `{method_name}` not found in class `{class_name}`")

        self.snippet_reader = SnippetReader(self.project_path)
        source_path = "/src/main/java/"+class_info["file"].replace("\\","/")
        context = {}
        pclass = {}
        # get api document
        if "javadoc" in class_info:
            context[f"api document of class {class_name}"] = class_info["javadoc"]
        # get the constructor info
        constructor_info = []
        for constructor in class_info["constructors"]:
            ptext = []
            for param in constructor["parameters"]:
                ptype = param["type"]
                pname = param["name"]
                pinfo = self._get_class_info(ptype)
                if pinfo is not None:
                    pclass[ptype] = pinfo
                    ptext.append(f"{ptype} {pname} ")
            start_line = constructor["start_line"]
            end_line = constructor["end_line"]
            body_pos = f"<position:[{source_path}, {start_line}, {end_line}]>"
            param_text = '\n'.join(ptext)
            constructor_info.append(f"params: {param_text}\nbody:\n```java\n{body_pos}\n```")
        if len(constructor_info) > 0:
            context[f"constructors for class `{class_name}`"] = '\n'.join(constructor_info)
        # parameter in constructor & focus method
        parameter_info = []
        for param in method_info["parameters"]:
            ptype = param["type"]
            pname = param["name"]
            pinfo = self._get_class_info(ptype)
            if pinfo is not None:
                pclass[ptype] = pinfo
        for param, pinfo in pclass.items():
            pcontext = f"class `{param}`:\n"
            if "javadoc" in pinfo:
                pcontext += f"api document : {pinfo['javadoc']}\n"
            pcontext += f"constructor:\n```java\n"
            for constructor in pinfo["constructors"]:
                file_path = "src/main/java/" + pinfo["file"].replace("\\","/")
                start_line = constructor["start_line"]
                end_line = constructor["end_line"]
                pcontext += f"<position:[{file_path}, {start_line}, {end_line}]>\n"
            pcontext += f"```"
            parameter_info.append(pcontext)
        if len(parameter_info) > 0:
            context[f"parameters in constructors and focal method"] = '\n'.join(parameter_info)
        # get existing test class
        test_url = class_url.replace("main","test").replace(".java", "Test.java")
        test_class = self._get_test_classes(test_url)
        if test_class is not None:
            lines = test_class.splitlines()
            if len(lines) > 150:
                test_class = '\n'.join(lines[:100]) + "\n......\n" + '\n'.join(lines[-50:])
            context["existing test class"] = f"```java\n{test_class}\n```"
        # more context can be added here
        context = self._extract_snippet(context)
        return context


    # TODO: compress overlong context
    def collect_usage_context(self, class_name, method_name:str):
        '''
        content in usage context:
        - Parameter & Return Value in the focus method, expecially classes defined in the project
        - External variables and methods called in the focus method
        - Related mathods with focal method and dependent method
        - Code context for calling focus methods (unimplemented)
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
        depclass = self.DependentClassInfo()
        method_sig = method_info["signature"]
        return_type = method_info["return_type"].split('.')[-1] + " "
        query_list = [{
            "sig": class_name + "." + method_sig[method_sig.index(return_type)+len(return_type):],
            "function": [cm["signature"] for cm in method_info["call_methods"]],
            "field": [cf["name"] for cf in method_info["external_fields"]],
        }]
        
        # api documents
        if "javadoc" in class_info:
            context[f"api document of class {class_name}"] = class_info["javadoc"]
        if "javadoc" in method_info:
            context[f"api document of method {method_name}"] = method_info["javadoc"]
        # parameters in focus method
        for param in method_info["parameters"]:
            ptype = param["type"]
            pinfo = self._get_class_info(ptype)
            if pinfo is not None:
                if "javadoc" in pinfo:
                    depclass.update_str(ptype, "APIdoc", pinfo["javadoc"])
            pass
        # return type in focus method
        return_type:str = method_info["return_type"]
        if return_type!="void" and not return_type.startswith("java"):
            context["return type"] = return_type
        # calling methods in focus method
        for cmethod in method_info["call_methods"]:
            method_sig = cmethod["signature"]
            sig_split = method_sig.split(".")
            class_name = '.'.join(sig_split[:-1])
            method_name = sig_split[-1]
            cinfo = self._get_class_info(class_name)
            if cinfo is not None:
                if "javadoc" in cinfo:
                    depclass.update_str(class_name, "APIdoc", cinfo["javadoc"])
                minfo = self._get_method_info(cinfo, method_name)
                if minfo is not None:
                    api_doc = minfo.get("javadoc")
                    return_type = minfo["return_type"]
                    cmtext = f"method `{method_name}` returns `{return_type}`"
                    if api_doc is not None: cmtext += f", api document: {api_doc}"
                    depclass.update_list(class_name, "dep_func", cmtext)
                    query_list.append({
                        "sig": method_sig,
                        "function": [cm["signature"] for cm in minfo["call_methods"]],
                        "field":[cf["name"] for cf in minfo["external_fields"]],
                    })
        # external field in focus method
        for field in method_info["external_fields"]:
            fqn = field["name"]
            ftype = field["type"]
            class_name = '.'.join(fqn.split(".")[:-1])
            if self._get_class_info(class_name) is not None:
                depclass.update_list(class_name, "dep_field", f"{ftype} {fqn};")
        # related functions
        sim_funcs = self.search_similar_function(query_list)
        self.logger.debug(f"length of search result: {len(sim_funcs)}")
        for func in sim_funcs:
            class_fqn = func["class_fqn"]
            method_sig = func["signature"]
            caller = func["related_func"]
            cinfo = self._get_class_info(class_fqn)
            minfo = self._get_method_info(cinfo, method_sig)
            api_doc = minfo.get("javadoc")
            return_type = minfo["return_type"]
            cmtext = f"method `{method_sig}` returns `{return_type}`, related with `{'`, `'.join(caller)}`"
            if api_doc is not None: cmtext += f", api document: {api_doc}"
            depclass.update_list(class_fqn, "rel_func", cmtext)
        context["dependent classes"] = str(depclass)
        # add more context here
        return context

    def search_similar_function(self, query:list) -> list[dict]:
        """
        Search the similar function in the Java project and extract the context.
        Args:
            target_function: Function to search for.
        Returns:
            A list containing similar function information. Each element is a dictionary containing file path, line number, and context.
        """
        CodeSearcher = jpype.JClass("CodeSearcher")
        result_str = str(CodeSearcher.main([self.project_path, self.index_path, str(query), self.top_k]))
        results = json.loads(result_str)
        return results

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

    # def search_method_usage(self, target_method: str) -> list[dict]:
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
    import sys 
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project_path = "dataset/projects/commons-csv"
    code_info_path = "dataset/project_index/json/commons-csv.json"
    index_path = "./dataset/project_index//lucene/commons-csv"
    top_k = 10
    method_name = "nextToken(Token)"
    searcher = CodeSearcher(project_path,code_info_path,index_path,top_k)
    # results = searcher.search_method_usage(method_name)
    class_name = "org.apache.commons.csv.Lexer" 
    # results = searcher.search_class_usage(class_name)
    class_url = "src/main/java/org/apache/commons/csv/CSVFormat.java"
    results = searcher.collect_construct_context(class_name, method_name, class_url)
    print(results)