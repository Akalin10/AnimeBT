from textual.app import App, ComposeResult
from .results_table import ResultsTable
from .themes import RAM_THEME
from .input import TerminalInput
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Input, Button, DataTable, Static, TextArea
from textual import work
from textual.binding import Binding
from animebt.core.torrent import resolve_magnet
from animebt.core.results import filter_sort, display_date
from animebt.core.torrent import save_torrent
from .torrent_save import TorrentSaveScreen, DirectorySettingsScreen
from animebt.config import save_settings
from .recovery import RecoveryAppMixin
from animebt.core.runtime import record_error


class AnimeBTApp(RecoveryAppMixin, App):
    TITLE = "Search"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { background: $background; }
    HeaderIcon { display: none; }
    #searchbar { height: 3; margin-bottom: 1; }
    #keyword { width: 1fr; }
    #status { display: none; }
    DataTable { height: 1fr; min-height: 3; background: $surface; }
    #detail { height: 5; margin-top: 1; background: $surface; }
    Footer { padding: 0 1; }
    Footer FooterKey { margin-right: 3; }
    """
    BINDINGS = [
        Binding("ctrl+c", "copy_magnet", "复制 Magnet", priority=True),
        Binding("ctrl+s", "save_torrent", "保存种子", priority=True),
        Binding("ctrl+o", "settings", "设置", priority=True),
        *[Binding(key, action, label, priority=True, show=False) for key, action, label in [
            ("ctrl+q", "quit", "退出"), ("ctrl+r", "refresh", "刷新"),
            ("ctrl+f", "focus_search", "搜索"), ("ctrl+l", "focus_results", "结果")]],
    ]

    def __init__(self, service, startup_error=None):
        super().__init__()
        self.animation_level = "none"
        self._detail_timer = None
        self.service = service
        self.register_theme(RAM_THEME)
        self.theme = service.settings.theme
        self.resources = []
        self.all_resources = []
        self.search_status = ""
        self.sort = "time_desc"
        self.startup_error = startup_error
        self.generation = 0
        self.detail_generation = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="searchbar"):
            yield TerminalInput(id="keyword")
            yield Button("搜索", id="search", variant="primary")
        yield Static("", id="status", markup=False)
        yield ResultsTable(id="results", cursor_type="row", cell_padding=2)
        yield TextArea("选择结果查看详情。", read_only=True, soft_wrap=False, id="detail")
        yield Footer(show_command_palette=False)

    def on_mount(self):
        self.update_columns()
        self.query_one(Input).focus()
        if self.startup_error:
            self.notify(self.startup_error, severity="error", timeout=15)

    def check_action(self, action, parameters):
        if self.is_mounted and isinstance(self.screen, TorrentSaveScreen):
            return action == "quit"
        return True

    def on_input_submitted(self):
        self.start_search()

    def on_button_pressed(self, event):
        if event.button.id == "search":
            self.start_search()

    def action_settings(self):
        self.push_screen(DirectorySettingsScreen(self.service.settings.torrent_directory, self.service.settings.theme), self.configure_directory)

    def configure_directory(self, value):
        if not value:
            return
        value, chosen_theme = value
        from pathlib import Path
        settings = self.service.settings
        old = settings.torrent_directory
        old_theme = settings.theme
        try:
            target = Path(value).expanduser().resolve()
            target.mkdir(parents=True, exist_ok=True)
            settings.torrent_directory = str(target)
            settings.theme = chosen_theme
            save_settings(self.service.directory.parent, settings)
            self.theme = chosen_theme
            self.notify("设置已保存")
        except (OSError, ValueError) as error:
            settings.torrent_directory = old
            settings.theme = old_theme
            record_error("保存目录设置失败", error)
            self.notify(f"设置失败：{error}", severity="error")

    COLUMN_FIELDS = [("名称", "name"), ("集数", "episode"), ("分辨率", "resolution"),
                     ("字幕组", "fansub"), ("大小", "size"),
                     ("发布时间", "time")]

    def update_columns(self):
        table = self.query_one(DataTable)
        table.clear(columns=True)
        for label, field in self.COLUMN_FIELDS:
            widths = {"name": 72, "episode": 8, "resolution": 9, "fansub": 28, "size": 13, "time": 18}
            table.add_column(label, key=field, width=widths[field])

    def on_data_table_header_selected(self, event):
        field = event.column_key.value
        self.sort = field + ("_desc" if self.sort == field + "_asc" else "_asc")
        self.apply_view()

    def action_save_torrent(self):
        resource = self.selected_resource()
        if resource is None:
            self.notify("请先选择搜索结果")
            return
        if not resource.torrent_url:
            self.notify("此资源没有 torrent 文件链接；可以复制 Magnet", severity="warning")
            return
        from pathlib import Path
        import hashlib
        filename = (resource.info_hash or hashlib.sha256(resource.torrent_url.encode()).hexdigest()[:20]) + ".torrent"
        self.push_screen(TorrentSaveScreen(str(Path(self.service.settings.torrent_directory or str(Path.home() / "Downloads")) / filename)),
                         lambda path: self.save_resource_torrent(resource, path) if path else None)

    @work(exclusive=True, group="save-torrent")
    async def save_resource_torrent(self, resource, path):
        try:
            import asyncio
            target = await asyncio.wait_for(save_torrent(resource, path, self.service.client),
                                            self.service.settings.timeout)
            self.notify(f"种子已保存：{target}", timeout=10)
        except Exception as error:
            record_error("种子保存失败", error)
            self.notify(f"种子保存失败：{error}", severity="error", timeout=8)

    def action_focus_search(self):
        self.query_one(Input).focus()

    def action_focus_results(self):
        self.query_one(DataTable).focus()

    def action_refresh(self):
        self.start_search(refresh=True)

    def start_search(self, refresh=False):
        keyword = self.query_one(Input).value.strip()
        selected = [source.name for source in self.service.sources]
        if not keyword or not selected:
            self.query_one("#status", Static).update("请输入关键词并配置至少一个来源。")
            self.notify("请输入关键词并配置至少一个来源。", severity="warning")
            return
        self.generation += 1
        self.detail_generation += 1
        self.query_one("#status", Static).update("搜索中…")
        self.resources = []
        self.all_resources = []
        self.search_status = "搜索中…"
        self.query_one(DataTable).clear()
        self.query_one(TextArea).load_text("搜索中…")
        self.perform_search(keyword, selected, refresh, self.generation)

    @work(exclusive=True, group="search")
    async def perform_search(self, keyword, selected, refresh, generation):
        result = await self.service.search(keyword, selected, refresh)
        if generation != self.generation:
            return
        self.all_resources = result.resources
        status = " · ".join(f"{s}: {state}" + (f" ({result.counts[s]})" if s in result.counts else "")
                            for s, state in result.statuses.items())
        if result.cached:
            status += " · 缓存: " + ", ".join(result.cached)
        if result.errors:
            status += "\n" + "\n".join(f"{s}: {error}" for s, error in result.errors.items())
            self.notify("；".join(f"{s}: {error}" for s, error in result.errors.items()), severity="warning", timeout=12)
        self.search_status = status
        self.apply_view()

    def apply_view(self):
        if not self.is_mounted:
            return
        previous = self.selected_resource()
        self.resources = filter_sort(self.all_resources, sort=self.sort)
        self.detail_generation += 1
        table = self.query_one(DataTable)
        with self.batch_update():
            table.clear()
            for index, item in enumerate(self.resources):
                metadata = item.metadata
                table.add_row(metadata.anime_name, metadata.episode or "未知", metadata.resolution or "未知",
                              metadata.fansub or "未知", item.display_size,
                              display_date(item.publish_time), key=str(index))
            if previous in self.resources:
                table.move_cursor(row=self.resources.index(previous))
        self.query_one("#status", Static).update(f"显示 {len(self.resources)} / {len(self.all_resources)} 条去重结果 · {self.search_status}")
        resource = self.selected_resource()
        if resource:
            self.show_resource(resource)
        else:
            self.query_one(TextArea).load_text("没有搜索结果，请更换关键词。")

    def selected_resource(self):
        if isinstance(self.screen, TorrentSaveScreen):
            return None
        table = self.query_one(DataTable)
        return self.resources[table.cursor_row] if self.resources and table.cursor_row < len(self.resources) else None

    def show_resource(self, resource):
        metadata = resource.metadata
        self.query_one(TextArea).load_text(f"{resource.title}\n动画: {metadata.anime_name} · 集数: {metadata.episode or '未知'} · "
                                         f"{metadata.resolution or '未知分辨率'} / {metadata.codec or '未知编码'} · 字幕组: {metadata.fansub or '未知'}\n"
                                         f"大小: {resource.display_size}\n发布时间: {resource.publish_time or '未知'}\n"
                                         f"来源: {', '.join(resource.sources)}\nHash: {resource.info_hash or '待解析'}\n"
                                         f"Magnet: {resource.magnet or '待解析'}\n种子: {resource.torrent_url or '无'}")

    def on_data_table_row_selected(self):
        resource = self.selected_resource()
        if resource:
            self.detail_generation += 1
            self.show_resource(resource)
            self.resolve_resource(resource, False, self.detail_generation)

    def on_data_table_row_highlighted(self):
        self.detail_generation += 1
        if self._detail_timer:
            self._detail_timer.stop()
        self._detail_timer = self.set_timer(0.08, self.update_selected_detail)

    def update_selected_detail(self):
        self._detail_timer = None
        resource = self.selected_resource()
        if resource:
            self.show_resource(resource)

    def action_copy_magnet(self):
        resource = self.selected_resource()
        if resource:
            self.detail_generation += 1
            self.resolve_resource(resource, True, self.detail_generation)
        else:
            self.notify("请先选择结果")

    @work(exclusive=True, group="details")
    async def resolve_resource(self, resource, copy, generation):
        try:
            import asyncio
            magnet = await asyncio.wait_for(resolve_magnet(resource, self.service.client), self.service.settings.timeout)
            if generation != self.detail_generation:
                return
            self.show_resource(resource)
            if copy:
                # Windows clipboard works even when the terminal does not support OSC52.
                import sys
                if sys.platform == "win32":
                    import subprocess
                    process = await asyncio.create_subprocess_exec("powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                        "Set-Clipboard -Value ([Console]::In.ReadToEnd())", stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    _, stderr = await asyncio.wait_for(process.communicate(magnet.encode("utf-8")), 5)
                    if process.returncode:
                        raise RuntimeError(stderr.decode(errors="replace"))
                else:
                    self.copy_to_clipboard(magnet)
                self.notify("Magnet 已复制")
        except Exception as error:
            record_error("种子解析或剪贴板操作失败", error)
            if generation == self.detail_generation:
                self.notify(f"解析或复制失败: {error}", severity="error", timeout=8)
