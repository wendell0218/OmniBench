import json
import os
import time
from typing import Tuple, Dict, Union, Any
import re
from envs.desktop_env import DesktopEnv

import openai
import yaml
from openai import OpenAI

from config.config import Config
# from ant_api.utils import (
#     get_default_config,
#     ask_chatgpt
# )
from utils import encode_image_from_path
from utils import revise_line_breaks
from utils import get_command_string
from utils import print_response

configs = Config.get_instance().config_data  # Load the configuration data


def get_llm_response(prompt_message: list[dict]) -> dict:
    """
    Get the response from the LLM based on the prompt message.
    Args:
        prompt_message (list[dict]): The prompt message to send to the LLM.
    Returns:
        dict: The response from the LLM.
    """
    # 保存prompt_message到文件，file name: prompt_message+timestamp.json
    # file_name = "prompt_message" + str(int(time.time())) + ".json"
    # with open(file_name, 'w') as f:
    #     f.write(json.dumps(prompt_message))
    try:
        # 1. Ant API
        # param = get_default_config(model="gpt-4o")
        # param["queryConditions"]["model"] = "gpt-4o"
        # param["queryConditions"]["temperature"] = "0.6"
        # param["queryConditions"]["messages"] = prompt_message
        # response = ask_chatgpt(param)

        # # 2. openai API Qwen/Qwen2-VL-7B-Instruct
        # qwenvl7b_instruct_config = configs["QWEN2_VL_7B_INSTRUCT"]
        # client = OpenAI(
        #     api_key="EMPTY",
        #     base_url=qwenvl7b_instruct_config["OPEN_API_BASE"]  # Todo:配置文件merge
        # )
        # print("calling openai API:"+qwenvl7b_instruct_config["OPEN_API_BASE"]+"model:"+qwenvl7b_instruct_config["MODEL_NAME"])
        #
        # raw_response = client.chat.completions.create(
        #     model=qwenvl7b_instruct_config["MODEL_NAME"],
        #     messages=prompt_message,
        #     temperature=0.6,
        # )
        # response = raw_response.choices[0].message.content
        # print("response from "+qwenvl7b_instruct_config["MODEL_NAME"]+":"+response)

        # 3. openai API qwen-vl-max
        qwen_vl_config = configs["QWEN_VL_MAX"]
        client = OpenAI(
            api_key=qwen_vl_config["API_KEY"],
            base_url=qwen_vl_config["OPEN_API_BASE"]
        )
        print("calling openai API:"+qwen_vl_config["OPEN_API_BASE"]+"model:"+qwen_vl_config["MODEL_NAME"])
        raw_response = client.chat.completions.create(
            model=qwen_vl_config["MODEL_NAME"],
            messages=prompt_message,
            temperature=0.6,
        )
        response = raw_response.choices[0].message.content
        print("response from "+qwen_vl_config["MODEL_NAME"]+":"+response)

        # 4. OS-Atlas-Pro-7B
        # os_atlas_pro_7b_config = configs["OS_ATLAS_PRO_7B"]
        # client = OpenAI(
        #     api_key="EMPTY",
        #     base_url=os_atlas_pro_7b_config["OPEN_API_BASE"]
        # )
        # print("calling openai API:"+os_atlas_pro_7b_config["OPEN_API_BASE"]+"model:"+os_atlas_pro_7b_config["MODEL_NAME"])
        # raw_response = client.chat.completions.create(
        #     model=os_atlas_pro_7b_config["MODEL_NAME"],
        #     messages=prompt_message,
        #     temperature=0.6,
        # )
        # response = raw_response.choices[0].message.content
        # print("response from "+os_atlas_pro_7b_config["MODEL_NAME"]+":"+response)

    except Exception as e:
        print("LLM encountered an error while generating a response...")
        raise e

    return response


def extract_response(response) -> dict:
    _response_json = {}
    try:
        if response[0] == '`':  # Remove the extra characters ```json and ```?
            response = response[7:-3]
        _response_json = json.loads(response)
        assert _response_json != None
        assert _response_json.get("Function", "") in ["click_input", "keyboard_input", "wheel_mouse_input", ""]
        assert _response_json.get("Status", "") in ["CONTINUE", "FINISH"]
    except Exception as e:
        print("LLM encountered an error while parsing a response...")
        raise e
    return _response_json

