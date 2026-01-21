import json
import os
import base64
import io
from pathlib import Path
from tqdm import tqdm
from PIL import Image
from data_process.schema.trajectory import Trajectory
from data_process.schema.action import GUIAction, ImageObservation, TextObservation

def convert(input_dir, output_dir):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {input_path} for JSON files...")
    files = list(input_path.glob('*.json'))
    print(f"Found {len(files)} files.")

    for file_path in tqdm(files, desc="Converting"):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Skip if basic validation fails or validation against schema fails
            try:
                traj_data = Trajectory(**data)
            except Exception as e:
                print(f"Validation error in {file_path.name}: {e}")
                continue

            # Use example_id if available, otherwise task_id
            example_id = traj_data.example_id if traj_data.example_id else traj_data.task_id
            
            # Create folder with just the ID
            task_dir_name = f"{example_id}"
            task_dir = output_path / task_dir_name
            task_dir.mkdir(parents=True, exist_ok=True)

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
                                codes = []
                                for action in item.guiactions:
                                    # Convert normalized coordinates to absolute
                                    if 'x' in action.args and 'y' in action.args:
                                        if isinstance(action.args['x'], float) and width > 0:
                                            action.args['x'] = int(action.args['x'] * width)
                                        if isinstance(action.args['y'], float) and height > 0:
                                            action.args['y'] = int(action.args['y'] * height)
                                    
                                    # Additional coordinate conversion might be needed for other action types (drag, etc)
                                    # PyAutoGUIAction defaults to x, y. 
                                    # MobileAction has from_coord, to_coord. But this seems to be desktop data mostly.
                                    # Let's handle 'from_coord' and 'to_coord' if present (list of [x, y])
                                    
                                    if 'from_coord' in action.args and isinstance(action.args['from_coord'], (list, tuple)):
                                        fx, fy = action.args['from_coord']
                                        action.args['from_coord'] = (int(fx * width), int(fy * height))
                                    
                                    if 'to_coord' in action.args and isinstance(action.args['to_coord'], (list, tuple)):
                                        tx, ty = action.args['to_coord']
                                        action.args['to_coord'] = (int(tx * width), int(ty * height))

                                    codes.append(action.to_command())
                                
                                code_str = "\n".join(codes)

                                new_traj.append({
                                    "index": step_idx,
                                    "code": code_str,
                                    "screenshot": img_filename
                                })
                                step_idx += 1
                            except Exception as e:
                                print(f"Error saving image or processing action in {file_path.name}: {e}")
                                import traceback
                                traceback.print_exc()

            output_json = {
                "task_id": example_id,
                "instruction": instruction,
                "traj": new_traj
            }

            # Put the json file under the folder
            with open(task_dir / f"{example_id}.json", 'w') as f:
                json.dump(output_json, f, indent=4)
                
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print("Usage: python -m src.standardized_to_vis <input_dir> <output_dir>")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    convert(input_dir, output_dir)
