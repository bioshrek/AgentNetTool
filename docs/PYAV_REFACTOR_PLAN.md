# PyAV Refactor Plan: Video Clip Generation

## Background

Video clip generation in `agentnet-annotator/api/core/action_reduction/action.py` currently
uses OpenCV (`cv2`) for both frame-level annotation drawing and video I/O
(decode + encode). The annotation drawing (`cv2.circle`, `cv2.putText`,
`cv2.line`, `cv2.fillPoly`) is the right tool for the job and will not change.
The I/O layer (`cv2.VideoCapture`, `cv2.VideoWriter`) is a consequential
dependency that can be replaced with **PyAV** to gain:

- **H.264 encoding on Linux** — prebuilt `opencv-python` on Ubuntu does not
  include `libx264`, so the current code falls back to `mp4v`. PyAV bundles
  its own FFmpeg with `libx264`, so H.264 is always available without any
  system-level dependency.
- **`ultrafast` preset for `type` clips** — `type` actions span the full
  real-world typing duration (can be 10+ minutes = 18,000+ frames). With
  libx264's `ultrafast` preset, encoding throughput is ~5-10x faster than
  `mp4v`, from ~30fps to ~200fps effective encode rate at 1080p.
- **Clean resource management** — PyAV's context managers (`with av.open(...)`)
  eliminate the `cap.release()` / `out.release()` calls currently scattered
  across all five `process_video_segment` overrides.
- **PTS-accurate seeking** — `av.Container.seek()` by presentation timestamp
  is more reliable than `cv2.CAP_PROP_POS_FRAMES` for long files with B-frames.

---

## How cv2 Annotation Works With PyAV

The bridge is numpy:

```
H.264 bitstream
  │  av.demux + decode
  ▼
av.VideoFrame (yuv420p)
  │  .to_ndarray(format="bgr24")   # YUV→BGR color convert
  ▼
numpy uint8 [H, W, 3]  BGR  ← identical to cv2.VideoCapture.read() output
  │  cv2.circle / putText / line / fillPoly  (UNCHANGED)
  ▼
numpy uint8 [H, W, 3]  BGR  (modified in-place)
  │  av.VideoFrame.from_ndarray(..., format="bgr24")  # BGR→YUV color convert
  ▼
av.VideoFrame
  │  stream.encode + mux
  ▼
H.264 bitstream (output file)
```

`format="bgr24"` must be specified on both sides to match cv2's byte order.
The two YUV↔BGR conversions are negligible overhead vs encode time.

---

## Scope of Changes

### What changes

**`action.py` — `Action.to_video()`**

Replace:

```python
cap = cv2.VideoCapture(video_path)
cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
fourcc = cv2.VideoWriter_fourcc(*codec)
out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
```

With:

```python
with av.open(video_path) as src, av.open(output_path, mode="w") as dst:
    in_stream = src.streams.video[0]
    out_stream = dst.add_stream("libx264", rate=fps)
    out_stream.width, out_stream.height = width, height
    out_stream.pix_fmt = "yuv420p"
    out_stream.options = {"preset": "ultrafast", "crf": "28"}
    src.seek(start_pts, stream=in_stream)
    # frame loop passed to subclass
```

**`action.py` — `process_video_segment` signature**

The current signature:

```python
def process_video_segment(self, start_time, end_time, cap, out, video_attrs, window_attrs)
```

Change to pass in an iterable of `(av.VideoFrame, frame_number)` tuples and
an output encoder, or lift the I/O frame loop entirely into `to_video()` and
make `process_video_segment` a pure annotator:

```python
def annotate_frame(self, img: np.ndarray, frame_number: int,
                   start_time: float, video_attrs: dict, window_attrs: dict) -> np.ndarray:
    """Return annotated copy (or in-place modified) numpy BGR frame."""
    return img  # base: no annotation
```

Subclasses override `annotate_frame` only. `to_video()` owns the decode/encode
loop, calls `annotate_frame` per frame, and muxes the result.

### What does NOT change

- `cv2.circle`, `cv2.putText`, `cv2.line`, `cv2.fillPoly`, `cv2.getTextSize`
  — all annotation calls are identical; they only care about the numpy array.
- All action class logic: `_get_video_start_time`, `_get_video_end_time`,
  `process_start_end_time`, time-trace logic in `Type`, coordinate scaling in
  `Click`, drag trace building in `process_drag_video_segment`.
- `Reducer.process_actions_multithreaded` — threading model, queue, worker
  function, and pre-resolved `video_attrs` dict are unchanged.
