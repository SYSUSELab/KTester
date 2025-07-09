import re
import networkx as nx
from queue import Queue
from networkx import Graph

import tools.io_utils as io_utils
from tools.code_search import SnippetReader

def process_signature(osig, return_type=None):
        if return_type:
            method_sig = osig[osig.index(return_type)+len(return_type):]
        else:
            method_sig = osig
        while len(re.findall(r"<[^<>]*>", method_sig, flags=re.DOTALL))>0:
            method_sig = re.sub(r"<[^<>]*>", "", method_sig, flags=re.DOTALL)
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
                    method_sig = method_sig[method_sig.index(return_type)+len(return_type):]
                    for call_info in minfo["call_methods"]:
                        call_split = call_info["signature"].split('#')
                        callee = call_split[0]
                        call_sig = process_signature(call_split[-1])
                        if callee in calling_graph and call_sig in calling_graph[callee]:
                            calling_graph[callee][call_sig]["caller"].append({
                                "sig": f"{callee}#{method_sig}",
                                "lines": call_info["line_numbers"]
                                })
        graph_path = f"{code_info_path}/codegraph/{pj_name}_callgraph.json"
        io_utils.write_json(graph_path, calling_graph)


class InvokePatternExtractor:
    call_graph: Graph
    method_cfgs: dict
    def __init__(self, code_info_path, calling_path, cfg_path):
        self.code_info = io_utils.load_json(code_info_path)
        calling_data = io_utils.load_json(calling_path)
        cfg_data = io_utils.load_json(cfg_path)
        self.build_calling_graph(calling_data)
        self.build_method_cfg(cfg_data)
        pass

    def build_calling_graph(self, calling_data:dict):
        graph = Graph()
        nodes:set[tuple[str,dict[str,str]]] = set()
        edges = []
        for class_fqn, cdata in calling_data.items():
            for method_sig, mdata in cdata.items():
                node_id = f"{class_fqn}#{method_sig}"
                nodes.add((node_id, {"type": mdata["type"]}))
                for caller in mdata["caller"]:
                    edges.append((node_id, caller["sig"], {"target": caller["lines"]}))
        graph.add_nodes_from(nodes)
        graph.add_edges_from(edges)
        nodes = list(graph.nodes)
        # delete nodes without edges
        for node in nodes:
            if graph.degree(node)==0:
                graph.remove_node(node)
        self.call_graph = graph
        return

    def build_method_cfg(self, cfg_data):
        cfg_cache = {}
        for class_fqn, cdata in cfg_data.items():
            for method_sig, mdata in cdata.items():
                method_graph = Graph()
                nodes = []
                edges = []
                nodes = [(node["id"], {"kind": node["kind"], "lines": node["lines"]}) for node in mdata["nodes"]]
                edges = [(edge["source"], edge["target"], {"is_back": edge["is_back"]}) for edge in mdata["edges"]]
                method_graph.add_nodes_from(nodes)
                method_graph.add_edges_from(edges)
                cfg_cache[f"{class_fqn}#{method_sig}"] = method_graph
        self.method_cfgs = cfg_cache
        return

    def _build_path(self, prev, start_id, start_node):
        path = []
        cur_node = start_node
        cur_node_id = start_id
        while cur_node_id is not None:
            path.append((cur_node, cur_node["target"]))
            cur_node_id, cur_node = prev[cur_node_id]
        return path

    def get_call_chain(self, node_id):
        bfs_queue = Queue()
        bfs_queue.put(node_id)
        prev = {}
        prev[node_id] = (None, {})
        visited = {node_id}
        target_node = self.call_graph.nodes[node_id]
        call_chains = []
        while not bfs_queue.empty():
            cur_node_id = bfs_queue.get()
            cur_node = self.call_graph.nodes[cur_node_id]
            # if cur_node in self.call_graph:
            if cur_node["type"] != "PRIVATE" and cur_node_id!=node_id:
                path = self._build_path(prev, cur_node_id, cur_node)
                call_chains.append(path)
            # get cur_node's edge:
            for edge in self.call_graph.edges(cur_node_id):
                caller = edge[1]
                caller_file = self.call_graph.nodes[caller]["file"]
                if caller not in visited:
                    bfs_queue.put(caller)
                    prev[caller] =(cur_node_id, {"target": edge[2]["target"]})
                    visited.add(caller)
        # keep the shortest 3 paths
        call_chains.sort(key=lambda x: len(x))
        call_chains = call_chains[:min(3, len(call_chains))]
        return call_chains

    def _order_code_lines(self, code_lines:list):
        '''
        simplify lines expression, e.g. [1,2,3,4,5,7,9] to [[1,5],7,9]
        '''
        if len(code_lines) <= 1:return code_lines
        code_lines.sort()
        ordered_lines = []
        start = code_lines[0]
        end = start
        for i in range(1, len(code_lines)):
            if code_lines[i] == end + 1:
                end = code_lines[i]
            else:
                if start == end: ordered_lines.append(start)
                else: ordered_lines.append([start, end])
                start = code_lines[i]
                end = start
        if start == end: ordered_lines.append(start)
        else: ordered_lines.append([start, end])
        return ordered_lines

    def _get_lines_from_cfg(self, cfg:Graph, target_lines):
        visited = set(target_lines)
        # find the node with kind="BEGIN"
        start_node: int
        target_nodes = set()
        for nid, node in cfg.nodes.data():
            if any(line in node["lines"] for line in target_lines):
                target_nodes.add(nid)
            if node["kind"] == "BEGIN":
                start_node = nid
        for target in target_lines:
            paths = nx.all_shortest_paths(cfg, start_node, target)
            for path in paths:
                for node in path:
                    visited.add(node)
        return list(visited)

    def _get_lines_from_method(self, class_fqn, method_sig, target_lines):
        method_cfg = self.method_cfgs[f"{class_fqn}#{method_sig}"]
        return self._get_lines_from_cfg(method_cfg, target_lines)

    def extract_code_public(self, caller, target_sig):
        return
    
    def extract_code_private(self, call_chains, target_sig):
        code_lines = []
        for call_chain in call_chains:
            pass
            # for node in call_chain:
            #     code_lines += self._get_lines_from_cfg(node, target_sig)
        return

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
    def extract_invoke_pattern(self, calling_data, code_info):
        invoke_patterns = {}
        # extract invoke pattern
        for class_fqn, cdata in calling_data.items():
            invoke_patterns[class_fqn] = {}
            for method_sig, mdata in cdata.items():
                if len(mdata["caller"])==0: continue
                node_id = f"{class_fqn}#{method_sig}"
                if mdata["type"] == "PRIVATE":
                    call_chains = self.get_call_chain(node_id)
                else:
                    callers = [edge[1] for edge in self.call_graph.edges(node_id)]
        return


def extract_invoke_patterns():
    code_info_path = file_structure.CODE_INFO_PATH
    dataset_dir = f"{file_structure.DATASET_PATH}/dataset_info.json"
    dataset_info = io_utils.load_json(dataset_dir)
    for pj_name, pj_info in dataset_info.items():
        code_info = io_utils.load_json(f"{code_info_path}/json/{pj_name}.json")
        calling_graph = io_utils.load_json(f"{code_info_path}/codegraph/{pj_name}_callgraph.json")
        method_cfg = io_utils.load_json(f"{code_info_path}/codegraph/{pj_name}_controlflow.json")

        pass
    pass