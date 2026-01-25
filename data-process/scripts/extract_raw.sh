set -e
NUM_SAMPLES=${1:-1}
DIR="$(cd "$(dirname "$0")"/.. && pwd)"
PYTHONPATH="$DIR" uv run python -m src.extract_raw "$DIR/datasets/raw_trajs" -n "$NUM_SAMPLES" --raw_dir "$DIR/datasets/raw"