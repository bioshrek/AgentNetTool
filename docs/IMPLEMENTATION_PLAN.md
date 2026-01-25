# Export Feature Implementation Plan

## Overview
Integrate `data-process` visualization script into `agentnet-annotator` to allow users to export recordings.

## components

### 1. Data Process Script
**File:** `data-process/scripts/raw_to_vis_std.sh`
- Update script to accept `INPUT_DIR` and `OUTPUT_DIR` as arguments.
- Maintain backward compatibility with existing hardcoded paths if no arguments are provided.

### 2. Backend (Python/Flask)
**Service:** `agentnet-annotator/api/services/recording_service.py`
- Add `export_recording(recording_name, output_path)` method.
- Add `export_all_recordings(output_path)` method.
- Logic:
  - Locate the `data-process` script relative to the annotator content.
  - Use `subprocess.run` to execute the shell script.
  - Pass the recording(s) path as input and user selected path as output.
  
**Controller:** `agentnet-annotator/api/controllers/recording_controller.py`
- Add endpoints:
  - `POST /api/recordings/<name>/export`
  - `POST /api/recordings/export_all`
- Parse destination path from request body.

**Route Registration:** `agentnet-annotator/api/backend.py`
- Register the new endpoints in `_setup_routes`.

### 3. Electron Layer
**Main Process:** `agentnet-annotator/src/index.ts`
- Add IPC handler `dialog:openDirectory` using `electron.dialog.showOpenDialog`.

**Preload:** `agentnet-annotator/src/preload.ts`
- Expose `openDirectoryDialog` to the renderer via `contextBridge`.

### 4. Frontend (React)
**Types:** `agentnet-annotator/src/types/global.d.ts`
- Update `Window` interface to include the new `openDirectoryDialog` API.

**Component: Dashboard** (`agentnet-annotator/src/components/Dashboard/Regular/RegDashboard.tsx`)
- Add "Export All" button.
- Handler:
  1. Call `window.electron.openDirectoryDialog()`.
  2. If path selected, call API `POST /api/recordings/export_all` with paths.
  3. Show loading/success/error feedback.

**Component: Recording Detail** (`agentnet-annotator/src/components/Local/page.tsx`)
- Add "Export" button.
- Handler similar to Dashboard but for single record.

## Environment Integration
- The backend will invoke the script using `cd ../data-process && uv run ...` or absolute paths to ensure the `data-process` environment (managed by `uv` or `pip`) is used, independent of the annotator's environment.
