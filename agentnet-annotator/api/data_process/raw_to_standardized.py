import argparse
import json
import os
from pathlib import Path

import orjson as oj
from tqdm import tqdm

from data_process.schema.action import (
    GUIAction,
    GUIActionType,
    PyAutoGUIAction,
    ComputerAction,
    triple_click_func,
    terminate_func,
)
from data_process.schema.action import ImageObservation, TextObservation
from data_process.schema.trajectory import Trajectory

# Copied from core.action_reduction.reduction_helper to avoid circular import dependencies
# These are the authoritative key definitions used during recording
# KEEP IN SYNC with core/action_reduction/reduction_helper.py
MODIFIED_KEYS = {"alt", "alt_l", "alt_r", "alt_gr",'altleft', 'altright',
                 "ctrl", "ctrl_l", "ctrl_r",'ctrlleft', 'ctrlright',
                 "shift", "shift_l", "shift_r", 'shiftleft', 'shiftright',
                 "cmd", "cmd_l", "cmd_r", 'command', 
                 'fn', 'windows', 'win', 'winleft', 'winright', 'super', 'meta'}

FUNCTIONAL_KEYS = {
    'tab', 'space', 'enter', 'return', 'esc', 'escape', 'backspace','up', 'down', 'left', 'right', 
    'caps', 'capslock', 'caps_lock', 'num_lock', 'numlock', 'clear', 'convert',  'decimal', 'del', 'delete', 'divide',  'end',
    'insert', 'pagedown', 'pageup', 'pause', 'pgdn', 'pgup', 'print_screen', 'power', 'numpad_lock', 'scroll', 'scrolllock', 'scroll_lock',
    'accept', 'add',  'apps', 'execute', 'playpause', 'prevtrack', 'print', 'printscreen', 'prntscrn',
    'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9','f10', 'f11', 'f12', 'f13', 
    'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24', 
    'browserstop', 'browserforward', 'browserhome', 'browserrefresh', 'browsersearch', 'browserback', 'browserfavorites', 
    'web', 'mail', 'calculator', 'computer', 'search', 'favorites',
    'media_play_pause', 'media_volume_mute', 'media_volume_down', 'media_volume_up', 'media_next', 'media_previous',
    'volumedown', 'volumemute', 'volumeup',  'yen', 'final',  'hanguel', 'hangul', 'hanja', 'help', 'home',  
    'prtsc', 'prtscr', 'scrolllock', 'select', 'separator', 'sleep', 'stop', 'subtract',   
    'option', 'optionleft', 'optionright','menu', 'break',
    'numpad_divide', 'numpad_multiply', 'numpad_subtract', 'numpad_add', 'numpad_enter', 'numpad_decimal',
    'junja', 'kana', 'kanji', 'launchapp1', 'launchapp2', 'launchmail', 
    'ro', 'katakanahiragana', 'yen', 'henkan', 'muhenkan',
    'num0', 'num1', 'num2', 'num3', 'num4', 'num5', 'num6', 'num7', 'num8', 'num9', 
    'launchmediaselect',  'modechange', 'multiply', 'nexttrack', 'nonconvert',
    'context_menu', 'numpad_clear', 'numpad_equal', 'gamepad', 'fn_lock',
    'lang1', 'lang2', 'attn', 'crsel', 'exsel', 'ereof', 'play', 'zoom', 'pa1', 'oem_clear',
    'audio_mute', 'audio_vol_down', 'audio_vol_up', 'audio_play', 'audio_stop', 'audio_pause', 'audio_prev','audio_next',
    'brightness_down', 'brightness_up', 'abnt_c1', 'abnt_c2', 'ax', 'numpad_comma', 'eject'
}


SCROLL_DIRECTION_MAP = {
    "\u2b07\ufe0f": "down",  # ⬇️
    "↙": "down-left",  # ↙️
    "\u2b06\ufe0f": "up",  # ⬆️
    "↘": "down-right",  # ↘️
    "↖": "up-left",  # ↖
    "↗️": "up-right",  # ↗️
    "\u2b05\ufe0f": "left",  # ⬅️
    "\u27a1\ufe0f": "right",  # ➡️
}


