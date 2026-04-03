import os
import av
import cv2
import numpy as np
from collections import OrderedDict
from typing import List, Dict, Optional

from copy import deepcopy

# When True, Type clips are produced via stream-copy (no decode/re-encode).
# The key-name overlay is skipped, but generation is orders of magnitude faster.
SKIP_TYPE_OVERLAY = True

if __name__ == "__main__":
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.abspath(os.path.join(current_dir, "../../"))
    sys.path.append(parent_dir)
    from api.core.action_reduction.reduction_helper import (
        MODIFIED_KEYS, MOUSE_LONG_PRESS_INTERVAL,
        wrap_func_key,
    )
    from api.core.logger import logger
else:
    from .reduction_helper import (
        MODIFIED_KEYS, MOUSE_LONG_PRESS_INTERVAL,
        wrap_func_key,
    )
    from ..logger import logger


class ActionBuilder:
    @staticmethod
    def build(event):
        action_type = event["action"]
        if action_type == "move":
            return Move(event)
        elif action_type == "click":
            return Click(event)
        elif action_type == "press":
            key_name = event["name"]
            if key_name not in MODIFIED_KEYS:
                return Type(event)
            else:
                return Press(event)
        elif action_type == "type":
            return Type(event)
        elif action_type == "scroll":
            return Scroll(event)
        else:
            raise ValueError(f"Event type {action_type} is not supported.")


