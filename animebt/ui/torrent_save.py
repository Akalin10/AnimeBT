from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Input, Button, Static, Select
from animebt.config import THEMES
from .recovery import RecoveryMixin
from .input import TerminalInput


class TorrentSaveScreen(RecoveryMixin, ModalScreen):
    DEFAULT_CSS = """
    TorrentSaveScreen { align: center middle; }
    #save-dialog { width: 70; height: auto; border: round $accent; padding: 1 2; }
    #save-dialog Horizontal { height: 3; }
    """
    BINDINGS = [("escape", "cancel", "取消")]

    def __init__(self, path):
        super().__init__()
        self.path = path

    def compose(self):
        with Vertical(id="save-dialog"):
            yield Static("保存 torrent 文件（已有文件不会覆盖）")
            yield TerminalInput(self.path, id="torrent-path")
            with Horizontal():
                yield Button("保存", id="confirm-save", variant="primary")
                yield Button("取消", id="cancel-save")

    def on_mount(self):
        self.query_one(Input).focus()

    def action_cancel(self):
        self.dismiss(None)

    def on_input_submitted(self, event):
        event.stop()
        self.confirm()

    def confirm(self):
        path = self.query_one(Input).value.strip()
        if path:
            self.dismiss(path)
        else:
            self.notify("请输入保存路径", severity="warning")

    def on_button_pressed(self, event):
        event.stop()
        if event.button.id == "confirm-save":
            self.confirm()
        else:
            self.action_cancel()


class DirectorySettingsScreen(TorrentSaveScreen):
    DEFAULT_CSS = """
    DirectorySettingsScreen #save-dialog {
        padding: 1 3; max-height: 90%; overflow-y: auto;
    }
    DirectorySettingsScreen #save-dialog Static { margin-bottom: 1; }
    DirectorySettingsScreen #torrent-directory { margin-bottom: 1; }
    DirectorySettingsScreen #theme-choice { margin-bottom: 1; }
    DirectorySettingsScreen #cancel-save { margin-left: 2; }
    """

    def __init__(self, path, theme="textual-dark"):
        super().__init__(path)
        self.selected_theme = theme

    def compose(self):
        with Vertical(id="save-dialog"):
            yield Static("设置种子默认保存目录")
            yield TerminalInput(self.path, id="torrent-directory")
            yield Static("界面主题")
            yield Select([(label, value) for value, label in THEMES.items()],
                         value=self.selected_theme, allow_blank=False, id="theme-choice")
            with Horizontal():
                yield Button("保存设置", id="confirm-save", variant="primary")
                yield Button("取消", id="cancel-save")

    def confirm(self):
        path = self.query_one(Input).value.strip()
        if path:
            self.dismiss((path, self.query_one(Select).value))
        else:
            self.notify("请输入保存路径", severity="warning")
