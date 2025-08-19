"""Resizable container widgets for mouse-driven pane resizing."""

from typing import Optional, Tuple
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static
from textual.reactive import reactive
from textual.events import MouseDown, MouseMove, MouseUp, Click
from textual.geometry import Offset
import logging

logger = logging.getLogger(__name__)


class ResizeSplitter(Static):
    """A visual splitter/handle for resizing panes."""
    
    DEFAULT_CSS = """
    ResizeSplitter.horizontal {
        width: 1;
        min-width: 1;
        max-width: 1;
        background: $primary;
        height: 100%;
    }
    
    ResizeSplitter.horizontal:hover {
        background: $primary-lighten-1;
        width: 1;
    }
    
    ResizeSplitter.horizontal.dragging {
        background: $accent;
        width: 1;
    }
    
    ResizeSplitter.vertical {
        height: 1;
        min-height: 1;
        max-height: 1;
        width: 100%;
        background: $primary;
    }
    
    ResizeSplitter.vertical:hover {
        background: $primary-lighten-1;
        height: 1;
    }
    
    ResizeSplitter.vertical.dragging {
        background: $accent;
        height: 1;
    }
    """
    
    def __init__(self, orientation: str = "horizontal", **kwargs):
        """Initialize the splitter.
        
        Args:
            orientation: Either "horizontal" or "vertical"
        """
        super().__init__(**kwargs)
        self.orientation = orientation
        self.add_class(orientation)
        self.dragging = False
        self.drag_start_pos = None
        self.initial_sizes = None
    
    def on_mouse_down(self, event: MouseDown) -> None:
        """Start dragging when mouse is pressed on splitter."""
        if event.button == 1:  # Left mouse button
            self.dragging = True
            self.drag_start_pos = (event.screen_x, event.screen_y)
            self.add_class("dragging")
            
            # Capture mouse to receive all mouse events
            self.capture_mouse()
            
            # Store initial sizes of adjacent panes
            parent = self.parent
            if parent and hasattr(parent, '_store_initial_sizes'):
                parent._store_initial_sizes()
            
            event.stop()
    
    def on_mouse_up(self, event: MouseUp) -> None:
        """Stop dragging when mouse is released."""
        if self.dragging:
            self.dragging = False
            self.drag_start_pos = None
            self.remove_class("dragging")
            
            # Release mouse capture
            self.release_mouse()
            
            event.stop()
    
    def on_mouse_move(self, event: MouseMove) -> None:
        """Handle mouse movement during drag."""
        if self.dragging and self.drag_start_pos:
            parent = self.parent
            if parent and hasattr(parent, '_handle_resize'):
                if self.orientation == "horizontal":
                    delta = event.screen_x - self.drag_start_pos[0]
                else:
                    delta = event.screen_y - self.drag_start_pos[1]
                
                # Update drag start position for continuous dragging
                self.drag_start_pos = (event.screen_x, event.screen_y)
                
                # Let parent handle the actual resizing
                parent._handle_resize(delta)
            
            event.stop()