def find_controls_by_coordinate(coordinate, controls_info):
    """
    根据给定的point坐标在屏幕上查找对应的控件。
    参数:
    coordinate (tuple): 目标点的坐标 (x, y)
    controls_info (list): 包含所有控件信息的列表，每个控件信息包含 id, title 和 rect 等字段
    返回: 与该点重叠的控件信息，若有多个则返回面积最小且title不为空的控件
    """

    rect_pattern = r"\(L(\d+), T(\d+), R(\d+), B(\d+)\)"
    # 筛选其中面积最小且title不为空的控件
    min_area = float("inf")
    target_control = None
    for control in controls_info:
        rect_str = control.get("rect", "")
        match = re.match(rect_pattern, rect_str)

        if match:
            left, top, right, bottom = map(int, match.groups())
            x, y = coordinate
            if left <= x <= right and top <= y <= bottom:
                area = (right - left) * (bottom - top)
                if area < min_area and control.get("title", ""):
                    min_area = area
                    target_control = control

    return target_control

def parse_response_json(response_json: dict, observation: dict) -> dict:
    """
    解析response json,将其中仅有coordinates键值没有ControlLabel,ControlText的键值的对象 用ControlLabel,ControlText替换
    """
    coordinate = response_json.get("coordinates", [])
    # 将coordinates 从原本的1000*1000坐标系转换为实际屏幕坐标系 1920*1080
    # coordinate = (int(coordinate[0] * 1920 / 1000), int(coordinate[1] * 1080 / 1000))

    control_info =observation["a11y"]
    control = find_controls_by_coordinate(coordinate, control_info)
    if control:
        response_json["ControlLabel"] = control.get("label", "")
        response_json["ControlText"] = control.get("title", "")
    else:
        response_json["ControlLabel"] = ""
        response_json["ControlText"] = ""
        print("No control found at the given coordinate.")

    return response_json




