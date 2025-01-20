# evaluator/evaluator.py

import os
import time
import uuid
import json
from enum import Enum
from typing import List, Dict, Any, Optional
from envs.desktop_env import DesktopEnv

from config.config import Config
from agents.agent import Agent
from evaluator.TaskDAG import TaskDAG

configs = Config.get_instance().config_data
MAX_STEPS_PER_TASK = configs.get("MAX_STEP", 200)

WAIT_LIMIT = configs.get("WAIT_LIMIT", 20)  # 如果20步之内没有子任务完成，就认为评估该任务执行失败

# WAIT_LIMIT = configs.get("WAIT_LIMIT", 4) # 用于快速测试
class EvaluateResult:
    """
    用于存储评估函数的执行结果。
    """

    def __init__(self, success: bool, message: str):
        self.success = success
        self.message = message


class Evaluator:
    """
    Evaluator 类，用于评估Agent对一个TaskDAG的执行效果。
    """

    def __init__(self, task_dag: TaskDAG, configs: Dict[str, Any], env: DesktopEnv):
        """
        初始化 Evaluator 实例。
        Args:
            task_dag (TaskDAG): 任务DAG对象。
            configs (Dict[str, Any]): 配置信息。
            env (DesktopEnv): DesktopEnv对象。
        """
        self.task_dag = task_dag
        self.env = env
        self.configs = configs
        self.step_count = 0
        self.max_steps = MAX_STEPS_PER_TASK
        self.wait_limit = WAIT_LIMIT
        self.wait_step = 0
        # self.subtask_wait_counts = {sid: 0 for sid in self.task_dag.nodes}  # 用于记录每个子任务的等待步数

    def run_step_evaluation(self, status) -> Dict[str, Any]:
        """
        运行评估循环，直到任务完成或超出步数限制。
        Returns:
            Dict[str, Any]: 包含任务执行状态和评分的结果字典。
        """
        self.step_count += 1
        self.wait_step += 1
        if self.step_count > self.max_steps:
            outcome = "Fail (exceeded max steps)"
            score = self.get_task_score()
            return {"outcome": outcome, "score": score}
        if self.wait_step > self.wait_limit:
            outcome = "Fail (waited too long)"
            score = self.get_task_score()
            return {"outcome": outcome, "score": score}

        # 对处于 Evaluating 状态的子任务进行评估
        for sid, subtask in self.task_dag.subtask_dict.items():
            if subtask["status"] == "Evaluating":
                success, reason = self.__run_evaluation_function(subtask)
                if success:
                    self.task_dag.update_node_status(sid)
                    self.wait_step = 0
                else:
                    pass

        # 检查 Agent 的状态是否为 FINISH
        if status == "FINISH":
            if self.task_dag.all_subtasks_completed():
                outcome = "Success"
            else:
                outcome = "Fail (Agent finished before completing all subtasks)"
            score = self.get_task_score()
            return {"outcome": outcome, "score": score}

        # 暂停一段时间以避免过快循环
        time.sleep(0.1)
        return {"outcome": "running", "score": ""}

    def __run_evaluation_function(self, subtask: Dict[str, Any]) -> (bool, str):
        """
        动态执行子任务的评估函数，并返回结果。
        Args:
            subtask (Dict[str, Any]): 子任务的字典对象，包含 'eval_func_code' 和 'parameters'。
        Returns:
            (bool, str): 成功标志和原因消息。
        """
        # 获取评估函数代码
        # # 若subtask的评估函数单独存储在"subtask_id/eval_function.txt"文件中
        # eval_func_path = os.path.join(self.configs["LOG_ROOT"], subtask["id"], "eval_function.txt")
        # if not os.path.exists(eval_func_path):
        #     return False, "Evaluation function file not found."
        # with open(eval_func_path, "r", encoding="utf-8") as f:
        #     eval_func_code = f.read()

        # 若subtask的评估函数直接存储在subtask字典中
        eval_func_code = subtask.get("eval_func_code", "")

        parameters = subtask.get("available_parameters", {})
        namespace = globals().copy()
        # exec部分仅仅是在namespace空间中放入函数代码，完成了函数的声明定义。
        # func实际上是返回了一个定义好的函数，
        # result = func(**parameters)才真正执行该函数
        try:
            exec(eval_func_code, namespace, namespace)  # 将eval_func_code字符串作为代码执行,声明了一个evaluate_agent_task_completion函数
            # 评估函数约定名称：evaluate_agent_task_completion
            func = namespace.get("evaluate_agent_task_completion")
            if func is None:
                return False, "No evaluation function found."
            result = func(**parameters)  # 调用evaluate_agent_task_completion函数
            if not isinstance(result, EvaluateResult):
                return False, "Invalid evaluation function return type."
            return result.success, result.message
        except Exception as e:
            return False, f"Error in evaluation function: {str(e)}"

    def __get_completion_score(self) -> float:
        """
        计算任务完成度得分:完成部分的DAG的层数占总层数的比例
        Returns:
            float: 任务完成度得分
        """
        completed_levels = self.task_dag.get_completed_levels()
        if self.task_dag.depth == 0:
            return 0.0
        print(f"completed_levels: {completed_levels};total_levels: {self.task_dag.depth}")
        return completed_levels / self.task_dag.depth

    def __get_max_same_app_seq_len(self, subtask_id_list) -> int:
        """
        计算序列中最大相同related_app的subtask序列长度
        Args:
            subtask_id_list (List[str]): 子任务ID序列
        Returns:
            int: 最大相同related_app的子任务序列长度。
        """
        max_len = 0
        cur_len = 1
        for i in range(1, len(subtask_id_list)):
            subtask = self.task_dag.subtask_dict[subtask_id_list[i]]
            prev_subtask = self.task_dag.subtask_dict[subtask_id_list[i - 1]]
            if subtask["application"] == prev_subtask["application"]:
                cur_len += 1
            else:
                max_len = max(max_len, cur_len)
                cur_len = 1
        max_len = max(max_len, cur_len)
        return max_len

    def __get_coherence_score(self) -> float:
        all_topo_seq = self.task_dag.get_all_topo()
        exec_seq = self.task_dag.successful_topo

        # 计算执行序列的最大相同related_app序列长度
        exec_max_len = self.__get_max_same_app_seq_len(exec_seq)

        # 计算所有可能的拓扑序列的最大相同related_app序列长度
        topo_max_len = max(
            self.__get_max_same_app_seq_len(topo_seq) for topo_seq in all_topo_seq
        ) if all_topo_seq else 1

        return (exec_max_len - 1) / (topo_max_len - 1) if topo_max_len > 1 else 0.0

    def get_task_score(self) -> dict[str, float]:
        """
        对任务执行情况进行打分，基于两个指标：
        1.Completion: 完成部分的DAG的层数占总层数的比例
        2.coherence:执行的subtask序列中，subtask.related_app的连贯性，即当前序列最大相同related_app的subtask序列长度/所有可能的topo序列中最大相同related_app的subtask序列长度
        Returns:
            dict: 包含两个指标的得分
        """
        # Completion score
        completion_score = self.__get_completion_score()
        print(f"completion_score: {completion_score}")
        # Coherence score
        coherence_score = self.__get_coherence_score()
        print(f"coherence_score: {coherence_score}")
        return {"completion": completion_score, "coherence": coherence_score}
