"""
Utility functions for getting fresh (non-cached) screen resolution.
"""

from platform import system
from typing import Tuple
from .logger import logger


def get_fresh_screen_resolution() -> Tuple[int, int]:
    """
    Get the current screen resolution without caching.
    Uses platform-specific APIs to ensure fresh values.
    
    Returns:
        Tuple[int, int]: (width, height) of the primary display
    """
    os_type = system()
    
    try:
        if os_type == "Darwin":
            # macOS - use AppKit directly to avoid caching
            import AppKit
            screen = AppKit.NSScreen.mainScreen()
            frame = screen.frame()
            # Get the backing scale factor for Retina displays
            scale = screen.backingScaleFactor()
            width = int(frame.size.width)
            height = int(frame.size.height)
            logger.debug(f"macOS screen resolution (logical): {width}x{height}, scale: {scale}")
            return width, height
            
        elif os_type == "Windows":
            # Windows - use ctypes to call GetSystemMetrics
            import ctypes
            user32 = ctypes.windll.user32
            # SM_CXSCREEN = 0, SM_CYSCREEN = 1
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            logger.debug(f"Windows screen resolution: {width}x{height}")
            return width, height
            
        elif os_type == "Linux":
            # Linux - try multiple methods
            try:
                # Method 1: Use Xlib directly
                from Xlib import display
                d = display.Display()
                screen = d.screen()
                width = screen.width_in_pixels
                height = screen.height_in_pixels
                logger.debug(f"Linux screen resolution (Xlib): {width}x{height}")
                return width, height
            except ImportError:
                # Method 2: Parse xrandr output
                import subprocess
                try:
                    output = subprocess.check_output(['xrandr']).decode('utf-8')
                    for line in output.split('\n'):
                        if ' connected' in line and 'primary' in line:
                            # Parse line like: "eDP-1 connected primary 1920x1080+0+0"
                            parts = line.split()
                            for part in parts:
                                if 'x' in part and '+' in part:
                                    resolution = part.split('+')[0]
                                    width, height = map(int, resolution.split('x'))
                                    logger.debug(f"Linux screen resolution (xrandr): {width}x{height}")
                                    return width, height
                except Exception as e:
                    logger.warning(f"Failed to get resolution via xrandr: {e}")
        
        # Fallback to pyautogui if platform-specific methods fail
        logger.warning(f"Using fallback method (pyautogui) for {os_type}")
        import pyautogui
        size = pyautogui.size()
        return size.width, size.height
        
    except Exception as e:
        logger.exception(f"Error getting fresh screen resolution: {e}")
        # Last resort fallback
        import pyautogui
        size = pyautogui.size()
        return size.width, size.height
