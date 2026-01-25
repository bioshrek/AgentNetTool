# Click

```python

# left click
pyautogui.click(145, 252, button='left')

# right click
pyautogui.click(145, 252, button='right')

# middle click
pyautogui.click(145, 252, button='middle')
```

# Double Click

```python
pyautogui.doubleClick(145, 252)
```

# Drag

```python
pyautogui.drag(start=[123, 252], end=[433, 583], button='left')
```

# Scroll

```python
# no moveTo needed, scroll at current mouse position
pyautogui.scroll(-100)
```

# Press

```python
# single key press
pyautogui.press('enter')
pyautogui.press('backspace')

# multiple key press
pyautogui.press(['ctrl', 'c'])
```

# Write

```python
pyautogui.write('hello world')
```
