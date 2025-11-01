import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import tools.io_utils as io_utils

class ChatUniTestRunner():
    def __init__(self):
        pass


class UTGenRunner():
    data_folder = ""

    def __init__(self, dfolder):
        self.data_folder = dfolder
        return
    
    def prepare_dataset(self, dataset):
        csv_file = f"{self.data_folder}/projects_binary/classes.csv"
        csv_header = ["project", "class"]
        csv_data = []
        extracted_classes = set()
        for pname,pinfo in dataset.items():
            for minfo in pinfo["focal-methods"]:
                class_name = minfo["class"]
                if class_name not in extracted_classes:
                    csv_data.append([pname, class_name])
                    extracted_classes.add(class_name)
        io_utils.write_csv(csv_file, csv_data, csv_header)
        pass
    
    def process_test_classes(self):
        pass


if __name__ == "__main__":
    # test runners
    from settings import BaseLine, FileStructure
    utgen_data_folder = BaseLine.UTGEN_DATA
    dataset_file = f"{FileStructure.DATASET_PATH}/dataset_info.json"
    dataset = io_utils.load_json(dataset_file)
    utgen_runner = UTGenRunner(utgen_data_folder)
    utgen_runner.prepare_dataset(dataset)
    pass