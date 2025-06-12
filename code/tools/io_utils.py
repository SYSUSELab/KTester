import os
import csv
import json
import pickle
import shutil
import logging
# import xml.etree.ElementTree as ET
# from lxml import etree

def load_json(json_file):
    with open(json_file, 'r', errors='ignore', encoding='utf-8') as jf:
        data = json.load(jf)
    return data


def load_text(file):
    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    return text


def read_csv(filename, with_title=False):
    with open(filename, 'r') as file:
        reader = csv.reader(file)
        if with_title: data = list(reader)
        else: data = list(reader)[1:] # Skip the first row
    return data


def write_json(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return


def write_text(file,text):
    with open(file, 'w', encoding="utf-8") as f:
        f.write(text)
    return


def write_csv(file, data, header:list|None):
    with open(file, 'w', newline='') as f:
        writer = csv.writer(f)
        if header: writer.writerow(header)
        writer.writerows(data)
    return


# def read_XML(file):
#     with open(file,'r', encoding='utf-8') as f:
#         tree = ET.parse(f)
#     return tree


# def writeObjs2xml(xml_file, objs, obj_name):
#     """
#     Write a list of objects (e.g., Question post or Comment) to an XML file.
#     """
#     root = etree.Element(obj_name, attrib={'count': str(len(objs))})

#     for obj in objs:
#         try:
#             etree.SubElement(root, 'row', attrib=obj.to_dict_s())
#         except Exception as e:
#             print ('***** Error in writeObjs2xml() *****', e, ':', obj.to_dict_s())

#     tree = etree.ElementTree(root)
#     tree.write(xml_file, pretty_print=True, xml_declaration=True, encoding='utf-8')


def read_pickle(file):
    with open(file, 'rb') as f:
        data = pickle.load(f)
    return data


def write_pickle(file, data):
    with open(file, 'wb') as f:
        pickle.dump(data, f)
    return

def check_path(path):
    destination_dir = os.path.dirname(path)
    if destination_dir and not os.path.exists(destination_dir):
        os.makedirs(destination_dir)
    return


# Copy a directory with files inside it to a target path
def copy_dir(source_dir, target_path, ignore_error=False):
    print(f"Copying {source_dir} to {target_path}")
    check_path(target_path)
    try:
        shutil.copytree(source_dir, target_path, dirs_exist_ok=True)
    except Exception as e:
        print(e)
        if ignore_error: return
        else: raise FileNotFoundError(f"Error occurred while copying the directory {source_dir} to {target_path}")


def copy_file(source_file, target_path, ignore_error=False):
    # print(f"Copying {source_file} to {target_path}")
    check_path(target_path)
    try:
        shutil.copy2(source_file, target_path)
    except Exception as e:
        print(e)
        if ignore_error: return
        else: raise FileNotFoundError(f"Error occurred while copying the file {source_file} to {target_path}")


class StreamToLogger:
    """
    represents a file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ""

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass