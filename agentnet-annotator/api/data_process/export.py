"""
Export module for converting raw recordings to visualization format.
This module provides a direct Python API for exporting recordings,
replacing the previous subprocess-based approach.
"""

import os
from pathlib import Path
from typing import Union

from data_process.raw_to_vis_std import process_single_directory, convert_examples, process_trajectory


def export_raw_to_vis_std(input_path: Union[str, Path], output_path: Union[str, Path]) -> None:
    """
    Export raw recordings to visualization standard format.
    
    This function processes raw recording directories and converts them to the
    visualization standard format used by the application.
    
    Args:
        input_path: Path to raw recording(s). Can be:
            - A single raw recording directory (contains metadata.json)
            - A directory containing multiple raw recording directories
            - A JSON file or directory of JSON files
        output_path: Directory where visualization format will be saved
        
    Raises:
        FileNotFoundError: If input_path doesn't exist
        Exception: If processing fails
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Get list of already processed recordings
    processed_episode_ids = {item for item in os.listdir(output_path)} if output_path.exists() else set()
    
    # Check if input is a single raw recording directory
    if input_path.is_dir() and (input_path / "metadata.json").exists():
        print(f"Processing single raw recording directory: {input_path}")
        parent_dir = str(input_path.parent)
        dir_name = input_path.name
        
        if dir_name in processed_episode_ids:
            print(f"Skipping {dir_name} - already processed")
            return
        
        # Extract raw trajectory from folder
        try:
            raw_example = process_single_directory(parent_dir, dir_name, load_image=True)
        except Exception as e:
            import traceback
            error_msg = (
                f"Failed to extract raw data from directory: {input_path}\n"
                f"Error type: {type(e).__name__}\n"
                f"Error message: {str(e)}\n"
                f"Traceback:\n"
            )
            traceback.print_exc()
            print(error_msg)
            raise Exception(error_msg) from e
        
        if raw_example:
            converted_examples = convert_examples([raw_example])
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
                    error_msg = (
                        f"Failed to process trajectory for {dir_name}\n"
                        f"Error type: {type(e).__name__}\n"
                        f"Error message: {str(e)}\n"
                        f"Input path: {input_path}\n"
                        f"Output path: {output_path}\n"
                    )
                    traceback.print_exc()
                    print(error_msg)
                    raise Exception(error_msg) from e
            else:
                error_msg = (
                    f"Failed to convert raw example to standardized format\n"
                    f"Directory: {dir_name}\n"
                    f"Input path: {input_path}\n"
                    f"Raw example had {len(raw_example.get('events', []))} events\n"
                    f"Task name: {raw_example.get('task_name', 'unknown')}\n"
                )
                print(error_msg)
                raise Exception(error_msg)
        else:
            # Check what files exist in the directory for better debugging
            dir_contents = list(input_path.iterdir()) if input_path.exists() else []
            has_metadata = (input_path / "metadata.json").exists()
            has_video = any(f.suffix == '.mp4' for f in dir_contents)
            has_vis_events = (input_path / "reduced_events_vis.jsonl").exists()
            has_complete_events = (input_path / "reduced_events_complete.jsonl").exists()
            
            error_msg = (
                f"Failed to extract raw data from directory: {input_path}\n"
                f"Directory exists: {input_path.exists()}\n"
                f"Has metadata.json: {has_metadata}\n"
                f"Has .mp4 video: {has_video}\n"
                f"Has reduced_events_vis.jsonl: {has_vis_events}\n"
                f"Has reduced_events_complete.jsonl: {has_complete_events}\n"
                f"Files in directory: {[f.name for f in dir_contents[:10]]}\n"
                f"\nThis likely means one of the required files is missing or corrupted.\n"
            )
            print(error_msg)
            raise Exception(error_msg)
        return
    
    # Check if input is a directory of raw recordings
    if input_path.is_dir() and not (input_path / "metadata.json").exists() and not list(input_path.glob("*.json")):
        print(f"Processing directory of raw recordings: {input_path}")
        parent_dir = str(input_path)
        
        # Iterate over all subdirectories
        for item in input_path.iterdir():
            if item.is_dir() and (item / "metadata.json").exists():
                dir_name = item.name
                if dir_name in processed_episode_ids:
                    print(f"Skipping {dir_name} - already processed")
                    continue
                
                try:
                    print(f"Processing {dir_name}...")
                    raw_example = process_single_directory(parent_dir, dir_name, load_image=True)
                    if not raw_example:
                        # Check what files exist for debugging
                        has_metadata = (item / "metadata.json").exists()
                        has_video = any(f.suffix == '.mp4' for f in item.iterdir())
                        has_vis_events = (item / "reduced_events_vis.jsonl").exists()
                        has_complete_events = (item / "reduced_events_complete.jsonl").exists()
                        print(
                            f"Failed to extract raw data from {dir_name}\n"
                            f"  - Has metadata.json: {has_metadata}\n"
                            f"  - Has .mp4 video: {has_video}\n"
                            f"  - Has reduced_events_vis.jsonl: {has_vis_events}\n"
                            f"  - Has reduced_events_complete.jsonl: {has_complete_events}\n"
                        )
                        continue
                    
                    converted_examples = convert_examples([raw_example])
                    if not converted_examples:
                        print(
                            f"Failed to convert {dir_name}\n"
                            f"  - Raw example had {len(raw_example.get('events', []))} events\n"
                            f"  - Task name: {raw_example.get('task_name', 'unknown')}\n"
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
                    # Continue with other recordings even if one fails
                    continue
        return
    
    # If we get here, the input format is not supported
    raise ValueError(
        f"Unsupported input format. Expected:\n"
        f"  - A raw recording directory (contains metadata.json)\n"
        f"  - A directory containing raw recording directories\n"
        f"  - A JSON file or directory of JSON files\n"
        f"Got: {input_path}"
    )