def preprocess_events(events):
    for index, item in enumerate(events):
        if index + 1 >= len(events):
            continue
        if (
            item["action"] == "mouse_press"
            and events[index + 1]["action"] == "type"
            and (events[index + 1]["description"] == "Type: c" or events[index + 1]["description"] == "Type: C")
        ):
            item["action"] = "drag"
            item["description"] = "Drag from (0,0) to (0, 0)"
            events[index + 1]["action"] = "press"
            events[index + 1]["description"] = "Press: $cmd$ + c"
        elif (
            item["action"] == "drag"
            and events[index + 1]["action"] == "type"
            and ("Type: c" in events[index + 1]["description"] or "Type: v" in events[index + 1]["description"])
        ):
            events[index + 1]["action"] = "press"
            if "Type: c" in events[index + 1]["description"]:
                events[index + 1]["description"] = "Press: $cmd$ + c"
            elif "Type: v" in events[index + 1]["description"]:
                events[index + 1]["description"] = "Press: $cmd$ + v"
    return events


def parse_scroll_to_cardinal(scroll_text):
    directions = {"up": 0, "down": 0, "left": 0, "right": 0}
    actions = scroll_text.replace("Scroll ", "").split()
    for action in actions:
        if "\u00d7" in action:
            direction, magnitude = action.split("\u00d7")
            magnitude = int(magnitude)
            if direction in SCROLL_DIRECTION_MAP:
                mapped_direction = SCROLL_DIRECTION_MAP[direction]
                if mapped_direction in directions:
                    directions[mapped_direction] += magnitude
                elif mapped_direction == "down-left":
                    directions["down"] += magnitude
                    directions["left"] += magnitude
                elif mapped_direction == "down-right":
                    directions["down"] += magnitude
                    directions["right"] += magnitude
                elif mapped_direction == "up-left":
                    directions["up"] += magnitude
                    directions["left"] += magnitude
                elif mapped_direction == "up-right":
                    directions["up"] += magnitude
                    directions["right"] += magnitude
    return directions


def get_action_type(action: str):
    action = action.lower()
    if "single right click" in action:
        return "rightClick"
    elif "double right click" in action:
        return "rightClick"
    elif "single left click" in action or "single x1 click" in action:
        return "click"
    elif "double left click" in action:
        return "doubleClick"
    elif "single middle click" in action:
        return "middleClick"
    elif "triple left click" in action:
        return "tripleClick"
    elif "mouse long press left button" in action:
        return "click"
    elif "mouse long press right button" in action:
        return "rightClick"
    elif "mouse long press middle button" in action:
        return "middleClick"
    elif "type" in action:
        return "write"
    elif "press" in action:
        return "press"
    elif "drag" in action:
        return "dragTo"
    elif "scroll" in action:
        return "scroll"
    elif "terminate" in action:
        return "terminate"
    else:
        raise ValueError(f"Unknown action: {action}")


def reduce_actions(actionlist):
    reduced_actionlist = []
    for action in actionlist:
        if action.action_type == "press":
            unknown_flag = any("Unknown" in key for key in action.args.get("keys", []))
            if unknown_flag:
                continue
        if (
            action.action_type == "press"
            and len(reduced_actionlist) >= 1
            and reduced_actionlist[-1].action_type == "write"
            and action.args["keys"][0] == "space"
            and len(action.args["keys"]) == 1
        ):
            reduced_actionlist[-1].args["message"] += " "
        elif (
            action.action_type == "write"
            and len(reduced_actionlist) >= 1
            and reduced_actionlist[-1].action_type == "write"
        ):
            reduced_actionlist[-1].args["message"] += action.args["message"]
        elif (
            action.action_type == "press"
            and len(reduced_actionlist) >= 1
            and reduced_actionlist[-1].action_type == "write"
            and action.args["keys"][0] == "backspace"
            and len(action.args["keys"]) == 1
        ):
            reduced_actionlist[-1].args["message"] = reduced_actionlist[-1].args["message"][:-1]
        else:
            reduced_actionlist.append(action)
    return reduced_actionlist


