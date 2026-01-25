#!/bin/bash
# Convert raw trajectories directly to visualization format

export PYTHONPATH=$PYTHONPATH:.

# Default paths
DEFAULT_INPUT="datasets/raw_trajs"
DEFAULT_OUTPUT="datasets/vis_std"

INPUT_DIR="$DEFAULT_INPUT"
OUTPUT_DIR="$DEFAULT_OUTPUT"

# Check if arguments are provided
if [ "$#" -ge 1 ]; then
    INPUT_DIR="$1"
    shift
fi

if [ "$#" -ge 1 ]; then
    OUTPUT_DIR="$1"
    shift
fi

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# Run the conversion script
# Usage: python -m src.raw_to_vis_std <input_raw_trajs_dir> <output_dir>
uv run python -m src.raw_to_vis_std "$INPUT_DIR" "$OUTPUT_DIR" "$@"
