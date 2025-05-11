import re
import tree_sitter_java as ts_java
from queue import Queue
from tree_sitter import Language, Parser

class ASTParser:
    source_code: str
    parser: Parser
    tree = None
    lines:list

    def __init__(self):
        self.parser = Parser(Language(ts_java.language()))
        return

    # def __init__(self, source_code):
    #     self.parser = Parser(Language(ts_java.language()))
    #     self.parse(source_code)
    #     return
    
    def parse(self, source_code):
        self.source_code = source_code
        self.lines = source_code.splitlines()
        byte_code = source_code.encode('utf8')
        self.tree = self.parser.parse(byte_code, encoding='utf8')
        return

    def _traverse_get(self, type):
        node_list = []
        bfs_queue = Queue()
        bfs_queue.put(self.tree.root_node)
        while not bfs_queue.empty():
            node = bfs_queue.get()
            if node.type == type:
                node_list.append(node)
            else:
                for child in node.children:
                    bfs_queue.put(child)
        return node_list

    def _get_functions(self):
        functions = []
        # get method_declaration nodes
        method_list = self._traverse_get('method_declaration')
        for node in method_list:
            # get function body
            start_line = node.start_point[0]
            end_line = node.end_point[0]
            while self.lines[start_line-1].lstrip().startswith('@'):
                start_line -= 1
            function_code = '\n'.join(self.lines[start_line:end_line+1])
            functions.append(function_code)
        return functions
    
    def _get_imports(self):
        return re.findall(r'import .*;', self.source_code, re.MULTILINE)


    def get_additional_imports(self, existing_imports):
        imports = self._get_imports()
        additional_imports = []
        for imp in imports:
            if imp not in existing_imports:
                additional_imports.append(imp)
        return additional_imports


    def get_test_cases(self) -> list:
        test_cases = []
        exclude_annotations = ['@BeforeEach', '@AfterEach', '@BeforeAll', '@AfterAll']
        functions = self._get_functions()
        for func in functions:
            flag = True
            for annotation in exclude_annotations:
                if func.find(annotation) > -1:
                    flag = False
            if flag:
                test_cases.append(func)
        return test_cases


#test
if __name__ == '__main__':
    source_code = '''
    package infostructure;
    import java.io.IOException;
    public class MyClass {
        @Test
        public void test1(int a) {
            // test code
        }

        @Test
        public void test2(Token token) {
            // test code
        }

        public void myMethod() {
            // code
        }
    }
    '''
    # ast = ASTParser()
    # ast.parse(source_code)
    # print(ast.get_test_cases())
    # print(ast.get_additional_imports(set()))