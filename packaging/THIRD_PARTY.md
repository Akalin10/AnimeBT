# 第三方组件声明

Windows 包内的 `licenses/` 收录构建环境提供的第三方许可文本，以及 Qt 使用的 GPLv3 和 LGPLv3 文本。项目自身尚未指定开源许可证。

- 本版本使用 Qt 6.12.0、PySide6 Essentials 6.12.0 和 Shiboken6 6.12.0 的公开发行版，按 LGPLv3 动态链接。Qt 和 Python 绑定的 DLL 与插件位于 `_internal/`，可替换为兼容版本。适用许可证允许为调试对 LGPL 库所作的修改而进行逆向工程。[Qt 许可说明](https://doc.qt.io/qt-6/licensing.html) · [Qt 对应版本源码](https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/) · [PySide6 和 Shiboken6 对应版本源码](https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.12.0)
- 使用 PyInstaller 6.22.3 构建。启动器的分发例外见其自带许可和 [PyInstaller 许可说明](https://pyinstaller.org/en/stable/license.html)。
- GUI 使用当前系统的字体。安装包不附带 Anthropic、苹方或其他系统字体。Bangumi 封面在运行时请求，未收录于 Windows 包。
