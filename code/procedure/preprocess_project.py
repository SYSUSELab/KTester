import re
import copy
import networkx as nx
from queue import Queue
from networkx import DiGraph

import tools.io_utils as io_utils
from tools.code_search import SnippetReader

def process_signature(osig, return_type=None):
        if return_type:
            method_sig = osig[osig.index(return_type)+len(return_type):]
        else:
            method_sig = osig
        while len(re.findall(r"<[^<>]*>", method_sig, flags=re.DOTALL))>0:
            method_sig = re.sub(r"<[^<>]*>", "", method_sig, flags=re.DOTALL)
        method_sig = re.sub(r"\w+\.", "", method_sig, flags=re.DOTALL)
        return method_sig

'''
structure of calling graph:
{
    "<class_fqn>": {
        "<method_sig>": {
            "type" : "<access_type>",
            "file": "<file_path>",
            "caller": [
                {   
                    "sig": "<classfqn>#<method_sig>",
                    "lines": [2,3,...]
                },
                {...}
            ]
        }
    }
}
'''
def build_calling_graph(file_structure):
    code_info_path = file_structure.CODE_INFO_PATH
    dataset_dir = f"{file_structure.DATASET_PATH}/dataset_info.json"
    dataset_info = io_utils.load_json(dataset_dir)

    for pj_name, pj_info in dataset_info.items():
        calling_graph = {}
        code_info = io_utils.load_json(f"{code_info_path}/json/{pj_name}.json")
        source_data = code_info["source"]
        for class_fqn, cinfo in source_data.items():
            class_data = {}
            for _, method_infos in cinfo["methods"].items():
                for minfo in method_infos:
                    return_type = minfo["return_type"].split('.')[-1] + " "
                    method_sig = process_signature(minfo["signature"], return_type)
                    class_data[method_sig] = {
                        "type": minfo["access_type"],
                        "caller": []
                    }
            for minfo in cinfo["constructors"]:
                method_sig = minfo["signature"]
                class_data[method_sig] = {
                        "type": minfo["access_type"],
                        "caller": []
                }
            calling_graph.update({class_fqn: class_data})

        for class_fqn, cinfo in source_data.items():
            # class_data = calling_graph[class_fqn]
            for _, method_infos in cinfo["methods"].items():
                for minfo in method_infos:
                    method_sig = minfo["signature"]
                    return_type = minfo["return_type"].split('.')[-1] + " "
                    # method_sig = method_sig[method_sig.index(return_type)+len(return_type):]
                    method_sig = process_signature(method_sig, return_type)

                    for call_info in minfo["call_methods"]:
                        call_split = call_info["signature"].split('#')
                        callee = call_split[0]
                        call_sig = process_signature(call_split[-1])
                        if callee in calling_graph and call_sig in calling_graph[callee]:
                            calling_graph[callee][call_sig]["caller"].append({
                                "sig": f"{class_fqn}#{method_sig}",
                                "lines": call_info["line_numbers"]
                                })
        graph_path = f"{code_info_path}/codegraph/{pj_name}_callgraph.json"
        io_utils.write_json(graph_path, calling_graph)


