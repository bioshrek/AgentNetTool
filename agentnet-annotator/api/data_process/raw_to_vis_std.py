import argparse
import base64
import json
import io
import os
import shutil
from pathlib import Path

import orjson as oj
from tqdm import tqdm
from PIL import Image

from data_process.raw_to_standardized import convert_examples
from data_process.schema.action import GUIAction, GUIActionType, PyAutoGUIAction, ImageObservation, TextObservation
from data_process.schema.trajectory import Trajectory
from data_process.extract_raw import process_single_directory

def process_trajectory(traj_data, output_path, source_path=None):
    # Use example_id if available, otherwise task_id
    example_id = traj_data.example_id if traj_data.example_id else traj_data.task_id
    
    # Create folder with just the ID
    task_dir_name = f"{example_id}"
    task_dir = output_path / task_dir_name
    task_dir.mkdir(parents=True, exist_ok=True)

    # Copy video file if source_path is provided
    if source_path:
        source_path = Path(source_path)
        # Look for .mp4 file in the source directory
        video_files = list(source_path.glob("*.mp4"))
        if video_files:
            # Copy the first video file found
            src_video = video_files[0]
            dst_video = task_dir / "recording.mp4"
            shutil.copy2(src_video, dst_video)

    # Find instruction
    instruction = ""
    # Look for user text observation first
    for item in traj_data.content:
        if isinstance(item, TextObservation) and item.source == 'user':
                instruction = item.content
                break
    
    # Fallback to instruction in the first GUIAction
    if not instruction:
            for item in traj_data.content:
                if isinstance(item, GUIAction):
                    instruction = item.instruction
                    break

    new_traj = []
    last_image = None
    step_idx = 0

    for item in traj_data.content:
        if isinstance(item, ImageObservation):
            last_image = item
        elif isinstance(item, GUIAction):
            if last_image:
                    # Save image
                    image_data = last_image.content
                    if image_data and image_data.startswith('data:image/png;base64,'):
                        image_data = image_data.replace('data:image/png;base64,', '')
                    
                    if image_data:
                        try:
                            img_bytes = base64.b64decode(image_data)
                            
                            # Get image dimensions for coordinate conversion
                            with Image.open(io.BytesIO(img_bytes)) as img:
                                width, height = img.size
                            
                            img_filename = f"step_{step_idx}.png"
                            img_path = task_dir / img_filename
                            with open(img_path, 'wb') as img_f:
                                img_f.write(img_bytes)
                            
                            # Generate code with absolute coordinates
                            # First, convert normalized coordinates to absolute for all actions
                            for action in item.guiactions:
                                if not isinstance(action, PyAutoGUIAction):
                                    continue
                                
                                # Ensure action_type is a GUIActionType enum, not a string
                                if isinstance(action.action_type, str):
                                    action.action_type = GUIActionType(action.action_type)
                                
                                # Convert normalized coordinates to absolute
                                if 'x' in action.args and 'y' in action.args:
                                    if isinstance(action.args['x'], float) and width > 0:
                                        action.args['x'] = int(action.args['x'] * width)
                                    if isinstance(action.args['y'], float) and height > 0:
                                        action.args['y'] = int(action.args['y'] * height)
                                
                                if 'from_coord' in action.args and isinstance(action.args['from_coord'], (list, tuple)):
                                    fx, fy = action.args['from_coord']
                                    action.args['from_coord'] = (int(fx * width), int(fy * height))
                                
                                if 'to_coord' in action.args and isinstance(action.args['to_coord'], (list, tuple)):
                                    tx, ty = action.args['to_coord']
                                    action.args['to_coord'] = (int(tx * width), int(ty * height))
                            
                            # Now process actions, filtering and merging as needed
                            codes = []
                            i = 0
                            pyautogui_actions = [a for a in item.guiactions if isinstance(a, PyAutoGUIAction)]
                            
                            while i < len(pyautogui_actions):
                                action = pyautogui_actions[i]
                                
                                # Check if this is a moveTo followed by scroll - skip moveTo
                                if (action.action_type == GUIActionType.MOVE_TO and 
                                    i + 1 < len(pyautogui_actions) and 
                                    pyautogui_actions[i + 1].action_type == GUIActionType.SCROLL):
                                    i += 1
                                    continue
                                
                                # Check if this is a moveTo followed by dragTo - merge into drag
                                if (action.action_type == GUIActionType.MOVE_TO and 
                                    i + 1 < len(pyautogui_actions) and 
                                    pyautogui_actions[i + 1].action_type == GUIActionType.DRAG_TO):
                                    move_action = action
                                    drag_action = pyautogui_actions[i + 1]
                                    
                                    # Get start position from moveTo
                                    start_x = move_action.args.get('x', 0)
                                    start_y = move_action.args.get('y', 0)
                                    
                                    # Get end position from dragTo
                                    end_x = drag_action.args.get('x', start_x)
                                    end_y = drag_action.args.get('y', start_y)
                                    
                                    # Create merged drag action
                                    merged_drag = PyAutoGUIAction(
                                        action_type=GUIActionType.DRAG_TO,
                                        args={
                                            'from_coord': [start_x, start_y],
                                            'to_coord': [end_x, end_y],
                                            'button': drag_action.args.get('button', 'left')
                                        }
                                    )
                                    codes.append(merged_drag.to_command())
                                    i += 2
                                    continue
                                
                                codes.append(action.to_command())
                                i += 1
                            
                            code_str = "\n".join(codes)

                            # Add step regardless of whether code is empty (keep termination steps)
                            new_traj.append({
                                "index": step_idx,
                                "code": code_str,
                                "screenshot": img_filename
                            })
                            step_idx += 1
                        except Exception as e:
                            print(f"Error saving image or processing action in {example_id}: {e}")
                            import traceback
                            traceback.print_exc()

    output_json = {
        "task_id": example_id,
        "instruction": instruction,
        "traj": new_traj
    }

    # Put the json file under the folder with name traj.json
    with open(task_dir / "traj.json", 'w') as f:
        json.dump(output_json, f, indent=4)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_file", type=str, help="Path to raw JSON (.json) or directory of raw JSONs (datasets/raw_trajs)")
    parser.add_argument("output_dir", type=str, help="Output directory for visualization standardized trajectories")
    parser.add_argument("--num_samples", type=int, default=-1)
    args = parser.parse_args()

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    processed_episode_ids = {item for item in os.listdir(args.output_dir)}

    input_path = Path(args.raw_file)

    # Check if input is a single raw recording directory
    if input_path.is_dir() and (input_path / "metadata.json").exists():
        print(f"Processing single raw recording directory: {input_path}")
        parent_dir = str(input_path.parent)
        dir_name = input_path.name
        
        # Extract raw trajectory from folder
        # Note: process_single_directory expects str paths
        raw_example = process_single_directory(parent_dir, dir_name, load_image=True)
        
        if raw_example:
            converted_examples = convert_examples([raw_example])
            if converted_examples:
                try:
                    process_trajectory(converted_examples[0], output_path, source_path=input_path)
                    print(f"Successfully processed {dir_name}")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"Error processing trajectory {dir_name}: {e}")
            else:
                 print("Failed to convert raw example to standardized format")
        else:
             print("Failed to extract raw data from directory")
        return

    # Check if input is a directory of raw recordings
    # If it is a directory but NO metadata.json, it might be the parent folder of many recordings
    if input_path.is_dir() and not (input_path / "metadata.json").exists() and not list(input_path.glob("*.json")):
        print(f"Processing directory of raw recordings: {input_path}")
        parent_dir = str(input_path)
        
        # Iterate over all subdirectories
        for item in input_path.iterdir():
            if item.is_dir() and (item / "metadata.json").exists():
                dir_name = item.name
                if dir_name in processed_episode_ids:
                    continue

                try:
                    print(f"Processing {dir_name}...")
                    raw_example = process_single_directory(parent_dir, dir_name, load_image=True)
                    if not raw_example: 
                        continue
                        
                    converted_examples = convert_examples([raw_example])
                    if not converted_examples:
                        continue
                        
                    process_trajectory(converted_examples[0], output_path, source_path=item)
                    print(f"Successfully processed {dir_name}")
                except Exception as e:
                    print(f"Error processing {dir_name}: {e}")
        return

    processed_episode_ids = {item for item in os.listdir(args.output_dir)}

    if args.raw_file.endswith(".json"):
        with open(args.raw_file, encoding="utf-8") as f:
            raw_examples = oj.loads(f.read())
        if args.num_samples != -1:
            raw_examples = raw_examples[: args.num_samples]
        
        # Ensure it's a list
        if isinstance(raw_examples, dict):
             raw_examples = [raw_examples]

        for raw_example in tqdm(raw_examples):
            if raw_example["episode_id"] in processed_episode_ids:
                continue
            
            try:
                converted_examples = convert_examples([raw_example])
                if converted_examples:
                    process_trajectory(converted_examples[0], output_path)
            except Exception as e:
                print(f"Error processing {raw_example.get('episode_id', 'unknown')}: {e}")

    else:
        raw_files = list(Path(args.raw_file).glob("*.json"))
        if args.num_samples != -1:
            raw_files = raw_files[: args.num_samples]
        for raw_file in tqdm(raw_files):
            episode_id = raw_file.stem
            if episode_id in processed_episode_ids:
                continue
            try:
                with open(raw_file, encoding="utf-8") as f:
                    raw_example = oj.loads(f.read())
                
                converted_examples = convert_examples([raw_example])
                if not converted_examples:
                    continue
                
                process_trajectory(converted_examples[0], output_path)
            except Exception as e:
                print(f"Error processing {raw_file.name}: {e}")

if __name__ == "__main__":
    main()
