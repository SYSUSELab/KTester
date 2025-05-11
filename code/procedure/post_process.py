import re
import jpype


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


# def insert_test_case(init_class:str, insert_code:str):
#     init_class = init_class.strip()
#     insert_code = insert_code.lstrip()
#     insert_ast = ASTParser()
#     insert_ast.parse(insert_code)
#     lines = init_class.splitlines()
#     # insert import lines
#     last_import_idx = -1
#     for i, line in enumerate(lines):
#         if line.strip().startswith('import '):
#             last_import_idx = i
#     existing_imports = set(re.findall(r'import .*;', init_class, re.MULTILINE))
#     additional_imports = insert_ast.get_additional_imports(existing_imports)
#     if len(additional_imports) > 0:
#         lines = lines[:last_import_idx+1] + additional_imports + lines[last_import_idx+1:]
#     # insert test case
#     add_test_case = insert_ast.get_test_cases()
#     lines = lines[:-1] + add_test_case + [lines[-1]]
#     added_class = '\n'.join(lines)
#     return added_class