from typing import Optional, Dict, Any
import base64
import mimetypes
import os

def encode_image_from_path(image_path: str, mime_type: Optional[str] = None) -> str:
    """
    Encode an image file to base64 string.
    :param image_path: The path of the image file.
    :param mime_type: The mime type of the image.
    :return: The base64 string.
    """

    file_name = os.path.basename(image_path)
    mime_type = (
        mime_type if mime_type is not None else mimetypes.guess_type(file_name)[0]
    )
    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("ascii")

    if mime_type is None or not mime_type.startswith("image/"):
        print(
            "Warning: mime_type is not specified or not an image mime type. Defaulting to png."
        )
        mime_type = "image/png"

    image_url = f"data:{mime_type};base64," + encoded_image
    return image_url

def revise_line_breaks(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace '\\n' with '\n' in the arguments.
    :param args: The arguments.
    :return: The arguments with \\n replaced with \n.
    """
    if not args:
        return {}

    # Replace \\n with \\n
    for key in args.keys():
        if isinstance(args[key], str):
            args[key] = args[key].replace("\\n", "\n")

    return args

def get_command_string(command_name: str, params: Dict) -> str:
    """
    Generate a function call string.
    :param command_name: The function name.
    :param params: The arguments as a dictionary.
    :return: The function call string.
    """
    # Format the arguments
    args_str = ", ".join(f"{k}={v!r}" for k, v in params.items())

    # Return the function call string
    return f"{command_name}({args_str})"

def print_response(response_dict: Dict) -> None:
    """
    Print the response.
    :param response: The response dictionary.
    """

    control_text = response_dict.get("ControlText")
    control_label = response_dict.get("ControlLabel")
    if not control_text:
        control_text = "[No control selected.]"
    observation = response_dict.get("Observation")
    thought = response_dict.get("Thought")
    status = response_dict.get("Status")
    function_call = response_dict.get("Function")
    args = revise_line_breaks(response_dict.get("Args"))
    generated_subtask = response_dict.get("GeneratedSubtask")

    # Generate the function call string
    action = get_command_string(function_call, args)

    print("Status📊: {status}".format(status=status))
    print("Observations👀: {observation}".format(observation=observation))
    print("Thoughts💡: {thought}".format(thought=thought))
    print("Selected item🕹️: {control_text}, Label: {label}".format(
        control_text=control_text, label=control_label
    ))
    print("Action applied⚒️: {action}".format(action=action))
    print("Generated Subtask🧩: {generated_subtask}".format(generated_subtask=generated_subtask))