class ResizableHorizontal(Horizontal):
    """A horizontal container with resizable panes."""
    
    # Reactive properties for pane sizes
    left_width = reactive(35)  # Percentage
    
    DEFAULT_CSS = """
    ResizableHorizontal {
        height: 100%;
    }
    
    ResizableHorizontal > .left-pane {
        min-width: 20;
    }
    
    ResizableHorizontal > .right-pane {
        min-width: 30;
    }
    """
    
    def __init__(self, 
                 left_widget: Optional[Container] = None,
                 right_widget: Optional[Container] = None,
                 initial_left_width: int = 35,
                 min_left_width: int = 20,
                 max_left_width: int = 70,
                 on_resize_callback: Optional[callable] = None,
                 **kwargs):
        """Initialize resizable horizontal container.
        
        Args:
            left_widget: Widget for left pane
            right_widget: Widget for right pane
            initial_left_width: Initial width of left pane as percentage
            min_left_width: Minimum width of left pane as percentage
            max_left_width: Maximum width of left pane as percentage
            on_resize_callback: Optional callback when size changes
        """
        # Set all attributes BEFORE calling super().__init__ to avoid reactive property issues
        self.min_left_width = min_left_width
        self.max_left_width = max_left_width
        self.on_resize_callback = on_resize_callback
        self.left_widget = left_widget
        self.right_widget = right_widget
        self.splitter = None
        self._initial_left_size = None
        self._initial_container_width = None
        super().__init__(**kwargs)
        # Set reactive property AFTER super().__init__
        self.left_width = initial_left_width
    
    def compose(self) -> ComposeResult:
        """Compose the resizable horizontal layout."""
        # If widgets were passed as constructor args, use them
        if self.left_widget or self.right_widget:
            if self.left_widget:
                self.left_widget.add_class("left-pane")
                self.left_widget.styles.width = f"{self.left_width}%"
                yield self.left_widget
            
            self.splitter = ResizeSplitter(orientation="horizontal")
            yield self.splitter
            
            if self.right_widget:
                self.right_widget.add_class("right-pane")
                self.right_widget.styles.width = f"{100 - self.left_width}%"
                yield self.right_widget
    
    def on_mount(self) -> None:
        """Set initial sizes when mounted."""
        # When used as a context manager, find the widgets by their classes
        for child in self.children:
            if "left-pane" in child.classes and not self.left_widget:
                self.left_widget = child
                child.styles.width = f"{self.left_width}%"
            elif "right-pane" in child.classes and not self.right_widget:
                self.right_widget = child
                child.styles.width = f"{100 - self.left_width}%"
            elif "h-splitter" in child.classes and not self.splitter:
                # Replace the plain Static splitter with our ResizeSplitter
                if not isinstance(child, ResizeSplitter):
                    new_splitter = ResizeSplitter(orientation="horizontal")
                    # Replace in place
                    index = self.children.index(child)
                    child.remove()
                    self.mount(new_splitter, before=self.children[index] if index < len(self.children) else None)
                    self.splitter = new_splitter
                else:
                    self.splitter = child
        
        self._update_pane_sizes()
    
    def watch_left_width(self, new_value: int) -> None:
        """React to left_width changes."""
        self._update_pane_sizes()
        # Call callback if provided
        if self.on_resize_callback:
            self.on_resize_callback('horizontal', new_value)
    
    def _update_pane_sizes(self) -> None:
        """Update the CSS widths of the panes."""
        if self.left_widget and self.right_widget:
            # Ensure width is within bounds
            self.left_width = max(self.min_left_width, 
                                min(self.max_left_width, self.left_width))
            
            right_width = 100 - self.left_width
            
            # Update CSS styles
            self.left_widget.styles.width = f"{self.left_width}%"
            self.right_widget.styles.width = f"{right_width}%"
    
    def _store_initial_sizes(self) -> None:
        """Store initial sizes at start of drag."""
        if self.left_widget:
            self._initial_left_size = self.left_widget.size.width
            self._initial_container_width = self.size.width
    
    def _handle_resize(self, delta_x: int) -> None:
        """Handle resize based on mouse movement.
        
        Args:
            delta_x: Horizontal mouse movement delta in characters
        """
        if self._initial_container_width and self._initial_container_width > 0:
            # Calculate new percentage based on pixel movement
            # Each character is roughly equivalent to some pixels
            percentage_change = (delta_x / self._initial_container_width) * 100
            
            # Update left width
            new_left_width = self.left_width + percentage_change
            
            # Clamp to bounds
            new_left_width = max(self.min_left_width, 
                               min(self.max_left_width, new_left_width))
            
            # Only update if change is significant (avoid jitter)
            if abs(new_left_width - self.left_width) > 0.5:
                self.left_width = new_left_width


