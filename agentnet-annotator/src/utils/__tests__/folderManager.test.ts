/**
 * Simple tests for the FolderManager utility
 * Run in browser console to verify functionality
 */

import folderManager from '../folderManager';

// Test 1: Create folders
console.log('Test 1: Creating folders...');
const folder1 = folderManager.createFolder('Work Projects');
const folder2 = folderManager.createFolder('Personal');
const folder3 = folderManager.createFolder('Demos');
console.log('Created folders:', folderManager.getFolders());

// Test 2: Get folder by ID
console.log('\nTest 2: Getting folder by ID...');
const retrieved = folderManager.getFolder(folder1.id);
console.log('Retrieved folder:', retrieved);

// Test 3: Rename folder
console.log('\nTest 3: Renaming folder...');
folderManager.renameFolder(folder1.id, 'Work Projects (Updated)');
console.log('Renamed folder:', folderManager.getFolder(folder1.id));

// Test 4: Move recordings to folders
console.log('\nTest 4: Moving recordings to folders...');
const mockRecordings = ['rec1', 'rec2', 'rec3', 'rec4', 'rec5'];
folderManager.moveRecordingToFolder('rec1', folder1.id);
folderManager.moveRecordingToFolder('rec2', folder1.id);
folderManager.moveRecordingToFolder('rec3', folder2.id);
folderManager.moveRecordingToFolder('rec4', folder3.id);
// rec5 stays uncategorized

console.log('Recordings in Work Projects:', 
    folderManager.getRecordingsInFolder(folder1.id, mockRecordings));
console.log('Recordings in Personal:', 
    folderManager.getRecordingsInFolder(folder2.id, mockRecordings));
console.log('Uncategorized recordings:', 
    folderManager.getUncategorizedRecordings(mockRecordings));

// Test 5: Get folder for a recording
console.log('\nTest 5: Getting folder for recording...');
console.log('rec1 is in folder:', folderManager.getRecordingFolder('rec1'));
console.log('rec5 is in folder:', folderManager.getRecordingFolder('rec5'));

// Test 6: Cleanup deleted recordings
console.log('\nTest 6: Cleanup deleted recordings...');
const activeRecordings = ['rec1', 'rec3', 'rec5']; // rec2 and rec4 deleted
folderManager.cleanupDeletedRecordings(activeRecordings);
console.log('After cleanup - recordings in Work Projects:', 
    folderManager.getRecordingsInFolder(folder1.id, activeRecordings));

// Test 7: Export structure
console.log('\nTest 7: Exporting folder structure...');
const exportData = folderManager.exportFolderStructure();
console.log('Export data:', exportData);

// Test 8: Delete folder
console.log('\nTest 8: Deleting folder...');
folderManager.deleteFolder(folder3.id);
console.log('Remaining folders:', folderManager.getFolders());

// Test 9: Verify persistence
console.log('\nTest 9: Verifying localStorage persistence...');
console.log('Folders in localStorage:', 
    JSON.parse(localStorage.getItem('agentnet_folders') || '[]'));
console.log('Mappings in localStorage:', 
    JSON.parse(localStorage.getItem('agentnet_recording_folder_mapping') || '{}'));

console.log('\n✅ All tests completed!');
console.log('Check the console output above to verify functionality.');
