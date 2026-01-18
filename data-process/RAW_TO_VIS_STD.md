# Raw to Vis_Std Transformation

Converts raw GUI recordings to PyAutoGUI-compatible format with screenshots.

## Input/Output

**Input:** `datasets/raw/{episode_id}/`

- `metadata.json` - System info, timestamps, screen dimensions
- `task_name.json` - Task instruction
- `reduced_events_vis.jsonl` - Action events with coordinates
- `*.mp4` - Screen recording

**Output:** `datasets/vis_std/{episode_id}/`

- `{episode_id}.json` - Trajectory with PyAutoGUI commands
- `step_*.png` - Screenshots

```json
{
  "task_id": "665f681d-b88a-41dc-9cd9-7f98e1b0332e_raw",
  "instruction": "User's task description",
  "traj": [
    {
      "index": 0,
      "code": "pyautogui.click(x=145, y=252)",
      "screenshot": "step_0.png"
    },
    {
      "index": 1,
      "code": "pyautogui.hotkey(keys=['ctrl', 'c'])",
      "screenshot": "step_1.png"
    }
  ]
}
```

## Usage

```bash
# Single recording
uv run python -m src.raw_to_vis_std ./datasets/raw/{episode_id} ./datasets/vis_std

# All recordings
uv run python -m src.raw_to_vis_std ./datasets/raw ./datasets/vis_std

# Or use script
./scripts/raw_to_vis_std.sh
```

### Pipeline Steps

#### 1. Raw Data Extraction (`extract_raw.py`)

When processing a raw recording directory, the pipeline first extracts structured data:

- **Load metadata**: Parse `metadata.json` for system info and timestamps
- **Load task**: Read `task_name.json` for the instruction
- **Load events**: Parse `reduced_events_vis.jsonl` for action events
- **Extract frames**: Extract video frames at action timestamps using OpenCV

**Key Function:** `process_single_directory(basedir, dir_name, load_image=True)`

Returns a raw example dictionary with:

```python
{
    "episode_id": str,
    "task_name": str,
    "metadata": dict,
    "events": list[dict],  # Each event has action type, timestamp, target coords
    "screenshots": list[str]  # Base64 encoded images
}
```

#### 2. Standardization (`raw_to_standardized.py`)

Pipeline

1. **Extract** (`extract_raw.py`): Load metadata, task, events, extract video frames
2. **Standardize** (`raw_to_standardized.py`): Convert to `Trajectory` objects
3. **Generate** (`process_trajectory()`): Create vis_std output
   - Save screenshots as PNG
   - Convert normalized coords [0,1] → absolute pixels
   - Generate PyAutoGUI commands via `action.to_command()# GUIElement

Represents a UI target element:

```python
class GUIElement(BaseModel):
    bbox: Tuple[float, float, float, float]  # Normalized (x1, y1, x2, y2)
    pixel_bbox: Tuple[int, int, int, int]    # Absolute pixels
    image_size: Tuple[int, int]              # (width, height)
    text: Optional[str]                      # Text content if applicable
```

### GUIAction

Container for one or more PyAutoGUI actions at a single step:

```python
class GUIAction(Action):
    guiactions: list[PyAutoGUIAction]
    instruction: str | None
    thoughts: str | None
    screenshot: Optional[str]  # Base64 encoded image
```

## Usage Examples

### Process a Single Recording

```bash
cd data-process
uv run python -m src.raw_to_vis_std \
    ./datasets/raw/665f681d-b88a-41dc-9cd9-7f98e1b0332e_raw \
    ./datasets/vis_std
```

### Process All Recordings

```bash
cd data-process
uv run python -m src.raw_to_vis_std ./datasets/raw ./datasets/vis_std
```

### Using Shell Script

```bash
cd data-process
./scripts/raw_to_vis_std.sh
```

The script automatically:

- Skips already-processed episodes
- Handles errors gracefully
- Shows progress for batch processing

## Code Generation Examples

### Click Action

```python
# Input: normalized coordinates (0.0755, 0.2333)
# Image size: 1920x1080
# Output: pyautogui.click(x=145, y=252)
```

### Keyboard Shortcuts

```python
# Input: hotkey event with keys ['ctrl', 'c']
# Output: pyautogui.hotkey(keys=['ctrl', 'c'])
```

### Text Input

```python
# Input: type event with text "hello world"
# Output: pyautogui.write(message='hello world')
```

### Drag Operation

```python
# Input: from_coord=(0.3, 0.4), to_coord=(0.6, 0.7), size=(1920, 1080)
# Output: pyautogui.dragTo(x=1152, y=756)
```

**PyAutoGUIAction** - Single operation (CLICK, WRITE, SCROLL, HOTKEY, DRAG_TO, etc.)
**GUIElement** - Target with bbox (normalized + pixel), image_size, text
**GUIAction** - Container for one or more PyAutoGUIActions per stepeasy to share/move individual trajectories

## Performance Considerations

- **Parallel Processing**: The pipeline supports concurrent processing of multiple episodes (not implemented in current version but structure allows it)
- **Incremental Processing**: Skips already-processed episodes by checking output directory
- **Memory Efficiency**: Processes one trajectory at a time, releases resources between episodes
- **Image Handling**: Base64 decoding and PIL operations are optimized for speed

## Troubleshooting

### Common Issues

1. **Missing metadata.json**: Ensure raw recordings are complete
2. **Video file not found**: Check that .mp4 files exist in raw directory
3. **Coordinate out of bounds**: Verify screen dimensions in metadata
4. **Empty trajectory**: Check that reduced_events_vis.jsonl contains valid events

### Debug Mode

Add error logging:

```python
import traceback
try:
    process_trajectory(converted_examples[0], output_path)
except Exception as e:
    traceback.print_exc()
    print(f"Error: {e}")
```

## Future Enhancements

- [ ] Support for additional action types (clipboard, window management)
- [ ] Trajectory validation and quality checks
- [ ] Compression options for images
- [ ] Parallel batch processing
- [ ] Trajectory visualization tool
- [ ] Action replay functionality
      Examples

```python
# Click: (0.0755, 0.2333) @ 1920x1080 → pyautogui.click(x=145, y=252)
# Hotkey: ['ctrl', 'c'] → pyautogui.hotkey(keys=['ctrl', 'c'])
# Type: "hello" → pyautogui.write(message='hello')
# Scroll: 16 → pyautogui.scroll(16)
# Multi-action:
# pyautogui.moveTo(x=51, y=199)
#

```

Raw Dir → [extract_raw] → Raw Dict → [raw_to_standardized] →
Trajectory → [process_trajectory] → Vis_Std (JSON + PNGs)

```

## Notes

- Normalized coords [0,1] → absolute pixels for PyAutoGUI compatibility
- PNG screenshots separate from JSON for efficient loading
- Skips already-processed episodes automatically
- Handles missing metadata/video gracefull
```