class Action:
    def __init__(self, event) -> None:
        self.pre_move = None
        if "pre_move" in event:
            self.pre_move = Move(event["pre_move"])
        # TODO: each action should have action id and event start, end id
        self.event_start_idx = event["event_idx"]
        self.children: Optional[List[Action]] = None
        self.complete: bool = event["complete"]
        self.action: str = event["action"]
        self.start_time: float = event["start_time"]
        self.end_time: float = event["end_time"]
        self.key: tuple = event["key"]
        self.transformed: bool = False
        self.description: str = None
        self.vis: bool = True
        self.show_all_move: bool = False
        self.exception = False
        self.depth = 0
        self.base_ignore_attrs: list = [
            "vis_dump_attrs",
            "ignore_log_attr_names",
            "complete_dump_excluded_attrs",
            "key",
            "show_all_move",
            "transformed",
            "excluded_attrs",
            "base_ignore_attrs",
            "pre_move",
            "children",
            "action_start_video_buffer_time",
            "action_end_video_buffer_time",
        ]

        self.complete_dump_excluded_attrs: list = self.base_ignore_attrs
        self.vis_dump_attrs: list = [
            "id",
            "action",
            "description",
            "start_time",
            "end_time",
            "time_stamp",
            "depth"
        ]

        self.action_start_video_buffer_time = 0.5
        self.action_end_video_buffer_time = 0.2
        self.target = None
        self.axtree = None
        self.past_frame_target = None
        self.gpt_target = None

    def set_id(self, id: int):
        self.id = id

    def get_start_time(self) -> float:
        if self.pre_move is not None:
            return self.pre_move.get_start_time()
        else:
            return self.start_time

    def get_str(self, connect_str=""):
        s = wrap_func_key(self.key_names[0])
        for i in range(1, len(self.key_names)):
            s += connect_str + wrap_func_key(self.key_names[i])
        return s

    def get_end_time(self) -> float | None:
        if self.end_time is not None:
            return self.end_time
        elif self.children is None:
            return self.start_time
        else:
            return self.children[-1].get_end_time()

    def set_pre_move(self, action):
        if isinstance(action, dict):
            self.pre_move = Move(action)
        else:
            self.pre_move = action

    def add_child(self, child_action):
        if not isinstance(child_action, Action):
            child_action = ActionBuilder.build(child_action)

        if self.children is None:
            self.children = []

        self.children.append(child_action)

    def transform(self):
        self.transformed = True

    def complete_dump(self):
        """
        Dump the action's information into a Dict
        Presever the complete information as the raw data.
        """
        attrs = vars(self)

        ordered_attrs = OrderedDict()
        ordered_attrs["action"] = self.action

        self.complete_dump_excluded_attrs += [
            key
            for key in attrs
            if attrs[key] is None or key in self.complete_dump_excluded_attrs
        ]

        for k, v in attrs.items():
            if k not in self.complete_dump_excluded_attrs and k not in ordered_attrs:
                ordered_attrs[k] = v

        if self.pre_move is not None:
            ordered_attrs["pre_move"] = self.pre_move.complete_dump()
        if self.children is not None:
            ordered_attrs["children"] = [
                child.complete_dump() for child in self.children
            ]

        return ordered_attrs

    def vis_dump(self):
        """
        Dump the action into a Dict
        Simplify attributes for visualization
        """
        if self.vis == False:
            return None

        attrs = vars(self)

        ordered_attrs = OrderedDict()
        for k in self.vis_dump_attrs:
            if k in attrs and k not in ordered_attrs:
                ordered_attrs[k] = attrs[k]

        if self.target is not None:
            ordered_attrs["target"] = self.target
        else:
            ordered_attrs["target"] = {"mark": False}

        if self.gpt_target is not None:
            ordered_attrs["gpt_target"] = self.gpt_target

        ordered_attrs["axtree"] = self.axtree
        if self.past_frame_target is not None:
            ordered_attrs["past_frame_target"] = self.past_frame_target

        if self.children is not None and len(self.children) > 0:
            ordered_attrs["children"] = []
            for child in self.children:
                if child.vis == True:
                    child_attrs = child.vis_dump()
                    ordered_attrs["children"].append(child_attrs)
        if "children" in ordered_attrs and len(ordered_attrs["children"]) == 0:
            del ordered_attrs["children"]

        return ordered_attrs

    def _get_video_start_time(self):
        """
        Get video start time
        """
        if self.pre_move is not None:
            return max(
                self.pre_move.get_start_time(),
                self.start_time - self.action_start_video_buffer_time,
            )
        else:
            return self.start_time

    def _get_video_end_time(self):
        if self.end_time is not None:
            return self.end_time + self.action_end_video_buffer_time
        elif self.children is None:
            return self.start_time + 0.2  # exception case
        else:
            return self.children[-1]._get_video_end_time()

    def _get_video_name(self, recording_path):
        # Prefer files that don't start with "original" (those are backups).
        candidates = sorted(
            (f for f in os.listdir(recording_path) if f.endswith(".mp4")),
            key=lambda f: (f.startswith("original"), f),
        )
        return candidates[0] if candidates else None

    def process_start_end_time(self, start_time, end_time):
        if end_time - start_time < 0.5:
            start_time = start_time - 0.3
            end_time = end_time + 0.1
        return start_time, end_time

    def to_video(self, recording_path, video_attrs, window_attrs):
        video_start_time = video_attrs["video_start_time"]
        start_time = self._get_video_start_time() - video_start_time
        end_time = self._get_video_end_time() - video_start_time
        start_time, end_time = self.process_start_end_time(
            start_time, end_time)

        video_clip_name = f"{self.id}_{self.action}"

        if end_time <= start_time:
            logger.warning(
                f"action.py to_video error: Invalid time range for action {self.id}. Skipping."
            )
            return

        video_path = video_attrs.get("video_path")
        if video_path is None:
            video_name = self._get_video_name(recording_path)
            video_path = os.path.join(recording_path, video_name)

        fps = video_attrs.get("fps")
        width = video_attrs.get("width")
        height = video_attrs.get("height")
        total_frames = video_attrs.get("total_frames")

        os.makedirs(os.path.join(recording_path, "video_clips"), exist_ok=True)
        output_path = os.path.join(
            recording_path, "video_clips", f"{video_clip_name}.mp4"
        )

        codec_name = "libx264" if "libx264" in av.codec.codecs_available else "mpeg4"

        with av.open(video_path) as src, av.open(output_path, mode="w") as dst:
            in_stream = src.streams.video[0]

            # Resolve metadata from stream if not pre-populated by Reducer.
            if fps is None:
                fps = int(float(in_stream.average_rate))
            if width is None:
                width = in_stream.width
            if height is None:
                height = in_stream.height
            if total_frames is None or total_frames == 0:
                if in_stream.frames:
                    total_frames = in_stream.frames
                elif in_stream.duration and in_stream.time_base:
                    total_frames = int(
                        in_stream.duration * float(in_stream.time_base) * fps
                    )
                else:
                    total_frames = 2 ** 31

            out_stream = dst.add_stream(codec_name, rate=fps)
            out_stream.width = width
            out_stream.height = height
            out_stream.pix_fmt = "yuv420p"
            if codec_name == "libx264":
                out_stream.options = self._get_encoder_options()

            local_video_attrs = {
                "fps": fps,
                "width": width,
                "height": height,
                "total_frames": total_frames,
                "video_start_time": video_attrs["video_start_time"],
            }

            start_frame = max(0, int(start_time * fps))
            end_frame = min(total_frames, int(end_time * fps))
            max_frames = end_frame - start_frame

            annotate = self._make_annotator(
                start_time, end_time, start_frame, local_video_attrs, window_attrs
            )

            start_pts = int(start_time / float(in_stream.time_base))
            src.seek(start_pts, stream=in_stream)

            frame_count = 0
            done = False
            for packet in src.demux(in_stream):
                if packet.dts is None:
                    break
                for frame in packet.decode():
                    if frame.pts is None:
                        continue
                    frame_time = float(frame.pts * in_stream.time_base)
                    if frame_time < start_time:
                        continue
                    if frame_time >= end_time or frame_count >= max_frames:
                        done = True
                        break
                    img = frame.to_ndarray(format="bgr24")
                    img = annotate(img, start_frame + frame_count)
                    out_frame = av.VideoFrame.from_ndarray(img, format="bgr24")
                    out_frame.pts = frame_count
                    for p in out_stream.encode(out_frame):
                        dst.mux(p)
                    frame_count += 1
                if done:
                    break

            for p in out_stream.encode():
                dst.mux(p)

    def _get_encoder_options(self) -> dict:
        """libx264 options for this action type. Override in subclasses as needed."""
        return {"preset": "medium", "crf": "28"}

    def _make_annotator(self, start_time, end_time, start_frame, video_attrs, window_attrs):
        """Return a callable (img, frame_number) -> img for per-frame annotation."""
        def annotate(img, frame_number):
            return img
        return annotate


