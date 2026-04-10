"""Recording service for managing recording operations."""

import os
import time
import threading
import pyautogui
from queue import Queue
from datetime import datetime
from typing import Dict, Optional, Tuple

from core.logger import logger
from data_process.export import export_raw_to_vis_std
from core.recorder import Recorder
from core.action_reduction import Reducer
from core.obs_client import OBSClient, is_obs_recording, check_and_stop_recording
from core.screen_utils import get_fresh_screen_resolution
from core.utils import (
    get_task_name_from_folder,
    get_description_from_folder,
    get_video_by_id,
    RECORDING_DIR,
    REVIEW_RECORDING_DIR,
    read_encrypted_jsonl,
    write_encrypted_jsonl,
    read_encrypted_json,
    write_encrypted_json,
    check_recording_visualizable,
    check_recording_broken,
    check_recording_recoverable,
    find_mp4,
    cut_video,
)
from core.backend_func import read_recording_status
from core.constants import SUCCEED, FAILED


class RecordingService:
    """Service for handling recording operations."""

    def __init__(self, socketio):
        self.socketio = socketio
        self.recorder_thread = None
        self.reducer = None
        self.user_recordings = None
        self.opened_single_recording = None

        # Recording configuration
        self.natural_scrolling_checkbox_checked = True
        self.generate_window_a11y = False
        self.generate_element_a11y = True

        # Setup reducer queue processing
        self.reducer_queue = Queue()
        self.reducer_thread = threading.Thread(
            target=self._process_reducer_queue, daemon=True
        )
        self.reducer_thread.start()

        # Check for orphaned recording
        if check_and_stop_recording():
             logger.info("RecordingService: Stopped orphaned OBS recording on startup.")

    def _validate_screen_resolution(self) -> Tuple[str, str]:
        """Validate that screen resolution is 1920x1080."""
        try:
            # Get fresh screen resolution using platform-specific APIs
            # to avoid caching issues with pyautogui/screeninfo
            timestamp = time.time()
            width, height = get_fresh_screen_resolution()
            required_width = 1920
            required_height = 1080
            
            # Always log the current screen size with timestamp
            logger.info(f"RecordingService: [timestamp={timestamp:.2f}] Fresh screen resolution detected: {width}x{height}")
            logger.info(f"RecordingService: Required resolution: {required_width}x{required_height}")
            
            # Also compare with pyautogui to see if there's a discrepancy
            try:
                cached_size = pyautogui.size()
                if (cached_size.width, cached_size.height) != (width, height):
                    logger.warning(
                        f"RecordingService: Resolution mismatch! "
                        f"Fresh API: {width}x{height}, "
                        f"pyautogui (possibly cached): {cached_size.width}x{cached_size.height}"
                    )
            except Exception:
                pass
            
            if width != required_width or height != required_height:
                error_msg = (
                    f"Invalid screen resolution: {width}x{height}. "
                    f"Required resolution is {required_width}x{required_height}. "
                    f"Please adjust your display settings to {required_width}x{required_height} before starting the recording."
                )
                logger.warning(f"RecordingService: {error_msg}")
                return FAILED, error_msg
            
            logger.info(f"RecordingService: Screen resolution validated successfully: {width}x{height}")
            return SUCCEED, "Resolution validated"
        except Exception as e:
            error_msg = f"Failed to check screen resolution: {str(e)}"
            logger.exception(f"RecordingService: {error_msg}")
            return FAILED, error_msg

    def start_recording(self, task_hub_data: Dict) -> Tuple[str, str]:
        """Start a new recording session."""
        logger.info("RecordingService: start_recording")

        if self.recorder_thread is not None:
            return FAILED, "Recording already in progress"

        # Validate screen resolution before starting
        validation_status, validation_message = self._validate_screen_resolution()
        if validation_status == FAILED:
            return FAILED, validation_message

        try:
            self.recorder_thread = Recorder(
                socketio=self.socketio,
                natural_scrolling=self.natural_scrolling_checkbox_checked,
                generate_window_a11y=self.generate_window_a11y,
                generate_element_a11y=self.generate_element_a11y,
            )
            recording_path = self.recorder_thread.recording_path

            width, height = get_fresh_screen_resolution()
            self.reducer = Reducer(
                recording_path=recording_path,
                window_attrs={"width": width, "height": height},
                configs={
                    "generate_window_a11y": self.generate_window_a11y,
                    "generate_element_a11y": self.generate_element_a11y,
                },
            )

            # Handle task hub data if provided
            if task_hub_data:
                self._save_task_hub_data(recording_path, task_hub_data)

            self.recorder_thread.start()
            logger.info("RecordingService: Recording started successfully")
            return SUCCEED, "Recording started successfully"

        except Exception as e:
            self._cleanup_failed_recording()
            logger.exception("RecordingService: start_recording failed")
            return FAILED, f"Failed to start recording: {str(e)}"

    def stop_recording(self) -> Tuple[str, str]:
        """Stop the current recording session."""
        logger.info("RecordingService: stop_recording")

        if not hasattr(self, "recorder_thread") or self.recorder_thread is None:
            return FAILED, "No active recording"

        recording_id: Optional[str] = None
        try:
            recording_id = os.path.basename(
                getattr(self.recorder_thread, "recording_path", "")
            )
            self.recorder_thread.stop_recording()
            if recording_id:
                self._mark_recording_processing(recording_id)
            self.reducer_queue.put(self.reducer)
            self.recorder_thread = None
            logger.info("RecordingService: Recording stopped successfully")
            return SUCCEED, "Recording stopped successfully"

        except Exception as e:
            logger.exception("RecordingService: stop_recording failed")
            return FAILED, f"Failed to stop recording: {str(e)}"

    def recover_recording(self, recording_name: str) -> Tuple[str, str]:
        """Recover a broken recording."""
        logger.info(f"RecordingService: recover_recording: {recording_name}")
        
        recording_path = self._get_recording_path(recording_name, reviewing=False)
        if not os.path.exists(recording_path):
            return FAILED, "Recording not found"

        # Try to stop OBS if it's still running
        try:
             # Just create a client with dummy metadata to check status
            temp_obs_client = OBSClient(
                recording_path=recording_path,
                metadata={"screen_width": 1920, "screen_height": 1080, "system": "Linux"}, # Dummy metadata, exact values don't matter for stopping
            )
            if is_obs_recording(temp_obs_client):
                logger.info("RecordingService: OBS is still recording, stopping it...")
                temp_obs_client.stop_recording()
                # Wait a bit for OBS to finalize the file
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Failed to check/stop OBS: {e}")
            
        # Try to load metadata to get screen size
        try:
            from core.utils import read_encrypted_json
            metadata_path = os.path.join(recording_path, "metadata.json")
            if os.path.exists(metadata_path):
                metadata = read_encrypted_json(metadata_path)
                width = metadata.get("screen_width")
                height = metadata.get("screen_height")
            else:
                width, height = get_fresh_screen_resolution()
                logger.warning(f"Metadata not found for {recording_name}, using current screen size: {width}x{height}")
        except Exception as e:
            logger.warning(f"Failed to load metadata for {recording_name}, using current screen size: {e}")
            width, height = get_fresh_screen_resolution()
            
        try:
            # Check for existing data files
            has_window_a11y = os.path.exists(os.path.join(recording_path, "a11y.jsonl"))
            has_element_a11y = os.path.exists(os.path.join(recording_path, "element.jsonl"))

            # Trim video to the last event timestamp
            try:
                metadata_path = os.path.join(recording_path, "metadata.json")
                events_path = os.path.join(recording_path, "events.jsonl")
                
                if os.path.exists(metadata_path) and os.path.exists(events_path):
                    metadata = read_encrypted_json(metadata_path)
                    video_start_timestamp = metadata.get("video_start_timestamp")
                    
                    # Read the last line of events.jsonl
                    with open(events_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        if lines:
                            import json
                            last_event = json.loads(lines[-1].strip())
                            last_event_timestamp = last_event.get("time_stamp")
                            
                            if video_start_timestamp and last_event_timestamp:
                                duration = last_event_timestamp - video_start_timestamp + 1.0 # Add 1s buffer
                                
                                video_filename = find_mp4(recording_path)
                                if video_filename:
                                    video_path = os.path.join(recording_path, video_filename)
                                    original_video_path = os.path.join(recording_path, f"original_{video_filename}")
                                    
                                    # Rename original video
                                    if not os.path.exists(original_video_path):
                                        os.rename(video_path, original_video_path)
                                        
                                        # Cut video
                                        if cut_video(original_video_path, recording_path, 0, duration):
                                            logger.info(f"Video trimmed to {duration} seconds")
                                            # Rename the output video to the original name (cut_video outputs to video.mp4 inside the folder usually)
                                            # Wait, cut_video implementation: 
                                            # output_file_path = os.path.join(new_video_path, "video.mp4")
                                            # It creates "video.mp4" in the target directory.
                                            
                                            # If the original file was "video.mp4", cut_video will overwrite it if we are not careful?
                                            # cut_video takes (old_path, new_folder_path, start, end)
                                            # It puts "video.mp4" in new_folder_path.
                                            
                                            # If video_filename is not "video.mp4", we should rename the result.
                                            cut_output = os.path.join(recording_path, "video.mp4")
                                            if video_filename != "video.mp4" and os.path.exists(cut_output):
                                                os.rename(cut_output, video_path)
                                            
                                        else:
                                            logger.error("Failed to trim video, restoring original")
                                            if os.path.exists(original_video_path):
                                                os.rename(original_video_path, video_path)
                                    else:
                                         logger.info("Original backup video already exists, skipping trim to avoid data loss.")

            except Exception as e:
                logger.error(f"Error trimming video: {e}")

            self.reducer = Reducer(
                recording_path=recording_path,
                window_attrs={"width": width, "height": height},
                configs={
                    "generate_window_a11y": has_window_a11y,
                    "generate_element_a11y": has_element_a11y,
                },
            )
            
            # Update status to processing immediately
            if self.user_recordings and recording_name in self.user_recordings:
                 self.user_recordings[recording_name]["status"] = "processing"
            else:
                 # Initialize it if not exists (though it should exist if we are recovering it)
                 self.user_recordings = self.user_recordings or {}
                 if recording_name not in self.user_recordings:
                     self.user_recordings[recording_name] = self._create_recording_info(recording_name)
                     self.user_recordings[recording_name]["status"] = "processing"

            # Add to queue
            self.reducer_queue.put(self.reducer)
            
            return SUCCEED, "Recovery started"
        except Exception as e:
            logger.exception(f"Recovery failed: {e}")
            return FAILED, f"Recovery failed: {e}"

    def get_user_recordings(self) -> Dict:
        """Get list of user recordings."""
        logger.info("RecordingService: get_user_recordings")

        if not os.path.exists(RECORDING_DIR):
            os.makedirs(RECORDING_DIR, exist_ok=True)
            return {
                "uploaded_recordings": [],
                "not_uploaded_recordings": [],
            }

        # Handle legacy recording name conversion
        self._convert_legacy_recording_names()

        local_recording_ids = [
            f for f in os.listdir(RECORDING_DIR) if ".ds_store" not in f.lower()
        ]

        if self.user_recordings is not None:
            self._update_existing_recordings(local_recording_ids)
        else:
            self._initialize_recordings(local_recording_ids)

        return {
            "uploaded_recordings": [],
            "not_uploaded_recordings": list(self.user_recordings.values()),
        }

    def get_single_recording(
        self, recording_name: str, reviewing: bool = False
    ) -> Tuple[str, Dict]:
        """Get details of a single recording."""
        logger.info(f"RecordingService: get_single_recording: {recording_name}")

        folder_path = self._get_recording_path(recording_name, reviewing)

        if not os.path.exists(folder_path):
            return FAILED, {"error": "Recording not found"}

        try:
            recording_data = self._build_recording_data(
                recording_name, folder_path, reviewing
            )
            events = self._load_recording_events(folder_path)
            recording_data["events"] = events

            self.opened_single_recording = recording_data
            logger.info("RecordingService: get_single_recording completed")
            return SUCCEED, recording_data

        except Exception as e:
            logger.exception(f"RecordingService: get_single_recording failed: {e}")
            return FAILED, {"error": "Failed to load recording"}

    def confirm_recording(
        self, recording_name: str, events_data: list
    ) -> Tuple[str, str]:
        """Confirm and save recording modifications."""
        logger.info("RecordingService: confirm_recording")

        if self.opened_single_recording is None:
            return FAILED, "No recording opened"

        try:
            folder_path = os.path.join(RECORDING_DIR, recording_name)
            self._remove_unused_videos(folder_path, events_data)
            self._save_modified_events(folder_path, events_data)
            return SUCCEED, "Recording modifications saved successfully"

        except Exception as e:
            logger.exception("RecordingService: confirm_recording failed")
            return FAILED, f"Failed to confirm recording: {str(e)}"

    def get_video_path(
        self, recording_name: str, event_index: str, verifying: bool = False
    ) -> Tuple[str, Dict]:
        """Get video path for a specific event."""
        if self.opened_single_recording is None:
            return FAILED, {"error": "No recording opened"}

        if self.opened_single_recording["recording_name"] != recording_name:
            return FAILED, {"error": "Wrong recording opened"}

        try:
            videos_folder_path = self._get_videos_folder_path(recording_name, verifying)
            event = self.opened_single_recording["events"][int(event_index)]
            video_name = get_video_by_id(video_path=videos_folder_path, id=event["id"])

            return SUCCEED, {
                "success": "Video path retrieved successfully",
                "path": os.path.join(videos_folder_path, video_name),
            }

        except Exception as e:
            logger.warning(f"RecordingService: get_video_path failed: {e}")
            return FAILED, {"error": str(e)}

    def regenerate_clip(
        self, recording_name: str, event_index: int, verifying: bool = False
    ) -> Tuple[str, Dict]:
        """Regenerate the video clip for a single event with full visual overlays.

        Reconstructs the Action object from reduced_events_complete.jsonl and calls
        action.to_video() so that click circles, drag arrows, and scroll arrows are
        drawn exactly as in the original reduction pipeline.
        """
        import json as _json
        from core.action_reduction.action import reconstruct_action

        recording_path = self._get_recording_path(recording_name, verifying)
        videos_folder_path = self._get_videos_folder_path(recording_name, verifying)

        if not os.path.exists(recording_path):
            return FAILED, {"error": "Recording not found"}

        metadata_path = os.path.join(recording_path, "metadata.json")
        if not os.path.exists(metadata_path):
            return FAILED, {"error": "metadata.json not found"}

        try:
            with open(metadata_path) as f:
                metadata = _json.load(f)

            video_start_time = metadata.get("video_start_timestamp")
            if video_start_time is None:
                return FAILED, {"error": "video_start_timestamp not found in metadata"}

            screen_width = metadata.get("screen_width")
            screen_height = metadata.get("screen_height")
            if screen_width is None or screen_height is None:
                return FAILED, {"error": "screen_width/screen_height not found in metadata"}

            complete_events_path = os.path.join(recording_path, "reduced_events_complete.jsonl")
            if not os.path.exists(complete_events_path):
                return FAILED, {"error": "reduced_events_complete.jsonl not found"}

            complete_events = read_encrypted_jsonl(complete_events_path)
            if event_index < 0 or event_index >= len(complete_events):
                return FAILED, {"error": f"Event index {event_index} out of range"}

            event_data = complete_events[event_index]

            video_file = find_mp4(recording_path)
            if not video_file:
                return FAILED, {"error": "Source video file not found"}

            video_path = os.path.join(recording_path, video_file)
            video_attrs = {
                "video_start_time": video_start_time,
                "video_path": video_path,
            }
            window_attrs = {
                "width": screen_width,
                "height": screen_height,
            }

            os.makedirs(videos_folder_path, exist_ok=True)

            action = reconstruct_action(event_data)
            # to_video writes into recording_path/video_clips/{id}_{action}.mp4
            action.to_video(recording_path, video_attrs, window_attrs)

            event_id = event_data["id"]
            event_action = event_data["action"]
            clip_name = f"{event_id}_{event_action}.mp4"
            output_path = os.path.join(videos_folder_path, clip_name)

            if not os.path.exists(output_path):
                return FAILED, {"error": "Clip file was not created by to_video"}

            return SUCCEED, {
                "success": "Clip regenerated successfully",
                "path": output_path,
                "clip_name": clip_name,
            }

        except Exception as e:
            logger.exception(f"RecordingService: regenerate_clip failed: {e}")
            return FAILED, {"error": str(e)}

    def toggle_window_a11y(self, flag: bool) -> None:
        """Toggle window accessibility generation."""
        self.generate_window_a11y = flag
        logger.info(f"RecordingService: generate_window_a11y set to {flag}")

    def _save_task_hub_data(self, recording_path: str, task_hub_data: Dict) -> None:
        """Save task hub data to recording directory."""
        hub_task_id = task_hub_data.get("hub_task_id")
        if hub_task_id:
            with open(os.path.join(recording_path, "hub_task_id.txt"), "w") as f:
                f.write(hub_task_id)

            task_name = task_hub_data.get("hub_task_name")
            description = task_hub_data.get("hub_task_description", "")
            if task_name:
                write_encrypted_json(
                    os.path.join(recording_path, "task_name.json"),
                    data={"task_name": task_name, "description": description},
                )

    def _cleanup_failed_recording(self) -> None:
        """Clean up resources after failed recording."""
        if hasattr(self, "recorder_thread") and self.recorder_thread:
            self.recorder_thread.stop()
        self.recorder_thread = None
        self.reducer = None

    def _process_reducer_queue(self) -> None:
        """Process the reducer queue in background thread."""
        while True:
            reducer = self.reducer_queue.get()
            if reducer is None:
                self.reducer_queue.task_done()
                continue

            recording_id = os.path.basename(
                getattr(reducer, "recording_path", "")
            )
            try:
                reducer.reduce_pipeline()
                self._mark_recording_ready(recording_id)
                self.socketio.emit(
                    "reduced",
                    {"status": "succeed", "message": "Recording processing completed"},
                )
            except Exception as e:
                logger.exception(f"RecordingService: Error in reduce_pipeline: {e}")
                self._mark_recording_ready(recording_id)
                self.socketio.emit(
                    "reduced",
                    {"status": "failed", "message": "Recording processing failed"},
                )
            finally:
                self.reducer_queue.task_done()

    def _mark_recording_processing(self, recording_id: str) -> None:
        if not recording_id:
            return
        if self.user_recordings is None:
            self.user_recordings = {}

        if recording_id not in self.user_recordings:
            self.user_recordings[recording_id] = self._create_recording_info(
                recording_id
            )

        recording = self.user_recordings[recording_id]
        recording["status"] = "processing"
        recording["visualizable"] = False
        recording["broken"] = False
        recording["recoverable"] = False

    def _mark_recording_ready(self, recording_id: str) -> None:
        if not recording_id or not self.user_recordings:
            return
        if recording_id in self.user_recordings:
            self.user_recordings[recording_id]["status"] = "local"

    def _convert_legacy_recording_names(self) -> None:
        """Convert legacy recording names to recording IDs."""
        for recording_name in os.listdir(RECORDING_DIR):
            if recording_name.startswith("recording"):
                recording_status = read_recording_status(
                    recording_path=os.path.join(RECORDING_DIR, recording_name)
                )
                if recording_status:
                    old_path = os.path.join(RECORDING_DIR, recording_name)
                    new_path = os.path.join(
                        RECORDING_DIR, recording_status["recording_id"]
                    )
                    os.rename(old_path, new_path)
                else:
                    logger.error(f"Invalid recording {recording_name}, removing")
                    # TODO: Use proper file deletion utility

    def _update_existing_recordings(self, local_recording_ids: list) -> None:
        """Update existing recordings list with local changes."""
        # Remove deleted recordings
        for recording_id in list(self.user_recordings.keys()):
            if recording_id not in local_recording_ids:
                del self.user_recordings[recording_id]

        # Add new recordings
        new_recording_ids = []
        for recording_id in local_recording_ids:
            if recording_id not in self.user_recordings:
                new_recording_ids.append(recording_id)
                recording = self._create_recording_info(recording_id)
                self.user_recordings[recording_id] = recording

        # Update existing recordings
        for recording_id, recording in self.user_recordings.items():
            if recording_id not in new_recording_ids:
                self._update_recording_info(recording, recording_id, False)

    def _initialize_recordings(self, local_recording_ids: list) -> None:
        """Initialize recordings list from scratch."""
        local_recordings = {}
        for recording_name in local_recording_ids:
            local_recordings[recording_name] = self._create_recording_info(
                recording_name
            )

        self.user_recordings = local_recordings

    def _create_recording_info(self, recording_name: str) -> Dict:
        """Create recording info dictionary."""
        recording_path = os.path.join(RECORDING_DIR, recording_name)

        recording = {
            "name": recording_name,
            "task_name": get_task_name_from_folder(recording_name, reviewing=False),
            "task_description": get_description_from_folder(
                recording_name, reviewing=False
            ),
            "status": "local",
            "verify_feedback": None,
            "uploaded": False,
            "visualizable": True,  # Simplified for now
            "broken": False,
            "recoverable": False
        }

        # Add creation time
        creation_time = os.path.getctime(recording_path)
        recording["creation_time"] = datetime.fromtimestamp(creation_time).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        return recording

    def _update_recording_info(
        self, recording: Dict, recording_name: str, reviewing: bool
    ) -> Dict:
        """Update recording info with latest data."""
        # Only set status to local if it's not currently processing
        if recording.get("status") != "processing":
            recording["status"] = "local"
            
        recording["task_name"] = get_task_name_from_folder(recording_name, reviewing)
        recording["task_description"] = get_description_from_folder(
            recording_name, reviewing
        )
        recording["visualizable"] = check_recording_visualizable(
            recording_name, reviewing
        )
        recording["broken"] = check_recording_broken(recording_name, reviewing)
        recording["recoverable"] = check_recording_recoverable(recording_name, reviewing)
        return recording

    def _get_recording_path(self, recording_name: str, reviewing: bool) -> str:
        """Get the full path to a recording directory."""
        base_dir = REVIEW_RECORDING_DIR if reviewing else RECORDING_DIR
        return os.path.join(base_dir, recording_name)

    def _build_recording_data(
        self, recording_name: str, folder_path: str, reviewing: bool
    ) -> Dict:
        """Build recording data dictionary."""
        recording_data = {
            "recording_id": recording_name,
            "recording_name": recording_name,
        }

        # Get recording info from cache
        recordings_cache = (
            self.user_recordings if not reviewing else {}
        )  # TODO: handle review recordings
        if recordings_cache and recording_name in recordings_cache:
            recording_info = recordings_cache.get(recording_name, {})
            recording_data.update(recording_info)

        # Add task info for non-uploaded recordings
        if not recording_data.get("uploaded", False):
            recording_data.update(
                {
                    "task_name": get_task_name_from_folder(recording_name, reviewing),
                    "description": get_description_from_folder(
                        recording_name, reviewing
                    ),
                    "verify_status": "local",
                    "verify_feedback": None,
                }
            )

        return recording_data

    def _load_recording_events(self, folder_path: str) -> list:
        """Load events from recording directory."""
        events_file_path = os.path.join(folder_path, "reduced_events_vis.jsonl")
        if not os.path.exists(events_file_path):
            raise FileNotFoundError("reduced_events.jsonl file not found")

        return read_encrypted_jsonl(events_file_path)

    def _remove_unused_videos(self, folder_path: str, events_data: list) -> None:
        """Remove video files that are no longer used."""
        ids_left = [event["id"] for event in events_data]
        for action in self.opened_single_recording["events"]:
            if action["id"] not in ids_left:
                video_path = os.path.join(
                    folder_path, "video_clips", f"{action['id']}_{action['action']}.mp4"
                )
                if os.path.exists(video_path):
                    os.remove(video_path)
                    logger.info(
                        f"RecordingService: Removed {action['id']}_{action['action']}.mp4"
                    )

    def _save_modified_events(self, folder_path: str, events_data: list) -> None:
        """Save modified events to files."""
        # Update opened recording
        self.opened_single_recording["events"] = events_data

        # Save visual events
        vis_events_path = os.path.join(folder_path, "reduced_events_vis.jsonl")
        write_encrypted_jsonl(vis_events_path, events_data)

        # Save complete events
        complete_events_path = os.path.join(
            folder_path, "reduced_events_complete.jsonl"
        )
        if os.path.exists(complete_events_path):
            complete_events_data = read_encrypted_jsonl(complete_events_path)
            
            # Create mapping of id -> description from UI-modified events
            vis_descriptions = {event["id"]: event["description"] for event in events_data}
            
            ids_left = [event["id"] for event in events_data]
            new_complete_data = []
            for action in complete_events_data:
                if action["id"] in ids_left:
                    # Sync description from vis file to maintain consistency
                    if action["id"] in vis_descriptions:
                        action["description"] = vis_descriptions[action["id"]]
                    new_complete_data.append(action)
            
            write_encrypted_jsonl(complete_events_path, new_complete_data)

    def _get_videos_folder_path(self, recording_name: str, verifying: bool) -> str:
        """Get path to videos folder."""
        base_dir = REVIEW_RECORDING_DIR if verifying else RECORDING_DIR
        return os.path.join(base_dir, recording_name, "video_clips")

    def export_recording(self, recording_name: str, output_path: str) -> None:
        """Export a single recording to the specified path."""
        recording_path = os.path.join(RECORDING_DIR, recording_name)
        self._run_export_script(recording_path, output_path)

    def export_all_recordings(self, output_path: str) -> None:
        """Export all valid recordings to the specified path."""
        self._run_export_script(RECORDING_DIR, output_path)

    def _run_export_script(self, input_path: str, output_path: str) -> None:
        """Run the export function directly (no subprocess)."""
        try:
            logger.info(f"Exporting from {input_path} to {output_path}")
            
            # Ensure input and output paths are absolute
            abs_input = os.path.abspath(input_path)
            abs_output = os.path.abspath(output_path)
            
            # Ensure output directory exists
            os.makedirs(abs_output, exist_ok=True)
            
            # Call the export function directly
            export_raw_to_vis_std(abs_input, abs_output)
            
            logger.info(f"Export successful")
        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            raise Exception(f"Export failed: {str(e)}")

    def update_recording_name(self, recording_name: str, new_task_name: str) -> Tuple[str, str]:
        """Update the task name for a recording."""
        try:
            recording_path = os.path.join(RECORDING_DIR, recording_name)
            task_name_path = os.path.join(recording_path, "task_name.json")
            
            if not os.path.exists(recording_path):
                return FAILED, f"Recording {recording_name} not found"
            
            # Read existing task data or create new
            if os.path.exists(task_name_path):
                task_data = read_encrypted_json(task_name_path)
            else:
                task_data = {"task_name": "", "description": ""}
            
            # Update task name
            task_data["task_name"] = new_task_name
            
            # Write back to file
            write_encrypted_json(task_name_path, task_data)
            
            logger.info(f"Updated task name for recording {recording_name} to: {new_task_name}")
            return SUCCEED, f"Task name updated successfully"
            
        except Exception as e:
            logger.error(f"Failed to update task name for recording {recording_name}: {str(e)}")
            return FAILED, f"Failed to update task name: {str(e)}"

