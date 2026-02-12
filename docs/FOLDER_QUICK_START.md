# Quick Start Guide: Organizing Local Recordings with Folders

## Getting Started

### 1. Access Folder Management

Look for the **Local** section in the sidebar. You'll see a new folder icon with a plus sign next to the sort button.

```
Local  [📁+] [⇅] [5]
```

Click the folder icon to open the Folder Management dialog.

### 2. Create Your First Folder

In the Folder Management dialog:

1. Type a folder name (e.g., "Screenshots", "Tutorials", "Bugs")
2. Press Enter or click "Create"
3. Your folder appears in the list with a colored icon

**Tip:** Folders are automatically assigned different colors for easy identification!

### 3. Move a Recording into a Folder

Two ways to move recordings:

**Method 1: Using the Move Button**

1. Find your recording in the sidebar
2. Click the small folder-with-arrow icon next to it
3. Select your destination folder
4. Done!

**Method 2: From Folder Management**

1. Open Folder Management dialog
2. See the count next to each folder
3. Close the dialog
4. Use the move button on recordings

### 4. Browse Your Organized Recordings

Your sidebar now shows:

```
Local  [📁+] [⇅] [5]
  📁 Screenshots (2)
    ▼
    • Recording 1
    • Recording 2
  📁 Tutorials (1)
    ▼
    • Recording 3
  📁 Uncategorized (2)
    ▼
    • Recording 4
    • Recording 5
```

Click the arrow next to any folder to expand/collapse it.

## Common Tasks

### Rename a Folder

1. Open Folder Management
2. Click the pencil (✏️) icon next to the folder
3. Type the new name
4. Press Enter or click the checkmark ✓

### Delete a Folder

1. Open Folder Management
2. Click the trash (🗑️) icon next to the folder
3. Confirm deletion
4. **Note:** Recordings aren't deleted! They move to "Uncategorized"

### Move Recording to "Uncategorized"

1. Click the move icon next to a recording
2. Select "Uncategorized" at the top of the folder list

### Find Where a Recording Is

Recordings are organized under their folders. If you don't see a recording:

1. Expand all folders by clicking the arrows
2. Check the "Uncategorized" section
3. Use the search box (if available) in your sidebar

## Tips & Tricks

### Organizing Strategy

- **By Project:** Create folders for each project or client
- **By Type:** Screenshots, Demos, Bugs, Features, etc.
- **By Status:** To Review, Completed, In Progress
- **By Date:** Q1 2024, January, Week 1, etc.

### Best Practices

1. **Keep it simple:** Don't create too many folders (5-10 is ideal)
2. **Descriptive names:** Use clear, searchable folder names
3. **Regular cleanup:** Move old recordings or delete unused folders
4. **Consistent naming:** Use a naming convention across folders

### Keyboard Workflow (Future)

Currently, use mouse clicks. Future versions may include:

- `Cmd/Ctrl + N`: New folder
- `Arrow keys`: Navigate folders
- `Enter`: Expand/collapse folder
- Drag and drop support

## Troubleshooting

**Q: I don't see my folders after refreshing**

- Folders are stored in browser localStorage
- Make sure you're using the same browser
- Check if localStorage is enabled in browser settings

**Q: Can I create nested folders?**

- No, only 1-tier folders are supported
- This keeps the organization simple and performant

**Q: What happens if I delete a folder with recordings?**

- Recordings are never deleted
- They automatically move to "Uncategorized"
- You can create a new folder and move them back

**Q: Can I change folder colors?**

- Colors are automatically assigned
- Custom colors may be added in future updates

**Q: How many folders can I create?**

- No hard limit
- Recommended: 5-10 folders for best performance
- localStorage has ~5-10MB limit (depends on browser)

**Q: Can I share folders with my team?**

- Folders are local to your browser only
- No server synchronization (by design)
- Use Export/Import for backups (future feature)

## Examples

### Example 1: Screenshot Organization

```
📁 Product Screenshots (15)
📁 Bug Reports (8)
📁 User Flows (12)
📁 Uncategorized (3)
```

### Example 2: Project-Based

```
📁 Client A - Website (5)
📁 Client B - App (10)
📁 Internal Tools (7)
📁 Demos (4)
📁 Uncategorized (2)
```

### Example 3: Status-Based

```
📁 Ready for Review (6)
📁 In Progress (9)
📁 Completed (20)
📁 Archived (15)
📁 Uncategorized (1)
```

## What's Next?

Future enhancements being considered:

- Drag and drop recordings between folders
- Custom folder colors
- Bulk move operations
- Folder templates
- Export/import folder structure
- Statistics and analytics per folder
- Search within folders

---

**Need Help?**

- Check the main documentation: `docs/FOLDER_FEATURE.md`
- Report issues on GitHub
- Feature requests welcome!
