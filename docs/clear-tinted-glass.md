# Clear ↔ Tinted 全局背景磨砂

## 实现

设置内删除旧“玻璃柔化”滑块，替换为 0–100、步长 0.1 的 Clear ↔ Tinted 滑块。默认 0（Clear），保持无染色的 100% 背景透射。深浅色分别自动保存为 glassFrostLight/glassFrostDark，关闭时禁用；旧透明度键保留在用户配置中但不再读取，不强行删除用户文件。

全局 GlassThemeManager 将数值映射为连续的 0–18 DIP 采样半径，所有玻璃表面使用同一参数。glass.frag 使用共享 ShaderEffectSource 的 mip 层级、连续纹理 LOD 与归一化 3×3 Gaussian 核过滤实际背景纹理。采样权重总和为 1，不混入底色、不绘制不透明遮罩、不降低文字或窗口整体透明度。Clear 保留细节和轻微透镜位移，Tinted 降低背景空间高频，保留背景颜色及光影。

## 菜单重影根因

此前菜单捕获完整 sceneContent，其中包含资源标题。玻璃对这些标题低通和折射后重新绘制，导致截图中的模糊重复字形。

菜单、设置、工具提示和右键菜单现在采样独立 ambient 背景平面，不采样页面文字/图标/资源控件。AI 弹窗内控件只采样其下层材质背景，不包含弹窗文字。Dialog 消费者不再触发完整页面采样。菜单和前景文字由原有 QML 文本独立渲染，无整层模糊、无递归采样。

这是一项明确的分层选择：Clear 显示清晰应用背景，但不会把菜单后方的资源标题透射进菜单。未加入 Windows 桌面捕获，背景不是其他窗口或桌面壁纸。

## 实际 GUI 五档验证

通过 Windows/D3D11 实际 Main.qml，在真实 ambient 层放置动态 QML 粉蓝条纹，实际鼠标点击滑块五档并连续拖动；深浅色均通过。

| 数值 | 背景模糊半径 DIP | 背景采样段红通道标准差 |
| --- | ---: | ---: |
| 0 | 0 | 91.66 |
| 25 | 3.18 | 80.30 |
| 50 | 7.57 | 48.91 |
| 75 | 12.56 | 19.02 |
| 100 | 18 | 1.81 |

标准差逐档下降，说明实际高频纹理被滤除。Tinted 采样均值约 143，与粉蓝源色平均值相符，未被黑白底色替代。连续拖动得到 36.1、37.3、38.9、41.0 等不同值。

同一前景资源标题在五档中单独 grabToImage，像素 SHA-256 完全一致（每个主题分别比较），opacity 始终 1。前景文字未随磨砂处理改变。

- [Clear 实际截图](../artifacts/clear-tinted/frost-000.png)
- [Tinted 实际截图](../artifacts/clear-tinted/frost-100.png)
- [修复后菜单](../artifacts/clear-tinted/dark-dropdown.png)
- [深色五档原始数据](../artifacts/clear-tinted/report.json)
- [浅色五档原始数据](../artifacts/clear-tinted-light/report.json)

实际窗口同时检查海报、列表、详情、菜单、设置和 AI 弹窗；封面来自真实本地缓存，资源行明确标记为离线验收样本，未冒充在线搜索。

## 回归与性能

102 项完整 unittest 通过；设置测试覆盖范围钳制、键盘/拖动、深浅色独立保存、关闭时刷新保存和重启恢复。视觉模式测试覆盖 Liquid Glass 关闭后滑块不可用、玻璃 Shader 释放及页面采样为空。旧滑块对象已不存在。

千条离线资源，在滚动同时连续改变磨砂值、保持设置打开：FrameAnimation 帧间隔中位数 11.61–12.10 ms，P95 15.90–16.50 ms，QML 警告 0。这是 UI 墙钟间隔，不是硬件显示帧率或 GPU 时间戳，不宣称任何设备均锁定 60FPS。

## 修改范围与限制

修改 Main.qml、GlassThemeManager.qml、GlassSurface.qml、GlassPopupFrame.qml、GlassMenu.qml、GlassMenuItem.qml、GlassTextField.qml、glass.frag 及编译后的 QSB；更新相关测试与验证/性能工具。未修改搜索、AI 解析、筛选、归属或磁链业务逻辑。

软件渲染仍不支持 Shader 折射/磨砂，保留原有降级，不将其称为真实背景模糊。完全透射在任意复杂背景上不能保证所有文字达到同一对比度；未添加阅读底板来伪造清晰度。

仅修改本地源码，未提交、推送或发布，未重新打包旧 EXE。从源码重启查看：.venv/Scripts/python.exe -m animebt.gui。
