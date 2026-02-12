import React from "react";
import {
  Modal,
  ModalDialog,
  DialogTitle,
  DialogContent,
  List,
  ListItem,
  ListItemButton,
  ListItemContent,
  Typography,
  IconButton,
} from "@mui/joy";
import FolderIcon from "@mui/icons-material/Folder";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import CloseIcon from "@mui/icons-material/Close";
import folderManager from "../../utils/folderManager";

interface MoveToFolderDialogProps {
  open: boolean;
  onClose: () => void;
  recordingName: string;
  currentFolderId?: string;
  onMove?: (folderId: string) => void;
}

export default function MoveToFolderDialog({
  open,
  onClose,
  recordingName,
  currentFolderId = "",
  onMove,
}: MoveToFolderDialogProps) {
  const folders = folderManager.getFolders();

  const handleMoveToFolder = (folderId: string) => {
    folderManager.moveRecordingToFolder(recordingName, folderId);
    if (onMove) {
      onMove(folderId);
    }
    onClose();
  };

  return (
    <Modal open={open} onClose={onClose}>
      <ModalDialog sx={{ minWidth: 400 }}>
        <DialogTitle>Move to Folder</DialogTitle>
        <IconButton
          onClick={onClose}
          sx={{
            position: "absolute",
            top: 8,
            right: 8,
          }}
        >
          <CloseIcon />
        </IconButton>
        <DialogContent>
          <Typography level="body-sm" sx={{ mb: 2 }}>
            Choose a folder for this recording
          </Typography>
          <List
            sx={{
              "--List-padding": "4px",
              "--ListItem-radius": "8px",
            }}
          >
            {/* Uncategorized option */}
            <ListItem>
              <ListItemButton
                selected={currentFolderId === ""}
                onClick={() => handleMoveToFolder("")}
              >
                <FolderOpenIcon sx={{ mr: 1 }} />
                <ListItemContent>
                  <Typography level="title-sm">Uncategorized</Typography>
                </ListItemContent>
              </ListItemButton>
            </ListItem>

            {/* Folders */}
            {folders.map((folder) => (
              <ListItem key={folder.id}>
                <ListItemButton
                  selected={currentFolderId === folder.id}
                  onClick={() => handleMoveToFolder(folder.id)}
                >
                  <FolderIcon
                    sx={{ mr: 1, color: folder.color || "#3b82f6" }}
                  />
                  <ListItemContent>
                    <Typography level="title-sm">{folder.name}</Typography>
                  </ListItemContent>
                </ListItemButton>
              </ListItem>
            ))}
          </List>
          {folders.length === 0 && (
            <Typography
              level="body-sm"
              sx={{ color: "text.secondary", textAlign: "center", py: 2 }}
            >
              No folders available. Create one from the folder management
              dialog.
            </Typography>
          )}
        </DialogContent>
      </ModalDialog>
    </Modal>
  );
}
