import json
import os
from datetime import datetime
from platform import uname

from .logger import logger
from .screen_utils import get_fresh_screen_resolution


class MetadataManager:
    """
    Handles various system metadata collection.
    """

    def __init__(self, recording_path: str, natural_scrolling: bool):
        self.recording_path = recording_path

        self.metadata = uname()._asdict()
        if "node" in self.metadata:
            del self.metadata["node"]

        # Get fresh (non-cached) screen resolution using platform-specific APIs
        width, height = get_fresh_screen_resolution()
        self.metadata["screen_width"] = width
        self.metadata["screen_height"] = height
        
        logger.info(f"MetadataManager: Detected screen resolution: {width}x{height}")

        try:
            match self.metadata["system"]:
                case "Windows":
                    import wmi

                    for item in wmi.WMI().Win32_ComputerSystem():
                        self.metadata["model"] = item.Model
                        break
                case "Darwin":
                    import subprocess

                    model = (
                        subprocess.check_output(["sysctl", "-n", "hw.model"])
                        .decode()
                        .strip()
                    )
                    self.metadata["model"] = model
                case "Linux":
                    with open("/sys/devices/virtual/dmi/id/product_name", "r") as f:
                        self.metadata["model"] = f.read().strip()
        except:
            self.metadata["model"] = "Unknown"

        self.metadata["scroll_direction"] = -1 if natural_scrolling else 1

    def save_metadata(self):
        metadata_path = os.path.join(self.recording_path, "metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(self.metadata, f, indent=4, ensure_ascii=False)

    def collect(self):
        self.metadata["start_time"] = self._get_time_stamp()

    def end_collect(self):
        self.metadata["stop_time"] = self._get_time_stamp()

    def add_obs_record_state_timings(self, record_state_events: dict[str, float]):
        self.metadata["obs_record_state_timings"] = record_state_events

    def _get_time_stamp(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def set_video_start_timestamp(self, timestamp: float):
        self.metadata["video_start_timestamp"] = timestamp