- The fallback codec logic in `action.py` is removed (replaced by libx264
  always being available via PyAV's bundled FFmpeg).

---

## Affected Files

| File                                                                              | Change type                                           |
| --------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `agentnet-annotator/api/core/action_reduction/action.py`                          | Core refactor                                         |
| `agentnet-annotator/api/core/action_reduction/reducer.py`                         | Minor: remove cv2 VideoCapture for metadata; use PyAV |
| `requirements_ubuntu.txt` / `requirements_macos.txt` / `requirements_windows.txt` | Add `av`                                              |
| `agentnet-annotator/api/build.py`                                                 | Add `av` to bundled packages if applicable            |

---

## Implementation Steps

### Step 1 — Add PyAV dependency

```bash
uv add av
# or: pip install av
```

Verify `libx264` is available in PyAV's bundled FFmpeg:

```python
import av
print(av.codec.codecs_available)  # should contain 'libx264'
```

### Step 2 — Refactor `Action.to_video()`

Replace the `cv2.VideoCapture` open + retry loop and `cv2.VideoWriter`
fallback chain with a single `av.open()` context. Key points:

- Seek by PTS: `start_pts = int(start_time / float(in_stream.time_base))`
- Use `src.demux(in_stream)` to iterate packets, decode to frames
- Skip frames before `start_pts`, break after `end_pts`
- Call `self.annotate_frame(img, frame_number, ...)` per frame
- Flush encoder after the loop: `for p in out_stream.encode(): dst.mux(p)`

The `video_attrs` pre-population in `Reducer.process_actions_multithreaded`
can also switch to `av.open()` for reading `fps`, `width`, `height`,
`total_frames`.

### Step 3 — Refactor `process_video_segment` to `annotate_frame`

Rename and simplify each override so it only draws on a numpy array:

**Base `Action`** (currently: pass-through, no annotation):

```python
def annotate_frame(self, img, frame_number, start_time, video_attrs, window_attrs):
    return img
```

**`Type`** (currently: `cv2.putText` with time-trace key lookup):

```python
def annotate_frame(self, img, frame_number, start_time, video_attrs, window_attrs):
    # existing key-display logic, replacing cap.read() loop variables with parameters
    current_time = start_time + frame_number / video_attrs["fps"]
    # ... key_index tracking (needs to become instance state or a closure) ...
    if current_key:
        cv2.putText(img, current_key, ...)
    return img
```

Note: `key_index` is currently tracked as a local variable in the frame loop.
Since `annotate_frame` is called per-frame from outside the loop, it needs to
become a closure variable or a small stateful helper class initialized before
the loop.

**`Click.process_click_video_segment`**:

```python
def annotate_frame(self, img, frame_number, start_time, video_attrs, window_attrs):
    cv2.circle(img, (x, y), 15, (0, 0, 255), 2)
    return img
```

**`Click.process_drag_video_segment`**: The drag trace and arrowhead are
pre-computed before the frame loop (unchanged). `annotate_frame` just draws
`cv2.line` and `cv2.fillPoly` on each frame.

**`Press`**:

```python
def annotate_frame(self, img, frame_number, start_time, video_attrs, window_attrs):
    cv2.putText(img, display_text, ...)
    return img
```

### Step 4 — Handle `key_index` state in `Type.annotate_frame`

The type key-index tracking is currently a local variable that increments
across the frame loop. With the per-frame callback design, use a closure:

```python
def _make_type_annotator(self, start_time, video_attrs):
    key_index = 0
    current_key = ""
    key_display_time = 0.5
    video_start_time = video_attrs["video_start_time"]
    fps = video_attrs["fps"]

    def annotate(img, frame_number):
        nonlocal key_index, current_key
        current_time = start_time + frame_number / fps
        if (key_index < len(self.time_trace) and
                self.time_trace[key_index] <= current_time + video_start_time):
            current_key = self.key_names[key_index]
            key_index += 1
        elif (current_time + video_start_time >
              self.time_trace[key_index - 1] + key_display_time):
            current_key = ""
        if current_key:
            # ... existing cv2.putText logic ...
        return img

    return annotate
```

Call `annotator = self._make_type_annotator(...)` before the frame loop in
`to_video()`, then `img = annotator(img, frame_number)` per frame.

### Step 5 — Benchmark and validate

After refactoring:

```bash
# run the slow-case test recording
uv run agentnet-annotator/api/core/action_reduction/reducer.py \
    --recording_path ~/Downloads/slow-case-da5b773e-a3bd-40bf-9340-80d87b8f100f

# check output clips play correctly in Electron viewer
# check codec used:
ffprobe -v quiet -select_streams v -show_entries stream=codec_name \
    -of default=nw=1:nk=1 \
    ~/Downloads/slow-case-da5b773e-a3bd-40bf-9340-80d87b8f100f/video_clips/14_type.mp4
# expected: h264
```

Target: action 14 (21,700-frame type clip) should drop from ~120s to ~20-30s
with `ultrafast` preset.

---

## Expected Performance After Refactor

Based on libx264 `ultrafast` encoding benchmarks at 1920×1080:

| Action type                 | Current (mp4v) | After (libx264 ultrafast) |
| --------------------------- | -------------- | ------------------------- |
| click (~20 frames)          | ~0.27s         | ~0.1s                     |
| type, short (~300 frames)   | ~1.5s          | ~0.5s                     |
| type, long (~21,700 frames) | ~120s          | **~20s**                  |
| Total (53 clips, 8 threads) | ~135s          | **~30s**                  |

---

## Risks and Mitigations

| Risk                                                     | Mitigation                                                                                         |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| PyAV not available in prod Docker image                  | Add `av` to `requirements_ubuntu.txt`; PyAV is pure pip, no system lib needed                      |
| `libx264` not in PyAV's bundled FFmpeg on some platforms | Check `av.codec.codecs_available` at startup and log a warning; fall back to `libx265` or `mpeg4`  |
| PTS-based seeking lands on wrong keyframe                | Add a pre-roll: decode but discard frames before `start_pts` (same as current `cap.set` + skip)    |
| `key_index` closure state bugs in `Type`                 | Unit test the annotator closure with a synthetic time_trace                                        |
| Output file incompatible with react-player/Electron      | `mp4` + `h264` + `yuv420p` is the most widely supported combination; confirmed working in Chromium |
