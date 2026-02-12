import React, { useState } from "react";
import {
  Modal,
  ModalDialog,
  DialogTitle,
  DialogContent,
  Stack,
  FormControl,
  FormLabel,
  Input,
  Button,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemContent,
  Typography,
  Chip,
  Box,
} from "@mui/joy";
import FolderIcon from "@mui/icons-material/Folder";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import CheckIcon from "@mui/icons-material/Check";
import folderManager, { Folder } from "../../utils/folderManager";

interface FolderDialogProps {
  open: boolean;
  onClose: () => void;
  onFolderChange?: () => void;
  recordingNames?: string[];
}

export default function FolderDialog({
  open,
  onClose,
  onFolderChange,
  recordingNames = [],
}: FolderDialogProps) {
  const [folders, setFolders] = useState<Folder[]>(folderManager.getFolders());
  const [newFolderName, setNewFolderName] = useState("");
  const [editingFolderId, setEditingFolderId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  const refreshFolders = () => {
    setFolders(folderManager.getFolders());
    if (onFolderChange) {
      onFolderChange();
    }
  };

  const handleCreateFolder = () => {
    if (newFolderName.trim()) {
      folderManager.createFolder(newFolderName);
      setNewFolderName("");
      refreshFolders();
    }
  };

  const handleStartEdit = (folder: Folder) => {
    setEditingFolderId(folder.id);
    setEditingName(folder.name);
  };

  const handleSaveEdit = (folderId: string) => {
    if (editingName.trim()) {
      folderManager.renameFolder(folderId, editingName);
      setEditingFolderId(null);
      setEditingName("");
      refreshFolders();
    }
  };

  const handleCancelEdit = () => {
    setEditingFolderId(null);
    setEditingName("");
  };

  const handleDeleteFolder = (folderId: string) => {
    if (
      confirm(
        "Are you sure you want to delete this folder? Recordings will be moved to uncategorized.",
      )
    ) {
      folderManager.deleteFolder(folderId);
      refreshFolders();
    }
  };

  const getFolderCount = (folderId: string): number => {
    return folderManager.getRecordingsInFolder(folderId, recordingNames).length;
  };

  return (
    <Modal open={open} onClose={onClose}>
      <ModalDialog sx={{ minWidth: 500, maxWidth: 600 }}>
        <DialogTitle>Manage Folders</DialogTitle>
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
          <Stack spacing={2}>
            {/* Create New Folder */}
            <FormControl>
              <FormLabel>Create New Folder</FormLabel>
              <Stack direction="row" spacing={1}>
                <Input
                  placeholder="Folder name"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === "Enter") {
                      handleCreateFolder();
                    }
                  }}
                  sx={{ flex: 1 }}
                />
                <Button
                  startDecorator={<AddIcon />}
                  onClick={handleCreateFolder}
                  disabled={!newFolderName.trim()}
                >
                  Create
                </Button>
              </Stack>
            </FormControl>

            {/* Existing Folders */}
            <Box>
              <Typography level="body-sm" sx={{ mb: 1 }}>
                Existing Folders ({folders.length})
              </Typography>
              {folders.length === 0 ? (
                <Typography
                  level="body-sm"
                  sx={{ color: "text.secondary", textAlign: "center", py: 2 }}
                >
                  No folders yet. Create one above!
                </Typography>
              ) : (
                <List
                  sx={{
                    maxHeight: 400,
                    overflow: "auto",
                    "--List-padding": "4px",
                    "--ListItem-radius": "8px",
                  }}
                >
                  {folders.map((folder) => (
                    <ListItem
                      key={folder.id}
                      sx={{
                        bgcolor: "background.surface",
                        mb: 0.5,
                      }}
                    >
                      {editingFolderId === folder.id ? (
                        // Editing mode
                        <Stack
                          direction="row"
                          spacing={1}
                          sx={{ width: "100%", alignItems: "center" }}
                        >
                          <Input
                            value={editingName}
                            onChange={(e) => setEditingName(e.target.value)}
                            onKeyPress={(e) => {
                              if (e.key === "Enter") {
                                handleSaveEdit(folder.id);
                              } else if (e.key === "Escape") {
                                handleCancelEdit();
                              }
                            }}
                            autoFocus
                            sx={{ flex: 1 }}
                            size="sm"
                          />
                          <IconButton
                            size="sm"
                            color="success"
                            onClick={() => handleSaveEdit(folder.id)}
                          >
                            <CheckIcon />
                          </IconButton>
                          <IconButton
                            size="sm"
                            color="neutral"
                            onClick={handleCancelEdit}
                          >
                            <CloseIcon />
                          </IconButton>
                        </Stack>
                      ) : (
                        // Display mode
                        <ListItemButton sx={{ gap: 1 }}>
                          <FolderIcon
                            sx={{ color: folder.color || "#3b82f6" }}
                          />
                          <ListItemContent>
                            <Typography level="title-sm">
                              {folder.name}
                            </Typography>
                          </ListItemContent>
                          <Chip size="sm" variant="soft">
                            {getFolderCount(folder.id)}
                          </Chip>
                          <IconButton
                            size="sm"
                            variant="plain"
                            onClick={() => handleStartEdit(folder)}
                          >
                            <EditIcon />
                          </IconButton>
                          <IconButton
                            size="sm"
                            variant="plain"
                            color="danger"
                            onClick={() => handleDeleteFolder(folder.id)}
                          >
                            <DeleteIcon />
                          </IconButton>
                        </ListItemButton>
                      )}
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>
          </Stack>
        </DialogContent>
      </ModalDialog>
    </Modal>
  );
}