def reduce_content(episode_id, step_num, content):
    import re

    reduced_content = []
    continue_flag = False
    for index, item in enumerate(content):
        if continue_flag:
            continue_flag = False
            continue
        try:
            if isinstance(item, (TextObservation, ImageObservation)):
                reduced_content.append(item)
            elif isinstance(item, GUIAction) and len(item.guiactions) == 0:
                if isinstance(reduced_content[-1], ImageObservation):
                    reduced_content.pop()
                elif isinstance(reduced_content[-1], TextObservation):
                    task_instruction = reduced_content.pop()
                    reduced_content.pop()
                    reduced_content.append(content[index + 1])
                    reduced_content.append(task_instruction)
                    continue_flag = True
                continue
            elif (
                isinstance(item, GUIAction)
                and len(item.guiactions) > 0
                and item.guiactions[0].action_type == GUIActionType.WRITE
            ):
                # Look for the most recent GUIAction with write, skipping over ImageObservations
                last_write_idx = None
                for i in range(len(reduced_content) - 1, -1, -1):
                    if isinstance(reduced_content[i], GUIAction):
                        # Check if the first action is WRITE (typing action)
                        if reduced_content[i].guiactions and reduced_content[i].guiactions[0].action_type == GUIActionType.WRITE:
                            last_write_idx = i
                        break
                    elif not isinstance(reduced_content[i], (ImageObservation, TextObservation)):
                        # Stop if we hit something that's not an image or text observation
                        break
                
                if last_write_idx is not None:
                    # Merge: remove all items after last_write_idx (images and current item)
                    items_to_remove = len(reduced_content) - last_write_idx - 1
                    for _ in range(items_to_remove):
                        reduced_content.pop()
                    
                    # Merge the write actions
                    last_write_item = reduced_content.pop()
                    last_write_item.instruction = last_write_item.instruction + " " + item.instruction
                    last_write_item.guiactions.extend(item.guiactions)
                    last_write_item.guiactions = reduce_actions(last_write_item.guiactions)
                    reduced_content.append(last_write_item)
                else:
                    # No previous write action found, just add this one
                    if hasattr(item, "instruction"):
                        item.instruction = re.sub(r"\\u[0-9A-Fa-f]{4}", "", item.instruction)
                    reduced_content.append(item)
            elif (
                isinstance(item, GUIAction)
                and item.guiactions[0].action_type == GUIActionType.CLICK
                and isinstance(reduced_content[-2], GUIAction)
                and reduced_content[-2].guiactions[-1].action_type == GUIActionType.CLICK
                and item.guiactions[0].args["x"] == reduced_content[-2].guiactions[-1].args["x"]
                and item.guiactions[0].args["y"] == reduced_content[-2].guiactions[-1].args["y"]
            ):
                # Check time interval - only merge into double-click if <= 500ms apart
                time_diff = None
                if item.start_time is not None and reduced_content[-2].end_time is not None:
                    time_diff = item.start_time - reduced_content[-2].end_time
                
                # Only convert to double-click if time difference is small enough (500ms threshold)
                if time_diff is None or time_diff <= 0.5:
                    reduced_content.pop()
                    second_last_item = reduced_content.pop()
                    second_last_item.instruction = second_last_item.instruction + " " + item.instruction
                    second_last_item.guiactions[-1].action_type = "doubleClick"
                    reduced_content.append(second_last_item)
                else:
                    # Keep as separate clicks if time difference is too large
                    if hasattr(item, "instruction"):
                        item.instruction = re.sub(r"\\u[0-9A-Fa-f]{4}", "", item.instruction)
                    reduced_content.append(item)
            else:
                if hasattr(item, "instruction"):
                    item.instruction = re.sub(r"\\u[0-9A-Fa-f]{4}", "", item.instruction)
                reduced_content.append(item)
        except Exception as e:
            raise ValueError(f"Unknown item:{item} in episode:{episode_id}, step:{step_num}") from e
    return reduced_content


