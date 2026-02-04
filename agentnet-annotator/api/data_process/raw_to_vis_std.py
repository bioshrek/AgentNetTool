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

def process_trajectory(traj_data, output_path, source_path=None, raw_events=None):
    # Use example_id if available, otherwise task_id
    example_id = traj_data.example_id if traj_data.example_id else traj_data.task_id
    
    # Create folder with just the ID
    task_dir_name = f"{example_id}"
    task_dir = output_path / task_dir_name
    task_dir.mkdir(parents=True, exist_ok=True)

    # Copy video file and raw trajectory if source_path is provided
    if source_path:
        source_path = Path(source_path)
        # Look for .mp4 file in the source directory
        video_files = list(source_path.glob("*.mp4"))
        if video_files:
            # Copy the first video file found
            src_video = video_files[0]
            dst_video = task_dir / "recording.mp4"
            shutil.copy2(src_video, dst_video)

        raw_traj_src = source_path / "traj_raw.jsonl"
        if raw_traj_src.exists():
            shutil.copy2(raw_traj_src, task_dir / "traj_raw.jsonl")

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
    action_count = 0  # Track which action we're processing for raw_events lookup

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
                            
                            # Save candidate images if available from raw events
                            if raw_events and action_count < len(raw_events):
                                raw_event = raw_events[action_count]
                                if "frame_candidates" in raw_event and raw_event["frame_candidates"]:
                                    candidates_dir = task_dir / "step_img_candidates" / f"step_{step_idx}"
                                    candidates_dir.mkdir(parents=True, exist_ok=True)
                                    
                                    for candidate in raw_event["frame_candidates"]:
                                        try:
                                            candidate_data = candidate["frame"]
                                            if candidate_data.startswith('data:image/png;base64,'):
                                                candidate_data = candidate_data.replace('data:image/png;base64,', '')
                                            
                                            candidate_bytes = base64.b64decode(candidate_data)
                                            candidate_filename = f"{candidate['label']}.png"
                                            candidate_path = candidates_dir / candidate_filename
                                            
                                            with open(candidate_path, 'wb') as cand_f:
                                                cand_f.write(candidate_bytes)
                                        except Exception as e:
                                            print(f"Warning: Failed to save candidate image '{candidate.get('label', 'unknown')}' for step {step_idx}: {e}")
                            
                            action_count += 1
                            
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
        try:
            raw_example = process_single_directory(parent_dir, dir_name, load_image=True)
        except Exception as e:
            import traceback
            print(
                f"Error extracting raw data from {dir_name}:\n"
                f"  - Error type: {type(e).__name__}\n"
                f"  - Error message: {str(e)}\n"
            )
            traceback.print_exc()
            raise
        
        if raw_example:
            try:
                converted_examples = convert_examples([raw_example])
            except Exception as e:
                import traceback
                print(
                    f"Error converting raw example to standardized format for {dir_name}:\n"
                    f"  - Error type: {type(e).__name__}\n"
                    f"  - Error message: {str(e)}\n"
                    f"  - Raw example had {len(raw_example.get('events', []))} events\n"
                    f"  - Task name: {raw_example.get('task_name', 'unknown')}\n"
                )
                traceback.print_exc()
                raise
                
            if converted_examples:
                try:
                    process_trajectory(
                        converted_examples[0], 
                        output_path, 
                        source_path=input_path,
                        raw_events=raw_example.get('events', [])
                    )
                    print(f"Successfully processed {dir_name}")
                except Exception as e:
                    import traceback
                    print(
                        f"Error processing trajectory {dir_name}:\n"
                        f"  - Error type: {type(e).__name__}\n"
                        f"  - Error message: {str(e)}\n"
                    )
                    traceback.print_exc()
                    raise
            else:
                error_msg = (
                    f"Failed to convert raw example to standardized format\n"
                    f"  - Directory: {dir_name}\n"
                    f"  - Raw example had {len(raw_example.get('events', []))} events\n"
                    f"  - Task name: {raw_example.get('task_name', 'unknown')}\n"
                )
                print(error_msg)
                raise Exception(error_msg)
        else:
            error_msg = (
                f"Failed to extract raw data from directory (process_single_directory returned None)\n"
                f"  - Directory: {input_path}\n"
                f"  - This usually means required files are missing or corrupted\n"
                f"  - Check the logs above for specific file errors\n"
            )
            print(error_msg)
            raise Exception(error_msg)
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
                        print(f"Skipping {dir_name}: process_single_directory returned None (check logs above for details)")
                        continue
                        
                    converted_examples = convert_examples([raw_example])
                    if not converted_examples:
                        print(
                            f"Skipping {dir_name}: Failed to convert to standardized format\n"
                            f"  - Raw example had {len(raw_example.get('events', []))} events\n"
                        )
                        continue
                        
                    process_trajectory(
                        converted_examples[0], 
                        output_path, 
                        source_path=item,
                        raw_events=raw_example.get('events', [])
                    )
                    print(f"Successfully processed {dir_name}")
                except Exception as e:
                    import traceback
                    print(
                        f"Error processing {dir_name}:\n"
                        f"  - Error type: {type(e).__name__}\n"
                        f"  - Error message: {str(e)}\n"
                    )
                    traceback.print_exc()
        return

    processed_episode_ids = {item for item in os.listdir(args.output_dir)}

    if args.raw_file.endswith(".json"):
        try:
            with open(args.raw_file, encoding="utf-8") as f:
                raw_examples = oj.loads(f.read())
        except FileNotFoundError:
            print(f"Error: File not found: {args.raw_file}")
            return
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {args.raw_file}: {e}")
            return
        except Exception as e:
            print(f"Error reading {args.raw_file}: {type(e).__name__}: {e}")
            return
            
        if args.num_samples != -1:
            raw_examples = raw_examples[: args.num_samples]
        
        # Ensure it's a list
        if isinstance(raw_examples, dict):
             raw_examples = [raw_examples]

        for raw_example in tqdm(raw_examples):
            episode_id = raw_example.get("episode_id", "unknown")
            if episode_id in processed_episode_ids:
                continue
            
            try:
                converted_examples = convert_examples([raw_example])
                if converted_examples:
                    process_trajectory(
                        converted_examples[0], 
                        output_path,
                        raw_events=raw_example.get('events', [])
                    )
                else:
                    print(f"Failed to convert {episode_id}: convert_examples returned empty list")
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
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON in {raw_file.name}: {e}")
                continue
            except Exception as e:
                print(f"Error reading {raw_file.name}: {type(e).__name__}: {e}")
                continue
                
            try:
                converted_examples = convert_examples([raw_example])
                if not converted_examples:
                    print(f"Failed to convert {raw_file.name}: convert_examples returned empty list")
                    continue
                
                process_trajectory(
                    converted_examples[0], 
                    output_path,
                    raw_events=raw_example.get('events', [])
                )
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
