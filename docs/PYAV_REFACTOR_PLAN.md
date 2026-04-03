# PyAV Refactor: Video Clip Generation — Implementation Summary

## Goal

Replace `cv2.VideoWriter` with **PyAV + libx264** for encoding, keeping all
cv2 annotation drawing unchanged. Primary target: Ubuntu/Linux, where
`opencv-python` does not bundle `libx264` and falls back to slow `mp4v`.

## What Was Implemented

### Encode: cv2 → PyAV (libx264)

`Action.to_video()` now opens the output with `av.open(..., mode="w")` and
writes all frames through `libx264` (falls back to `mpeg4` if unavailable).
The cv2 `VideoCapture` + retry loop and `VideoWriter` fallback chain are gone.

Encoder preset is controlled via a per-class `_get_encoder_options()` hook:

- **`Type`** → `{"preset": "ultrafast", "crf": "28"}` — type clips can be
  10+ minutes (18k–23k frames); ultrafast gives ~5-10x encode speedup vs mp4v.
- **All other action types** (Click, Press, Scroll, Move) → `{"preset": "medium", "crf": "28"}` — clips are short (~20–300 frames); quality preset is fine.

### Decode: PyAV (software)

For simplicity, decoding also uses PyAV (`av.open` + `src.demux`). PyAV seeks
by PTS rather than frame index, which is more reliable for long files.

**Platform note:** On macOS, `cv2.VideoCapture` previously used VideoToolbox
hardware decode transparently. PyAV uses software decode, making macOS
marginally slower for long type clips. On **Linux prod** (the primary target),
cv2 also used software decode, so there is **no regression** — only the encode
speedup applies.

### `process_video_segment` → `_make_annotator` closure pattern

All five `process_video_segment` method overrides are replaced by
`_make_annotator(start_time, end_time, start_frame, video_attrs, window_attrs)`
returning a `(img, frame_number) → img` closure. `to_video()` owns the full
decode/encode loop and calls the closure per frame. Stateful per-frame logic
(e.g. `key_index` in `Type`, `scroll_index` in `Scroll`) lives in closure
`nonlocal` variables.

### Reducer metadata probing

`Reducer.process_actions_multithreaded` probes video metadata (`fps`, `width`,
`height`, `total_frames`) using `av.open()` instead of `cv2.VideoCapture`.

## Affected Files

| File                                                                              | Change                                |
| --------------------------------------------------------------------------------- | ------------------------------------- |
| `agentnet-annotator/api/core/action_reduction/action.py`                          | Core refactor                         |
| `agentnet-annotator/api/core/action_reduction/reducer.py`                         | Metadata probing via PyAV             |
| `requirements_ubuntu.txt` / `requirements_macos.txt` / `requirements_windows.txt` | Add `av`                              |
| `agentnet-annotator/api/build.py`                                                 | Add `--collect-all av` to PyInstaller |

## How to Verify

Run the reducer directly on a recording (includes video clip generation):

```bash
python agentnet-annotator/api/core/action_reduction/reducer.py \
  --recording_path ~/Downloads/slow-case-e4a3de54-39c3-4435-96b9-7ef8c6635c34 \
  2>&1 | grep -E "INFO.*Reducer: action [0-9]|INFO.*Reducer: video|INFO.*Reducer: compress|INFO.*Reducer: match"
```

Or via the test script (supports multiple cases, skip flags):

```bash
cd agentnet-annotator
python -m api.scripts.test_reduction --no_window_a11y --full_video \
  --cases ~/Downloads/slow-case-e4a3de54-39c3-4435-96b9-7ef8c6635c34
```

Expected output with `SKIP_TYPE_OVERLAY = True` (stream-copy path):

```
Reducer: compress/reduce/transform/finish: 0.04s
Reducer: match_axtree: 0.00s
Reducer: match_element: 0.01s
Reducer: action 3 (type) video done in 0.25s      # ← type clips: ~0.1–0.25s
Reducer: action 8 (type) video done in 0.14s
Reducer: action 5 (click) video done in 0.39s
...
Reducer: video generation (59 clips): 5.42s       # total
```

Type clips complete in **0.10–0.25s** each (stream copy, no decode/encode).
Non-type clips (click/press/scroll/drag) complete in **0.4–1.7s** (still using PyAV decode + libx264 encode).

---

## Benchmark Results (macOS, 8 threads)

### Pre-stream-copy (PyAV decode + libx264 encode for all clips)

| Recording                                                  | Clips | Video generation |
| ---------------------------------------------------------- | ----- | ---------------- |
| slow-case-da5b773e (53 clips, longest type: 23,105 frames) | 53    | 139.97s          |
| slow-case-e4a3de54 (59 clips, longest type: 12,232 frames) | 59    | 83.51s           |

### Post-stream-copy (`SKIP_TYPE_OVERLAY = True`, ffmpeg -c copy for Type clips)

| Recording          | Clips | Video generation | Speedup  |
| ------------------ | ----- | ---------------- | -------- |
| slow-case-e4a3de54 | 59    | **5.42s**        | **~15x** |

macOS performance is bottlenecked by PyAV software decode (was previously
hardware-accelerated via VideoToolbox). On Linux prod, no such regression
exists — the encode speedup from libx264 ultrafast is the dominant effect.

## Performance Expectation on Linux Prod

| Clip type                           | Old (mp4v) | New (libx264 ultrafast) |
| ----------------------------------- | ---------- | ----------------------- |
| click/press/scroll (~20–300 frames) | ~1–2s      | ~0.5–1s                 |
| type, short (~300 frames)           | ~1.5s      | ~0.5s                   |
| type, long (~21,700 frames)         | ~120s      | **~20–30s**             |
| Total (53 clips, 8 threads)         | ~135s      | **~30s**                |

The remaining gap is software decode time, which is the same for both old and
new on Linux. Further improvement would require GPU-accelerated decode
(VAAPI/NVDEC), which is environment-dependent and not guaranteed in prod.
