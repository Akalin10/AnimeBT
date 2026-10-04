from animebt.core.runtime import record_error


class RecoveryMixin:
    """Catch custom UI dispatch failures before Textual closes its message queue."""
    async def _dispatch_message(self, message):
        try:
            await super()._dispatch_message(message)
        except Exception as error:
            self.app._handle_exception(error)


class RecoveryAppMixin(RecoveryMixin):
    def _handle_exception(self, error):
        original = getattr(error, "error", error)
        record_error("TUI 未捕获异常", original)
        if getattr(self, "_reporting_error", False):
            return
        self._reporting_error = True
        try:
            self.notify("操作失败，详情已写入日志；可以重试或继续使用。", severity="error", timeout=10)
        finally:
            self._reporting_error = False
