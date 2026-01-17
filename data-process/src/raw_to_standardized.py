import argparse
import json
import os
from pathlib import Path

import orjson as oj
from tqdm import tqdm

from src.schema.action import (
    GUIAction,
    PyAutoGUIAction,
    ComputerAction,
    triple_click_func,
    terminate_func,
)
from src.schema.action import ImageObservation, TextObservation
from src.schema.trajectory import Trajectory


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
                and item.guiactions[0].action_type == "write"
                and isinstance(reduced_content[-2], GUIAction)
                and reduced_content[-2].guiactions[-1].action_type == "write"
            ):
                reduced_content.pop()
                second_last_item = reduced_content.pop()
                second_last_item.instruction = second_last_item.instruction + " " + item.instruction
                second_last_item.guiactions.extend(item.guiactions)
                second_last_item.guiactions = reduce_actions(second_last_item.guiactions)
                reduced_content.append(second_last_item)
            elif (
                isinstance(item, GUIAction)
                and item.guiactions[0].action_type == "click"
                and isinstance(reduced_content[-2], GUIAction)
                and reduced_content[-2].guiactions[-1].action_type == "click"
                and item.guiactions[0].args["x"] == reduced_content[-2].guiactions[-1].args["x"]
                and item.guiactions[0].args["y"] == reduced_content[-2].guiactions[-1].args["y"]
            ):
                reduced_content.pop()
                second_last_item = reduced_content.pop()
                second_last_item.instruction = second_last_item.instruction + " " + item.instruction
                second_last_item.guiactions[-1].action_type = "doubleClick"
                reduced_content.append(second_last_item)
            elif (
                isinstance(item, GUIAction)
                and item.guiactions[0].action_type == "hotkey"
                and len(item.guiactions[0].args["keys"]) == 1
                and (item.guiactions[0].args["keys"][0] in ["shift", "ctrl", "cmd"])
            ):
                if isinstance(reduced_content[-1], ImageObservation):
                    reduced_content.pop()
                elif isinstance(reduced_content[-1], TextObservation):
                    task_instruction = reduced_content.pop()
                    reduced_content.pop()
                    reduced_content.append(content[index + 1])
                    reduced_content.append(task_instruction)
                    continue_flag = True
                continue
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
                PyAutoGUIAction(action_type=action_type, target=None, args={"x": x / img_size[0], "y": y / img_size[1]}),
            ]
        except Exception:
            return None
    elif action_type == "tripleClick":
        coordinates = action.split("(")[1].split(")")[0]
        x, y = map(float, coordinates.split(","))
        x = max(0, min(x, img_size[0]))
        y = max(0, min(y, img_size[1]))
        actionlist = [
            ComputerAction(action_type="tripleClick", args={"x": x / img_size[0], "y": y / img_size[1]}),
        ]
    elif action_type == "write":
        whole = action.split("Type: ")[-1]
        stack = []
        current = ""
        contents = []
        actions = []
        for char in whole:
            if char == "$":
                if stack and stack[-1] == "$":
                    stack.pop()
                    if current:
                        contents.append(["keys", current])
                        current = ""
                else:
                    if current:
                        if "caps_lock" in current:
                            current = process_caps_lock(current)
                        contents.append(["text", current])
                        current = ""
                    stack.append("$")
            else:
                current += char
        if current:
            if "caps_lock" in current:
                current = process_caps_lock(current)
            contents.append(["text", current])
        for content in contents:
            if content[0] == "keys":
                actions.append(PyAutoGUIAction(action_type="press", target=None, args={"keys": [content[1]]}))
            else:
                actions.append(PyAutoGUIAction(action_type="write", target=None, args={"message": content[1]}))
        actionlist = actions
    elif action_type == "press":
        action = action.replace("\n", "")
        try:
            keys = [action.split("Press: ")[1]]
        except Exception:
            raise ValueError(f"Unknown press action: {action} in episode:{episode_id}, step:{step_num}")
        if "+" in action:
            keys = action.split("Press: ")[1].split(" + ")
        for index in range(len(keys)):
            if keys[index].startswith("$") and keys[index].endswith("$") and keys[index].count("$") == 2:
                keys[index] = keys[index].replace("$", "")
            if "$" in keys[index]:
                new_keys = keys[index]
                new_keys = new_keys.split("$")
                keys[index] = new_keys[0]
                for new_index, new_key in enumerate(new_keys[1:]):
                    if new_key == "":
                        continue
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
                actionlist = [PyAutoGUIAction(action_type="hotkey", target=None, args={"keys": ["shift"]})]
            elif len(keys) == 2 and keys[1] == "enter":
                actionlist = [PyAutoGUIAction(action_type="hotkey", target=None, args={"keys": ["shift", "enter"]})]
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
                    actionlist = [PyAutoGUIAction(action_type="hotkey", target=None, args={"keys": ["shift"]})]
                else:
                    for content in contents:
                        if content[0] == "text":
                            if len(actionlist) == 0:
                                actionlist = [
                                    PyAutoGUIAction(action_type="write", target=None, args={"message": content[1]}),
                                ]
                            else:
                                actionlist.append(
                                    PyAutoGUIAction(action_type="write", target=None, args={"message": content[1]})
                                )
                        elif content[0] == "keys":
                            if len(actionlist) == 0:
                                actionlist = [
                                    PyAutoGUIAction(action_type="press", target=None, args={"keys": [content[1]]}),
                                ]
                            else:
                                actionlist.append(
                                    PyAutoGUIAction(action_type="press", target=None, args={"keys": [content[1]]})
                                )
        else:
            actionlist = [PyAutoGUIAction(action_type="hotkey", target=None, args={"keys": keys})]
    elif action_type == "dragTo":
        from_coor, target_coor = action.split("Drag from ")[1].split(" to ")
        from_x, from_y = map(float, from_coor.split("(")[1].split(")")[0].split(","))
        to_x, to_y = map(float, target_coor.split("(")[1].split(")")[0].split(","))
        actionlist = [
            PyAutoGUIAction(
                action_type="moveTo",
                target=None,
                args={"x": max(0, min(from_x / img_size[0], 1)), "y": max(0, min(from_y / img_size[1], 1))},
            ),
            PyAutoGUIAction(
                action_type="dragTo",
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
                    action_type="moveTo",
                    target=None,
                    args={"x": max(0, min(x / img_size[0], 1)), "y": max(0, min(y / img_size[1], 1))},
                )
            )
            if dx != 0:
                actionlist.append(PyAutoGUIAction(action_type="hscroll", target=None, args={"clicks": dx}))
            if dy != 0:
                actionlist.append(PyAutoGUIAction(action_type="scroll", target=None, args={"clicks": dy}))
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
                        action_type="scroll",
                        target=None,
                        args={"clicks": scroll_directions["up"] - scroll_directions["down"]},
                    )
                )
            if scroll_directions["left"] != 0 or scroll_directions["right"] != 0 and abs(
                (scroll_directions["right"] - scroll_directions["left"])
            ) >= 2:
                actionlist.append(
                    PyAutoGUIAction(
                        action_type="hscroll",
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
        episode_id = item["episode_id"]
        if episode_id in skip_episode:
            continue
        task_instruction = item["task_name"]
        try:
            step_num = len(item["events"])
        except Exception:
            continue
        img_size = [item["metadata"]["screen_width"], item["metadata"]["screen_height"]]
        item["events"] = preprocess_events(item["events"])
        content = None
        for i in range(step_num):
            if i == 0:
                try:
                    content = [
                        ImageObservation(content=item["events"][i]["frame"], filename=f"{episode_id}_{i}.png", source="os"),
                    ]
                except Exception:
                    raise ValueError(f"Error in episode {episode_id}, step {i}")
                content.append(TextObservation(content=task_instruction, source="user"))
            else:
                try:
                    content.append(
                        ImageObservation(content=item["events"][i]["frame"], filename=f"{episode_id}_{i}.png", source="os")
                    )
                except Exception:
                    continue
            instruction = item["events"][i]["action"]
            rawaction = item["events"][i]["description"]
            trace = item["events"][i].get("trace")
            actions = build_actions(episode_id, i, rawaction, img_size, trace)
            if actions is not None:
                content.append(GUIAction(instruction=instruction, guiactions=actions))
            else:
                raise ValueError(f"Unknown action: {rawaction} in episode {episode_id}, step {i}")

        if content is not None:
            system_instruction = (
                "You are a GUI agent. You are given a task and a screenshot of the screen. You need to perform a series of "
                "pyautogui actions to complete the task."
            )
            content = [TextObservation(content=system_instruction, source="system")] + content
            reduced_content = reduce_content(episode_id, i, content)
            trajs.append(
                Trajectory(task_id="agentnet", type="end2end", example_id=str(episode_id), content=reduced_content)
            )
        else:
            return []
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
        with open(args.raw_file, encoding="utf-8") as f:
            raw_examples = oj.loads(f.read())
        if args.num_samples != -1:
            raw_examples = raw_examples[: args.num_samples]
        for raw_example in tqdm(raw_examples):
            if raw_example["episode_id"] in processed_episode_ids:
                continue
            converted_example = convert_examples([raw_example])[0]
            with open(f"{args.output_dir}/{converted_example.example_id}.json", "wb") as f:
                f.write(oj.dumps(converted_example.model_dump()))
    else:
        raw_files = list(Path(args.raw_file).glob("*.json"))
        if args.num_samples != -1:
            raw_files = raw_files[: args.num_samples]
        for raw_file in tqdm(raw_files):
            episode_id = raw_file.stem
            if episode_id in processed_episode_ids:
                continue
            with open(raw_file, encoding="utf-8") as f:
                raw_example = oj.loads(f.read())
            converted_examples = convert_examples([raw_example])
            if not converted_examples:
                continue
            converted_example = converted_examples[0]
            with open(f"{args.output_dir}/{converted_example.example_id}.json", "wb") as f:
                f.write(oj.dumps(converted_example.model_dump()))


if __name__ == "__main__":
    main()


