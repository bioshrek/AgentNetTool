/**
 * Folder Manager - Manages local record organization with 1-tier folders
 * Data is stored in Documents/AgentNet/folder-structure.json
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

interface FolderData {
    folders: Folder[];
    mapping: RecordingFolderMapping;
}

const DEFAULT_FOLDER_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

class FolderManager {
    private folders: Folder[] = [];
    private mapping: RecordingFolderMapping = {};
    private initialized = false;

    constructor() {
        // Load will be called async
    }

    /**
     * Initialize and load folders from file system
     */
    async initialize(): Promise<void> {
        if (this.initialized) return;
        
        try {
            const data = await window.electron.loadFolderData();
            if (data) {
                this.folders = data.folders || [];
                this.mapping = data.mapping || {};
                console.log('Folder data loaded from Documents/AgentNet/folder-structure.json');
            } else {
                // Try to migrate from localStorage if exists
                await this.migrateFromLocalStorage();
            }
        } catch (error) {
            console.error('Error loading folder data from file:', error);
            // Try localStorage as fallback
            await this.migrateFromLocalStorage();
        }
        
        this.initialized = true;
    }

    /**
     * Migrate data from localStorage to file system (one-time migration)
     */
    private async migrateFromLocalStorage(): Promise<void> {
        try {
            const foldersData = localStorage.getItem('agentnet_folders');
            const mappingData = localStorage.getItem('agentnet_recording_folder_mapping');

            if (foldersData || mappingData) {
                this.folders = foldersData ? JSON.parse(foldersData) : [];
                this.mapping = mappingData ? JSON.parse(mappingData) : {};
                
                // Save to file system
                await this.save();
                
                // Clear localStorage after successful migration
                localStorage.removeItem('agentnet_folders');
                localStorage.removeItem('agentnet_recording_folder_mapping');
                
                console.log('Migrated folder data from localStorage to file system');
            }
        } catch (error) {
            console.error('Error migrating from localStorage:', error);
        }
    }

    /**
     * Save folders and mappings to file system
     */
    private async save(): Promise<void> {
        try {
            const data: FolderData = {
                folders: this.folders,
                mapping: this.mapping
            };
            await window.electron.saveFolderData(data);
        } catch (error) {
            console.error('Error saving folder data to file:', error);
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
        this.save();
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
        this.save();
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
        this.save();
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
        this.save();
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
            this.save();
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
    async importFolderStructure(jsonString: string): Promise<boolean> {
        try {
            const data = JSON.parse(jsonString);
            if (data.folders && data.mapping) {
                this.folders = data.folders;
                this.mapping = data.mapping;
                await this.save();
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
