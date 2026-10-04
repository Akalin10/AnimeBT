from textual.widgets import DataTable


class ResultsTable(DataTable):
    """Keep selection stable while the pointer moves over the results."""

    def _on_mouse_move(self, event):
        # DataTable normally redraws a second cursor for every hovered cell.
        # Selection remains available by click and keyboard, without hover repaint.
        event.stop()
        event.prevent_default()

    def _set_hover_cursor(self, visible):
        super()._set_hover_cursor(False)
