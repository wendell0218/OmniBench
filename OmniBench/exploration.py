import os
import json
import uuid
import argparse
import time as t
from datetime import datetime
import random

from config.config import Config
from agents.agent import Agent
from envs.desktop_env import DesktopEnv
"""
代码逻辑如下：

1. 从 `related_apps` 列表中随机选择一个应用程序。
2. 生成一个唯一的 `id`，并在 `configs["LOG_ROOT"]` 路径下创建一个对应的目录。
3. 初始化 `DesktopEnv` 对象，传入虚拟机路径、观察空间、动作空间、快照名称、是否无头模式、UUID 和相关应用程序。
4. 初始化 `Agent` 对象，传入观察空间、动作空间、UUID 和相关应用程序。
5. 进入一个循环，执行以下步骤：
   - 获取当前的观察结果。
   - 调用 `Agent` 对象的 `get_action` 方法获取动作和状态。
   - 执行获取的动作。
   - 更新步骤计数器。
   - 检查状态是否为 "FINISH" 或步骤计数器是否超过最大步骤数，如果是则跳出循环。
"""

# main function
def main():

    configs = Config.get_instance().config_data

    path = configs["LOG_ROOT"]

    related_apps = ["Cursor","ShareX","Zotero","Evernote","Windows PowerShell ISE"]

    for i in range(1000):
        """
        1. 从related_apps中随机选取一个app
        2. 从configs["LOG_ROOT"]中读取所有已有的trajectory id
        3. 初始化DesktopEnv和Agent
        
        """
        related_app = random.choice(related_apps)
        # related_app = "Windows PowerShell ISE"
        try:
            print(f"trajectory {i+1} / {100} is running...")
            id = str(uuid.uuid4()) # 生成一个唯一的id
            if not os.path.exists(f"{configs['LOG_ROOT']}/{id}"):
                os.makedirs(f"{configs['LOG_ROOT']}/{id}")
            env = DesktopEnv(
                path_to_vm=configs["VM_PATH"],
                observation_space=["Screen_A11Y"], # ["Screen", "A11Y", "Screen_A11Y", "SoM"]
                action_space="pyautogui",
                snapshot_name="init_state",
                headless=True,
                uuid=id,
                related_app=related_app,
            )
            # 等待虚拟机加载完成
            # t.sleep(20)
            agent = Agent(
                observation_space=["Screen_A11Y"],
                action_space="pyautogui",
                uuid=id,
                related_app=related_app,
            )
            # 每次探索前更新一下已有的subtask
            # 探索时提供resource的详细介绍，非必要不要新增resource
            step = 0
            while True:
                # 把第step步的obs存储在本地
                observation = env.get_observation()
                action, status = agent.get_action(observation)
                env.execute_action(action)

                step += 1
                agent.step = step
                env.step = step

                if status == "FINISH" or step > configs["MAX_STEP"]:
                    break
        except Exception as e:
            print(e)

if __name__ == "__main__":
    main()

