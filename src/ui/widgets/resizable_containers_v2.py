"""Simplified resizable container widgets for mouse-driven pane resizing."""

from typing import Optional
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static
from textual.reactive import reactive
from textual.events import MouseDown, MouseMove, MouseUp
import logging

logger = logging.getLogger(__name__)


class ResizableHorizontal(Container):
    """A horizontal container with mouse-resizable panes using a splitter."""
    
    DEFAULT_CSS = """
    ResizableHorizontal {
        layout: horizontal;
        height: 100%;
    }
    
    ResizableHorizontal > .left-pane {
        height: 100%;
    }
    
    ResizableHorizontal > .right-pane {
        height: 100%;
    }
    
    ResizableHorizontal > .h-splitter {
        width: 1;
        height: 100%;
        background: $primary;
    }
    
    ResizableHorizontal > .h-splitter:hover {
        background: $primary-lighten-2;
    }
    """
    
    left_width_percent = reactive(35)
    
    def __init__(self, 
                 initial_left_width: int = 35,
                 min_left_width: int = 15,
                 max_left_width: int = 70,
                 **kwargs):
        """Initialize resizable horizontal container."""
        # Initialize attributes before calling super().__init__
        self.min_left_width = min_left_width
        self.max_left_width = max_left_width
        self.dragging = False
        self.drag_start_x = 0
        self.left_pane = None
        self.right_pane = None
        self.splitter = None
        self._initial_left_width = initial_left_width
        super().__init__(**kwargs)
        # Set reactive property after super().__init__
        self.left_width_percent = self._initial_left_width
    
    def compose(self) -> ComposeResult:
        """Compose the layout - yield any pending children."""
        # Yield any children that were added via the 'with' statement
        if hasattr(self, '_pending_children'):
            yield from self._pending_children
    
    def on_mount(self) -> None:
        """Set up the panes when mounted."""
        # Find the panes
        for child in self.children:
            if "left-pane" in child.classes:
                self.left_pane = child
            elif "right-pane" in child.classes:
                self.right_pane = child
            elif "h-splitter" in child.classes:
                self.splitter = child
        
        # Set initial sizes
        self._update_sizes()
    
    def on_mouse_down(self, event: MouseDown) -> None:
        """Start dragging if clicking on the splitter."""
        if event.button == 1 and self.splitter:  # Left button
            # Check if click is on the splitter
            if self.splitter.region.contains(event.screen_offset):
                self.dragging = True
                self.drag_start_x = event.screen_x
                self.capture_mouse()
                event.stop()
    
    def on_mouse_up(self, event: MouseUp) -> None:
        """Stop dragging."""
        if self.dragging:
            self.dragging = False
            self.release_mouse()
            event.stop()
    
    def on_mouse_move(self, event: MouseMove) -> None:
        """Handle dragging."""
        if self.dragging and self.left_pane and self.right_pane:
            # Calculate the new position as a percentage
            container_width = self.size.width
            if container_width > 0:
                new_left_width_px = event.screen_x
                new_left_percent = (new_left_width_px / container_width) * 100
                
                # Clamp to limits
                new_left_percent = max(self.min_left_width, 
                                      min(self.max_left_width, new_left_percent))
                
                # Update if changed significantly
                if abs(new_left_percent - self.left_width_percent) > 0.5:
                    self.left_width_percent = new_left_percent
            
            event.stop()
    
    def watch_left_width_percent(self, value: float) -> None:
        """React to width changes."""
        # Only update if panes exist (after mount)
        if self.left_pane is not None and self.right_pane is not None:
            self._update_sizes()
    
    def _update_sizes(self) -> None:
        """Update the sizes of the panes."""
        if self.left_pane and self.right_pane:
            left_width = self.left_width_percent
            right_width = 100 - left_width - 1  # -1 for splitter
            
            self.left_pane.styles.width = f"{left_width}%"
            self.right_pane.styles.width = f"{right_width}%"


class ResizableVertical(Container):
    """A vertical container with mouse-resizable panes using a splitter."""
    
    DEFAULT_CSS = """
    ResizableVertical {
        layout: vertical;
        width: 100%;
    }
    
    ResizableVertical > .top-pane {
        width: 100%;
    }
    
    ResizableVertical > .bottom-pane {
        width: 100%;
    }
    
    ResizableVertical > .v-splitter {
        height: 1;
        width: 100%;
        background: $primary;
    }
    
    ResizableVertical > .v-splitter:hover {
        background: $primary-lighten-2;
    }
    """
    
    top_height_percent = reactive(40)
    
    def __init__(self,
                 initial_top_height: int = 40,
                 min_top_height: int = 15,
                 max_top_height: int = 70,
                 **kwargs):
        """Initialize resizable vertical container."""
        # Initialize attributes before calling super().__init__
        self.min_top_height = min_top_height
        self.max_top_height = max_top_height
        self.dragging = False
        self.drag_start_y = 0
        self.top_pane = None
        self.bottom_pane = None
        self.splitter = None
        self._initial_top_height = initial_top_height
        super().__init__(**kwargs)
        # Set reactive property after super().__init__
        self.top_height_percent = self._initial_top_height
    
    def compose(self) -> ComposeResult:
        """Compose the layout - yield any pending children."""
        # Yield any children that were added via the 'with' statement
        if hasattr(self, '_pending_children'):
            yield from self._pending_children
    
    def on_mount(self) -> None:
        """Set up the panes when mounted."""
        # Find the panes
        for child in self.children:
            if "top-pane" in child.classes:
                self.top_pane = child
            elif "bottom-pane" in child.classes:
                self.bottom_pane = child
            elif "v-splitter" in child.classes:
                self.splitter = child
        
        # Set initial sizes
        self._update_sizes()
    
    def on_mouse_down(self, event: MouseDown) -> None:
        """Start dragging if clicking on the splitter."""
        if event.button == 1 and self.splitter:  # Left button
            # Check if click is on the splitter
            if self.splitter.region.contains(event.screen_offset):
                self.dragging = True
                self.drag_start_y = event.screen_y
                self.capture_mouse()
                event.stop()
    
    def on_mouse_up(self, event: MouseUp) -> None:
        """Stop dragging."""
        if self.dragging:
            self.dragging = False
            self.release_mouse()
            event.stop()
    
    def on_mouse_move(self, event: MouseMove) -> None:
        """Handle dragging."""
        if self.dragging and self.top_pane and self.bottom_pane:
            # Calculate the new position as a percentage
            container_height = self.size.height
            if container_height > 0:
                new_top_height_px = event.screen_y - self.offset.y
                new_top_percent = (new_top_height_px / container_height) * 100
                
                # Clamp to limits
                new_top_percent = max(self.min_top_height, 
                                     min(self.max_top_height, new_top_percent))
                
                # Update if changed significantly
                if abs(new_top_percent - self.top_height_percent) > 0.5:
                    self.top_height_percent = new_top_percent
            
            event.stop()
    
    def watch_top_height_percent(self, value: float) -> None:
        """React to height changes."""
        # Only update if panes exist (after mount)
        if self.top_pane is not None and self.bottom_pane is not None:
            self._update_sizes()
    
    def _update_sizes(self) -> None:
        """Update the sizes of the panes."""
        if self.top_pane and self.bottom_pane:
            top_height = self.top_height_percent
            bottom_height = 100 - top_height - 1  # -1 for splitter
            
            self.top_pane.styles.height = f"{top_height}%"
            self.bottom_pane.styles.height = f"{bottom_height}%"