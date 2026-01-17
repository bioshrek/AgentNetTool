set -e
NUM_SAMPLES=${1:-"-1"}
DIR="$(cd "$(dirname "$0")"/.. && pwd)"
PYTHONPATH="$DIR" uv run python -m src.raw_to_standardized "$DIR/datasets/raw_trajs" "$DIR/datasets/standardized" --num_samples "$NUM_SAMPLES"