def build_actions(episode_id, step_num, action, img_size, trace=None):
    import re

    actionlist = []
    action_type = get_action_type(action)

    def process_caps_lock(string):
        positions = []
        start = 0
        while True:
            pos = string.find("caps_lock", start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + len("caps_lock")
        content = string[: positions[0]]
        for index, pos in enumerate(positions):
            if index % 2 == 0 and index + 1 < len(positions):
                content += string[pos + len("caps_lock") : positions[index + 1]].upper()
            elif index % 2 == 1 and index + 1 < len(positions):
                content += string[pos + len("caps_lock") : positions[index + 1]]
            elif index % 2 == 0 and index + 1 == len(positions):
                content += string[pos + len("caps_lock") :].upper()
            elif index % 2 == 1 and index + 1 == len(positions):
                content += string[pos + len("caps_lock") :]
        return content

    if action_type not in ["click", "doubleClick", "rightClick"]:
        pass
    if action_type in ["click", "doubleClick", "rightClick", "middleClick"]:
        try:
            coordinates = action.split("(")[1].split(")")[0]
            x, y = map(float, coordinates.split(","))
            x = max(0, min(x, img_size[0]))
            y = max(0, min(y, img_size[1]))
            actionlist = [
                PyAutoGUIAction(action_type=GUIActionType(action_type), target=None, args={"x": x / img_size[0], "y": y / img_size[1]}),
            ]
        except Exception as e:
            raise ValueError(f"Failed to parse click action '{action}' in episode:{episode_id}, step:{step_num}: {e}") from e
    elif action_type == "tripleClick":
        # Export triple click as single left click
        coordinates = action.split("(")[1].split(")")[0]
        x, y = map(float, coordinates.split(","))
        x = max(0, min(x, img_size[0]))
        y = max(0, min(y, img_size[1]))
        actionlist = [
            PyAutoGUIAction(action_type=GUIActionType.CLICK, target=None, args={"x": x / img_size[0], "y": y / img_size[1]}),
        ]
    elif action_type == "write":
        whole = action.split("Type: ")[-1]
        # Use the authoritative key definitions from the recording system
        # Combine both MODIFIED_KEYS and FUNCTIONAL_KEYS to get all special keys
        SPECIAL_KEYS = MODIFIED_KEYS | FUNCTIONAL_KEYS
        
        contents = []
        actions = []
        i = 0
        
        while i < len(whole):
            if whole[i] == "$":
                # Look ahead to find the next $
                j = i + 1
                while j < len(whole) and whole[j] != "$":
                    j += 1
                
                if j < len(whole):  # Found a closing $
                    token = whole[i+1:j]
                    # Check if this token is a special key
                    if token.lower() in SPECIAL_KEYS or "caps_lock" in token:
                        # This is a special key delimiter
                        contents.append(["keys", token])
                        i = j + 1  # Skip past the closing $
                        continue
                
                # If we get here, either no closing $ found, or token is not a special key
                # Treat this $ as literal text
                if len(contents) > 0 and contents[-1][0] == "text":
                    contents[-1][1] += "$"
                else:
                    contents.append(["text", "$"])
                i += 1
            else:
                # Regular character
                if len(contents) > 0 and contents[-1][0] == "text":
                    contents[-1][1] += whole[i]
                else:
                    contents.append(["text", whole[i]])
                i += 1
        
        for content in contents:
            if content[0] == "keys":
                actions.append(PyAutoGUIAction(action_type=GUIActionType.PRESS, target=None, args={"keys": [content[1]]}))
            else:
                actions.append(PyAutoGUIAction(action_type=GUIActionType.WRITE, target=None, args={"message": content[1]}))
        actionlist = actions
    elif action_type == "press":
        action = action.replace("\n", "")
        try:
            keys = [action.split("Press: ")[1]]
        except Exception:
            raise ValueError(f"Unknown press action: {action} in episode:{episode_id}, step:{step_num}")
        if "+" in action:
            keys = action.split("Press: ")[1].split(" + ")
        
        # Use the authoritative key definitions from the recording system
        # Combine both MODIFIED_KEYS and FUNCTIONAL_KEYS to get all special keys
        SPECIAL_KEYS_PRESS = MODIFIED_KEYS | FUNCTIONAL_KEYS
        
        for index in range(len(keys)):
            if keys[index].startswith("$") and keys[index].endswith("$") and keys[index].count("$") == 2:
                keys[index] = keys[index].replace("$", "")
            elif "$" in keys[index]:
                # Use smart parsing: only treat $TOKEN$ as delimiter if TOKEN is a special key
                whole = keys[index]
                parsed_keys = []
                i = 0
                current = ""
                
                while i < len(whole):
                    if whole[i] == "$":
                        # Look ahead to find the next $
                        j = i + 1
                        while j < len(whole) and whole[j] != "$":
                            j += 1
                        
                        if j < len(whole):  # Found a closing $
                            token = whole[i+1:j]
                            # Check if this token is a special key
                            if token.lower() in SPECIAL_KEYS_PRESS or "caps_lock" in token:
                                # This is a special key delimiter - flush current and add the key
                                if current:
                                    parsed_keys.append(current)
                                    current = ""
                                parsed_keys.append(token)
                                i = j + 1  # Skip past the closing $
                                continue
                        
                        # If we get here, either no closing $ found, or token is not a special key
                        # Treat this $ as literal text
                        current += "$"
                        i += 1
                    else:
                        # Regular character
                        current += whole[i]
                        i += 1
                
                if current:
                    parsed_keys.append(current)
                
                # Replace the key at this index with parsed keys
                if parsed_keys:
                    keys[index] = parsed_keys[0]
                    for new_index, new_key in enumerate(parsed_keys[1:]):
                        keys.insert(index + 1 + new_index, new_key)
        
        keys = [k for k in keys if k != ""]

        def extract_content(keys):
            contents = []
            content = ""
            for index_key, key in enumerate(keys):
                if "caps_lock" in key:
                    key = process_caps_lock(key)
                if key == "backspace":
                    if content != "":
                        content = content[:-1]
                    elif content == "":
                        contents.append(["keys", "backspace"])
                elif key == "space":
                    content += " "
                elif key == "enter":
                    if content != "":
                        contents.append(["text", content])
                        content = ""
                    contents.append(["keys", "enter"])
                elif key == "tab":
                    if content != "":
                        contents.append(["text", content])
                        content = ""
                    contents.append(["keys", "tab"])
                else:
                    for char in key:
                        if (65 <= ord(char) <= 90) or (97 <= ord(char) <= 122):
                            if index_key == 0 and len(content) == 0:
                                content = char.upper() if char.islower() else char
                            else:
                                content += char
                        elif char.isdigit():
                            content += char
                        elif char in [
                            "-",
                            "_",
                            "+",
                            "~",
                            "!",
                            "@",
                            "#",
                            "$",
                            "%",
                            "^",
                            "&",
                            "*",
                            "(",
                            ")",
                            "[",
                            "]",
                            "{",
                            "}",
                            "|",
                            ":",
                            '"',
                            "'",
                            "<",
                            ">",
                            "?",
                            "/",
                            "=",
                            "–",
                            ".",
                            ",",
                            ";",
                            "`",
                            "\\",
                            "）",
                            "（",
                            "！",
                            " ",
                            "，",
                            "、",
                            "。",
                            "โ",
                            "ต",
                            "；",
                            "§",
                        ]:
                            content += char
                        else:
                            raise ValueError(
                                f"Unknown key({char}) in keys:{keys} in episode:{episode_id}, step:{step_num}"
                            )
            if content != "":
                contents.append(["text", content])
            return contents

        if keys and keys[0] == "shift" and "cmd" not in keys and "ctrl" not in keys:
            if len(keys) == 1:
                actionlist = [PyAutoGUIAction(action_type=GUIActionType.HOTKEY, target=None, args={"keys": ["shift"]})]
            elif len(keys) == 2 and keys[1] == "enter":
                actionlist = [PyAutoGUIAction(action_type=GUIActionType.HOTKEY, target=None, args={"keys": ["shift", "enter"]})]
            elif keys[1][0].isalpha() or keys[1][0].isdigit() or keys[1][0] in [
                "_",
                "=",
                "+",
                "~",
                "!",
                "@",
                "#",
                "$",
                "%",
                "^",
                "&",
                "*",
                "(",
                ")",
                "[",
                "]",
                "{",
                "}",
                "|",
                ":",
                "-",
                '"',
                "'",
                "<",
                ">",
                "?",
                "/",
                ".",
                "\\",
                "）",
                "（",
                "！",
                "，",
                "、",
                "。",
                "โ",
                "ต",
                "；",
                "§",
            ]:
                contents = extract_content(keys[1:])
                if contents == []:
                    actionlist = [PyAutoGUIAction(action_type=GUIActionType.HOTKEY, target=None, args={"keys": ["shift"]})]
                else:
                    for content in contents:
                        if content[0] == "text":
                            if len(actionlist) == 0:
                                actionlist = [
                                    PyAutoGUIAction(action_type=GUIActionType.WRITE, target=None, args={"message": content[1]}),
                                ]
                            else:
                                actionlist.append(
                                    PyAutoGUIAction(action_type=GUIActionType.WRITE, target=None, args={"message": content[1]})
                                )
                        elif content[0] == "keys":
                            if len(actionlist) == 0:
                                actionlist = [
                                    PyAutoGUIAction(action_type=GUIActionType.PRESS, target=None, args={"keys": [content[1]]}),
                                ]
                            else:
                                actionlist.append(
                                    PyAutoGUIAction(action_type=GUIActionType.PRESS, target=None, args={"keys": [content[1]]})
                                )
        else:
            actionlist = [PyAutoGUIAction(action_type=GUIActionType.HOTKEY, target=None, args={"keys": keys})]
    elif action_type == "dragTo":
        from_coor, target_coor = action.split("Drag from ")[1].split(" to ")
        from_x, from_y = map(float, from_coor.split("(")[1].split(")")[0].split(","))
        to_x, to_y = map(float, target_coor.split("(")[1].split(")")[0].split(","))
        actionlist = [
            PyAutoGUIAction(
                action_type=GUIActionType.MOVE_TO,
                target=None,
                args={"x": max(0, min(from_x / img_size[0], 1)), "y": max(0, min(from_y / img_size[1], 1))},
            ),
            PyAutoGUIAction(
                action_type=GUIActionType.DRAG_TO,
                target=None,
                args={
                    "x": max(0, min(to_x / img_size[0], 1)),
                    "y": max(0, min(to_y / img_size[1], 1)),
                    "button": "left",
                },
            ),
        ]
    elif action_type == "scroll":
        actionlist = []
        if trace is not None:
            x, y = max(0, min(trace[0]["x"], img_size[0])), max(0, min(trace[0]["y"], img_size[1]))
            dx, dy = 0, 0
            for a in trace:
                dx += a["dx"]
                dy += a["dy"]
            actionlist.append(
                PyAutoGUIAction(
                    action_type=GUIActionType.MOVE_TO,
                    target=None,
                    args={"x": max(0, min(x / img_size[0], 1)), "y": max(0, min(y / img_size[1], 1))},
                )
            )
            if dx != 0:
                actionlist.append(PyAutoGUIAction(action_type=GUIActionType.HSCROLL, target=None, args={"clicks": dx}))
            if dy != 0:
                actionlist.append(PyAutoGUIAction(action_type=GUIActionType.SCROLL, target=None, args={"clicks": dy}))
        else:
            scroll_directions = parse_scroll_to_cardinal(action)
            assert not (
                scroll_directions["up"] == 0
                and scroll_directions["down"] == 0
                and scroll_directions["left"] == 0
                and scroll_directions["right"] == 0
            ), f"Unknown scroll action: {action} at step{step_num} in episode({episode_id})"
            if scroll_directions["up"] != 0 or scroll_directions["down"] != 0 and abs(
                (scroll_directions["up"] - scroll_directions["down"])
            ) >= 1:
                actionlist.append(
                    PyAutoGUIAction(
                        action_type=GUIActionType.SCROLL,
                        target=None,
                        args={"clicks": scroll_directions["up"] - scroll_directions["down"]},
                    )
                )
            if scroll_directions["left"] != 0 or scroll_directions["right"] != 0 and abs(
                (scroll_directions["right"] - scroll_directions["left"])
            ) >= 2:
                actionlist.append(
                    PyAutoGUIAction(
                        action_type=GUIActionType.HSCROLL,
                        target=None,
                        args={"clicks": scroll_directions["right"] - scroll_directions["left"]},
                    )
                )
    elif action_type == "terminate":
        actionlist = [ComputerAction(action_type="terminate", target=None, args={"status": "success"})]
    else:
        raise ValueError(f"Unknown action: {action}")

    try:
        reduced_actionlist = reduce_actions(actionlist)
    except Exception:
        raise ValueError(f"Unknown actionlist: {action}")
    return reduced_actionlist


def convert_examples(sample_raw):
    trajs = []
    skip_episode = set(
        [
            "20241016155654_prolific_test_3805_72eb88c4-ff2b-45a5-a819-e0fef670779b",
            "20240924144854_tianbaoxiexxx@gmail.com_0b23f6ee-5cc2-4f65-950f-a5a16115b8fc",
            "20241012203145_prolific_test_626_2c27d6bd-dbe9-4919-9393-aab6b826ecb9",
            "20240929152414_martinshin95@gmail.com_4255b742-5eff-45f0-808b-820a219e23ca",
            "20241116123450_samsiyahsamok@gmail.com_ae9478d3-e16f-404d-91db-adc8dee1adae",
            "20241022021432_prolific_test_8771_9b2a7f02-b0f4-4922-a9d8-c89d3adb0cfb",
        ]
    )
    for item in sample_raw:
        episode_id = item.get("episode_id", "unknown")
        if episode_id in skip_episode:
            print(f"Skipping known problematic episode: {episode_id}")
            continue
        
        task_instruction = item.get("task_name", "unknown")
        try:
            step_num = len(item["events"])
        except KeyError:
            print(f"Error in {episode_id}: 'events' key not found in raw data")
            continue
        except Exception as e:
            print(f"Error in {episode_id}: Failed to get events: {type(e).__name__}: {e}")
            continue
        
        if step_num == 0:
            print(f"Error in {episode_id}: No events found")
            continue
        
        try:
            img_size = [item["metadata"]["screen_width"], item["metadata"]["screen_height"]]
        except KeyError as e:
            print(f"Error in {episode_id}: Missing metadata field: {e}")
            continue
        except Exception as e:
            print(f"Error in {episode_id}: Failed to get screen size from metadata: {type(e).__name__}: {e}")
            continue
            
        item["events"] = preprocess_events(item["events"])
        content = None
        for i in range(step_num):
            if i == 0:
                try:
                    if "frame" not in item["events"][i]:
                        print(f"Error in {episode_id}, step {i}: 'frame' key not found in event")
                        break
                    content = [
                        ImageObservation(content=item["events"][i]["frame"], filename=f"{episode_id}_{i}.png", source="os"),
                    ]
                except Exception as e:
                    print(f"Error in {episode_id}, step {i}: Failed to create ImageObservation: {type(e).__name__}: {e}")
                    break
                content.append(TextObservation(content=task_instruction, source="user"))
            else:
                try:
                    if "frame" not in item["events"][i]:
                        print(f"Warning in {episode_id}, step {i}: 'frame' key not found, skipping this observation")
                        continue
                    content.append(
                        ImageObservation(content=item["events"][i]["frame"], filename=f"{episode_id}_{i}.png", source="os")
                    )
                except Exception as e:
                    print(f"Warning in {episode_id}, step {i}: Failed to create ImageObservation: {type(e).__name__}: {e}")
                    continue
            
            try:
                instruction = item["events"][i].get("action", "unknown")
                rawaction = item["events"][i].get("description", "")
                if not rawaction:
                    print(f"Error in {episode_id}, step {i}: Empty description field")
                    break
                trace = item["events"][i].get("trace")
                start_time = item["events"][i].get("start_time")
                end_time = item["events"][i].get("end_time")
            except Exception as e:
                print(f"Error in {episode_id}, step {i}: Failed to extract event fields: {type(e).__name__}: {e}")
                break
                
            try:
                actions = build_actions(episode_id, i, rawaction, img_size, trace)
                content.append(GUIAction(instruction=instruction, guiactions=actions, start_time=start_time, end_time=end_time))
            except Exception as e:
                print(
                    f"Error in {episode_id}, step {i}: Failed to build actions from '{rawaction}':\n"
                    f"  - Error type: {type(e).__name__}\n"
                    f"  - Error message: {str(e)}\n"
                )
                import traceback
                traceback.print_exc()
                break

        if content is not None:
            try:
                system_instruction = (
                    "You are a GUI agent. You are given a task and a screenshot of the screen. You need to perform a series of "
                    "pyautogui actions to complete the task."
                )
                content = [TextObservation(content=system_instruction, source="system")] + content
                reduced_content = reduce_content(episode_id, i, content)
                trajs.append(
                    Trajectory(task_id="agentnet", type="end2end", example_id=str(episode_id), content=reduced_content)
                )
            except Exception as e:
                print(
                    f"Error in {episode_id}: Failed to create trajectory:\n"
                    f"  - Error type: {type(e).__name__}\n"
                    f"  - Error message: {str(e)}\n"
                )
                import traceback
                traceback.print_exc()
                continue
        else:
            print(f"Error in {episode_id}: Content is None, likely due to errors in event processing")
            
    return trajs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_file", type=str, help="Path to raw JSON (.json) or directory of raw JSONs")
    parser.add_argument("output_dir", type=str, help="Output directory for standardized trajectories")
    parser.add_argument("--num_samples", type=int, default=-1)
    args = parser.parse_args()

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    processed_episode_ids = {item.split(".json")[0] for item in os.listdir(args.output_dir)}

    if args.raw_file.endswith(".json"):
        try:
            with open(args.raw_file, encoding="utf-8") as f:
                raw_examples = oj.loads(f.read())
        except FileNotFoundError:
            print(f"Error: File not found: {args.raw_file}")
            return
        except oj.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {args.raw_file}: {e}")
            return
        except Exception as e:
            print(f"Error reading {args.raw_file}: {type(e).__name__}: {e}")
            return
            
        if args.num_samples != -1:
            raw_examples = raw_examples[: args.num_samples]
        
        for raw_example in tqdm(raw_examples):
            episode_id = raw_example.get("episode_id", "unknown")
            if episode_id in processed_episode_ids:
                continue
            
            try:
                converted_examples = convert_examples([raw_example])
                if not converted_examples:
                    print(f"Warning: No trajectory produced for {episode_id}")
                    continue
                converted_example = converted_examples[0]
                with open(f"{args.output_dir}/{converted_example.example_id}.json", "wb") as f:
                    f.write(oj.dumps(converted_example.model_dump()))
            except Exception as e:
                import traceback
                print(
                    f"Error processing {episode_id}:\n"
                    f"  - Error type: {type(e).__name__}\n"
                    f"  - Error message: {str(e)}\n"
                )
                traceback.print_exc()
    else:
        raw_files = list(Path(args.raw_file).glob("*.json"))
        if not raw_files:
            print(f"Warning: No .json files found in {args.raw_file}")
            return
            
        if args.num_samples != -1:
            raw_files = raw_files[: args.num_samples]
        
        for raw_file in tqdm(raw_files):
            episode_id = raw_file.stem
            if episode_id in processed_episode_ids:
                continue
            
            try:
                with open(raw_file, encoding="utf-8") as f:
                    raw_example = oj.loads(f.read())
            except oj.JSONDecodeError as e:
                print(f"Error: Invalid JSON in {raw_file.name}: {e}")
                continue
            except Exception as e:
                print(f"Error reading {raw_file.name}: {type(e).__name__}: {e}")
                continue
            
            try:
                converted_examples = convert_examples([raw_example])
                if not converted_examples:
                    print(f"Warning: No trajectory produced for {raw_file.name}")
                    continue
                converted_example = converted_examples[0]
                with open(f"{args.output_dir}/{converted_example.example_id}.json", "wb") as f:
                    f.write(oj.dumps(converted_example.model_dump()))
            except Exception as e:
                import traceback
                print(
                    f"Error processing {raw_file.name}:\n"
                    f"  - Error type: {type(e).__name__}\n"
                    f"  - Error message: {str(e)}\n"
                )
                traceback.print_exc()


if __name__ == "__main__":
    main()


