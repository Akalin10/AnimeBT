# 自定义背景与 Liquid Glass

## 使用

Settings 的自定义背景区支持本地 JPG/JPEG、PNG、WebP，提供使用开关、选择图片、恢复默认、缩略图及填充（裁剪）/适应下拉框。默认填充。选择后异步显示并自动保存，无需重启；关闭壁纸或恢复默认保留原路径及显示方式，可以再次开启。

普通主题不绘制壁纸，保留当前普通深浅色配色。Liquid Glass 开关关闭时，壁纸设置区域禁用，壁纸纹理和共享高斯通道不渲染。文件不存在或解码失败时显示默认粉紫色背景及简短错误说明，不产生假成功提示。

## 采样与缓存

WallpaperBackground 位于原有 glassBackdropLayer 内。搜索框、资源行、筛选器和设置等玻璃继续读取这一共享背景，壁纸不是叠在前景上的装饰图片。图像填充/适应及窗口圆角由独立 wallpaper.frag 完成，保持原始比例。透明图片和适应模式的留白使用当前主题背景底色。

大图异步解码，源尺寸使用按屏幕/DPI 量化的 2048–4096 上限；窗口缩放只修改显示变换，不重新请求原图。测试中的 3200×1800 图片实际解码为 2048×1152，未拉伸。已修复 Qt Image aspect 模式隐式放大解码的问题；不可把隐藏纹理源的 Stretch 改成 aspect 模式，显示比例由 wallpaper shader 负责。缩略图只在设置打开时加载，单独使用小解码尺寸。

高频壁纸暴露了原稀疏模糊采样的条带混叠。现在采用共享横向/纵向两遍高斯模糊，各玻璃控件只采样结果，不逐卡片重复处理大图。Clear 绕过这两遍模糊；Tinted 仅处理背景，不处理文字、图标、控件或海报。采样权重归一化，未添加纯色遮罩。

## 实际验证

- 完整回归 103 项通过。新增 test_gui_wallpaper.py 实际加载 Windows/D3D11 Main.qml，导入真实生成的 PNG/JPG/WebP 文件，覆盖 Unicode/空格文件名、实时切换、裁剪/适应、窗口缩放、恢复默认保留路径、开关、设置保存/重启、失效文件和失效路径重启回退。
- 深浅色各验证 Clear/Tinted 五档；前景标题单独抓取的像素哈希在五档内完全一致。
- 测试壁纸采样段的红通道标准差（越低表示高频细节被滤除）：

| 数值 | 深色壁纸背景标准差 |
| --- | ---: |
| 0 | 85.29 |
| 25 | 46.68 |
| 50 | 3.61 |
| 75 | 0.47 |
| 100 | 0.91 |

纹理采样、图片解码和字形比较均来自实际 GUI，不依赖在线搜索，不使用伪造 BT 资源验证业务效果。测试行明确标注为离线界面样本。

- 千条离线资源，实际壁纸开启、滚动并连续调节磨砂时，FrameAnimation 帧间隔中位数约 11.80–12.76 ms，P95 16.16–16.51 ms。不是 GPU 时间戳或显示器帧率，不保证所有设备锁定 60FPS。
- 普通深浅色仍检查到玻璃 Shader=0、背景采样为空；壁纸测试另外检查共享模糊及壁纸 Shader 卸载。

## 证据

- [设置区](../artifacts/wallpaper/settings.png)
- [填充](../artifacts/wallpaper/fill.png) / [适应](../artifacts/wallpaper/fit.png)
- [Clear](../artifacts/wallpaper/dark-frost-000.png) / [Tinted](../artifacts/wallpaper/dark-frost-100.png)
- [恢复默认](../artifacts/wallpaper/restored-default.png)
- [原始验证数据](../artifacts/wallpaper/report.json) / [实际壁纸性能数据](../artifacts/wallpaper/application-benchmark.json)

## 修改文件与限制

Main.qml、AmbientBackground.qml、GlassThemeManager.qml、GlassSurface.qml；新增 WallpaperBackground.qml、BackdropBlur.qml、wallpaper.frag/qsb、backdropblur.frag/qsb；更新构建与验证/性能脚本，新增壁纸回归测试。现有 qml/*.qml 和 qml/shaders/*.qsb 包含规则覆盖新增运行资源。未修改搜索、AI、资源归属、筛选或磁链逻辑。

软件渲染下仍回退默认背景并给出设置提示，不宣称具有壁纸 Shader/玻璃折射；没有桌面捕获。超过解码上限的图像会缩小后上传 GPU；共享玻璃采样继续使用现有 1600×1000 纹理上限，超高 DPI 下的 Clear 不等同原图逐像素显示。原生文件选择对话框由 Qt/Windows 提供；自动化验证通过同一 accepted 回调导入文件，并验证真实解码与渲染，不声称自动化点击了系统文件列表。

仅本地源码修改，无分支、提交、PR、推送或 Release。未重新打包旧 EXE，请从源码重新启动查看。
