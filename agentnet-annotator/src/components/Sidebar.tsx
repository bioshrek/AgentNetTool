import * as React from "react";
import {
  GlobalStyles,
  Box,
  Sheet,
  Chip,
  Input,
  List,
  ListItem,
  ListItemButton,
  ListItemContent,
  Typography,
  Avatar,
  Divider,
  Tooltip,
  LinearProgress,
  CircularProgress,
  IconButton,
} from "@mui/joy";
import { listItemButtonClasses } from "@mui/joy/ListItemButton";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import HomeRoundedIcon from "@mui/icons-material/HomeRounded";
import DashboardRoundedIcon from "@mui/icons-material/DashboardRounded";
import AssignmentRoundedIcon from "@mui/icons-material/AssignmentRounded";
import SwapVertIcon from "@mui/icons-material/SwapVert";
import SupportRoundedIcon from "@mui/icons-material/SupportRounded";
import BugReportIcon from "@mui/icons-material/BugReport";
import SettingsRoundedIcon from "@mui/icons-material/SettingsRounded";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import DeleteForeverIcon from "@mui/icons-material/DeleteForever";
import AccountCircleIcon from "@mui/icons-material/AccountCircle";
import FolderIcon from "@mui/icons-material/Folder";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import CreateNewFolderIcon from "@mui/icons-material/CreateNewFolder";
import DriveFileMoveIcon from "@mui/icons-material/DriveFileMove";
import { useEffect, useState } from "react";
import ColorSchemeToggle from "./utils/ColorSchemeToggle";
import { useNavigate, Link, useParams } from "react-router-dom";
import { useMain } from "../context/MainContext";
import folderManager, { Folder } from "../utils/folderManager";
import FolderDialog from "./FolderManager/FolderDialog";
import MoveToFolderDialog from "./FolderManager/MoveToFolderDialog";
import "../public/globals.css";

function Toggler({
  defaultExpanded = true,
  renderToggle,
  children,
}: {
  defaultExpanded?: boolean;
  children: React.ReactNode;
  renderToggle: (params: {
    open: boolean;
    setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  }) => React.ReactNode;
}) {
  const [open, setOpen] = React.useState(defaultExpanded);

  return (
    <React.Fragment>
      {renderToggle({ open, setOpen })}
      <Box
        sx={{
          display: "grid",
          gridTemplateRows: open ? "1fr" : "0fr",
          transition: "0.2s ease",
          "& > *": {
            overflow: "hidden",
          },
        }}
      >
        {children}
      </Box>
    </React.Fragment>
  );
}

interface localRecordingProp {
  name: string;
  creation_time: string;
  task_name: string;
  recording_status: Record<string, any>;
  visualizable: boolean;
  status: string;
  broken?: boolean;
  recoverable?: boolean;
}

interface onlineRecordingProp {
  allocated_timestamp: string | null;
  upload_timestamp: string | null;
  verify_feedback: Record<string, any> | null;
  task_name: string | null;
  task_description: string | null;
  recording_id: string | null;
  downloaded: boolean;
  visualizable: boolean;
  status: string | null;
}