class Move(Action):
    def __init__(self, event):
        super().__init__(event)
        self.trace = event["trace"]
        self.time_trace = event["time_trace"]
        self.vis = False

    def transform(self):
        super().transform()
        self.description = "Mouse move from {} to {}".format(
            self.trace[0], self.trace[-1]
        )


class Type(Action):
    def __init__(self, event):
        super().__init__(event)
        if event["action"] == "type":
            self.action = event["action"]
            self.key_names = event["key_names"]
            
        elif event["action"] == "press":
            self.action = "type"
            self.key_names = [event["name"]]
            
        self.time_trace = [event["time_stamp"]]
        self.end_time = self.time_trace[-1] + 0.2
        
        self.action_start_video_buffer_time = 0.5
        self.action_end_video_buffer_time = 0.2

    def append(self, event):
        if isinstance(event, dict):
            self.key_names.append(event["name"])
            self.time_trace.append(event["time_stamp"])
            self.end_time = self.time_trace[-1] + 0.2
        elif isinstance(event, Type):
            self.key_names.extend(event.key_names)
            self.time_trace.extend(event.time_trace)
            self.end_time = self.time_trace[-1] + 0.2

    def extend(self, action):
        self.key_names.extend(action.key_names)
        self.time_trace.extend(action.time_trace)
        self.end_time = self.time_trace[-1] + 0.2

    def transform(self):
        super().transform()
        self.description = "⌨️ Type: "
        for key in self.key_names:
            self.description += wrap_func_key(key)
        logger.error("transform {}".format(self.key_names))

    def _get_encoder_options(self) -> dict:
        return {"preset": "ultrafast", "crf": "28"}

    def to_video(self, recording_path, video_attrs, window_attrs):
        """Override: use stream-copy when SKIP_TYPE_OVERLAY is enabled."""
        if SKIP_TYPE_OVERLAY:
            self._to_video_stream_copy(recording_path, video_attrs)
        else:
            super().to_video(recording_path, video_attrs, window_attrs)

    def _to_video_stream_copy(self, recording_path, video_attrs):
        """Remux the relevant segment without decode/re-encode (no overlay drawn).

        Uses ffmpeg -c copy so that PTS/DTS rewriting and keyframe alignment are
        handled natively. The output clip starts at PTS 0 and is independently
        seekable.
        """
        import shutil
        import subprocess

        video_start_time = video_attrs["video_start_time"]
        start_time = self._get_video_start_time() - video_start_time
        end_time = self._get_video_end_time() - video_start_time
        start_time, end_time = self.process_start_end_time(start_time, end_time)

        if end_time <= start_time:
            logger.warning(
                f"action.py _to_video_stream_copy: Invalid time range for action {self.id}. Skipping."
            )
            return

        video_path = video_attrs.get("video_path")
        if video_path is None:
            video_name = self._get_video_name(recording_path)
            video_path = os.path.join(recording_path, video_name)

        os.makedirs(os.path.join(recording_path, "video_clips"), exist_ok=True)
        video_clip_name = f"{self.id}_{self.action}"
        output_path = os.path.join(
            recording_path, "video_clips", f"{video_clip_name}.mp4"
        )

        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin is None:
            logger.warning(
                "action.py _to_video_stream_copy: ffmpeg not found on PATH, "
                "falling back to decode/encode path."
            )
            super().to_video(recording_path, video_attrs, {})
            return

        duration = end_time - start_time
        cmd = [
            ffmpeg_bin,
            "-y",                        # overwrite output
            "-ss", f"{start_time:.6f}",  # input seek (fast, before -i)
            "-t", f"{duration:.6f}",     # duration to copy
            "-i", video_path,
            "-c", "copy",                # stream copy — no decode/encode
            "-avoid_negative_ts", "make_zero",  # rewrite PTS to start at 0
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            logger.error(
                f"action.py _to_video_stream_copy: ffmpeg failed for action {self.id}:\n"
                + result.stderr.decode(errors="replace")
            )
            raise RuntimeError(f"ffmpeg stream copy failed for action {self.id}")

    def _make_annotator(self, start_time, end_time, start_frame, video_attrs, window_attrs):
        video_start_time = video_attrs["video_start_time"]
        fps = video_attrs["fps"]
        width = video_attrs["width"]
        height = video_attrs["height"]

        font_scale, font_thickness, font = 2.5, 3, cv2.FONT_HERSHEY_SIMPLEX
        text_color = (0, 0, 255)
        key_display_time = 0.5

        key_index = 0
        current_key = ""

        def annotate(img, frame_number):
            nonlocal key_index, current_key
            current_time = start_time + (frame_number - start_frame) / fps

            if (
                key_index < len(self.time_trace)
                and self.time_trace[key_index] <= current_time + video_start_time
            ):
                current_key = self.key_names[key_index]
                key_index += 1
            elif key_index > 0 and (
                current_time + video_start_time
                > self.time_trace[key_index - 1] + key_display_time
            ):
                current_key = ""

            if current_key:
                text_size = cv2.getTextSize(
                    current_key, font, font_scale, font_thickness
                )[0]
                text_x = (width - text_size[0]) // 2
                text_y = height - 100
                cv2.putText(
                    img,
                    current_key,
                    (text_x, text_y),
                    font,
                    font_scale,
                    text_color,
                    font_thickness,
                )
            return img

        return annotate


class Click(Action):  # single, double, triple, drag
    def __init__(self, event):
        super().__init__(event)
        self.click_type = 1
        self.button = event["button"]
        self.pressed = event["pressed"]
        self.coordinate = {"x": event["x"], "y": event["y"]}
        self.coordinates = [{"x": event["x"], "y": event["y"]}]
        self.time_trace = [
            {"start_time": event["start_time"], "end_time": event["end_time"]}
        ]
        if self.pressed == False:
            self.vis = False
        self.action_start_video_buffer_time = 0.5
        self.action_end_video_buffer_time = 0.1

    def _is_long_press(self):
        if self.children:
            if len(self.children) == 1 and self.children[0].action == "click":
                return False
            else:
                logger.warning("is_long_press")
                logger.warning(f"{self.action}, {self.children[0].action}")
                return self.end_time - self.start_time > MOUSE_LONG_PRESS_INTERVAL
        else:
            return False

    def cal_distance(self, mouse_action):
        if isinstance(mouse_action, Click):
            return (
                (self.coordinate["y"] - mouse_action.coordinate["y"]) ** 2
                + (self.coordinate["x"] - mouse_action.coordinate["x"]) ** 2
            ) ** 0.5
        elif isinstance(mouse_action, dict):
            return (
                (self.coordinate["y"] - mouse_action["y"]) ** 2
                + (self.coordinate["x"] - mouse_action["x"]) ** 2
            ) ** 0.5
        else:
            raise ValueError(
                f"Click cal_distance: {type(mouse_action)} type not supported."
            )

    def _is_drag(self):
        if self.children and len(self.children) == 1:
            child_action = self.children[0]
            if child_action.pre_move is not None:
                if self.cal_distance(child_action) > 6:  # TODO: need time?
                    logger.warning(f"{self.action} is drag")
                    return True
        return False

    def transform(self):
        super().transform()
        if self.pressed == False:  # TODO
            self.description = ""
            return

        if self.children and len(self.children) > 0:
            for child in self.children:
                if child.transformed == False:
                    child.transform()

        if self.click_type == 1:
            self.description = "Single {} Click".format(self.button)
        elif self.click_type == 2:
            self.description = "Double {} Click".format(self.button)
        elif self.click_type == 3:
            self.description = "Triple {} Click".format(self.button)
        else:
            self.description = "{} Click".format(self.button)

        if self._is_drag():
            self.action = "drag"
            child_action = self.children.pop(-1)
            self.children.append(child_action.pre_move)
            self.description = "Drag from ({}, {}) to ({}, {})".format(
                self.coordinate["x"],
                self.coordinate["y"],
                child_action.coordinate["x"],
                child_action.coordinate["y"],
            )
            return

        if self._is_long_press():
            self.action = "mouse_press"
            self.description = "Mouse long press {} button:\n".format(self.button)
            if self.children and len(self.children) > 0:
                for child in self.children:
                    if child.description:
                        self.description += child.description + "\n"

    def is_no_move_between_complete_click(self, click_action):
        if click_action.pre_move is None:
            return True
        elif self.cal_distance(click_action) < 4:
            return True
        else:
            return False

    def set_exception_end_event(self):
        self.complete = True
        duration = 0.5
        self.end_time = self.start_time + duration
        self.time_trace[-1]["end_time"] = self.start_time + duration
        self.exception = True
        exception_action = deepcopy(self)
        exception_action.start_time = self.start_time + duration
        exception_action.end_time = self.start_time + duration
        exception_action.pre_move = None
        exception_action.pressed = False
        exception_action.key = (
            exception_action.key[0], not exception_action.key[1])

        self.add_child(exception_action)

    def set_complete_event(self, event):  # TODO: no release coordinate
        self.end_time = event["time_stamp"]
        self.complete = True
        self.time_trace[-1]["end_time"] = event["time_stamp"]

    # TODO: already done / use this function
    def append(self, event):
        self.click_type += 1
        self.coordinates.append({"x": event["x"], "y": event["y"]})
        self.time_trace.append(
            {"start_time": event["start_time"], "end_time": event["end_time"]}
        )
        self.end_time = event["end_time"]

    def _make_annotator(self, start_time, end_time, start_frame, video_attrs, window_attrs):
        if self.action == "drag":
            return self._make_drag_annotator(start_time, end_time, start_frame, video_attrs, window_attrs)
        else:
            return self._make_click_annotator(start_time, end_time, start_frame, video_attrs, window_attrs)

    def _make_click_annotator(self, start_time, end_time, start_frame, video_attrs, window_attrs):
        height = video_attrs["height"]
        width = video_attrs["width"]
        height_ratio = height / window_attrs["height"]
        width_ratio = width / window_attrs["width"]

        x = int(self.coordinate["x"] * height_ratio)
        y = int(self.coordinate["y"] * width_ratio)

        def annotate(img, frame_number):
            cv2.circle(img, (x, y), 15, (0, 0, 255), 2)
            return img

        return annotate

    def _make_drag_annotator(self, start_time, end_time, start_frame, video_attrs, window_attrs):
        video_start_time = video_attrs["video_start_time"]
        fps = video_attrs["fps"]
        height = video_attrs["height"]
        width = video_attrs["width"]
        height_ratio = height / window_attrs["height"]
        width_ratio = width / window_attrs["width"]

        trace_color = (0, 0, 255)
        trace_thickness = 2
        arrow_color = (0, 0, 255)
        arrow_size = 20

        drawn_points = []
        if self.children and len(self.children) > 0:
            time_trace = self.children[0].time_trace
            trace = self.children[0].trace
        else:
            time_trace = self.drag_time_trace
            trace = self.drag_trace

        for time_point in time_trace:
            if (
                start_time + video_start_time
                <= time_point
                <= end_time + video_start_time
            ):
                xi, yi = trace[time_trace.index(time_point)]
                xi, yi = int(xi * width_ratio), int(yi * height_ratio)
                drawn_points.append((xi, yi))

        tip_point = left_wing = right_wing = None
        mid_index = len(drawn_points) // 2
        if mid_index > 0:
            start_point = drawn_points[mid_index - 1]
            end_point = drawn_points[mid_index:mid_index + 3][-1]
            direction = np.array(end_point) - np.array(start_point)
            norm = np.linalg.norm(direction)
            if norm != 0:
                direction = direction / norm * arrow_size
            else:
                direction = np.array([arrow_size, 0])
            perpendicular = np.array([-direction[1], direction[0]])
            tip_point = tuple(map(int, np.array(start_point)))
            left_wing = tuple(map(int, np.array(tip_point) + perpendicular / 2 - direction / 2))
            right_wing = tuple(map(int, np.array(tip_point) - perpendicular / 2 - direction / 2))

        def annotate(img, frame_number):
            if len(drawn_points) > 1 and tip_point is not None:
                for i in range(1, len(drawn_points)):
                    cv2.line(
                        img,
                        drawn_points[i - 1],
                        drawn_points[i],
                        trace_color,
                        trace_thickness,
                    )
                cv2.fillPoly(
                    img,
                    [np.array([tip_point, left_wing, right_wing], dtype=np.int32)],
                    arrow_color,
                )
            return img

        return annotate


class Press(Action):  # type, press, long press
    def __init__(self, event):
        super().__init__(event)

        self.key_name = event["name"]
        self.complete = event["complete"]
        self.pressed = self.key[-1]
        self.action_start_video_buffer_time = 0.3
        self.action_end_video_buffer_time = 0.2

    def set_complete_event(self, event: dict):
        self.end_time = event["time_stamp"]
        self.complete = True

    def is_typing(self) -> bool:
        if (
            self.complete
            and self.children is not None
            and len(self.children) == 1
            and isinstance(self.children[0], Type)
            and "shift" in self.key_name
        ):
            return True
        else:
            return False

    def transform(self):
        if self.exception:
            self.description = "⌨️ Press: {}".format(
                wrap_func_key(self.key_name))
            return

        super().transform()
        if self.pressed == False:  # TODO
            return

        if not self.children:
            self.description = "⌨️ Press: {}".format(
                wrap_func_key(self.key_name))
            return

        # TODO: sort by time, include child action
        if len(self.children) > 1:
            for i in range(len(self.children) - 1, 0, -1):
                if (
                    self.children[i - 1].end_time and self.children[i].end_time
                    and self.children[i - 1].start_time < self.children[i].start_time
                    and self.children[i - 1].end_time > self.children[i].end_time
                ):
                    logger.warning("Reducer: re-arrange: {} {} {}".format(
                        i-1, i, self.children[i].key))
                    child = self.children.pop(i)
                    self.children[i - 1].add_child(child)

        if self.children and len(self.children) > 0:
            for child in self.children:
                if child.transformed == False:
                    child.transform()

        # Modifier + click/drag/scroll combo detection.
        visible_children = [child for child in self.children if child.vis]
        if visible_children and all(isinstance(child, Click) for child in visible_children):
            drag_children = [child for child in visible_children if child.action == "drag"]
            # Modifier + drag combo: all visible children are drags
            if drag_children and len(drag_children) == len(visible_children):
                drag_child = drag_children[0]
                self.action = "modifier_drag"
                self.description = (
                    f"\u2328\ufe0f Modifier+Drag: {wrap_func_key(self.key_name)} {drag_child.description}"
                )
                return
            # Modifier + click combo: only non-drag click children
            click_children = [
                child
                for child in visible_children
                if child.pressed and child.coordinate is not None and child.action != "drag"
            ]
            if len(click_children) == len(visible_children):
                click_strs = [
                    f"{child.button} ({int(child.coordinate['x'])}, {int(child.coordinate['y'])})"
                    for child in click_children
                ]
                self.action = "modifier_click"
                self.description = (
                    f"\u2328\ufe0f Modifier+Click: {wrap_func_key(self.key_name)} "
                    + "; ".join(click_strs)
                )
                return

        # Modifier + scroll combo
        if visible_children and all(isinstance(child, Scroll) for child in visible_children):
            self.action = "modifier_scroll"
            self.description = f"\u2328\ufe0f Modifier+Scroll: {wrap_func_key(self.key_name)}"
            return

        if len(self.children) == 1:
            if self.children[0].action == "type":
                self.description = "⌨️ Press: {} + {}".format(
                    wrap_func_key(self.key_name), self.children[0].get_str()
                )
                self.children[0].vis = False

            elif self.children[0].action == "press":  # TODO: modify
                self.description = (
                    f"⌨️ Press: {wrap_func_key(self.key_name)} + "
                    + self.children[0].description.lstrip("⌨️ Press: ")
                )
            else:
                self.action = "long_press"
                self.description = "⌨️ Long Press: {}".format(
                    wrap_func_key(self.key_name)
                )
        else:
            self.action = "long_press"
            self.description = "⌨️ Long Press: {}".format(
                wrap_func_key(self.key_name))

        
        
    def _make_annotator(self, start_time, end_time, start_frame, video_attrs, window_attrs):
        width = video_attrs["width"]
        height = video_attrs["height"]

        font_scale = 1
        font_thickness = 2
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_color = (0, 0, 255)

        display_text = ""
        if self.description:
            display_text = (
                self.description.split(" ", 1)[1]
                if " " in self.description
                else self.description
            )

        def annotate(img, frame_number):
            text_size = cv2.getTextSize(display_text, font, font_scale, font_thickness)[0]
            text_x = (width - text_size[0]) // 2
            text_y = height - 60
            cv2.putText(
                img,
                display_text,
                (text_x, text_y),
                font,
                font_scale,
                text_color,
                font_thickness,
            )
            return img

        return annotate

    def set_exception_end_event(self):
        self.complete = True
        duration = 0.01
        self.end_time = self.start_time + duration
        self.exception = True
        exception_action = deepcopy(self)
        exception_action.start_time = self.start_time + duration
        exception_action.end_time = self.start_time + duration
        exception_action.pre_move = None
        exception_action.pressed = False
        exception_action.key = (
            exception_action.key[0], not exception_action.key[1])

        self.add_child(exception_action)


class Scroll(Action):
    def __init__(self, event):
        super().__init__(event)
        self.trace = event["trace"]
        self.time_trace = event["time_trace"]

        self.action_start_video_buffer_time = 0.5
        self.action_end_video_buffer_time = 0.2

    def extend(self, event):
        if event["action"] != self.action:
            raise ValueError(
                "Scroll extend error: action not match {}".format(
                    event["action"])
            )

        self.trace.extend(event["trace"])
        self.time_trace.extend(event["time_trace"])
        self.end_time = event["end_time"]

    def _get_direction_icon(self, dx, dy):
        if dx:
            dx /= abs(dx)
        if dy:
            dy /= abs(dy)
        direction2icon = {
            (0, 1): "⬆️",
            (0, -1): "⬇️",
            (1, 0): "⬅️",
            (-1, 0): "➡️",
            (1, 1): "↖",
            (-1, 1): "↗",
            (1, -1): "↙",
            (-1, -1): "↘",
        }
        return direction2icon[(dx, dy)]

    def _get_direction_text(self, dx, dy):
        if dx:
            dx /= abs(dx)
        if dy:
            dy /= abs(dy)
        direction2text = {
            (0, 1): "Up",
            (0, -1): "Down",
            (1, 0): "Left",
            (-1, 0): "Right",
            (1, 1): "Top Left",
            (-1, 1): "Top Right",
            (1, -1): "Bottom Left",
            (-1, -1): "Bottom Right",
        }
        return direction2text[(dx, dy)]

    def transform(self):
        super().transform()
        self.description = "Scroll "
        direction_count = {}
        for i in range(len(self.trace)):
            dx, dy = self.trace[i]["dx"], self.trace[i]["dy"]
            direction = self._get_direction_icon(dx, dy)
            if direction not in direction_count:
                direction_count[direction] = 1
            else:
                direction_count[direction] += 1

        for direction in direction_count:
            self.description += "{}×{}  ".format(
                direction, direction_count[direction])

    def _make_annotator(self, start_time, end_time, start_frame, video_attrs, window_attrs):
        video_start_time = video_attrs["video_start_time"]
        fps = video_attrs["fps"]
        width = video_attrs["width"]
        height = video_attrs["height"]
        height_ratio = height / window_attrs["height"]
        width_ratio = width / window_attrs["width"]

        min_display_time = 0.2
        scroll_index = 0
        last_scroll_time = None
        x = y = dx = dy = 0

        def annotate(img, frame_number):
            nonlocal scroll_index, last_scroll_time, x, y, dx, dy
            current_time = start_time + (frame_number - start_frame) / fps

            if (
                scroll_index < len(self.time_trace)
                and self.time_trace[scroll_index] <= current_time + video_start_time
            ):
                last_scroll_time = current_time
                trace = self.trace[scroll_index]
                x, y = int(trace["x"] * width_ratio), int(trace["y"] * height_ratio)
                dx, dy = trace["dx"], trace["dy"]
                scroll_index += 1

            if last_scroll_time is not None:
                if (
                    current_time - last_scroll_time < min_display_time
                    or scroll_index == len(self.time_trace)
                ):
                    arrow_length = 60
                    end_x = max(0, min(width - 1, x - int(dx * arrow_length)))
                    end_y = max(0, min(height - 1, y - int(dy * arrow_length)))
                    cv2.arrowedLine(
                        img, (x, y), (end_x, end_y), (0, 0, 255), 2, tipLength=0.3
                    )
                    direction_text = "Scroll " + self._get_direction_text(
                        np.sign(dx), np.sign(dy)
                    )
                    text_x = x + 20 if x < width / 2 else x - 20
                    cv2.putText(
                        img,
                        direction_text,
                        (int(text_x), y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 0, 255),
                        2,
                    )
                else:
                    last_scroll_time = None

            return img

        return annotate
