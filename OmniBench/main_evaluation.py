# main_evaluation.py

import uuid
import logging
import json
from typing import List, Dict, Any
from envs.desktop_env import DesktopEnv

from evaluator.TaskDAG import TaskDAG
from evaluator.evaluator import Evaluator, EvaluateResult
from agents.agent import Agent
from config.config import Config
import os
import random

configs = Config.get_instance().config_data

# def init_logging():
#     """
#     初始化日志配置，输出日志到文件和控制台
#     """
#     logging.basicConfig(level=logging.INFO,
#                         format='%(asctime)s [%(levelname)s] %(message)s',
#                         handlers=[
#                             logging.FileHandler("evaluation.log"),
#                             logging.StreamHandler()
#                         ])
#


def load_tasks_from_json(task_dag_dir: str, subtask_eval_func_dir: str,subtask_list )-> List[TaskDAG]:
    """
    从task dag directory中加载所有任务。
    Args:
        task_dag_dir (List[str]): 任务 DAG JSON 文件目录
    Returns:
        List[TaskDAG]: 任务 DAG 列表。
    """
    task_dags = []
    for file_name in os.listdir(task_dag_dir):
        task_dag = TaskDAG(
            task_id=file_name[0:-5],
            json_path=os.path.join(task_dag_dir, file_name),
            subtask_eval_func_dir=subtask_eval_func_dir,
            subtask_list=subtask_list
        )
        task_dags.append(task_dag)
    return task_dags


def main():
    # 加载配置

    # 定义任务 JSON 文件路径列表
    tasks_json_paths = configs["TASK_PATH"]
    subtasks_json_path = configs["SUBTASKS_JSON"]
    subtask_eval_func_dir = configs['SUBTASKS_EVALUATION_PATH']

    with open(subtasks_json_path, 'r', encoding='utf-8') as f:
        subtask_list = json.load(f)
    # 加载所有任务
    tasks = load_tasks_from_json(tasks_json_paths, subtask_eval_func_dir, subtask_list)

    # 初始化评估结果记录
    evaluation_results = {}

    # 随机打乱任务顺序
    # random.shuffle(tasks)

    for task_dag in tasks:
        task_id = task_dag.task_id
        task_log_dir = f"{configs['LOG_ROOT']}/{task_id}"
        # log dir
        if not os.path.exists(task_log_dir):
            os.makedirs(task_log_dir)

        print(f"Evaluating Task ID: {task_id}")
        task_dag.show()

        # 初始化 Agent 实例
        agent_uuid = str(uuid.uuid4())
        related_app = task_dag.task_data.get("related_app",
                                             "File Explorer")  # 从任务信息中获取相关应用,task没有related_app，这里默认为File Explorer
        env = DesktopEnv(
            path_to_vm=configs.get("VM_PATH", ""),  # 虚拟机路径
            # path_to_vm=r"D:/Virtual_Machines/Windows 11 x64_1/Windows 11 x64.vmx",
            observation_space=["Screen_A11Y"],  # ["Screen_A11Y"]
            action_space="pyautogui",
            snapshot_name="init_state",
            headless=True,
            uuid=task_dag.task_id,
            #  本应是subtask_id，但task dag中包含多个subtask，所以这里用task_id
            related_app=task_dag.task_data.get("related_app", "File Explorer")
            # 应该是一个subtask的related_app,但这里是评估task,和Agent统一设成 File Explorer
        )
        agent = Agent(
            uuid=agent_uuid,
            related_app=related_app,
            env=env
        )
        agent.set_task_info(task_instruction=task_dag.task_data.get("task_instruction", ""),task_id=task_id) # 设置task_id用于log


        # 初始化 Evaluator 实例
        evaluator = Evaluator(task_dag=task_dag, configs=configs, env=env)
        while True:
            # 从环境获取观测
            observation = env.get_observation()
            # 调用 Agent 获取动作
            action, status = agent.get_inference_action(observation)
            # 执行动作
            env.execute_action(action)
            env.step += 1
            # 运行评估
            result = evaluator.run_step_evaluation(status)
            if result["outcome"] != "running" or status == "FINISH":
                break

        # 记录评估结果
        evaluation_results[task_id] = {
            "outcome": result["outcome"],
            "score": result["score"],
            "steps_taken": evaluator.step_count
        }
        print(
            f"Task ID: {task_id} - Outcome: {result['outcome']} - Score: {result['score']} - Steps: {evaluator.step_count}")

    # 最终输出所有评估结果
    print("Final Evaluation Results:")
    for task_id, res in evaluation_results.items():
        print(f"Task ID: {task_id}, Outcome: {res['outcome']}, Score: {res['score']}, Steps: {res['steps_taken']}")

    # 评估结果保存到文件
    result_file = "evaluation_results.json"
    with open(result_file, "w", encoding='utf-8') as f:
        json.dump(evaluation_results, f, indent=4)


if __name__ == "__main__":
    main()