interface SidebarProps {
  tasks?: {
    uploaded_recordings: localRecordingProp[];
    not_uploaded_recordings: onlineRecordingProp[];
  };
  init_open: boolean;
}
export default function Sidebar({ tasks, init_open }: SidebarProps) {
  const {
    uploadedTasks,
    notUploadedTasks,
    fetchTasks,
    showError,
    showInfo,
    showSuccess,
    myos,
    allVerifyTasks,
    fetchNewTasksToVerify,
    username,
    user_id,
    userData,
  } = useMain();
  const navigate = useNavigate();
  const params = useParams();
  const [open, setOpen] = useState(init_open);
  const [notUploadedTasksList, setNotUploadedTasksList] = useState(
    [...notUploadedTasks].sort((a, b) => {
      return a.task_name.localeCompare(b.task_name); // sorted by task name as default
    }),
  );
  const [uploadedTasksList, setUploadedTasksList] = useState(
    [...uploadedTasks].sort((a, b) => {
      return a.task_name.localeCompare(b.task_name); // sorted by task name as default
    }),
  );
  const [sortType, setSortType] = useState("creation_time");
  const [visibleNotUploadedIconIndex, setVisibleNotUploadedIconIndex] =
    useState<number | null>(null);
  const [visibleUploadedIconIndex, setVisibleUploadedIconIndex] = useState<
    number | null
  >(null);
  const [isEnablingWebSocket, setIsEnablingWebSocket] = useState(false);
  const [recoveringRecordings, setRecoveringRecordings] = useState<string[]>(
    [],
  );
  const showSidebarDeleteActions = false;

  // Folder management state
  const [folders, setFolders] = useState<Folder[]>([]);
  const [showFolderDialog, setShowFolderDialog] = useState(false);
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [selectedRecordingForMove, setSelectedRecordingForMove] =
    useState<string>("");
  const [folderExpandState, setFolderExpandState] = useState<
    Record<string, boolean>
  >({});
  const [contextMenuAnchor, setContextMenuAnchor] =
    useState<null | HTMLElement>(null);
  const [contextMenuRecording, setContextMenuRecording] = useState<string>("");
  
  // Editing state for inline name editing
  const [editingRecordingName, setEditingRecordingName] = useState<string | null>(null);
  const [editingNewName, setEditingNewName] = useState<string>("");
  const editInputRef = React.useRef<HTMLInputElement>(null);

  // Missing state variables for verify tasks and UI
  const [toVerifyTasksList, setToVerifyTasksList] = useState(allVerifyTasks);
  const [visibleVerifyIconIndex, setVisibleVerifyIconIndex] = useState<
    number | null
  >(null);
  const [toVerifyTasksProgress, setToVerifyTasksProgress] = useState<
    Record<number, number>
  >({});

  // Refs for user data and UI elements
  const LoginStatusRef = React.useRef(!!user_id);
  const user_avatar_urlRef = React.useRef("");
  const user_idRef = React.useRef(user_id);
  const usernameRef = React.useRef(username);
  const LinearProgressRef = React.useRef<HTMLDivElement>(null);

  // Initialize folder manager on mount
  useEffect(() => {
    const initFolders = async () => {
      await folderManager.initialize();
      setFolders(folderManager.getFolders());
    };
    initFolders();
  }, []);

  useEffect(() => {
    setToVerifyTasksList(allVerifyTasks);
  }, [allVerifyTasks]);

  useEffect(() => {
    LoginStatusRef.current = !!user_id;
    user_idRef.current = user_id;
    usernameRef.current = username;
  }, [user_id, username]);

  useEffect(() => {
    console.log("Sidebar: Initial render, fetching tasks...");
    fetchTasks(); // local tasks
  }, []);

  useEffect(() => {
    console.log("Sidebar: uploadedTasks changed:", uploadedTasks);
    console.log("Sidebar: notUploadedTasks changed:", notUploadedTasks);
  }, [uploadedTasks, notUploadedTasks]);

  useEffect(() => {
    setNotUploadedTasksList(
      [...notUploadedTasks].sort((a, b) => {
        const time_a = new Date(a.creation_time);
        const time_b = new Date(b.creation_time);
        return time_b.getTime() - time_a.getTime();
      }),
    );
    // Cleanup folder mappings when tasks change
    const recordingNames = notUploadedTasks.map((task) => task.name);
    folderManager.cleanupDeletedRecordings(recordingNames);
  }, [notUploadedTasks]);

  useEffect(() => {
    setUploadedTasksList(
      [...uploadedTasks].sort((a, b) => {
        const time_a = new Date(a.creation_time);
        const time_b = new Date(b.creation_time);
        return time_b.getTime() - time_a.getTime();
      }),
    );
  }, [uploadedTasks]);

  const handleSortChange = (event: any) => {
    setSortType(event.target.value);
    const sortedNotUploadedTasklist = [...notUploadedTasksList].sort((a, b) => {
      if (event.target.value === "task_name") {
        return a.task_name.localeCompare(b.task_name);
      } else {
        const time_a = new Date(a.creation_time);
        const time_b = new Date(b.creation_time);
        return time_b.getTime() - time_a.getTime();
      }
    });
    setNotUploadedTasksList(sortedNotUploadedTasklist);
    const sortedUploadedTasklist = [...uploadedTasksList].sort((a, b) => {
      if (event.target.value === "task_name") {
        return a.task_name.localeCompare(b.task_name);
      } else {
        const time_a = new Date(a.creation_time);
        const time_b = new Date(b.creation_time);
        return time_b.getTime() - time_a.getTime();
      }
    });
    setUploadedTasksList(sortedUploadedTasklist);
  };

  const handleDeleteRecording = async (
    recordingName: string,
    taskName: string,
  ) => {
    try {
      const response = await fetch(
        `http://localhost:5328/api/recording/${recordingName}/delete_local_recording`,
      );
      const result = await response.json();

      if (response.ok) {
        showSuccess(result.success);
      } else {
        showError(result.error);
      }
    } catch (error) {
      showError("Network error or server is down.");
    } finally {
      showInfo(`Task ${taskName} deleted`);
      fetchTasks();
      if (params.recording_name === recordingName) {
        navigate("/");
      }
    }
  };

  const handleDeleteVerifyRecording = async (
    recordingName: string,
    taskName: string,
  ) => {
    try {
      const response = await fetch(
        `http://localhost:5328/api/recording/${recordingName}/delete_local_verify_recording`,
      );
      const result = await response.json();

      if (response.ok) {
        showSuccess(result.success);
      } else {
        showError(result.error);
      }
    } catch (error) {
      showError("Network error or server is down.");
    } finally {
      showInfo(`Task ${taskName} deleted`);
      setToVerifyTasksList(
        toVerifyTasksList.filter((task) => task.recording_id !== recordingName),
      );
      fetchNewTasksToVerify();
      if (params.recording_name === recordingName) {
        navigate("/");
      }
    }
  };

  const handleRecoverRecording = async (recordingName: string) => {
    setRecoveringRecordings((prev) => [...prev, recordingName]);
    try {
      const response = await fetch(
        `http://localhost:5328/api/recording/${recordingName}/recover`,
        { method: "POST" },
      );
      const result = await response.json();

      if (response.ok) {
        showSuccess(result.message || "Recovery started");
      } else {
        showError(result.error);
      }
    } catch (error) {
      showError("Network error or server is down.");
    } finally {
      fetchTasks();
      // We might want to keep it in loading state until we get a socket event,
      // but for now let's just clear it after the request returns
      // or maybe wait a bit?
      // Actually, if the backend returns "Recovery started", it goes into data processing
      // which might take time. The list won't update to "visualizable=true" instantly.
      // But we are refreshing fetchTasks().
      // If the status is still broken, maybe we should keep showing loading?
      // Let's just remove it for now to let user retry if needed, but the processing happens in background.
      setRecoveringRecordings((prev) =>
        prev.filter((name) => name !== recordingName),
      );
    }
  };

  // Folder management handlers
  const handleOpenFolderDialog = () => {
    setShowFolderDialog(true);
  };

  const handleCloseFolderDialog = () => {
    setShowFolderDialog(false);
  };

  const handleFolderChange = () => {
    setFolders(folderManager.getFolders());
  };

  const handleOpenMoveDialog = (recordingName: string) => {
    setSelectedRecordingForMove(recordingName);
    setMoveDialogOpen(true);
    setContextMenuAnchor(null);
  };

  const handleCloseMoveDialog = () => {
    setMoveDialogOpen(false);
    setSelectedRecordingForMove("");
  };

  const handleMoveRecording = () => {
    // Refresh the view after moving
    handleFolderChange();
  };

  const toggleFolderExpand = (folderId: string) => {
    setFolderExpandState((prev) => ({
      ...prev,
      [folderId]: !prev[folderId],
    }));
  };

  const getRecordingsInFolder = (folderId: string): localRecordingProp[] => {
    const recordingNames = folderManager.getRecordingsInFolder(
      folderId,
      notUploadedTasksList.map((r) => r.name),
    );
    return notUploadedTasksList.filter((r) => recordingNames.includes(r.name));
  };

  const getUncategorizedRecordings = (): localRecordingProp[] => {
    const recordingNames = folderManager.getUncategorizedRecordings(
      notUploadedTasksList.map((r) => r.name),
    );
    return notUploadedTasksList.filter((r) => recordingNames.includes(r.name));
  };

  const handleContextMenu = (
    event: React.MouseEvent<HTMLElement>,
    recordingName: string,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    setContextMenuRecording(recordingName);
    setContextMenuAnchor(event.currentTarget);
  };

  const handleCloseContextMenu = () => {
    setContextMenuAnchor(null);
    setContextMenuRecording("");
  };

  // Handle double-click to enter edit mode
  const handleDoubleClickName = (recording: localRecordingProp) => {
    if (recording.visualizable && recording.status !== "processing") {
      setEditingRecordingName(recording.name);
      setEditingNewName(recording.task_name);
    }
  };

  // Handle save of edited name
  const handleSaveEdit = async (recordingName: string) => {
    const recording = notUploadedTasksList.find(r => r.name === recordingName);
    if (!recording || !editingNewName.trim() || editingNewName === recording.task_name) {
      // If name is empty or unchanged, just cancel
      setEditingRecordingName(null);
      setEditingNewName("");
      return;
    }

    try {
      // Use the /cut endpoint with full range to just update the name
      // This is the same approach used in Local/page.tsx for saving task names
      const response = await fetch(
        `http://localhost:5328/api/recording/${recordingName}/cut`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            cutTaskName: editingNewName,
            cutDescription: "",
            valMin: 1,
            valMax: 999999, // Large number to ensure it matches full range
          }),
        }
      );

      const result = await response.json();

      if (response.ok) {
        showSuccess("Recording name updated successfully");
        fetchTasks(); // Refresh the list
      } else {
        showError(result.error || "Failed to update recording name");
      }
    } catch (error) {
      showError("Network error or server is down.");
    } finally {
      setEditingRecordingName(null);
      setEditingNewName("");
    }
  };

  // Handle cancel editing
  const handleCancelEdit = () => {
    setEditingRecordingName(null);
    setEditingNewName("");
  };

  // Focus the input when entering edit mode
  useEffect(() => {
    if (editingRecordingName && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingRecordingName]);

  // Helper function to render a recording item
  const renderRecordingItem = (recording: localRecordingProp) => {
    const isEditing = editingRecordingName === recording.name;
    
    return (
      <ListItem
        key={recording.name}
        onMouseEnter={() => {
          if (!showSidebarDeleteActions) {
            return;
          }
          setVisibleNotUploadedIconIndex(
            notUploadedTasksList.indexOf(recording),
          );
        }}
        onMouseLeave={() => {
          if (!showSidebarDeleteActions) {
            return;
          }
          setVisibleNotUploadedIconIndex(null);
        }}
      >
        <Tooltip arrow size="md" title={recording.task_name} placement="right" disableInteractive={isEditing}>
          <ListItemButton
            className="flex flex-row justify-between w-full"
            onContextMenu={(e) => handleContextMenu(e, recording.name)}
          >
            {recording.status === "processing" ? (
              <div
                style={{
                  maxWidth: "70%",
                }}
                className="flex flex-col gap-0"
              >
                <p className="text-sm font-semibold text-gray-400 truncate">
                  <div
                    className="animate-spin inline-block size-3 border-[2px] border-current border-t-transparent text-gray-600 rounded-full"
                    role="status"
                    aria-label="loading"
                  >
                    <span className="sr-only">Loading...</span>
                  </div>{" "}
                  {recording.task_name}
                </p>
                <p className="text-[10px] text-gray-400">Processing...</p>
              </div>
            ) : recording.visualizable ? (
              isEditing ? (
                <div
                  style={{
                    maxWidth: "70%",
                  }}
                  className="flex flex-col gap-0"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                  }}
                >
                  <Input
                    ref={editInputRef}
                    value={editingNewName}
                    onChange={(e) => setEditingNewName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleSaveEdit(recording.name);
                      } else if (e.key === "Escape") {
                        e.preventDefault();
                        handleCancelEdit();
                      }
                    }}
                    onBlur={() => handleSaveEdit(recording.name)}
                    size="sm"
                    sx={{ 
                      fontSize: "0.875rem",
                      padding: "2px 4px",
                      minHeight: "auto"
                    }}
                  />
                  <p className="text-[10px] text-zinc-600 dark:text-zinc-400">
                    {recording.creation_time}
                  </p>
                </div>
              ) : (
                <Link
                  to={`tasks/${recording.name}`}
                  style={{
                    maxWidth: "70%",
                  }}
                  onDoubleClick={(e) => {
                    e.preventDefault();
                    handleDoubleClickName(recording);
                  }}
                >
                  <div className="flex flex-col gap-0">
                    <p className="text-sm font-semibold text-black dark:text-white truncate">
                      {recording.task_name}
                    </p>
                    <p className="text-[10px] text-zinc-600 dark:text-zinc-400">
                      {recording.creation_time}
                    </p>
                  </div>
                </Link>
              )
            ) : (
              <div
                style={{
                  maxWidth: "70%",
                }}
                className="flex flex-col gap-0"
              >
                <p className="text-sm font-semibold text-zinc-600 truncate dark:text-zinc-400">
                  <del>{recording.task_name}</del>
                </p>
                {recoveringRecordings.includes(recording.name) ? (
                  <div className="flex gap-1 items-center">
                    <div
                      className="animate-spin inline-block size-3 border-[2px] border-current border-t-transparent text-gray-600 rounded-full"
                      role="status"
                      aria-label="loading"
                    >
                      <span className="sr-only">Loading...</span>
                    </div>
                    <p className="text-[10px] text-gray-400">Recovering...</p>
                  </div>
                ) : recording.broken && recording.recoverable ? (
                  <Chip
                    size="sm"
                    variant="solid"
                    color="warning"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRecoverRecording(recording.name);
                    }}
                    sx={{ cursor: "pointer", fontSize: "10px", height: "20px" }}
                  >
                    Recover
                  </Chip>
                ) : (
                  <p className="text-[10px] text-zinc-600 truncate dark:text-zinc-400">
                    BROKEN
                  </p>
                )}
              </div>
            )}
            <IconButton
              size="sm"
              variant="plain"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleOpenMoveDialog(recording.name);
              }}
              sx={{ ml: "auto" }}
            >
              <DriveFileMoveIcon fontSize="small" />
            </IconButton>
            {showSidebarDeleteActions &&
              visibleNotUploadedIconIndex ===
                notUploadedTasksList.indexOf(recording) && (
                <DeleteForeverIcon
                  className=""
                  onClick={() =>
                    handleDeleteRecording(recording.name, recording.task_name)
                  }
                />
              )}
          </ListItemButton>
        </Tooltip>
      </ListItem>
    );
  };

  const handleEnableOBSWebSocket = async () => {
    setIsEnablingWebSocket(true);
    try {
      const response = await fetch(
        "http://localhost:5328/enable_obs_websocket",
        {
          method: "GET",
        },
      );
      const result = await response.json();
      if (response.ok) {
        showSuccess("OBS WebSocket enabled successfully");
      } else {
        showError(result.error || "Failed to enable OBS WebSocket");
      }
    } catch (error) {
      showError("Network error or server is down.");
    } finally {
      setIsEnablingWebSocket(false);
    }
  };

  useEffect(() => {
    if (init_open) {
      setOpen(true);
    }
  }, [init_open]);
  return (
    <Sheet
      sx={{
        position: { xs: "fixed", md: "sticky" },
        transform: {
          xs: "translateX(calc(100% * (var(--SideNavigation-slideIn, 0) - 1)))",
          md: "none",
        },
        transition: "transform 0.4s, width 0.4s",
        height: "100vh",
        width: "var(--Sidebar-width)",
        top: 0,
        left: 0,
        pl: 2,
        pr: 2,
        pt: 1,
        pb: 1,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: 2,
        borderRight: "1px solid",
        borderColor: "divider",
        bgcolor: "background.surface",
        overflow: "hidden",
      }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => {
        if (!init_open) {
          setOpen(false);
        }
      }}
      className="z-5"
    >
      <GlobalStyles
        styles={(theme) => ({
          ":root": {
            "--Sidebar-width": open ? "30vw" : "5vw",
            [theme.breakpoints.up("lg")]: {
              "--Sidebar-width": open ? "400px" : "64px",
            },
          },
        })}
      />
      <Box
        sx={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100vw",
          height: "100vh",
          opacity: "var(--SideNavigation-slideIn)",
          backgroundColor: "var(--joy-palette-background-backdrop)",
          transition: "opacity 0.4s",
          transform: {
            xs: "translateX(calc(100% * (var(--SideNavigation-slideIn, 0) - 1) + var(--SideNavigation-slideIn, 0) * var(--Sidebar-width, 0px)))",
            lg: "translateX(-100%)",
          },
        }}
        className="z-4"
      />

      <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
        <ColorSchemeToggle />
        {open && (
          <Typography level="title-lg" sx={{ color: "text.primary" }}>
            AgentNet
          </Typography>
        )}
      </Box>
      <Input
        size="sm"
        startDecorator={<SearchRoundedIcon />}
        placeholder="Search"
        sx={{
          "--Input-placeholderColor": "text.tertiary",
          "--Input-decoratorColor": "text.secondary",
        }}
      />
      <Box
        sx={{
          minHeight: 0,
          overflow: "hidden auto",
          flexGrow: 1,
          display: "flex",
          flexDirection: "column",
          [`& .${listItemButtonClasses.root}`]: {
            gap: 1.5,
          },
        }}
      >
        <List
          size="sm"
          sx={{
            gap: 1,
            "--List-nestedInsetStart": "30px",
            "--ListItem-radius": (theme) => theme.vars.radius.sm,
            "--ListItem-color": "text.primary",
            "--ListItem-hoverColor": "text.primary",
            "--ListItem-activeColor": "text.primary",
          }}
        >
          <ListItem>
            <Link to={``}>
              <ListItemButton>
                <HomeRoundedIcon />
                <ListItemContent>
                  <Typography level="title-sm">Home</Typography>
                </ListItemContent>
              </ListItemButton>
            </Link>
          </ListItem>
          {false && (
            <ListItem>
              <Link to={`dashboard`}>
                <ListItemButton>
                  <DashboardRoundedIcon />
                  <ListItemContent>
                    <Typography level="title-sm">Dashboard</Typography>
                  </ListItemContent>
                </ListItemButton>
              </Link>
            </ListItem>
          )}

          {true && (
            <ListItem nested>
              <Toggler
                renderToggle={({ open, setOpen }) => (
                  <ListItemButton>
                    <AssignmentRoundedIcon />
                    <ListItemContent
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <Typography level="title-sm">Local</Typography>
                      <div className="flex gap-1">
                        <Tooltip
                          arrow
                          color="primary"
                          size="sm"
                          variant="solid"
                          title="Manage Folders"
                        >
                          <IconButton
                            size="sm"
                            variant="plain"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenFolderDialog();
                            }}
                          >
                            <CreateNewFolderIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip
                          arrow
                          color="primary"
                          size="sm"
                          variant="solid"
                          title={`Sort by ${
                            sortType === "task_name"
                              ? "creation time"
                              : "task name"
                          }`}
                        >
                          <SwapVertIcon
                            onClick={() =>
                              handleSortChange({
                                target: {
                                  value:
                                    sortType === "task_name"
                                      ? "creation_time"
                                      : "task_name",
                                },
                              })
                            }
                          />
                        </Tooltip>
                        <Chip size="sm" color="primary" variant="solid">
                          {notUploadedTasksList.length}
                        </Chip>
                      </div>
                    </ListItemContent>
                    <KeyboardArrowDownIcon
                      sx={{
                        transform: open ? "rotate(180deg)" : "none",
                      }}
                      onClick={() => setOpen(!open)}
                    />
                  </ListItemButton>
                )}
              >
                <List sx={{ gap: 0.5, pl: 1 }}>
                  {/* Render folders */}
                  {folders.map((folder) => {
                    const recordingsInFolder = getRecordingsInFolder(folder.id);
                    const isExpanded = folderExpandState[folder.id] !== false;

                    return (
                      <ListItem key={folder.id} nested sx={{ my: 0.5 }}>
                        <Toggler
                          defaultExpanded={isExpanded}
                          renderToggle={({ open, setOpen }) => (
                            <ListItemButton
                              onClick={() => {
                                setOpen(!open);
                                toggleFolderExpand(folder.id);
                              }}
                              sx={{
                                py: 0.5,
                                minHeight: 32,
                              }}
                            >
                              <FolderIcon
                                sx={{
                                  color: folder.color || "#3b82f6",
                                  fontSize: "18px",
                                }}
                              />
                              <ListItemContent>
                                <Typography
                                  level="body-sm"
                                  sx={{ fontWeight: 500 }}
                                >
                                  {folder.name}
                                </Typography>
                              </ListItemContent>
                              <Chip
                                size="sm"
                                variant="soft"
                                sx={{ fontSize: "10px", height: "18px" }}
                              >
                                {recordingsInFolder.length}
                              </Chip>
                              <KeyboardArrowDownIcon
                                sx={{
                                  transform: open ? "rotate(180deg)" : "none",
                                  fontSize: "18px",
                                }}
                              />
                            </ListItemButton>
                          )}
                        >
                          <List sx={{ gap: 0.5, pl: 2 }}>
                            {recordingsInFolder.map((recording) =>
                              renderRecordingItem(recording),
                            )}
                            {recordingsInFolder.length === 0 && (
                              <Typography
                                level="body-xs"
                                sx={{
                                  pl: 2,
                                  py: 1,
                                  color: "text.tertiary",
                                }}
                              >
                                No recordings
                              </Typography>
                            )}
                          </List>
                        </Toggler>
                      </ListItem>
                    );
                  })}

                  {/* Uncategorized recordings */}
                  {getUncategorizedRecordings().length > 0 && (
                    <ListItem nested sx={{ my: 0.5 }}>
                      <Toggler
                        defaultExpanded={
                          folderExpandState["uncategorized"] !== false
                        }
                        renderToggle={({ open, setOpen }) => (
                          <ListItemButton
                            onClick={() => {
                              setOpen(!open);
                              toggleFolderExpand("uncategorized");
                            }}
                            sx={{
                              py: 0.5,
                              minHeight: 32,
                            }}
                          >
                            <FolderOpenIcon sx={{ fontSize: "18px" }} />
                            <ListItemContent>
                              <Typography
                                level="body-sm"
                                sx={{ fontWeight: 500 }}
                              >
                                Uncategorized
                              </Typography>
                            </ListItemContent>
                            <Chip
                              size="sm"
                              variant="soft"
                              sx={{ fontSize: "10px", height: "18px" }}
                            >
                              {getUncategorizedRecordings().length}
                            </Chip>
                            <KeyboardArrowDownIcon
                              sx={{
                                transform: open ? "rotate(180deg)" : "none",
                                fontSize: "18px",
                              }}
                            />
                          </ListItemButton>
                        )}
                      >
                        <List sx={{ gap: 0.5, pl: 2 }}>
                          {getUncategorizedRecordings().map((recording) =>
                            renderRecordingItem(recording),
                          )}
                        </List>
                      </Toggler>
                    </ListItem>
                  )}

                  {/* Show message if no recordings at all */}
                  {notUploadedTasksList.length === 0 && (
                    <Typography
                      level="body-sm"
                      sx={{
                        pl: 2,
                        py: 2,
                        color: "text.tertiary",
                        textAlign: "center",
                      }}
                    >
                      No recordings yet
                    </Typography>
                  )}
                </List>
              </Toggler>
            </ListItem>
          )}
          {false && (
            <ListItem nested>
              <Toggler
                renderToggle={({ open, setOpen }) => (
                  <ListItemButton>
                    <AssignmentRoundedIcon />
                    <ListItemContent
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <Typography level="title-sm">Uploaded</Typography>
                      <div className="flex gap-1">
                        <Chip size="sm" color="success" variant="solid">
                          {uploadedTasksList.length}
                        </Chip>
                      </div>
                    </ListItemContent>
                    <KeyboardArrowDownIcon
                      sx={{
                        transform: open ? "rotate(180deg)" : "none",
                      }}
                      onClick={() => setOpen(!open)}
                    />
                  </ListItemButton>
                )}
              >
                <List sx={{ gap: 0.5 }}>
                  {uploadedTasksList.map((recording) => (
                    <ListItem
                      key={recording.name}
                      onMouseEnter={() => {
                        if (!showSidebarDeleteActions) {
                          return;
                        }
                        setVisibleUploadedIconIndex(
                          uploadedTasksList.indexOf(recording),
                        );
                      }}
                      onMouseLeave={() => {
                        if (!showSidebarDeleteActions) {
                          return;
                        }
                        setVisibleUploadedIconIndex(null);
                      }}
                    >
                      <Tooltip
                        arrow
                        size="md"
                        title={recording.task_name}
                        placement="right"
                      >
                        <ListItemButton className="flex flex-row justify-between w-full">
                          {recording.status === "processing" ? (
                            <div
                              style={{
                                maxWidth: "80%",
                              }}
                              className="flex flex-col gap-0"
                            >
                              <p className="text-sm font-semibold text-gray-400 truncate">
                                <div
                                  className="animate-spin inline-block size-3 border-[2px] border-current border-t-transparent text-gray-600 rounded-full"
                                  role="status"
                                  aria-label="loading"
                                >
                                  <span className="sr-only">Loading...</span>
                                </div>{" "}
                                {recording.task_name}
                              </p>
                              <p className="text-[10px] text-gray-400">
                                Processing...
                              </p>
                            </div>
                          ) : recording.visualizable ? (
                            <Link
                              to={`tasks/${recording.name}`}
                              style={{
                                maxWidth: "80%",
                              }}
                            >
                              <div className="flex flex-col gap-0">
                                <p className="text-sm font-semibold text-black dark:text-white truncate">
                                  {recording.task_name}
                                </p>
                                <p className="text-[10px] text-zinc-600 dark:text-zinc-400">
                                  {recording.creation_time}
                                </p>
                              </div>
                            </Link>
                          ) : (
                            <div
                              style={{
                                maxWidth: "80%",
                              }}
                              className="flex flex-col gap-0"
                            >
                              <p className="text-sm font-semibold text-zinc-600 truncate dark:text-zinc-400">
                                <del>{recording.task_name}</del>
                              </p>
                              <p className="text-[10px] text-zinc-600 truncate dark:text-zinc-400">
                                BROKEN
                              </p>
                            </div>
                          )}
                          {showSidebarDeleteActions &&
                            visibleUploadedIconIndex ===
                              uploadedTasksList.indexOf(recording) && (
                              <DeleteForeverIcon
                                className=""
                                onClick={() =>
                                  handleDeleteRecording(
                                    recording.name,
                                    recording.task_name,
                                  )
                                }
                              />
                            )}
                        </ListItemButton>
                      </Tooltip>
                    </ListItem>
                  ))}
                </List>{" "}
              </Toggler>
            </ListItem>
          )}
          {false && (
            <ListItem nested>
              <Toggler
                renderToggle={({ open, setOpen }) => (
                  <ListItemButton>
                    <AssignmentRoundedIcon />
                    <ListItemContent
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <Typography level="title-sm">Verify</Typography>
                      <div className="flex gap-1"></div>
                    </ListItemContent>
                    <KeyboardArrowDownIcon
                      sx={{
                        transform: open ? "rotate(180deg)" : "none",
                      }}
                      onClick={() => setOpen(!open)}
                    />
                  </ListItemButton>
                )}
              >
                <List sx={{ gap: 0.5 }}>
                  {toVerifyTasksList.map((recording) => (
                    <ListItem
                      key={recording.recording_id}
                      onMouseEnter={() => {
                        if (!showSidebarDeleteActions) {
                          return;
                        }
                        setVisibleVerifyIconIndex(
                          toVerifyTasksList.indexOf(recording),
                        );
                      }}
                      onMouseLeave={() => {
                        if (!showSidebarDeleteActions) {
                          return;
                        }
                        setVisibleVerifyIconIndex(null);
                      }}
                    >
                      <ListItemButton className="flex flex-row justify-between">
                        {recording.downloaded ? (
                          recording.visualizable ? (
                            <Link
                              to={`reviewtasks/${recording.recording_id}`}
                              style={{
                                maxWidth: "80%",
                              }}
                            >
                              <div className="flex flex-col gap-0">
                                <p className="text-sm font-semibold text-black truncate dark:text-white">
                                  {recording.task_name}
                                </p>
                                <p className="text-[10px] text-zinc-600 truncate dark:text-zinc-400">
                                  {recording.upload_timestamp}
                                </p>
                              </div>
                            </Link>
                          ) : (
                            <div
                              style={{
                                maxWidth: "80%",
                              }}
                              className="flex flex-col gap-0"
                            >
                              <div className="flex flex-col gap-0">
                                <p className="text-sm font-semibold text-zinc-600 truncate dark:text-zinc-400">
                                  <del>{recording.task_name}</del>
                                </p>
                                <p className="text-[10px] text-zinc-600 truncate dark:text-zinc-400">
                                  BROKEN
                                </p>
                              </div>
                            </div>
                          )
                        ) : (
                          <div
                            style={{
                              maxWidth: "80%",
                            }}
                            className="flex flex-col gap-0"
                          >
                            <div className="flex flex-col gap-0 w-full">
                              <p className="text-sm font-semibold text-black truncate dark:text-white">
                                {recording.task_name}
                              </p>
                              <LinearProgress
                                ref={LinearProgressRef}
                                className="w-full"
                                determinate
                                value={
                                  toVerifyTasksProgress[
                                    toVerifyTasksList.indexOf(recording)
                                  ]
                                }
                              />
                            </div>
                          </div>
                        )}{" "}
                        {showSidebarDeleteActions &&
                          visibleVerifyIconIndex ===
                            toVerifyTasksList.indexOf(recording) && (
                            <DeleteForeverIcon
                              className=""
                              onClick={() =>
                                handleDeleteVerifyRecording(
                                  recording.recording_id,
                                  recording.task_name,
                                )
                              }
                            />
                          )}
                      </ListItemButton>
                    </ListItem>
                  ))}
                </List>
              </Toggler>
            </ListItem>
          )}
        </List>

        <List
          size="sm"
          sx={{
            mt: "auto",
            flexGrow: 0,
            "--ListItem-radius": (theme) => theme.vars.radius.sm,
            "--List-gap": "8px",
            "--ListItem-color": "text.primary",
            "--ListItem-hoverColor": "text.primary",
            "--ListItem-activeColor": "text.primary",
          }}
        >
          <ListItem>
            <Link to={`Report`}>
              <ListItemButton>
                <BugReportIcon />
                Report
              </ListItemButton>
            </Link>
          </ListItem>
          {myos === "darwin" && (
            <ListItem>
              <ListItemButton
                onClick={handleEnableOBSWebSocket}
                disabled={isEnablingWebSocket}
              >
                {isEnablingWebSocket ? (
                  <CircularProgress size="sm" />
                ) : (
                  <SupportRoundedIcon />
                )}
                OBS configure
              </ListItemButton>
            </ListItem>
          )}
          <ListItem>
            <ListItemButton>
              <SettingsRoundedIcon />
              Settings
            </ListItemButton>
          </ListItem>
        </List>
      </Box>
      <Divider />
      {!LoginStatusRef.current ? (
        <Link to={`LoginAccount`}>
          <ListItemButton className=" mb-1" sx={{ color: "text.primary" }}>
            <Box
              sx={{
                display: "flex",
                gap: 1,
                alignItems: "center",
              }}
            >
              <Box className="px-2">
                <AccountCircleIcon />
              </Box>
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography level="title-sm">Login</Typography>
                <Typography level="body-xs">Click to login</Typography>
              </Box>
            </Box>
          </ListItemButton>
        </Link>
      ) : (
        <Box
          className="flex gap-1 items-center space-between w-full"
          id={username}
          sx={{ color: "text.primary" }}
        >
          <Box className="px-2">
            <Avatar
              variant="outlined"
              size="sm"
              src={user_avatar_urlRef.current}
            />
          </Box>
          <Tooltip title={user_idRef.current} variant="soft">
            <div className="flex-1">
              <p className="text-sm text-warp text-black dark:text-white">
                {usernameRef.current}
              </p>
              {userData?.user_type === "BANNED" ? (
                <Chip color="danger" variant="soft">
                  {userData?.user_type}
                </Chip>
              ) : userData?.user_type === "REGULAR" ? (
                <Chip color="primary" variant="soft">
                  {userData?.user_type}
                </Chip>
              ) : userData?.user_type === "ADMIN" ? (
                <Chip color="warning" variant="soft">
                  {userData?.user_type}
                </Chip>
              ) : null}
            </div>
          </Tooltip>
        </Box>
      )}

      {/* Folder Management Dialog */}
      <FolderDialog
        open={showFolderDialog}
        onClose={handleCloseFolderDialog}
        onFolderChange={handleFolderChange}
        recordingNames={notUploadedTasksList.map((r) => r.name)}
      />

      {/* Move to Folder Dialog */}
      <MoveToFolderDialog
        open={moveDialogOpen}
        onClose={handleCloseMoveDialog}
        recordingName={selectedRecordingForMove}
        currentFolderId={folderManager.getRecordingFolder(
          selectedRecordingForMove,
        )}
        onMove={handleMoveRecording}
      />
    </Sheet>
  );
}