class InvokePatternExtractor:
    code_info: dict
    calling_data: dict
    call_graph: DiGraph
    method_cfgs: dict

    def __init__(self, code_info_path, calling_path, cfg_path):
        self.code_info = io_utils.load_json(code_info_path)
        self.calling_data = io_utils.load_json(calling_path)
        cfg_data = io_utils.load_json(cfg_path)
        self.build_calling_graph(self.calling_data)
        self.build_method_cfg(cfg_data)
        pass

    def build_calling_graph(self, calling_data:dict):
        graph = DiGraph()
        nodes:dict = {}
        edges = []
        for class_fqn, cdata in calling_data.items():
            for method_sig, mdata in cdata.items():
                node_id = f"{class_fqn}#{method_sig}"
                nodes.update({node_id: {"type": mdata["type"]}})
                for caller in mdata["caller"]:
                    edges.append((node_id, caller["sig"], {"target": caller["lines"]}))
        graph.add_nodes_from([(node_id, nodes[node_id]) for node_id in nodes])
        graph.add_edges_from(edges)
        gnodes = list(graph.nodes)
        # delete nodes without edges
        for node in gnodes:
            if len(list(graph.neighbors(node))) + len(list(graph.predecessors(node))) == 0:
                graph.remove_node(node)
        self.call_graph = graph
        return

    def build_method_cfg(self, cfg_data):
        cfg_cache = {}
        for class_fqn, cdata in cfg_data.items():
            for method_sig, mdata in cdata.items():
                method_graph = DiGraph()
                nodes = []
                edges = []
                nodes = [(node["id"], {"kind": node["kind"], "lines": node["lines"]}) for node in mdata["nodes"]]
                edges = [(edge["source"], edge["target"], {"is_back": edge["is_back"]}) for edge in mdata["edges"]]
                method_graph.add_nodes_from(nodes)
                method_graph.add_edges_from(edges)
                cfg_cache[f"{class_fqn}#{method_sig}"] = method_graph
        self.method_cfgs = cfg_cache
        return

    def _build_path(self, prev, start_id):
        path = []
        cur_node_id = start_id
        cur_node = prev[start_id]
        while cur_node is not None:
            path.append((cur_node_id, cur_node["target"]))
            cur_node_id = cur_node["id"]
            cur_node = prev[cur_node_id]
        return path

    def get_call_chain(self, node_id):
        bfs_queue = Queue()
        bfs_queue.put((node_id,[]))
        call_chains = []
        while not bfs_queue.empty():
            cur_node_id, path = bfs_queue.get()
            for edge in self.call_graph.edges(cur_node_id,data=True):
                caller = edge[1]
                caller_node = self.call_graph.nodes[caller]
                chain = [node[0] for node in path]
                npath = copy.deepcopy(path)
                npath.append((caller, edge[2]["target"]))
                if caller_node["type"] == "PRIVATE" and caller not in chain:
                    bfs_queue.put((caller, npath))
                else:
                    call_chains.append(npath)
        # keep the shortest 3 paths
        call_chains.sort(key=lambda x: len(x))
        call_chains = call_chains[:min(3, len(call_chains))]
        print("call_chains of ",node_id,": ",call_chains)
        return call_chains

    def _order_code_lines(self, code_lines:list):
        '''
        simplify lines expression, e.g. [1,2,3,4,5,7,9] to [[1,5],7,9]
        '''
        length = len(code_lines)
        if length <= 1:return code_lines
        code_lines.sort()
        ordered_lines = []
        start = code_lines[0]
        end = start
        for i in range(1, length):
            if code_lines[i] == end + 1:
                end = code_lines[i]
            else:
                if start == end: ordered_lines.append(start)
                else: ordered_lines.append([start, end])
                start = code_lines[i]
                end = start
        if start == end: ordered_lines.append(start)
        else: ordered_lines.append([start, end])
        return (ordered_lines, length)

    def _get_lines_from_cfg(self, cfg:DiGraph, target_lines):
        visited = set(target_lines)
        # find the node with kind="BEGIN"
        start_node = None
        target_nodes = set()
        for nid, node in cfg.nodes.data():
            if any(line in node["lines"] for line in target_lines):
                target_nodes.add(nid)
            if node["kind"] == "BEGIN":
                start_node = nid
        # 如果没有找到BEGIN节点，返回已访问的行
        if start_node is None:
            return list(visited)
        for target in target_nodes:
            paths = nx.all_shortest_paths(cfg, start_node, target)
            for path in paths:
                for node in path:
                    visited.update(cfg.nodes[node]["lines"])
        return list(visited)

    def _equal_sig(self, candidate, target):
        cand_parts = candidate.replace("(", "( ").replace(")", " )").split()
        target_parts = target.replace("(", "( ").replace(")", " )").split()
        if len(cand_parts) != len(target_parts):
            return False
        if cand_parts[0] != target_parts[0]:
            return False
        for item_m, item_t in zip(cand_parts[1:-1], target_parts[1:-1]):
            if item_m.startswith("Object"): continue
            if len(item_t.replace(',','')) == 1: continue
            elif not item_t.startswith(item_m):
                return False
        return True

    def _get_lines_from_method(self, class_fqn, method_sig, target_lines):
        class_info = self.code_info["source"][class_fqn]
        method_info = None
        for method, m_infos in class_info["methods"].items():
            if method_sig.find(method) != -1:
                for m_info in m_infos: 
                    if process_signature(m_info["signature"]).endswith(method_sig):
                        method_info = m_info
                        break
        if method_info is None:
            for m_info in class_info["constructors"]:
                if process_signature(m_info["signature"]).endswith(method_sig):
                    method_info = m_info
                    break
        if method_info is None:
            err_msg = f"method {method_sig} not found in class {class_fqn}"
            raise ValueError(err_msg)
        method_cfg = None
        full_sig = f"{class_fqn}#{method_sig}"
        for candidate in self.method_cfgs.keys():
            if self._equal_sig(candidate, full_sig):
                method_cfg = self.method_cfgs[candidate]
                break
        if method_cfg is None: 
            err_msg = f"sig {full_sig} not found in method cfg"
            print(err_msg)
            # raise ValueError(err_msg)
            return (None, None)
        visited = self._get_lines_from_cfg(method_cfg, target_lines)
        visited.extend([method_info["start_line"], method_info["end_line"]-1])
        return self._order_code_lines(visited)

    def extract_code_public(self, callers):
        path_lines = []
        # callers: [("<class_fqn>#<method_sig>", [target_lines]),()]
        for full_fqn, target_lines in callers:
            path_line = []
            class_fqn, method_sig = full_fqn.split("#")
            code_line, length = self._get_lines_from_method(class_fqn, method_sig, target_lines)
            if code_line is None: continue
            file_path = self.code_info["source"][class_fqn]["file"]
            path_line.append({"file_path": file_path, "lines": code_line})
            path_lines.append((path_line, length))

        path_lines.sort(key=lambda x: x[1])
        path_lines = [x[0] for x in path_lines[:min(3, len(path_lines))]]
        return path_lines

    def extract_code_private(self, call_chains):
        path_lines = []
        # call_chain: [("<class_fqn>#<method_sig>", [target_lines]),()]
        for call_chain in call_chains:
            path_line = []
            for full_sig, target_lines in call_chain:
                class_fqn, method_sig = full_sig.split("#")
                result = self._get_lines_from_method(class_fqn, method_sig, target_lines)
                code_line, length = result
                if code_line is None: continue
                file_path = self.code_info["source"][class_fqn]["file"]
                path_line.append({"file_path": file_path, "lines": code_line})
            # 计算总长度
            total_length = sum(len(item.get("lines", [])) for item in path_line if isinstance(item, dict))
            path_lines.append((path_line, total_length))
        return path_lines

    '''
    invoke pattern:
    {
        "<class_fqn>": {
            "<method_sig>": [
                [{"file_path": "<path>", lines:[[1,5], 7, 9]}, {...}],
                [....]
            ]
        }
    }
    '''
    def extract_invoke_pattern(self):
        invoke_patterns = {}
        # extract invoke pattern
        for class_fqn, cdata in self.calling_data.items():
            invoke_patterns[class_fqn] = {}
            for method_sig, mdata in cdata.items():
                if len(mdata["caller"])==0: continue
                node_id = f"{class_fqn}#{method_sig}"
                if mdata["type"] == "PRIVATE":
                    call_chains = self.get_call_chain(node_id)
                    if len(call_chains)==0: continue
                    path_lines = self.extract_code_private(call_chains)
                    invoke_patterns[class_fqn][method_sig] = path_lines
                else:
                    callers = [(caller, edge["target"]) for _, caller, edge in self.call_graph.edges(node_id, data=True)]
                    path_lines = self.extract_code_public(callers)
                    invoke_patterns[class_fqn][method_sig] = path_lines
        return invoke_patterns


def extract_invoke_patterns(file_structure):
    code_info_path = file_structure.CODE_INFO_PATH
    dataset_dir = f"{file_structure.DATASET_PATH}/dataset_info.json"
    dataset_info = io_utils.load_json(dataset_dir)
    for pj_name, pj_info in dataset_info.items():
        code_info = f"{code_info_path}/json/{pj_name}.json"
        calling_graph = f"{code_info_path}/codegraph/{pj_name}_callgraph.json"
        method_cfg = f"{code_info_path}/codegraph/{pj_name}_controlflow.json"
        extractor = InvokePatternExtractor(code_info, calling_graph, method_cfg)
        invoke_patterns = extractor.extract_invoke_pattern()
        io_utils.write_json(f"{code_info_path}/codegraph/{pj_name}_invoke.json", invoke_patterns)
    return