# data-process

A minimal, script-first toolkit to process and standardize GUI agent trajectory data (AgentNet format), using a flattened layout and a simple `requirements.txt`.

## Installation

- Python 3.11

```bash
cd /cpfs03/data/shared/Group-m6/ludunjie.ldj/OpenCUA/data-process
pip install -r requirements.txt
```

On headless servers, install Xvfb so video/screenshot code can run without a physical display:
```bash
sudo apt-get update && sudo apt-get install -y xvfb
```

## Quick Start

The pipeline has two stages:

### 1) Extract raw trajectories
This scans `datasets/raw/` (each episode is a folder with `.mp4`, `metadata.json`, `reduced_events_*.jsonl`, etc.), builds event frames/thumbnails, and writes JSONs to `datasets/raw_trajs/`.

```bash
# Extract all samples
xvfb-run -a ./scripts/extract_raw.sh -1

# Extract the first 10 samples
xvfb-run -a ./scripts/extract_raw.sh 10
```

### 2) Convert to standardized format
This converts raw trajectory JSONs to a unified `Trajectory` schema and writes to `datasets/standardized/`.

```bash
# Convert all raw trajectories to standardized format
xvfb-run -a ./scripts/raw_to_standardized.sh -1

# Convert the first 10 raw trajectories
xvfb-run -a ./scripts/raw_to_standardized.sh 10
```

If `xvfb-run` is unavailable, you can run with a manual virtual display:
```bash
Xvfb :99 -screen 0 1920x1080x24 & export DISPLAY=:99
./scripts/extract_raw.sh -1
./scripts/raw_to_standardized.sh -1
```

## Project Structure

```
data-process/
├── datasets/
│   ├── raw/             # Raw per-episode folders
│   ├── raw_trajs/       # Raw trajectory JSON files (output of stage 1)
│   └── standardized/    # Standardized trajectory JSON files (output of stage 2)
├── scripts/
│   ├── extract_raw.sh         # Calls: python -m src.extract_raw
│   └── raw_to_standardized.sh # Calls: python -m src.raw_to_standardized
├── src/
│   ├── __init__.py
│   ├── extract_raw.py         # Raw data extraction logic
│   ├── raw_to_standardized.py # Conversion to Trajectory schema
│   ├── schema/
│   │   ├── __init__.py
│   │   ├── action.py
│   │   └── trajectory.py
│   └── utils/
│       ├── __init__.py
│       └── image.py
└── requirements.txt
```

## Programmatic usage
```python
import json
from src.schema.trajectory import Trajectory

with open('datasets/standardized/example.json', 'r') as f:
    data = json.load(f)
    traj = Trajectory(**data)

print(traj.task_id, traj.type, len(traj.content))
```

## Notes
- The repo is script-first; run modules via `python -m src.*`.
- Scripts skip already-processed episodes.
- Ensure `datasets/raw` points to your per-episode raw folders before running.
- The schema and utilities were minimized for this pipeline; extend as needed.

