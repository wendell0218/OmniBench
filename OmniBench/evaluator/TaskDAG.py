# evaluator/TaskDAG.py

import json
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional
import os

class TaskDAG:
    """
    从JSON文件或已有的数据中加载Task信息（包含task instruction、dag结构、subtask信息等）。
    提供对子任务操作的封装，如设置子任务状态、判断前驱完成情况、获取后继节点等。
    """

    def __init__(self, task_id: str = None, json_path: Optional[str] = None,
                    subtask_eval_func_dir: str = None,subtask_list: List[Dict[str, Any]] = None):
        """
        Args:
            task_id (str): 任务ID。
            json_path (Optional[str]): 任务信息JSON文件路径。
            subtask_eval_func_dir (str): 子任务评估函数路径。
            subtask_list (List[Dict[str, Any]]): 子任务信息列表。
        """
        # 同时传了 json_path 和 data 时，以 data 为主，json_path 可忽略或给出提示
        self.subtask_list = subtask_list
        self.task_id = task_id

        self.task_data: Dict[str, Any] = {}
        self.subtask_dict = {}  # { subtask_id: { 'eval_func_code':..., 'parameters':..., 'status':..., ... } }
        self.nodes: List[str] = []
        self.edges: Dict[str, List[str]] = {}
        self.successful_topo: List[str] = []  # 用于记录已完成的拓扑序列
        self.node_depth = {}  # 节点深度

        self.depth = 0  # 图的深度
        self.all_topo = []  # 用于记录所有可能的拓扑序列
        self.subtask_eval_func_dir = subtask_eval_func_dir # 子任务评估函数dir


        self.__load_data(json_path=json_path)
        self.__initialize_subtasks()
        self.__initialize_task_graph()

    def __load_data(self,json_path: str,data: Dict[str, Any] = None):
        """
        从JSON文件或数据中加载任务信息。
        """
        # 判断是否需要从文件读取
        if data is None:
            if json_path is not None:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                raise ValueError("Either json_path or data must be provided.")

        # 1. 提取 Task 信息（task_instruction, dag, successful_topo...）
        self.task_data = data  # 或者可以只取自己关心的key

        # 2. 读取节点和边
        dag_data = self.task_data.get("dag", {})
        self.nodes = dag_data.get("nodes", [])
        self.edges = dag_data.get("edges", {})


        # 若 JSON 中尚未给每个子任务标记 status，可在此初始化:
        for nid in self.nodes:
            self.subtask_dict.setdefault(nid, {}).setdefault("status", "Waiting")

    def __initialize_task_graph(self):
        """
        初始化任务图，计算每个节点的深度并记录图的最大深度
        result: self.node_depth, self.depth
        """
        # 使用拓扑排序计算每个节点的深度

        in_degree = defaultdict(int)
        for node in self.nodes:
            in_degree[node] = 0
            self.node_depth[node] = 1
        for u in self.edges:
            for v in self.edges[u]:
                in_degree[v] += 1

        # 拓扑排序的结果存放在 queue 中
        # 从入度为0的节点开始
        queue = deque([node for node in self.nodes if in_degree[node] == 0])
        topo_order = []

        while queue:
            u = queue.popleft()
            topo_order.append(u)
            for v in self.edges.get(u, []):
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        # 计算每个节点的深度
        for u in topo_order:
            for v in self.edges.get(u, []):
                self.node_depth[v] = max(self.node_depth[v], self.node_depth[u] + 1)

        # 计算图的深度
        self.depth = max(self.node_depth.values(), default=0)

    def __initialize_subtasks(self):
        """
        初始化子任务状态：对每一个subtask 读入其eval_func_code
        将无前驱节点置为 'Evaluating' 其余默认为 'Waiting'。
        """
        # 根据nodes每一项读取subtask_eval_func,路径为subtask_eval_func_dir+node+".txt"
        for node in self.nodes:
            subtask_eval_func_path = os.path.join(self.subtask_eval_func_dir, f"{node}.txt")
            with open(subtask_eval_func_path, 'r', encoding='utf-8') as f:
                eval_func_code = f.read()
            self.subtask_dict.setdefault(node, {}).setdefault("eval_func_code", eval_func_code)
            # 加载subtask_list中的subtask信息
            subtask_info = next((item for item in self.subtask_list if item["id"] == node), None) # 从subtask_list中找到对应的subtask信息
            if subtask_info:
                self.subtask_dict[node].update(subtask_info)

        # 收集所有后继节点
        all_successors = []
        for successors in self.edges.values():
            all_successors.extend(successors)

        # 找到无前驱的节点 -> 设置为 'Evaluating'
        for nid in self.nodes:
            if nid not in all_successors:
                self.__set_subtask_status(nid, "Evaluating")

    def get_all_topo(self) -> List[List[str]]:
        """
        获取所有可能的拓扑排序
        """

        def all_topo_util(in_degree, temp_list, result):
            if len(temp_list) == len(self.nodes):
                result.append(temp_list.copy())
                return

            for node in self.nodes:
                if in_degree[node] == 0:
                    temp_list.append(node)
                    in_degree[node] -= 1

                    # 将后继节点入度减1
                    for v in self.edges.get(node, []):
                        in_degree[v] -= 1

                    all_topo_util(in_degree, temp_list, result)

                    # 回溯
                    temp_list.pop()
                    in_degree[node] += 1
                    for v in self.edges.get(node, []):
                        in_degree[v] += 1

        # 计算每个节点的入度
        in_degree = defaultdict(int)
        for u in self.edges:
            for v in self.edges[u]:
                in_degree[v] += 1
        # 收集所有可能的拓扑排序
        result = []
        all_topo_util(in_degree, [], result)
        return result


    def __set_subtask_status(self, subtask_id: str, new_status: str) -> None:
        """
        设置指定子任务节点的状态,子任务节点json无status字段时，自动添加status字段
        """
        if subtask_id not in self.subtask_dict:
            raise KeyError(f"Subtask {subtask_id} not found in subtask_dict.")
        self.subtask_dict[subtask_id]["status"] = new_status

    def __get_subtask_status(self, subtask_id: str) -> str:
        """
        获取指定子任务节点的状态
        """
        return self.subtask_dict[subtask_id].get("status", "")

    def __all_predecessors_completed(self, subtask_id: str) -> bool:
        """
        判断给定 subtask_id 的所有前驱节点是否都为 Completed
        """
        # 找到subtask_id的前驱(在edges中, 所有edges[src]里包含subtask_id的src都是它的前驱)
        predecessors = []
        for src, successors in self.edges.items():
            if subtask_id in successors:
                predecessors.append(src)

        for p in predecessors:
            if self.__get_subtask_status(p) != "Completed":
                return False
        return True

    def all_subtasks_completed(self) -> bool:
        """
        判断是否所有子任务都处于 Completed 状态
        """
        for nid in self.nodes:
            if self.__get_subtask_status(nid) != "Completed":
                return False
        return True

    def get_completed_levels(self) -> int:  # 获取完成状态节点深度
        # 从0层到最大深度，检查每一层是否都已完成
        for level in range(self.depth):
            for node in self.nodes:
                if self.node_depth[node] == level and self.__get_subtask_status(node) != "Completed":
                    return level - 1
        return self.depth

    # 更新节点状态为Completed,并更新后继节点状态
    def update_node_status(self, node_id: str):
        self.subtask_dict[node_id]["status"] = "Completed"
        self.successful_topo.append(node_id)  # 更新已完成的拓扑序列
        print(f"TaskDAG: Node {node_id} completed.")
        # 更新后继节点状态为Evaluating
        successors = self.edges.get(node_id, [])
        for succ_id in successors:
            if self.__all_predecessors_completed(succ_id):
                self.subtask_dict[succ_id]["status"] = "Evaluating"
    def show(self):
        """
        打印任务信息
        - task_id, task_instruction
        - nodes, edges
        - subtasks
        """
        print(f"Task ID: {self.task_id}")
        print(f"Task Instruction: {self.task_data.get('task_instruction', '')}")
        print("Nodes:")
        for node in self.nodes:
            print(f"  - {node}")
        print("Edges:")
        for src, dests in self.edges.items():
            for dest in dests:
                print(f"  - {src} -> {dest}")
        print("Subtasks:")

        # 打印subtask信息 subtask_dict
        for subtask_id, subtask_info in self.subtask_dict.items():
            print(f"  - Subtask ID: {subtask_id}")
            print(f"    - Subtask Instruction: {subtask_info.get('instruction', '')}")


    def __repr__(self) -> str:
        return f"<TaskDAG task_id={self.task_data.get('task_id', '')} nodes={len(self.nodes)}>"
