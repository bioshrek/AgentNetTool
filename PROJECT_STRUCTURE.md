# Project Structure

## Overview
This project is a hybrid Electron application called **AgentNet Annotator**. It combines a TypeScript/React frontend with a Python (Flask) backend to provide recording, annotation, and system control capabilities.

## Directory Layout

### Root Directory
Contains configuration and setups for different operating systems.
- `requirements_*.txt`: Python dependencies for MacOS, Ubuntu, and Windows.
- `add-osx-cert.sh`: Certificate handling for MacOS.
- `pyproject.toml`: Python project configuration.
- `README.md`: General project documentation.

### agentnet-annotator/
The core application folder containing both the Electron frontend and Python backend.

#### `api/` (Python Backend)
The server-side logic, built with Flask.
- **`backend.py`**: The main entry point for the Python server.
- **`controllers/`**: HTTP and WebSocket route handlers.
  - `browser_controller.py`: Manages browser interactions.
  - `recording_controller.py`: Handles screen/action recording requests.
  - `websocket_controller.py`: Manages real-time communication.
- **`core/`**: Core functionalities and utilities.
  - `recorder.py`: Logic for screen recording.
  - `a11y/`: Accessibility tree extraction (Windows/Darwin).
  - `action_reduction/`: Logic for optimizing action sequences.
  - `cloud/`: Cloud service integrations (AWS S3, task hub).
- **`services/`**: Application services.
  - `obs_service.py`: Integration with OBS (Open Broadcaster Software).
  - `recording_service.py`: High-level recording management.
  - `upload_service.py`: File upload logic.

#### `src/` (Frontend)
The Electron renderer process and UI, built with React and TypeScript.
- **`components/`**: React UI components.
  - `Dashboard/`: Main user dashboard views.
  - `TaskHub/`: Task management interface.
  - `Sidebar.tsx`: Navigation sidebar.
- **`context/`**: React Context definitions for state management.
  - `MainContext.tsx`, `AdminDashboardContext.tsx`.
- **`public/`**: Static assets and root React component (`App.tsx`).
- **`utils/`**: Frontend utilities, including `SocketService.tsx` for backend communication.
- **Entry Points**:
  - `index.ts`: Electron main process entry.
  - `renderer.ts`: Electron renderer process entry.

#### Configuration Files
- `forge.config.ts`: Electron Forge build configuration.
- `webpack.*.config.ts`: Webpack bundling configurations.
- `tailwind.config.js`: Tailwind CSS configuration.
- `tsconfig.json`: TypeScript compiler options.