class Agent:
    def __init__(
            self,
            observation_space: list[str] = ["Screen_A11Y"],
            action_space: str = "pyautogui",
            uuid: str = "",
            step: int = 0,
            related_app: str = "",
            stage: str = "exploration",
            env: DesktopEnv = None,
    ) -> None:
        # Initialize the agent with the observation and action spaces.
        self.observation_space = observation_space
        self.action_space = action_space
        self.uuid = uuid
        self.step = step
        self.label =None
        self.task_id = None
        self.action_history = [] # 保存每一步的action
        self.env = env
        self.log_path = f"{configs['LOG_ROOT']}/{uuid}/"
        # 仅探索时有用，将以后的subtask传进去，避免重复
        self.existing_subtasks = []
        self.stage = stage
        self.task_info = None  # 评估阶段需要的 task信息
        self.related_app = related_app  # Not needed during inference
        self.taskbar_apps = ["File Explorer", "Settings", "Microsoft Store", "Microsoft To Do", "Mail", "Calendar",
                             "People", "Maps", "Sticky Notes", "Media Player", "Photos", "Snipping Tool",
                             "Record Screen - FREE", "Paint", "Microsoft Clipchamp", "Adobe Photoshop Express",
                             "Power Automate", "Calculator", "Recipe Keeper"]
    def set_task_info(self, task_instruction, task_id):
        self.task_info = task_instruction
        self.task_id = task_id
        self.log_path = f"{configs['LOG_ROOT']}/{task_id}/{self.uuid}/"

    def get_prompt_message(self, observation: dict) -> list[dict]:
        """
        Get the prompt message for the agent by loading prompt templates, API documentation, and examples.
        Stage: Exploration
        Returns:
            list[dict]: A list of dictionaries containing the system and user prompts with:
                - API documentation for available actions
                - Example interactions and responses
                - Formatted templates for consistent prompting
        """
        if self.observation_space == ["Screen_A11Y"]:
            # 加载prompt模板
            path = configs["PROMPT_PATH"]
            if os.path.exists(path):
                prompt = yaml.safe_load(open(path, "r", encoding="utf-8"))
            else:
                raise FileNotFoundError(f"Prompt template not found at {path}")

            # Load API template and construct API list 包含api的summary和usage
            api_prompt_template = yaml.safe_load(open(configs["API_PATH"], "r", encoding="utf-8"))
            api_list = [
                "- The action types for UI elements are: {actions}.".format(
                    actions=list(api_prompt_template.keys())
                )
            ]

            for key in api_prompt_template.keys():
                api = api_prompt_template[key]
                api_text = "{summary}\n{usage}".format(
                    summary=api["summary"], usage=api["usage"]
                )
                api_list.append(api_text)

            # Load example template and construct example list
            example_prompt_template = yaml.safe_load(open(configs["EXAMPLE_PATH"], "r", encoding="utf-8"))
            template = """
            [User Request]:
                {request}
            [Response]:
                {response}"""

            example_list = []
            for key in example_prompt_template.keys():
                if key.startswith("example"):
                    example = template.format(
                        request=example_prompt_template[key].get("Request"),
                        response=json.dumps(
                            example_prompt_template[key].get("Response")
                        ),
                    )
                    example_list.append(example)
            example_list += [json.dumps(example)]

            # Construct system and user content
            system_content = prompt['system'].format(
                apis=api_list,
                examples=example_list,
            )

            user_content = []
            if self.observation_space == ["Screen_A11Y"]:
                if configs["INCLUDE_LAST_SCREENSHOT"] and self.step > 0:
                    user_content.append({"type": "text",
                                         "text": "Screenshot for the last step, the red box annotated the control selected in the previous step:"})
                    user_content.append({"type": "image_url", "image_url": {
                        "url": encode_image_from_path(observation["screen"]["annotated_screenshot"])}})
                if configs["CONCAT_SCREENSHOT"]:
                    user_content.append(
                        {"type": "text", "text": "Current Screenshot(left) and Annotated Screenshot(right):"})
                    user_content.append({"type": "image_url", "image_url": {
                        "url": encode_image_from_path(observation["screen"]["concat_screenshot"])}})
                else:
                    user_content.append({"type": "text", "text": "Current Screenshots:"})
                    user_content.append({"type": "image_url", "image_url": {
                        "url": encode_image_from_path(observation["screen"]["raw_screenshot"])}})
                    user_content.append({"type": "text", "text": "Annotated Screenshot:"})
                    user_content.append({"type": "image_url", "image_url": {
                        "url": encode_image_from_path(observation["screen"]["annotated_screenshot"])}})
            subtasks_path = os.path.join(configs["LOG_ROOT"], f"{self.related_app}_subtasks.json")
            if not os.path.exists(subtasks_path):
                with open(subtasks_path, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False)
            with open(subtasks_path, 'r', encoding='utf-8') as f:
                dic = json.load(f)
            existing_subtasks = dic
            if os.path.exists(os.path.join(configs["DOCUMENT_PATH"], f"{self.related_app}.md")):
                document = open(os.path.join(configs["DOCUMENT_PATH"], f"{self.related_app}.md"), 'r',
                                encoding='utf-8').read()
            else:
                document = ""
            user_content.append(
                {
                    "type": "text",
                    "text": prompt['user'].format(
                        control_item=observation['a11y'],
                        action_history=self.action_history,
                        related_app=self.related_app,
                        document=document,
                        existing_subtasks=existing_subtasks,
                    ),
                }
            )

            prompt_message = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ]
            prompt = json.dumps(
                {
                    "step": self.step,
                    "prompt": prompt_message,
                }
            )
            prompt_path = self.log_path + f"action_step{self.step}_prompt.json"
            with open(prompt_path, 'w') as f:
                f.write(prompt)

            # 把第一步的label提取出来，为了get_response时第一步选app时使用
            for control in observation['a11y']: # todo:运行时偶尔会出现:'Agent' object has no attribute 'label'
                if self.step == 0 and control['control_text'] == self.related_app and control[
                    'control_type'] == "Button":
                    self.label = control['label']
                elif self.related_app not in self.taskbar_apps and self.step == 0 and control[
                    'control_text'] == self.related_app and control['control_type'] == "ListItem":
                    self.label = control['label']
            return prompt_message

    def get_response(self, prompt_message: list[dict]):
        """
        Get the response from the agent based on the prompt message.
        Stage: Exploration
        """
        # 对于第一步选择app的特殊处理
        # 这里不请求API，直接返回第一步的response，因为任务栏和桌面的app的controls是分别获取的
        response_json = {}
        if self.step == 0:
            if self.related_app in self.taskbar_apps:
                response_json = {
                    "Status": "CONTINUE",
                    "Observation": "There are many application icons on the taskbar, and I need to select the correct application to complete the task.",
                    "Thought": "To design subtasks, I need to first click the '{application}' button to open the corresponding application and explore the environment.".format(
                        application=self.related_app),
                    "ControlLabel": "{label}".format(label=self.label),
                    "ControlText": "{application}".format(application=self.related_app),
                    "Function": "click_input",
                    "Args": {"button": "left", "double": False},
                    "GeneratedSubtask": {}
                }
            else:
                response_json = {
                    "Status": "CONTINUE",
                    "Observation": "There are many application icons on the desktop, and I need to select the correct application to complete the task.",
                    "Thought": "To design subtasks, I need to first double click the '{application}' desktop icon to open the corresponding application and explore the environment.".format(
                        application=self.related_app),
                    "ControlLabel": "{label}".format(label=self.label),
                    "ControlText": "{application}".format(application=self.related_app),
                    "Function": "click_input",
                    "Args": {"button": "left", "double": True},
                    "GeneratedSubtask": {}
                }
        else:
            for i in range(configs["RETRY_TIMES"]):
                try:
                    response = get_llm_response(prompt_message)
                    response_json = extract_response(response)
                except Exception as e:
                    print(e)
                    print("Retrying...")
                    time.sleep(5)
                else:
                    break

        # 格式化response 并保存到文件
        response = json.dumps({
            "step": self.step,
            "response": response_json,
        }
        )
        response_path = self.log_path + f"action_step{self.step}_response.json"
        with open(response_path, 'w') as f:
            f.write(response)

        control_label = response_json.get("ControlLabel", "")
        control_text = response_json.get("ControlText", "")
        operation = response_json.get("Function", "")
        args = revise_line_breaks(response_json.get("Args", ""))
        status = response_json.get("Status", "")
        generated_subtask = response_json.get("GeneratedSubtask", {})
        if generated_subtask != {}:  # 如果该步骤生成子任务
            """
            如果该step生成了subtask，则与已有subtasks比较，如果相似度高则不添加
            similarity metrics: word overlap, length ratio, sequential word matching
            """
            subtasks_path = os.path.join(configs["LOG_ROOT"], f"{self.related_app}_subtasks.json")
            with open(subtasks_path, 'r', encoding='utf-8') as f:
                existing_subtasks = json.load(f)

            # Calculate similarity with existing subtasks
            should_add = True
            for existing in existing_subtasks:
                # Calculate multiple similarity metrics
                # 1. Word overlap similarity
                existing_words = set(existing["instruction_template"].lower().split())
                new_words = set(generated_subtask["instruction_template"].lower().split())
                common_words = existing_words.intersection(new_words)
                jaccard_sim = len(common_words) / len(existing_words.union(new_words))

                # 2. Length ratio similarity
                len_ratio = min(len(existing_words), len(new_words)) / max(len(existing_words), len(new_words))

                # 3. Sequential word matching
                existing_seq = existing["instruction_template"].lower().split()
                new_seq = generated_subtask["instruction_template"].lower().split()
                seq_matches = sum(1 for i in range(min(len(existing_seq), len(new_seq)))
                                  if existing_seq[i] == new_seq[i])
                seq_sim = seq_matches / min(len(existing_seq), len(new_seq))

                # Combined similarity score with weights
                similarity = (0.5 * jaccard_sim + 0.3 * len_ratio + 0.2 * seq_sim)

                # More strict threshold and additional conditions
                if (similarity > 0.6 or  # Lower threshold but multiple metrics
                        jaccard_sim > 0.7 or  # High word overlap
                        seq_sim > 0.8):  # High sequential match
                    should_add = False
                    break

            if should_add:  # Add the subtask to the list
                generated_subtask["path"] = self.log_path
                generated_subtask["related_app"] = self.related_app
                generated_subtask["id"] = self.uuid
                existing_subtasks.append(generated_subtask)
                with open(subtasks_path, 'w', encoding='utf-8') as f:
                    json.dump(existing_subtasks, f, ensure_ascii=False)
        # Compose the function call and the arguments string.
        action = {
            "control_label": control_label,
            "operation": operation,
            "args": args,
        }
        print_response(response_json)
        # save the action history{control_text, action}
        self.action_history.append({"control_text": control_text, "action": get_command_string(operation, args)})

        return action, status

    def __get_inference_coordinate_prompt_message(self, observation)->list[dict]:
        """
        evaluation阶段，根据task_info, observation, history 生成Agent的 prompt_message
        user: |-
          <Task Instruction:>{task_instruction}
          <observation:>{observation}
          <Your response:>
        """
        example = {
            "Status": "CONTINUE",
            "Observation": "The user is currently on the desktop with no open applications or documents.",
            "Thought": "The first step is to open the file 'C:\\Users\\user\\Desktop\\office\\invitation letter.pptx' using the 'open_file' function from pywinauto.",
            "coordinates": (150, 150),
            "Function": "click_input",
            "Args": {
                "button": "left",
                "double": True
              },
        }

        # 使用 json.dumps() 格式化 JSON 字符串
        formatted_example = json.dumps(example, indent=4)
        path = configs["INFERENCE_PROMPT_PATH"]
        if os.path.exists(path):
            prompt_tem = yaml.safe_load(open(path, "r", encoding="utf-8"))
        else:
            raise FileNotFoundError(f"Prompt template not found at {path}")

        # Load API template and construct API list 包含api的summary和usage
        api_prompt_template = yaml.safe_load(open(configs["API_PATH"], "r", encoding="utf-8"))
        api_list = [
            "- The action types for UI elements are: {actions}.".format(
                actions=list(api_prompt_template.keys())
            )
        ]

        for key in api_prompt_template.keys():
            api = api_prompt_template[key]
            api_text = "{summary}\n{usage}".format(
                summary=api["summary"], usage=api["usage"]
            )
            api_list.append(api_text)
        system_prompt = prompt_tem['system'].format(
            apis=api_list
        )

        # #将system_content转为字符串
        # system_prompt = json.dumps(system_prompt)

        # 生成用户内容
        user_content = []
        if self.observation_space == ["Screen_A11Y"]:
            if configs["INCLUDE_LAST_SCREENSHOT"] and self.step > 0:
                user_content.append({"type": "text",
                                     "text": "Screenshot for the last step, the red box annotated the control selected in the previous step:"})
                user_content.append({"type": "image_url", "image_url": {
                    "url": encode_image_from_path(observation["screen"]["annotated_screenshot"])}})
            if configs["CONCAT_SCREENSHOT"]:
                user_content.append(
                    {"type": "text", "text": "Current Screenshot(left) and Annotated Screenshot(right):"})
                user_content.append({"type": "image_url", "image_url": {
                    "url": encode_image_from_path(observation["screen"]["concat_screenshot"])}})
            else:
                user_content.append({"type": "text", "text": "Current Screenshots:"})
                user_content.append({"type": "image_url", "image_url": {
                    "url": encode_image_from_path(observation["screen"]["raw_screenshot"])}})
                user_content.append({"type": "text", "text": "Annotated Screenshot:"})
                user_content.append({"type": "image_url", "image_url": {
                    "url": encode_image_from_path(observation["screen"]["annotated_screenshot"])}})
        user_content.append(
            {
                "type": "text",
                "text": prompt_tem['user'].format(
                    task_instruction=self.task_info,
                    action_history=self.action_history,
                ),
            }
        )
        user_content.append({
            "type": "text",
            "text": f"example: {formatted_example}"
        })
        prompt_message = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        prompt = json.dumps(
            {
                "step": self.step,
                "prompt": prompt_message,
            }
        )
        prompt_path = self.log_path + f"action_step{self.step}_prompt.json"
        if not os.path.exists(self.log_path):
            os.makedirs(self.log_path)
        with open(prompt_path, 'w') as f:
            f.write(prompt)

        return prompt_message

    # 由于控件信息需要分别从屏幕和任务栏获取，需要点击任务栏才能获取任务栏control信息

    # 切换所在的屏幕区域 桌面/任务栏
    def __switch_screen_area(self, screen_area: str):# todo 完成该函数
        if self.env is None:
            raise ValueError("The agent environment is not set.")
        if screen_area == "Desktop":
            self.env.send_python_code_to_server("import pyautogui; screen_width, screen_height = pyautogui.size(); center_x = screen_width // 2; center_y = screen_height // 2; pyautogui.moveTo(center_x, center_y); pyautogui.click()")

        elif screen_area == "Taskbar":
            self.env.send_python_code_to_server("import pyautogui; screen_width, screen_height = pyautogui.size();  pyautogui.moveTo(1490, screen_height-20); pyautogui.click()")
        else:
            raise ValueError(f"Invalid screen area: {screen_area}")
    def __generate_control_info_first_step(self, observation_Desktop: dict, observation_Taskbar: dict):

        # 拼接两者的control_info,其为dict list,合并两个json list
        control_info = observation_Desktop["a11y"]
        control_info.extend(observation_Taskbar["a11y"])


        # 遍历并顺序分配新的id，避免重复，并建立原始id和新id的映射
        control_info_new = []
        id_map = {}
        initial_id = 1
        for control in control_info:
            raw_id = control["label"]
            control["label"] = initial_id
            id_map[raw_id] = initial_id
            control_info_new.append(control)
            initial_id += 1
        return control_info_new, id_map



    def __get_inference_control_prompt_message(self, observation: dict):
        """
         evaluation阶段，根据task_info, observation, history 生成Agent的 prompt_message
         user: |-
           <Task Instruction:>{task_instruction}
           <observation:>{observation}
           <Your response:>
         """
        example = {
            "Status": "CONTINUE",
            "Observation": "The screenshot shows that I am on the Main Page of Outlook. The Main Page has a list of control items and email received. The new email editing window is not opened. The last action took effect by opening the Outlook application.",
            "Thought": "Based on the screenshots and the control item list, I need to click the New Email button to open a New Email window for the one-step action.",
            "ControlLabel": "1",
            "ControlText": "New Email",
            "Function": "click_input",
            "Args": {
                "button": "left",
                "double": True
            }
        }


        # 使用 json.dumps() 格式化 JSON 字符串
        formatted_example = json.dumps(example, indent=4)
        path = configs["INFERENCE_PROMPT_CONTROL_PATH"]
        if os.path.exists(path):
            prompt_tem = yaml.safe_load(open(path, "r", encoding="utf-8"))
        else:
            raise FileNotFoundError(f"Prompt template not found at {path}")

        # Load API template and construct API list 包含api的summary和usage
        api_prompt_template = yaml.safe_load(open(configs["API_PATH"], "r", encoding="utf-8"))
        api_list = [
            "- The action types for UI elements are: {actions}.".format(
                actions=list(api_prompt_template.keys())
            )
        ]

        for key in api_prompt_template.keys():
            api = api_prompt_template[key]
            api_text = "{summary}\n{usage}".format(
                summary=api["summary"], usage=api["usage"]
            )
            api_list.append(api_text)
        system_prompt = prompt_tem['system'].format(
            apis=api_list
        )

        # #将system_content转为字符串
        # system_prompt = json.dumps(system_prompt)
        # 由于控件信息需要分别从屏幕和任务栏获取，需要点击任务栏才能获取任务栏control信息
        if self.step == 0:
            if self.env is None:
                raise ValueError("The agent environment is not set.")
            # 先点击Desktop，获取Desktopcontrol信息
            self.__switch_screen_area("Desktop")
            self.observation_Desktop = self.env.get_observation()

            # 再点击Taskbar，获取Taskbarcontrol信息
            self.__switch_screen_area("Taskbar")
            self.observation_Taskbar = self.env.get_observation() #临时保存

            control_info, self.id_map = self.__generate_control_info_first_step(self.observation_Desktop,self.observation_Taskbar)
            observation = self.observation_Desktop #用desktop的图片
        else:
            control_info=observation["a11y"]


        # 生成用户内容
        user_content = []
        if self.observation_space == ["Screen_A11Y"]:
            if configs["INCLUDE_LAST_SCREENSHOT"] and self.step > 0:
                user_content.append({"type": "text",
                                     "text": "Screenshot for the last step, the red box annotated the control selected in the previous step:"})
                user_content.append({"type": "image_url", "image_url": {
                    "url": encode_image_from_path(observation["screen"]["annotated_screenshot"])}})
            if configs["CONCAT_SCREENSHOT"]:
                user_content.append(
                    {"type": "text", "text": "Current Screenshot(left) and Annotated Screenshot(right):"})
                user_content.append({"type": "image_url", "image_url": {
                    "url": encode_image_from_path(observation["screen"]["concat_screenshot"])}})
            else:
                user_content.append({"type": "text", "text": "Current Screenshots:"})
                user_content.append({"type": "image_url", "image_url": {
                    "url": encode_image_from_path(observation["screen"]["raw_screenshot"])}})
                user_content.append({"type": "text", "text": "Annotated Screenshot:"})
                user_content.append({"type": "image_url", "image_url": {
                    "url": encode_image_from_path(observation["screen"]["annotated_screenshot"])}})
        user_content.append(
            {
                "type": "text",
                "text": prompt_tem['user'].format(
                    task_instruction=self.task_info,
                    control_item=control_info,
                    action_history=self.action_history,
                ),
            }
        )
        user_content.append({
            "type": "text",
            "text": f"example: {formatted_example}"
        })
        prompt_message = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        prompt = json.dumps(
            {
                "step": self.step,
                "prompt": prompt_message,
            }
        )
        prompt_path = self.log_path + f"action_step{self.step}_prompt.json"
        if not os.path.exists(self.log_path):
            os.makedirs(self.log_path)
        with open(prompt_path, 'w') as f:
            f.write(prompt)

        return prompt_message

    def __get_inference_response(self, prompt_message: list[dict], observation: dict):
        """
        Get the response from the agent based on the prompt message.
        Stage: Evaluation
        Returns:
            Tuple[Dict[str, Any], str]: The action and the status of the agent.
            - action template: {"control_label": "", "operation": "", "args": ""}
        """
        response_json = {}
        for i in range(configs["RETRY_TIMES"]):
            try:
                response = get_llm_response(prompt_message)
                response_json = extract_response(response)
                if "ControlLabel" not in response_json and "ControlText" not in response_json:
                    response_json = parse_response_json(response_json, observation)
            except Exception as e:
                print(e)
                print("Retrying...")
                time.sleep(5)
            else:
                break

        # 格式化response 并保存到文件
        response = json.dumps({
            "step": self.step,
            "response": response_json,
        })

        response_path = self.log_path + f"action_step{self.step}_response.json"
        with open(response_path, 'w') as f:
            f.write(response)

        control_label = response_json.get("ControlLabel", "")
        control_text = response_json.get("ControlText", "")
        operation = response_json.get("Function", "")
        args = revise_line_breaks(response_json.get("Args", ""))
        status = response_json.get("Status", "")
        # 对于第一步选择app的特殊处理,根据control_text获得control_label
        if self.step == 0:
            # 根据control_text找到看control是在desktop还是taskbar
            control_type = None
            for control in self.observation_Desktop["a11y"]:
                if control["control_text"] == control_text:
                    control_type = "Desktop"
                    break
            for control in self.observation_Taskbar["a11y"]:
                if control["control_text"] == control_text:
                    control_type = "Taskbar"
                    break
            self.__switch_screen_area(control_type)
            # 重新获取观察 每次分配的label都不一样
            observation = self.env.get_observation()
            for control in observation["a11y"]:
                if control["control_text"] == control_text:
                    control_label = control["label"]
                    break


        # Compose the function call and the arguments string.
        action = {
            "control_label": control_label,
            "operation": operation,
            "args": args,
        }
        print_response(response_json)
        # save the action history{control_text, action}
        self.action_history.append({"control_text": control_text, "action": get_command_string(operation, args)})

        return action, status

    def get_action(self, observation: dict):
        """
        Get the action from the agent based on the observation.
        """

        prompt_message = self.get_prompt_message(observation)
        action, status = self.get_response(prompt_message)
        self.step += 1
        return action, status

    def get_inference_action(self, observation: dict):
        """
        Get the action from the agent based on the observation.
        """
        if self.task_info is None:
            print("Task information not found.")
            return None, "Fail (Task information not found)"

        # prompt_message = self.__get_inference_coordinate_prompt_message(observation) # 使用坐标
        prompt_message = self.__get_inference_control_prompt_message(observation)  # 使用控件
        action, status = self.__get_inference_response(prompt_message, observation)
        self.step += 1
        return action, status