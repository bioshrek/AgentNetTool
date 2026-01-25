#!/bin/bash
# Convert standardized trajectories to visualization format

export PYTHONPATH=$PYTHONPATH:.

# Ensure output directory exists
mkdir -p datasets/vis_std

# Run the conversion script
# Usage: python -m src.standardized_to_vis <input_dir> <output_dir>
uv run python -m src.standardized_to_vis datasets/standardized datasets/vis_std
