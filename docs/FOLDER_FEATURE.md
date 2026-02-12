# Local Recording Folder Organization Feature

## Overview

This feature allows users to organize local recordings into folders (1-tier only, no nested folders). The implementation is entirely frontend-based with no server involvement, using browser localStorage for persistence.

## Components

### 1. Folder Manager (`src/utils/folderManager.ts`)

Core utility for managing folder data and operations.

**Features:**

- Create, rename, and delete folders
- Move recordings between folders
- Get recordings by folder
- Cleanup deleted recordings
- Export/import folder structure for backup
- Persistent storage using localStorage

**Data Structure:**

```typescript
interface Folder {
  id: string;
  name: string;
  createdAt: number;
  color?: string; // Visual color identifier
}

interface RecordingFolderMapping {
  [recordingName: string]: string; // recordingName -> folderId
}
```

**Storage Keys:**

- `agentnet_folders`: Stores folder definitions
- `agentnet_recording_folder_mapping`: Stores recording-to-folder mappings

### 2. Folder Dialog Component (`src/components/FolderManager/FolderDialog.tsx`)

Modal dialog for managing folders.

**Features:**

- Create new folders
- Rename existing folders
- Delete folders (recordings move to uncategorized)
- View folder statistics (recording count)
- Color-coded folder icons

**Usage:**

```tsx
<FolderDialog
  open={showFolderDialog}
  onClose={handleCloseFolderDialog}
  onFolderChange={handleFolderChange}
  recordingNames={recordingNames}
/>
```

### 3. Move to Folder Dialog (`src/components/FolderManager/MoveToFolderDialog.tsx`)

Modal dialog for moving a recording to a folder.

**Features:**

- Select target folder for a recording
- Shows current folder
- Option to move to "Uncategorized"

**Usage:**

```tsx
<MoveToFolderDialog
  open={moveDialogOpen}
  onClose={handleCloseMoveDialog}
  recordingName={selectedRecording}
  currentFolderId={currentFolderId}
  onMove={handleMoveRecording}
/>
```

### 4. Updated Sidebar (`src/components/Sidebar.tsx`)

Enhanced sidebar with folder organization.

**New Features:**

- Folder management button (folder icon with "+" in Local section header)
- Collapsible folder tree view
- Each folder shows recording count
- "Uncategorized" section for recordings not in any folder
- Move button on each recording item
- Color-coded folder icons
- Right-click context menu support (prepared for future enhancements)

## User Workflow

### Creating a Folder

1. Click the "Manage Folders" button (folder with plus icon) in the Local section header
2. Enter a folder name in the "Create New Folder" field
3. Click "Create" or press Enter
4. The folder appears in the sidebar with a color-coded icon

### Moving a Recording to a Folder

1. Find the recording in the sidebar
2. Click the move icon (folder with arrow) next to the recording
3. Select the target folder from the dialog
4. The recording is moved instantly

### Renaming a Folder

1. Open the folder management dialog
2. Click the edit icon next to the folder name
3. Enter the new name and press Enter or click the checkmark
4. Press Escape or click X to cancel

### Deleting a Folder

1. Open the folder management dialog
2. Click the delete icon next to the folder
3. Confirm the deletion
4. All recordings in the folder are moved to "Uncategorized"

## Technical Details

### Storage

- All data is stored in browser localStorage
- No server-side storage or API calls
- Data persists across browser sessions
- Automatic cleanup of deleted recordings

### Folder Limits

- Only 1-tier folders (no nested folders)
- Unlimited number of folders
- Unlimited recordings per folder
- Each recording can be in at most one folder

### Sorting

- Folders are displayed in creation order
- Recordings within folders follow the global sort setting (creation time or task name)
- Sort toggle in the Local section header affects all recordings

### Performance

- Efficient localStorage operations
- Minimal re-renders with React state management
- Cleanup operations run automatically when recordings change

## File Structure

```
agentnet-annotator/
├── src/
│   ├── utils/
│   │   └── folderManager.ts          # Core folder management logic
│   ├── components/
│   │   ├── FolderManager/
│   │   │   ├── FolderDialog.tsx      # Folder management UI
│   │   │   └── MoveToFolderDialog.tsx # Move recording UI
│   │   └── Sidebar.tsx                # Updated with folder support
```

## Future Enhancements

### Possible Additions

1. **Drag and Drop**: Drag recordings between folders
2. **Folder Colors**: Custom color picker for folders
3. **Bulk Operations**: Move multiple recordings at once
4. **Search**: Filter recordings by folder
5. **Folder Templates**: Predefined folder structures
6. **Statistics**: Visual analytics per folder
7. **Import/Export**: Backup and restore folder structure
8. **Keyboard Shortcuts**: Quick folder navigation

### Implementation Notes

- All features remain frontend-only
- No changes to backend or database
- Backward compatible with existing recordings
- Safe to enable/disable without data loss

## Troubleshooting

### Folders Not Appearing

- Check browser localStorage is enabled
- Clear browser cache if corrupted
- Check browser console for errors

### Recordings Lost After Folder Delete

- Recordings are never deleted, only moved to "Uncategorized"
- Check the Uncategorized section in the sidebar

### Performance Issues

- If you have many folders (>50), consider consolidating
- localStorage has a size limit (~5-10MB depending on browser)
- Use export/import to backup if needed

## Testing Checklist

- [x] Create folder
- [x] Rename folder
- [x] Delete folder
- [x] Move recording to folder
- [x] Move recording to uncategorized
- [x] Folders persist after page reload
- [x] Recordings show in correct folders
- [x] Folder counts are accurate
- [x] No TypeScript errors
- [x] Responsive UI
- [x] Dark mode compatible
