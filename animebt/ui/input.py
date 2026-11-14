from textual.widgets import Input


class TerminalInput(Input):
    """Keep the terminal's IME anchor aligned after layout and focus changes."""

    def on_mount(self):
        self.set_interval(0.1, self.sync_terminal_cursor)

    def sync_terminal_cursor(self):
        if self.screen is self.app.screen and self.has_focus and self.is_on_screen and self.content_region.width:
            position = self.cursor_screen_offset
            if self.app.cursor_position != position:
                self.app.cursor_position = position
                self.refresh()
