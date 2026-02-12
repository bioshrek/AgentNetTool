/**
 * Folder Manager - Manages local record organization with 1-tier folders
 * Data is stored in localStorage
 */

export interface Folder {
    id: string;
    name: string;
    createdAt: number;
    color?: string;
}

export interface RecordingFolderMapping {
    [recordingName: string]: string; // recordingName -> folderId (empty string for uncategorized)
}

const FOLDERS_KEY = 'agentnet_folders';
const MAPPING_KEY = 'agentnet_recording_folder_mapping';
const DEFAULT_FOLDER_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

class FolderManager {
    private folders: Folder[] = [];
    private mapping: RecordingFolderMapping = {};

    constructor() {
        this.loadFromStorage();
    }

    /**
     * Load folders and mappings from localStorage
     */
    private loadFromStorage(): void {
        try {
            const foldersData = localStorage.getItem(FOLDERS_KEY);
            const mappingData = localStorage.getItem(MAPPING_KEY);

            if (foldersData) {
                this.folders = JSON.parse(foldersData);
            }

            if (mappingData) {
                this.mapping = JSON.parse(mappingData);
            }
        } catch (error) {
            console.error('Error loading folder data from storage:', error);
            this.folders = [];
            this.mapping = {};
        }
    }

    /**
     * Save folders to localStorage
     */
    private saveFolders(): void {
        try {
            localStorage.setItem(FOLDERS_KEY, JSON.stringify(this.folders));
        } catch (error) {
            console.error('Error saving folders to storage:', error);
        }
    }

    /**
     * Save mappings to localStorage
     */
    private saveMapping(): void {
        try {
            localStorage.setItem(MAPPING_KEY, JSON.stringify(this.mapping));
        } catch (error) {
            console.error('Error saving mapping to storage:', error);
        }
    }

    /**
     * Get all folders
     */
    getFolders(): Folder[] {
        return [...this.folders];
    }

    /**
     * Get a folder by ID
     */
    getFolder(folderId: string): Folder | undefined {
        return this.folders.find(f => f.id === folderId);
    }

    /**
     * Create a new folder
     */
    createFolder(name: string): Folder {
        const folder: Folder = {
            id: `folder_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            name: name.trim(),
            createdAt: Date.now(),
            color: DEFAULT_FOLDER_COLORS[this.folders.length % DEFAULT_FOLDER_COLORS.length]
        };

        this.folders.push(folder);
        this.saveFolders();
        return folder;
    }

    /**
     * Rename a folder
     */
    renameFolder(folderId: string, newName: string): boolean {
        const folder = this.folders.find(f => f.id === folderId);
        if (!folder) {
            return false;
        }

        folder.name = newName.trim();
        this.saveFolders();
        return true;
    }

    /**
     * Delete a folder (recordings will be moved to uncategorized)
     */
    deleteFolder(folderId: string): boolean {
        const index = this.folders.findIndex(f => f.id === folderId);
        if (index === -1) {
            return false;
        }

        // Move all recordings in this folder to uncategorized
        Object.keys(this.mapping).forEach(recordingName => {
            if (this.mapping[recordingName] === folderId) {
                this.mapping[recordingName] = '';
            }
        });

        this.folders.splice(index, 1);
        this.saveFolders();
        this.saveMapping();
        return true;
    }

    /**
     * Get folder ID for a recording
     */
    getRecordingFolder(recordingName: string): string {
        return this.mapping[recordingName] || '';
    }

    /**
     * Move a recording to a folder
     */
    moveRecordingToFolder(recordingName: string, folderId: string): boolean {
        // Validate folder exists (or empty string for uncategorized)
        if (folderId !== '' && !this.folders.find(f => f.id === folderId)) {
            return false;
        }

        this.mapping[recordingName] = folderId;
        this.saveMapping();
        return true;
    }

    /**
     * Get all recordings in a folder
     */
    getRecordingsInFolder(folderId: string, allRecordings: string[]): string[] {
        return allRecordings.filter(recordingName => {
            return this.getRecordingFolder(recordingName) === folderId;
        });
    }

    /**
     * Get uncategorized recordings
     */
    getUncategorizedRecordings(allRecordings: string[]): string[] {
        return this.getRecordingsInFolder('', allRecordings);
    }

    /**
     * Clean up mappings for deleted recordings
     */
    cleanupDeletedRecordings(existingRecordings: string[]): void {
        const recordingSet = new Set(existingRecordings);
        let changed = false;

        Object.keys(this.mapping).forEach(recordingName => {
            if (!recordingSet.has(recordingName)) {
                delete this.mapping[recordingName];
                changed = true;
            }
        });

        if (changed) {
            this.saveMapping();
        }
    }

    /**
     * Get folder statistics
     */
    getFolderStats(folderId: string, allRecordings: string[]): {
        count: number;
        visualizable: number;
    } {
        const recordingsInFolder = this.getRecordingsInFolder(folderId, allRecordings);
        return {
            count: recordingsInFolder.length,
            visualizable: recordingsInFolder.length // This would need actual status from recordings
        };
    }

    /**
     * Export folder structure for backup
     */
    exportFolderStructure(): string {
        return JSON.stringify({
            folders: this.folders,
            mapping: this.mapping,
            exportDate: new Date().toISOString()
        }, null, 2);
    }

    /**
     * Import folder structure from backup
     */
    importFolderStructure(jsonString: string): boolean {
        try {
            const data = JSON.parse(jsonString);
            if (data.folders && data.mapping) {
                this.folders = data.folders;
                this.mapping = data.mapping;
                this.saveFolders();
                this.saveMapping();
                return true;
            }
            return false;
        } catch (error) {
            console.error('Error importing folder structure:', error);
            return false;
        }
    }
}

// Singleton instance
const folderManager = new FolderManager();
export default folderManager;
