import os
import sys
import jpype
import logging
import argparse

from settings import FileStructure as FS, TimeRecord as TR
import tools.io_utils as utils
import procedure.workspace_preparation as WSP
import procedure.preprocess_project as PreProcess


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-L','--log_level', type=str, default='info', help='log level: info, debug, warning, error, critical')
    parser.add_argument('-F','--log_file', help="storage file of output info", default=None)
    parser.add_argument('-W', '--workspace', action='store_true', help='prepare workspace: True/False')
    parser.add_argument('-D', '--dataset', action='store_true', help='prepare dataset_info.json: True/False')
    parser.add_argument('-P', '--project_index', action='store_true', help='prepare project index: True/False')

    args = parser.parse_args()
    log_level = {
        'info': logging.INFO,
        'debug': logging.DEBUG,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }
    args.log_level = log_level[args.log_level]
    return args


def set_file_structure():
    dataset_dir = f"{FS.DATASET_PATH}/dataset_info.json"
    dataset_info = utils.load_json(dataset_dir)
    prompt_path = FS.PROMPT_PATH
    fix_path = FS.FIX_PATH
    response_path = FS.RESPONSE_PATH
    testclass_path = FS.TESTCLASSS_PATH
    report_path = FS.REPORT_PATH
    time_record_path = TR.TIME_RECORD_PATH + '/'
    utils.check_path(time_record_path)
    for pj_name, pj_info in dataset_info.items():
        project_prompt = prompt_path.replace("<project>", pj_name)
        project_fix = fix_path.replace("<project>", pj_name)
        project_response = response_path.replace("<project>", pj_name)
        gen_folder = testclass_path.replace("<project>", pj_name)+'/'
        report_folder = report_path.replace("<project>", pj_name)
        report_csv = f"{report_folder}/jacoco-report-csv/"
        utils.check_path(gen_folder)
        utils.check_path(f"{gen_folder}temp/")
        utils.check_path(report_csv)
        
        for test_info in pj_info["focal-methods"]:
            id = test_info["id"]
            prompt_folder = f"{project_prompt}/{id}/"
            fix_folder = f"{project_fix}/{id}/"
            response_folder = f"{project_response}/{id}/"
            report_html = f"{report_folder}/jacoco-report-html/{id}/"
            utils.check_path(prompt_folder)
            utils.check_path(fix_folder)
            utils.check_path(response_folder)
            utils.check_path(report_html)
    pass


def run(args):
    logger = logging.getLogger(__name__)
    root_path = os.getcwd().replace("\\", "/")
    dataset_path = FS.DATASET_PATH
    code_info_path = FS.CODE_INFO_PATH
    dataset_abs = f"{root_path}/{dataset_path}"

    if args.workspace:
        logger.info("Preparing workspace...")
        WSP.prepare_workspace(dataset_abs)
        logger.info("Setting file structure...")
        set_file_structure()
    # if args.dataset:
    #     logger.info("Preparing dataset_info.json ...")
    #     DatasetProcessor = jpype.JClass("DatasetPrepare")
    #     DatasetProcessor.main([dataset_abs])
    if args.project_index:
        logger.info("Constructing project index ...")
        ProjectPreprocessor = jpype.JClass("PreProcessor")
        ProjectPreprocessor.main([dataset_abs, f"{root_path}/{code_info_path}/json"])
        PreProcess.build_calling_graph(FS)
        PreProcess.extract_invoke_patterns(FS)
        IndexBuilder = jpype.JClass("IndexBuilder")
        IndexBuilder.main(["group", f"{code_info_path}/json", f"{code_info_path}/lucene"])
    
    logger.info("preparation completed.")
    return


if __name__ == '__main__':
    args = get_args()
    if args.log_file:
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=args.log_level,
            filename=args.log_file)
        # sys.stdout = utils.StreamToLogger(logging.getLogger("STDOUT"), logging.INFO)
        # sys.stderr = utils.StreamToLogger(logging.getLogger("STDERR"), logging.ERROR)
    else:
        logging.basicConfig(
            level=args.log_level, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    jpype.startJVM(jpype.getDefaultJVMPath(), '-Xmx4g', "-Djava.class.path=./Java/project-info-process.jar;./Java/project-index-builder.jar")
    run(args)
    jpype.shutdownJVM()