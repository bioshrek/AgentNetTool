# Project Structure

## Overview

This project is a hybrid Electron application called **AgentNet Annotator**. It combines a TypeScript/React frontend with a Python (Flask) backend to provide recording, annotation, and system control capabilities.

## Directory Layout

### Root Directory

- `requirements_*.txt`: Python dependencies for macOS, Ubuntu, and Windows.
- `add-osx-cert.sh`: Certificate handling for macOS.
- `pyproject.toml`: Python project configuration.
- `data-process/`: Standalone data processing package with raw/processed datasets and utility scripts.

### agentnet-annotator/

The core application folder containing both the Electron frontend and Python backend.

#### `api/` (Python Backend)

The server-side logic, built with Flask.

- **`backend.py`**: Main entry point for the Python server.
- **`build.py`** / **`runtime-hook.py`**: PyInstaller build helpers.
- **`controllers/`**: HTTP and WebSocket route handlers.
  - `browser_controller.py`: Browser interaction endpoints.
  - `recording_controller.py`: Screen/action recording endpoints.
  - `system_controller.py`: System-level control endpoints.
  - `websocket_controller.py`: Real-time WebSocket communication.
- **`core/`**: Core logic and utilities.
  - `recorder.py`: Screen recording logic.
  - `a11y_listener.py`, `axtree_getter.py`: Accessibility event capture and tree extraction.
  - `ai_assistant.py`: AI-powered annotation assistance.
  - `backend_func.py`, `screen_utils.py`, `utils.py`: Shared helpers.
  - `obs_client.py`: OBS Studio client interface.
  - `metadata.py`, `constants.py`, `logger.py`, `tray.py`: App metadata, constants, logging, and tray icon.
  - `a11y/`: Platform-specific accessibility tree extraction (Windows/Darwin).
  - `action_reduction/`: Action sequence optimization.
  - `dom_utils/`: DOM parsing and manipulation utilities.
  - `cloud/`: AWS S3 and task hub integrations (`aws_s3.py`, `task_hub.py`, `admin_service.py`, `database.py`).
  - `cloud_v2/`: Aliyun OSS integration (`aliyun_oss.py`).
- **`data_process/`**: Data processing pipeline (export, extraction, standardization).
- **`services/`**: Application services.
  - `config_service.py`: Application configuration management.
  - `error_handler.py`: Centralized error handling.
  - `file_service.py`: File I/O operations.
  - `obs_service.py`: OBS integration service.
  - `recording_service.py`: High-level recording management.
  - `upload_service.py`: File upload logic.
- **`scripts/`**: Developer/utility scripts (encryption, OBS config, testing).

#### `src/` (Frontend)

The Electron renderer process and UI, built with React and TypeScript.

- **`components/`**: React UI components.
  - `Sidebar.tsx`: Navigation sidebar.
  - `Dashboard/`: Main user dashboard.
  - `Homepage/`: Landing/home screen.
  - `Login/`: Authentication screens.
  - `TaskHub/`: Task management interface.
  - `FolderManager/`: Recording folder management.
  - `Local/`: Local recordings view.
  - `Report/`: Annotation reporting.
  - `Verify/`: Data verification flow.
  - `ResolutionError/`: Resolution mismatch handling.
  - `prerequisite/`: Setup/prerequisite checks.
  - `utils/`: Shared component utilities.
- **`context/`**: React Context for state management.
  - `MainContext.tsx`, `AdminDashboardContext.tsx`, `SystemTheme.tsx`.
- **`public/`**: Root React app (`App.tsx`, `index.tsx`, `constant.ts`, `globals.css`).
- **`routes/`**: Route-level pages (`error-page.tsx`, `disagree-page.tsx`).
- **`types/`**: Shared TypeScript type definitions.
- **`utils/`**: Frontend utilities (`SocketService.tsx`, `folderManager.ts`, `uploadWorker.js`).
- **Entry Points**:
  - `index.ts`: Electron main process entry.
  - `renderer.ts`: Electron renderer process entry.
  - `Start.ts` / `Stop.ts`: Recording start/stop helpers.
  - `preload.ts`: Electron preload script.
  - `trayicon.ts`: System tray icon setup.

#### Configuration Files

- `forge.config.ts`: Electron Forge build configuration.
- `webpack.*.config.ts`: Webpack bundling configurations.
- `tailwind.config.js`: Tailwind CSS configuration.
- `tsconfig.json`: TypeScript compiler options.
