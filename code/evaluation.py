import sys
import logging
import argparse


import tools.io_utils as utils
from evaluations.coverage_test import test_coverage
from evaluations.extracrt_baseline_result import exract_baseline_coverage
from settings import FileStructure as FS, TaskSettings as TS, BaseLine as BL

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-L','--log_level', type=str, default='info', help='log level: info, debug, warning, error, critical')
    parser.add_argument('-F','--log_file', help="storage file of output info", default=None)
    parser.add_argument('-O','--operation',type=str, default='precision', help='evaluation operation: coverage')

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


def run(operation):
    '''
    procedure:
    1. run test & generate report
    2. extract: pass rate, coverage, .....
    '''
    dataset_path = FS.DATASET_PATH
    dataset_info = utils.load_json(f"{dataset_path}/dataset_info.json")

    if operation == 'coverage':
        test_coverage(FS, TS, dataset_info)
    if operation == 'baseline':
        exract_baseline_coverage(FS, TS, BL, dataset_info)
    if operation == 'check':
        from evaluations.check_empty_class import check_empty_class
        check_empty_class(FS, dataset_info)
    return


if __name__ == "__main__":
    args = get_args()
    if args.log_file:
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=args.log_level,
            filename=args.log_file)
        sys.stdout = utils.StreamToLogger(logging.getLogger("STDOUT"), logging.INFO)
        sys.stderr = utils.StreamToLogger(logging.getLogger("STDERR"), logging.ERROR)
    else:
        logging.basicConfig(
            level=args.log_level, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    run(args.operation)
    