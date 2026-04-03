"""
Test script for the action reduction pipeline.

Run from the repo root with the virtualenv active:

    python -m agentnet-annotator.api.scripts.test_reduction

Or from the agentnet-annotator/ directory:

    python -m api.scripts.test_reduction [--cases PATH [PATH ...]] [--no_window_a11y] [--no_element_a11y]
"""
import argparse
import os
import sys
import time

# ---------------------------------------------------------------------------
# Path setup so this script can be run directly or as a module
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_API_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from api.core.action_reduction.reducer import reduce_recording_by_path

# ---------------------------------------------------------------------------
# Default test cases (the two slow-case examples)
# ---------------------------------------------------------------------------
DEFAULT_TEST_CASES = [
    "~/Downloads/slow-case-e4a3de54-39c3-4435-96b9-7ef8c6635c34",
    "~/Downloads/slow-case-da5b773e-a3bd-40bf-9340-80d87b8f100f",
]

EXPECTED_OUTPUTS = [
    "reduced_events_complete.jsonl",
    "reduced_events_vis.jsonl",
]


def run_case(recording_path: str, generate_window_a11y: bool, generate_element_a11y: bool, skip_video: bool) -> bool:
    expanded = os.path.expanduser(recording_path)
    print(f"\n{'=' * 70}")
    print(f"Case: {expanded}")
    print(f"{'=' * 70}")

    if not os.path.isdir(expanded):
        print(f"[SKIP] Directory not found: {expanded}")
        return False

    start = time.perf_counter()
    try:
        reduce_recording_by_path(
            recording_path=expanded,
            generate_window_a11y=generate_window_a11y,
            generate_element_a11y=generate_element_a11y,
            skip_video=skip_video,
        )
    except Exception as exc:
        print(f"[FAIL] Reduction raised an exception: {exc}")
        return False
    elapsed = time.perf_counter() - start

    # Verify expected output files were created
    all_ok = True
    for fname in EXPECTED_OUTPUTS:
        fpath = os.path.join(expanded, fname)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            print(f"[OK]   {fname}  ({size} bytes)")
        else:
            print(f"[FAIL] {fname} was NOT created")
            all_ok = False

    status = "PASS" if all_ok else "FAIL"
    print(f"[{status}] Completed in {elapsed:.1f}s")
    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="Test the action reduction pipeline on one or more recording directories."
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        metavar="PATH",
        default=DEFAULT_TEST_CASES,
        help="Paths to recording directories to test (default: the two slow-case examples).",
    )
    parser.add_argument(
        "--no_window_a11y",
        action="store_true",
        help="Disable window-level accessibility tree extraction.",
    )
    parser.add_argument(
        "--no_element_a11y",
        action="store_true",
        default=True,
        help="Disable element-level accessibility tree extraction and predict_targets GPT calls (default: True).",
    )
    parser.add_argument(
        "--element_a11y",
        action="store_true",
        help="Enable element-level accessibility tree extraction including predict_targets GPT calls (requires server).",
    )
    parser.add_argument(
        "--full_video",
        action="store_true",
        help="Also run video clip generation (disabled by default — it is CPU-heavy and not needed to verify JSONL output).",
    )
    args = parser.parse_args()

    # By default skip the two expensive side-effects:
    #   1. Video clip cutting (CPU-heavy OpenCV multi-thread work)
    #   2. Element a11y matching incl. predict_targets (outbound GPT/server HTTP calls)
    # Pass --full_video / --element_a11y flags for the full production pipeline.
    generate_window_a11y = not args.no_window_a11y
    generate_element_a11y = args.element_a11y  # off by default
    skip_video = not args.full_video

    results = {}
    for case in args.cases:
        results[case] = run_case(
            recording_path=case,
            generate_window_a11y=generate_window_a11y,
            generate_element_a11y=generate_element_a11y,
            skip_video=skip_video,
        )

    print(f"\n{'=' * 70}")
    print("Summary")
    print(f"{'=' * 70}")
    passed = sum(1 for ok in results.values() if ok)
    total = len(results)
    for path, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {path}")
    print(f"\n{passed}/{total} cases passed.")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
