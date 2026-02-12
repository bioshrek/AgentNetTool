# Folder Organization - UI Reference

## Component Layout

### 1. Sidebar - Local Section Header
```
┌─────────────────────────────────────────┐
│ Local  [📁+] [⇅] [5]                    │
│        │     │    └─ Total count        │
│        │     └────── Sort toggle        │
│        └──────────── Folder mgmt button │
└─────────────────────────────────────────┘
```

### 2. Expanded Folder View
```
┌─────────────────────────────────────────┐
│ Local  [📁+] [⇅] [5]                ▼  │
│   📁 Work Projects (2)              ▼  │
│     • Screenshot 1      [→]             │
│     • Demo Recording    [→]             │
│   📁 Personal (1)                   ▼  │
│     • Quick Test        [→]             │
│   📁 Uncategorized (2)              ▼  │
│     • Recording A       [→]             │
│     • Recording B       [→]             │
└─────────────────────────────────────────┘

Legend:
  📁 = Folder icon (colored)
  ▼ = Expand/collapse arrow
  [→] = Move to folder button
  (N) = Recording count
```

### 3. Folder Management Dialog
```
┌───────────────────────────────────────────┐
│ Manage Folders                        [×] │
├───────────────────────────────────────────┤
│ Create New Folder                         │
│ ┌─────────────────────┐ ┌──────┐         │
│ │ Folder name...      │ │Create│         │
│ └─────────────────────┘ └──────┘         │
│                                           │
│ Existing Folders (3)                      │
│ ┌───────────────────────────────────────┐ │
│ │ 📁 Work Projects    (2) [✏️] [🗑️]      │ │
│ │ 📁 Personal         (1) [✏️] [🗑️]      │ │
│ │ 📁 Demos            (0) [✏️] [🗑️]      │ │
│ └───────────────────────────────────────┘ │
└───────────────────────────────────────────┘

Legend:
  [✏️] = Edit/rename folder
  [🗑️] = Delete folder
  (N) = Recording count in folder
```

### 4. Edit Folder Mode (Inline)
```
┌───────────────────────────────────────────┐
│ Existing Folders (3)                      │
│ ┌───────────────────────────────────────┐ │
│ │ [Work Projects Upd] [✓] [×]           │ │
│ │ 📁 Personal         (1) [✏️] [🗑️]      │ │
│ │ 📁 Demos            (0) [✏️] [🗑️]      │ │
│ └───────────────────────────────────────┘ │
└───────────────────────────────────────────┘

Legend:
  [✓] = Save changes
  [×] = Cancel editing
```

### 5. Move to Folder Dialog
```
┌───────────────────────────────────────────┐
│ Move to Folder                        [×] │
├───────────────────────────────────────────┤
│ Choose a folder for this recording        │
│                                           │
│ ┌───────────────────────────────────────┐ │
│ │ 📂 Uncategorized               [✓]    │ │
│ │ 📁 Work Projects              (2)     │ │
│ │ 📁 Personal                   (1)     │ │
│ │ 📁 Demos                      (0)     │ │
│ └───────────────────────────────────────┘ │
└───────────────────────────────────────────┘

Legend:
  [✓] = Currently selected folder
  📂 = Uncategorized (special folder)
  (N) = Current recording count
```

## Color Scheme

### Folder Colors (Auto-assigned in order)
1. **Blue** - `#3b82f6` (rgb: 59, 130, 246)
2. **Green** - `#10b981` (rgb: 16, 185, 129)
3. **Orange** - `#f59e0b` (rgb: 245, 158, 11)
4. **Red** - `#ef4444` (rgb: 239, 68, 68)
5. **Purple** - `#8b5cf6` (rgb: 139, 92, 246)
6. **Pink** - `#ec4899` (rgb: 236, 72, 153)

Colors cycle when more than 6 folders exist.

## States and Interactions

### Folder States
1. **Collapsed** - Arrow points right (►)
2. **Expanded** - Arrow points down (▼)
3. **Empty** - "No recordings" message shown
4. **Editing** - Inline input field active

### Recording States
1. **Normal** - Black text, clickable link
2. **Processing** - Gray with spinner
3. **Broken** - Strikethrough, gray text
4. **Recoverable** - Shows "Recover" button

### Interactive Elements

#### Hover Effects
- Folders: Light background highlight
- Recordings: Background highlight + show move button
- Buttons: Color change

#### Click Actions
- Folder name/arrow: Toggle expand/collapse
- Recording name: Navigate to recording page
- [📁+] button: Open folder management dialog
- [→] button: Open move to folder dialog
- [✏️] button: Enter edit mode
- [🗑️] button: Delete with confirmation

## Responsive Behavior

### Desktop (>= 1024px)
- Sidebar width: 240px (expanded), 64px (collapsed)
- Full folder names visible
- Icons and text both shown

### Tablet (768px - 1023px)
- Sidebar width: 200px (expanded)
- Truncated long folder names
- Icons and text both shown

### Mobile (< 768px)
- Sidebar: Fixed overlay
- Full width when open
- Auto-collapse on selection

## Accessibility

### Keyboard Navigation
- **Tab**: Navigate between elements
- **Enter**: Select/activate
- **Escape**: Close dialogs/cancel edit
- **Arrow keys**: (Future) Navigate folders

### Screen Reader Support
- Folder names announced with count
- Button labels clear and descriptive
- Modal dialogs properly labeled
- Loading states announced

### Visual Indicators
- Color not sole indicator (icons + text)
- Sufficient contrast ratios
- Focus visible on all interactive elements
- Loading spinners for long operations

## Dark Mode

All components support dark mode with automatic theme switching:

### Light Mode
- Background: White/light gray
- Text: Dark gray/black
- Folders: Bright colors
- Borders: Light gray

### Dark Mode
- Background: Dark gray/black
- Text: White/light gray
- Folders: Slightly muted colors
- Borders: Dark gray

## Animation

### Transitions
- Folder expand/collapse: 200ms ease
- Dialog open/close: Fade in/out
- Hover effects: Instant
- Loading spinners: Continuous rotation

### No Animation
- Data updates (instant)
- State changes (instant)
- Navigation (instant)

## Best Practices

### Folder Naming
- **Good:** "Client Work", "Screenshots", "Q1 2024"
- **Bad:** "Folder1", "asdf", "Untitled"

### Organization
- **Keep it simple:** 5-10 folders max
- **Be specific:** Clear, descriptive names
- **Stay consistent:** Use similar naming patterns

### Performance
- **Collapse unused folders:** Reduces visual clutter
- **Regular cleanup:** Delete empty/unused folders
- **Don't over-organize:** Too many folders = harder to find

---

**UI Framework:** MUI Joy  
**Icons:** Material Icons  
**Styling:** Tailwind CSS + Joy UI  
**Theme:** Light/Dark mode support
