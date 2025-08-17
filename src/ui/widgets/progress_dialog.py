"""Progress dialog for long-running operations."""

import logging
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Button, Label, ProgressBar, Static
from textual.screen import ModalScreen

logger = logging.getLogger(__name__)


class ProgressDialog(ModalScreen):
    """Modal dialog showing progress of an operation."""
    
    CSS = """
    ProgressDialog {
        align: center middle;
    }
    
    ProgressDialog > Container {
        width: 60;
        height: 12;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    
    ProgressDialog .title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    
    ProgressDialog .status {
        margin-bottom: 1;
    }
    
    ProgressDialog ProgressBar {
        margin-bottom: 1;
    }
    
    ProgressDialog .button-container {
        align: center middle;
        height: 3;
    }
    """
    
    def __init__(self, title: str = "Processing...", **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.cancelled = False
        self.progress_bar = None
        self.status_label = None
        self.details_label = None
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Static(self.title_text, classes="title")
            self.status_label = Label("Starting...", classes="status")
            yield self.status_label
            self.progress_bar = ProgressBar(total=100, show_eta=False)
            yield self.progress_bar
            self.details_label = Label("", classes="details")
            yield self.details_label
            with Container(classes="button-container"):
                yield Button("Cancel", variant="error", id="cancel_btn")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle cancel button press."""
        if event.button.id == "cancel_btn":
            self.cancelled = True
            self.status_label.update("Cancelling...")
            # The export manager should check self.cancelled periodically
    
    def update_progress(self, progress: float, status: str = None, details: str = None):
        """Update the progress display."""
        if self.progress_bar:
            self.progress_bar.update(progress=progress)
        
        if status and self.status_label:
            self.status_label.update(status)
        
        if details and self.details_label:
            self.details_label.update(details)
    
    def close_dialog(self):
        """Close the dialog."""
        self.dismiss()