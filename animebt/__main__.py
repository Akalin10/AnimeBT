import argparse
import asyncio
from dataclasses import asdict
import json
import sys
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from animebt.config import load_settings, Settings, save_settings
from animebt.core.search import SearchService
from animebt.core.runtime import default_data_dir, initialize_runtime, logger, record_error
from animebt.version import __version__


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="AnimeBT 动漫 BT 聚合搜索")
    parser.add_argument("--version", action="version", version=f"AnimeBT {__version__}")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--search", help="无界面搜索，输出 JSON")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    startup_error = None
    try:
        directory = initialize_runtime(args.data_dir or default_data_dir())
    except OSError:
        directory = initialize_runtime(Path(tempfile.mkdtemp(prefix="AnimeBT-")))
        startup_error = f"数据目录不可写，暂时使用 {directory}，请检查目录权限。"
        logger.error(startup_error)
    logger.info("AnimeBT %s 启动；数据目录 %s", __version__, directory)

    try:
        settings = load_settings(directory)
    except Exception as error:
        record_error("配置加载失败，使用默认配置", error)
        settings = Settings()
        startup_error = "配置无效，已保留原文件并使用默认配置；详情见日志。"
        try:
            path = directory / "config.json"
            if path.exists():
                shutil.copy2(path, directory / f"config.invalid-{datetime.now():%Y%m%d-%H%M%S-%f}.json")
            save_settings(directory, settings)
        except OSError as repair_error:
            record_error("配置备份或恢复失败", repair_error)
            startup_error = "配置不可读或不可写，本次使用默认配置；详情见日志。"

    async def run():
        service = SearchService(settings, directory)
        app = None
        def loop_error(loop, context):
            error = context.get("exception") or RuntimeError(context.get("message", "异步任务异常"))
            if app and app.is_running:
                app._handle_exception(error)
            else:
                record_error("异步未捕获异常", error)
        asyncio.get_running_loop().set_exception_handler(loop_error)
        try:
            if args.search:
                result = await service.search(args.search, refresh=args.refresh)
                print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
            else:
                from animebt.ui.app import AnimeBTApp
                app = AnimeBTApp(service, startup_error=startup_error)
                await app.run_async()
            return 0
        finally:
            await service.close()

    try:
        code = asyncio.run(run())
        if code:
            raise SystemExit(code)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        record_error("程序未捕获异常", error)
        print(f"程序遇到错误，详情见 {directory / 'logs' / 'animebt.log'}", file=sys.stderr)
        if getattr(sys, "frozen", False) and not args.search:
            try:
                input("按 Enter 关闭…")
            except (EOFError, KeyboardInterrupt):
                pass
        raise SystemExit(1)
    finally:
        logger.info("AnimeBT 退出")


if __name__ == "__main__":
    main()
