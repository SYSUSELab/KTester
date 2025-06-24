import os
import shutil
import subprocess

import tools.io_utils as utils


class WorkSpacePreparation:
    workspace = "./"
    def __init__(self, workspace):
        self.workspace = workspace

    def prepare_work_space(self,ds_info:dict):
        for pj_name, info in ds_info.items():
            project_url = info["project-url"]
            project_path = f"{self.workspace}/{project_url}"
            self.prepare_project_workspace(project_path)
        return

    def prepare_project_workspace(self, project_path):
        # clean maven project
        if os.path.exists(f"{project_path}/target"):
            self.clean_project_workspace(project_path)
        # build maven project
        if not os.path.exists(f"{project_path}/src/test-original"):
            os.rename(f"{project_path}/src/test", f"{project_path}/src/test-original")
            os.mkdir(f"{project_path}/src/test")
        cd_cmd = ['cd', project_path]
        dependency_cmd = ['mvn', 'dependency:copy-dependencies', '-DoutputDirectory=libs']
        compile_cmd = ['mvn', 'compiler:compile']
        script =  cd_cmd + ['&&'] + dependency_cmd + ['&&'] + compile_cmd
        result = subprocess.run(script, shell=True)
        if result.returncode != 0:
            install_cmd = ['mvn', 'clean', 'install']
            script = cd_cmd + ['&&'] + install_cmd + ['&&'] + dependency_cmd
            result = subprocess.run(script, shell=True)
            if result.returncode != 0:
                print(f"Error: Failed to build project {project_path}.")
                return
        # prepare classpath file for compiling test class
        libs_dic = f"{project_path}/libs"
        lib_list = [f"libs/{li}" for li in os.listdir(libs_dic)]
        libs ="target/classes;"+ ';'.join(lib_list)
        utils.write_text(f"{project_path}/dependencies.txt", libs)
        return
    
    def clean_workspace(self,ds_info:dict):
        for pj_name, info in ds_info.items():
            project_url = info["project-url"]
            project_path = f"{self.workspace}/{project_url}"
            self.clean_project_workspace(project_path)
        return

    def clean_project_workspace(self, project_path):
        # clean maven project
        cd_cmd = ['cd', project_path]
        clean_cmd = ['mvn', 'clean']
        script = cd_cmd + ['&&'] + clean_cmd
        result = subprocess.run(script, shell=True)
        # remove test classes
        test_original = f"{project_path}/src/test-original"
        test_dir = f"{project_path}/src/test/java/"
        if os.path.exists(test_original) and os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        return


def prepare_workspace(dataset_abs:str):
    prepare = WorkSpacePreparation(dataset_abs)
    dataset_file = f"{dataset_abs}/dataset_info.json"
    ds_info = utils.load_json(dataset_file)
    prepare.prepare_work_space(ds_info)
    return


# test
if __name__ == '__main__':
    # import settings as ST
    # root_path = os.getcwd().replace("\\", "/")
    # prepare = WorkSpacePreparation(f"{root_path}/{ST.DATASET_PATH}")
    # dataset_dir = f"{ST.DATASET_PATH}/dataset_info.json"
    # ds_info = utils.load_json(dataset_dir)
    # prepare.prepare_work_space(ds_info)
    # prepare.clean_workspace(ds_info)
    pass