class ResizableVertical(Vertical):
    """A vertical container with resizable panes."""
    
    # Reactive properties for pane sizes
    top_height = reactive(40)  # Percentage
    
    DEFAULT_CSS = """
    ResizableVertical {
        width: 100%;
    }
    
    ResizableVertical > .top-pane {
        min-height: 5;
    }
    
    ResizableVertical > .bottom-pane {
        min-height: 5;
    }
    """
    
    def __init__(self,
                 top_widget: Optional[Container] = None,
                 bottom_widget: Optional[Container] = None,
                 initial_top_height: int = 40,
                 min_top_height: int = 20,
                 max_top_height: int = 70,
                 on_resize_callback: Optional[callable] = None,
                 **kwargs):
        """Initialize resizable vertical container.
        
        Args:
            top_widget: Widget for top pane
            bottom_widget: Widget for bottom pane
            initial_top_height: Initial height of top pane as percentage
            min_top_height: Minimum height of top pane as percentage
            max_top_height: Maximum height of top pane as percentage
            on_resize_callback: Optional callback when size changes
        """
        # Set all attributes BEFORE calling super().__init__ to avoid reactive property issues
        self.min_top_height = min_top_height
        self.max_top_height = max_top_height
        self.on_resize_callback = on_resize_callback
        self.top_widget = top_widget
        self.bottom_widget = bottom_widget
        self.splitter = None
        self._initial_top_size = None
        self._initial_container_height = None
        super().__init__(**kwargs)
        # Set reactive property AFTER super().__init__
        self.top_height = initial_top_height
    
    def compose(self) -> ComposeResult:
        """Compose the resizable vertical layout."""
        # If widgets were passed as constructor args, use them
        if self.top_widget or self.bottom_widget:
            if self.top_widget:
                self.top_widget.add_class("top-pane")
                self.top_widget.styles.height = f"{self.top_height}%"
                yield self.top_widget
            
            self.splitter = ResizeSplitter(orientation="vertical")
            yield self.splitter
            
            if self.bottom_widget:
                self.bottom_widget.add_class("bottom-pane")
                self.bottom_widget.styles.height = f"{100 - self.top_height}%"
                yield self.bottom_widget
    
    def on_mount(self) -> None:
        """Set initial sizes when mounted."""
        # When used as a context manager, find the widgets by their classes
        for child in self.children:
            if "top-pane" in child.classes and not self.top_widget:
                self.top_widget = child
                child.styles.height = f"{self.top_height}%"
            elif "bottom-pane" in child.classes and not self.bottom_widget:
                self.bottom_widget = child
                child.styles.height = f"{100 - self.top_height}%"
            elif "v-splitter" in child.classes and not self.splitter:
                # Replace the plain Static splitter with our ResizeSplitter
                if not isinstance(child, ResizeSplitter):
                    new_splitter = ResizeSplitter(orientation="vertical")
                    # Replace in place
                    index = self.children.index(child)
                    child.remove()
                    self.mount(new_splitter, before=self.children[index] if index < len(self.children) else None)
                    self.splitter = new_splitter
                else:
                    self.splitter = child
        
        self._update_pane_sizes()
    
    def watch_top_height(self, new_value: int) -> None:
        """React to top_height changes."""
        self._update_pane_sizes()
        # Call callback if provided
        if self.on_resize_callback:
            self.on_resize_callback('vertical', new_value)
    
    def _update_pane_sizes(self) -> None:
        """Update the CSS heights of the panes."""
        if self.top_widget and self.bottom_widget:
            # Ensure height is within bounds
            self.top_height = max(self.min_top_height, 
                                min(self.max_top_height, self.top_height))
            
            bottom_height = 100 - self.top_height
            
            # Update CSS styles
            self.top_widget.styles.height = f"{self.top_height}%"
            self.bottom_widget.styles.height = f"{bottom_height}%"
    
    def _store_initial_sizes(self) -> None:
        """Store initial sizes at start of drag."""
        if self.top_widget:
            self._initial_top_size = self.top_widget.size.height
            self._initial_container_height = self.size.height
    
    def _handle_resize(self, delta_y: int) -> None:
        """Handle resize based on mouse movement.
        
        Args:
            delta_y: Vertical mouse movement delta in lines
        """
        if self._initial_container_height and self._initial_container_height > 0:
            # Calculate new percentage based on line movement
            percentage_change = (delta_y / self._initial_container_height) * 100
            
            # Update top height
            new_top_height = self.top_height + percentage_change
            
            # Clamp to bounds
            new_top_height = max(self.min_top_height, 
                               min(self.max_top_height, new_top_height))
            
            # Only update if change is significant (avoid jitter)
            if abs(new_top_height - self.top_height) > 0.5:
                self.top_height = new_top_height