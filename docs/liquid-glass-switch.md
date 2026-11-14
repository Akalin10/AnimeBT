# Liquid Glass 总开关

设置中新增 Liquid Glass 开关，默认开启，自动保存为 appearance.ini 的 liquidGlass。与浅色/深色设置独立；切换不清空关键词、海报或资源结果。

## 两种材质

- 开启：保留当前应用内透射、背景折射、光学模糊、环境光和原玻璃滑块参数。
- 关闭：使用 GitHub 已发布 GlassTheme.qml 中的浅色/深色 RGB 配色作为普通主题参考。共享 GlassSurface 绘制 Alpha=1 的普通背景及边框，关闭玻璃字形描边；不导入旧版业务代码。
- 标题栏、搜索、按钮、筛选、海报背景、资源行、菜单、工具提示、设置及 AI 弹窗使用同一开关。玻璃专用滑块在普通模式隐藏，其值保留，重新开启后恢复。
- 关闭时 GlassSurface Loader 销毁折射 Shader，AmbientBackground Loader 销毁环境光 Shader；窗口阴影效果按需卸载；三路 ShaderEffectSource.sourceItem 均为 null。普通图片的圆角裁切仍保留，它不属于玻璃捕获管线。
- 软件渲染仍按原有策略降级，不宣称具有 Shader 折射。开关控制整个视觉模式，而不是拿硬件是否可用代替用户选择。

## 修改文件

Main.qml、GlassTheme.qml、GlassThemeManager.qml、GlassSurface.qml、AmbientBackground.qml；ResourcePage.qml、TitleSettings.qml、GlassMenuItem.qml 和 GlassToolTip.qml 仅增加字形样式的视觉模式条件。没有修改搜索、AI、资源归属或磁链处理模块。

## 实测

- 完整 unittest：101 项通过，28.186 秒。
- 新增 test_gui_visual_mode.py：实际 Windows/D3D11 主窗口验证四种组合、反复实时切换、采样释放、普通背景 Alpha=1、关键词和资源保留、设置落盘及重启恢复。
- verify_graphite_theme.py 和 --plain：每种视觉模式检查海报、列表、详情、菜单、下拉、设置、AI 弹窗、深浅色及小窗口，共 32 张截图。使用真实缓存封面与明确标注的离线资源样本，不宣称为线上搜索验收。
- 普通模式每次截图检查：玻璃/环境光 Shader 实例 0；三路捕获源均 null；可见普通材质背景 Alpha=1；QML 警告 0。

| 组合 | 截图 |
| --- | --- |
| 普通浅色 | [设置](../artifacts/plain-theme/light-settings.png) |
| 普通深色 | [设置](../artifacts/plain-theme/dark-settings.png) |
| 玻璃浅色 | [设置](../artifacts/graphite-theme/light-settings.png) |
| 玻璃深色 | [设置](../artifacts/graphite-theme/dark-settings.png) |

原始报告：artifacts/plain-theme/report.json、artifacts/graphite-theme/report.json。未测整机 GPU 使用率，不以零玻璃 Shader 宣称整机 GPU 占用为零。

仅本地源码修改。未创建分支、提交、PR 或 Release，未重新打包已有 EXE。从源码重启：.venv/Scripts/python.exe -m animebt.gui。
