import re
import tree_sitter_java as ts_java
from queue import Queue
from tree_sitter import Language, Node, Parser

class JavaASTParser:
    source_code: str
    parser: Parser
    tree = None
    lines:list
    import_position: int = 0

    def __init__(self):
        self.parser = Parser(Language(ts_java.language()))
        return

    def parse(self, source_code):
        self.lines = source_code.splitlines()
        self._update_code()
        return
    
    def _get_import_position(self):
        for i, line in enumerate(self.lines):
            if line.strip().startswith('import'):
                self.import_position = i + 1
        return

    def _update_code(self, up_imp=True):
        """
        Update the source code and AST with the current lines
        """
        self.source_code = '\n'.join(self.lines)
        byte_code = self.source_code.encode('utf-8')
        self.tree = self.parser.parse(byte_code, encoding='utf8')
        if up_imp: self._get_import_position()
        return

    def _traverse_get(self, type):
        node_list:list[Node] = []
        bfs_queue = Queue[Node]()
        if self.tree is None: return node_list
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

    def _sort_line_number(self, positions:list[int|list[int]], rvs=False):
        lines = set[int]([pos for pos in positions if isinstance(pos, int)])
        ranges = [pos for pos in positions if isinstance(pos, list) and len(pos) == 2]
        for pos in ranges:
            lines.update(range(pos[0], pos[1]+1))
        sorted_lines = list(lines)
        sorted_lines.sort(reverse=rvs)
        sorted_lines = [i for i in sorted_lines if 0<=i<len(self.lines)]
        return sorted_lines

    def get_length(self):
        return len(self.lines)

    def get_code(self, position:list|None=None):
        if position is None:
            return self.source_code
        lines = self._sort_line_number(position)
        code_lines = [self.lines[i] for i in lines]
        return '\n'.join(code_lines)

    def get_test_cases(self) -> list:
        test_cases = []
        test_annotations = ['@Test', '@ParameterizedTest', '@RepeatedTest']
        functions = self._get_functions()
        for func in functions:
            flag = False
            for annotation in test_annotations:
                if func.find(annotation) > -1:
                    flag = True
                    break
            if flag:
                test_cases.append(func)
        return test_cases

    def get_test_case_position(self):
        """
        output format: [[start_lines], [end_lines], [method_name]]
        """
        function_nodes = self._traverse_get('method_declaration')
        test_cases = []
        exclude_annotations = ['@BeforeEach', '@AfterEach', '@BeforeAll', '@AfterAll']
        for node in function_nodes:
            start_line = node.start_point[0]
            end_line = node.end_point[0]
            while self.lines[start_line-1].lstrip().startswith('@'):
                start_line -= 1
            func_code = '\n'.join(self.lines[start_line:end_line+1])
            flag = True
            for annotation in exclude_annotations:
                if func_code.find(annotation) > -1:
                    flag = False
            if flag:
                method_name = node.child_by_field_name('name').text.decode('utf-8') # pyright: ignore[reportOptionalMemberAccess]
                test_cases.append([start_line, end_line, method_name])

        sorted_data = sorted(test_cases, key=lambda x: x[0])
        test_cases_positions = [[],[],[]]
        for obj in sorted_data:
            test_cases_positions[0].append(obj[0])
            test_cases_positions[1].append(obj[1])
            test_cases_positions[2].append(obj[2])
        return test_cases_positions


class JavaCodeEditor(JavaASTParser):
    def __init__(self):
        super().__init__()

    def comment_code(self, positions:list):
        comment_lines = self._sort_line_number(positions)
        for line in comment_lines:
            self.lines[line] = '// ' + self.lines[line]
        self._update_code()
        self.source_code = '\n'.join(self.lines)
        return
    
    def remove_lines(self, positions:list):
        """
        Remove lines from the source code.
        param remove_lines: List of line numbers to be removed.
        """
        removed_lines = self._sort_line_number(positions, rvs=True)
        for line in removed_lines:
            self.lines.pop(line)
        self._update_code()
        return

    def add_imports(self, import_lines:list[str]):
        """
        Add import lines to the source code.
        :param import_lines: List of import lines to be added.
        """
        # Insert the new imports and Update the import position
        self.lines = self.lines[:self.import_position] + import_lines + self.lines[self.import_position:]
        self.import_position += len(import_lines)
        self._update_code()
        return

    def add_exception(self, lines:list[int]):
        lines.sort()
        cur = 0
        cur_line = lines[cur]
        function_nodes = self._traverse_get('method_declaration')
        for node in function_nodes:
            start_line = node.start_point[0]
            end_line = node.end_point[0]
            if start_line<=cur_line and end_line>=cur_line:
                decl_line = start_line
                while self.lines[decl_line].lstrip().startswith('@'):
                    decl_line += 1
                decl = self.lines[decl_line]
                decl = re.sub(r'(throws .*Exception)? \{', 'throws Exception {', decl)
                self.lines[decl_line] = decl
                while cur<len(lines) and start_line<=cur_line and end_line>=cur_line:
                    cur += 1
                    if cur<len(lines): cur_line = lines[cur]
            if cur >= len(lines): break
        self._update_code(up_imp=False)
        return


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
    # ast = JavaASTParser()
    # ast.parse(source_code)
    # print(ast.get_test_case_position())