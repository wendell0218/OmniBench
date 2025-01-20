import logging
import requests
import json
import os
import subprocess
import time
from typing import Callable, Any, Optional, Tuple
from typing import List, Dict, Union
from config.config import Config

configs = Config.get_instance().config_data

def _execute_command(command: List[str]) -> None:
    def _is_contained_in(a, b):
        for v in set(a):
            if a.count(v) > b.count(v):
                return False
        return True

    # Specially handled for the `vmrun` command in Windows
    if _is_contained_in(["vmrun", "-T", "ws", "start"], command):
        p = subprocess.Popen(command)
        p.wait()
    else:
        result = subprocess.run(command, stdout=subprocess.PIPE, timeout=60, text=True, encoding="utf-8")
        
        return result.stdout
    

class DesktopEnv:
    """
    DesktopEnv with OpenAI Gym interface. It provides a desktop environment for setting and evaluating desktop automation tasks.
    """

    def __init__(
            self,
            path_to_vm: str,
            snapshot_name: str = "init_state",
            observation_space: list[str] = ["Screen_A11Y"],
            action_space: str = "computer_13",
            cache_dir: str = "cache",
            screen_size: Tuple[int] = (1920, 1080),
            headless: bool = False,
            require_a11y_tree: bool = True,
            require_terminal: bool = False,
            uuid: str = "",
            step: int = 0,
            related_app: str = "",
    ):
        # Initialize environment variables
        self.path_to_vm = os.path.abspath(os.path.expandvars(os.path.expanduser(path_to_vm)))
        self.observation_space = observation_space
        self.action_space = action_space
        self.step = step
        self.snapshot_name = snapshot_name
        self.cache_dir_base: str = cache_dir
        self.vm_screen_size = screen_size  # todo: add the logic to get the screen size from the VM
        self.headless = headless
        self.require_a11y_tree = require_a11y_tree
        self.require_terminal = require_terminal        
        self.taskbar_apps = ["File Explorer", "Settings", "Microsoft Store", "Microsoft To Do", "Mail", "Calendar", "People", "Maps", "Sticky Notes", "Media Player", "Photos", "Snipping Tool", "Record Screen - FREE", "Paint", "Microsoft Clipchamp", "Adobe Photoshop Express", "Power Automate", "Calculator", "Recipe Keeper"]
        self.log_path = f"{configs['LOG_ROOT']}/{uuid}/"
        self.related_app = related_app
        _execute_command(["vmrun", "-T", "ws", "-vp", "gdcB/2O3/p2bB4H9V1+n", "revertToSnapshot", self.path_to_vm, self.snapshot_name])
        time.sleep(5)
        self._start_emulator()
        self.vm_ip = self._get_vm_ip()
        if self.step == 0:
            # Initialize the first state.
            if self.related_app not in self.taskbar_apps:
                self.send_python_code_to_server("import pyautogui; screen_width, screen_height = pyautogui.size(); center_x = screen_width // 2; center_y = screen_height // 2; pyautogui.moveTo(center_x, center_y); pyautogui.click()")
 


    def _start_emulator(self):
        while True:
            output = subprocess.check_output("vmrun -T ws list", shell=True, stderr=subprocess.STDOUT)
            output = output.decode()
            output: List[str] = output.splitlines()
            # if self.path_to_vm.lstrip("~/") in output:
            if self.path_to_vm in output:
                break
            else:
                _execute_command(["vmrun", "-T", "ws", "-vp", "gdcB/2O3/p2bB4H9V1+n", "start", self.path_to_vm]) if not self.headless \
                    else _execute_command(["vmrun", "-T", "ws", "-vp", "gdcB/2O3/p2bB4H9V1+n", "start", self.path_to_vm, "nogui"])
                time.sleep(3)

    def _get_vm_ip(self):
        max_retries = 20
        for _ in range(max_retries):
            try:
                output = _execute_command(["vmrun", "-T", "ws", "-vp", "gdcB/2O3/p2bB4H9V1+n", "getGuestIPAddress", self.path_to_vm, "-wait"]).strip()
                return output
            except Exception as e:
                print(e)
                time.sleep(5)
        raise Exception("Failed to get VM IP address!")
    
    def send_python_code_to_server(self, python_code):
        command = f"python -c \"{python_code}\""
        payload = {
            "shell": True,  
            "command": command
        }
        while True:
            try:
                self.IP = self._get_vm_ip()
                response = requests.post(f"http://{self.IP}:5000/execute", json=payload)
                if response.status_code == 200:
                    break
                else:
                    print("status code != 200")
                    print(response.text)
                    time.sleep(5)
            except Exception as e:
                print("exception when execute code...")
                print(e)
                time.sleep(5)

    def capture_screenshot(self) -> None:
        """
        Capture the screenshot.
        """

        # Define the paths for the screenshots saved.
        self.raw_screenshot_save_path = self.log_path + f"action_step{self.step}_raw.png"
        self.annotated_screenshot_save_path = self.log_path + f"action_step{self.step}_annotated.png"
        self.concat_screenshot_save_path = self.log_path + f"action_step{self.step}_concat.png"
        # 如果path 不存在就创建
        if not os.path.exists(self.log_path):
            os.makedirs(self.log_path)

        while True:
            try:
                self.IP = self._get_vm_ip()
                response = requests.get("http://"+self.IP+":5000/get_observation")
                if response.status_code == 200:
                    break
                else:
                    print("status code != 200")
                    print(response.text)
                    time.sleep(5)
            except Exception as e:
                print("exception when get_observation...")
                print(e)
                time.sleep(5)
        while True:
            try:
                self.IP = self._get_vm_ip()
                response = requests.get("http://"+self.IP+":5000/raw_screenshot")
                if response.status_code == 200:
                    with open(self.raw_screenshot_save_path, 'wb') as f:
                        f.write(response.content)
                    break
                else:
                    print("status code != 200")
                    print(response.text)
                    time.sleep(5)
            except Exception as e:
                print("exception when get_raw_screenshot...")
                print(e)
                time.sleep(5)
        while True:
            try:
                self.IP = self._get_vm_ip()
                response = requests.get("http://"+self.IP+":5000/annotated_screenshot")
                if response.status_code == 200:
                    with open(self.annotated_screenshot_save_path, 'wb') as f:
                        f.write(response.content)
                    break
                else:
                    print("status code != 200")
                    print(response.text)
                    time.sleep(5)
            except Exception as e:
                print("exception when get_annotated_screenshot...")
                print(e)
                time.sleep(5)
        while True:
            try:
                self.IP = self._get_vm_ip()
                response = requests.get("http://"+self.IP+":5000/concat_screenshot")
                if response.status_code == 200:
                    with open(self.concat_screenshot_save_path, 'wb') as f:
                        f.write(response.content)
                    break
                else:
                    print("status code != 200")
                    print(response.text)
                    time.sleep(5)
            except Exception as e:
                print("exception when get_concat_screenshot...")
                print(e)
                time.sleep(5)

    def get_controls_info(self) -> None:
        """
        Get the control information.
        """
        # Get the control information for the control items and the filtered control items, in a format of list of dictionaries.
        self.controls_info_save_path = self.log_path + f"action_step{self.step}_controls_info.json"
        while True:
            try:
                self.IP = self._get_vm_ip()
                response = requests.get("http://"+self.IP+":5000/controls_info")
                if response.status_code == 200:
                    with open(self.controls_info_save_path, 'w') as f:
                        json.dump(response.json(), f)
                    break                
                else:
                    print("status code != 200")
                    print(response.text)
                    time.sleep(5)
            except Exception as e:
                print("exception when get_controls_info...")
                print(e)
                time.sleep(5)
        
        # The filtering operation is handled by the server.
        with open(self.controls_info_save_path, 'r') as f:
            controls = json.load(f)
            self.controls_info = []
            for control in controls:
                dic = {}
                dic['label'] = control['id']
                dic['control_text'] = control['title']
                dic['control_type'] = control['control_type']
                dic['parent_control_text'] = control['parent_title']
                dic['parent_control_type'] = control['parent_control_type']
                dic['rect'] = control['rect'] # todo zzk添加新属性 merge
                dic['title'] = control['title']
                self.controls_info.append(dic)
                # 这里是对于第一步选中app的特殊处理
                # if self.round_step == 0 and control['title'] == self.application and control['control_type'] == "Button":
                #     self.label = control['id']
                # elif self.application not in self.taskbar_apps and self.round_step == 0 and control['title'] == self.application and control['control_type'] == "ListItem":
                #     self.label = control['id']

    def get_observation(self) -> dict:
        if self.observation_space == ["Screen_A11Y"]:
            self.capture_screenshot()
            self.get_controls_info()
            return {
                "screen": {
                    "raw_screenshot": self.raw_screenshot_save_path,
                    "annotated_screenshot": self.annotated_screenshot_save_path,
                    "concat_screenshot": self.concat_screenshot_save_path,
                },
                "a11y": self.controls_info
            }

    def capture_control_screenshot(self) -> None:
        """
        Capture the screenshot of the selected control.
        :param control_selected: The selected control item.
        """
        control_screenshot_save_path = (
            self.log_path + f"action_step{self.step}_selected_controls.png"
        )
        while True:
            self.IP = self._get_vm_ip()
            response = requests.get("http://"+self.IP+":5000/action_screenshot")
            if response.status_code == 200:
                with open(control_screenshot_save_path, 'wb') as f:
                    f.write(response.content)
                break
            print("fail to get action screenshot...")
            time.sleep(5)

    def execute_action(self, action: dict) -> None:
        while True:
            try:
                self.IP = self._get_vm_ip()
                payload = json.dumps({"control_label": action['control_label'], "operation": action['operation'], "args": action['args']})
                headers = {
                    'Content-Type': 'application/json'
                }
                # {"control_label": "19", "operation": "click_input", "args": {"button": "left", "double": true}}
                response = requests.post("http://"+self.IP+":5000/execute_action", headers=headers, data=payload, timeout=90)
                if response.status_code == 200:
                    print("\n env execute_action:action executed successfully on "+self.IP+"\n")
                    print(payload)
                    break
                else:
                    print("status code != 200")
                    print(response.text)
                    requests.get("http://"+self.IP+":5000/get_observation")
                    time.sleep(5)
            except Exception as e:
                print(e)
                print("exception when execute_action...")
                time.sleep(5)
        # The process of opening the application may take some time.
        if self.step == 0:
            time.sleep(configs['FIRST_STEP_WAIT_TIME'])
        self.capture_control_screenshot()

        # if "Screen_A11Y" in self.observation_space:
        #     self.send_python_code_to_server(action)
        #     self.capture_control_screenshot()
        # else:
        #     # 这里要么是screen，要么是som、omniparser之类的
        #     # 探索以及生成轨迹时都是Screen_A11Y，所以不用考虑，真正bench时需要考虑一个关键问题
        #     # 评估的时候会参考历史controls轨迹，所以需要统一四种observation的action为controls格式
        #     pass
