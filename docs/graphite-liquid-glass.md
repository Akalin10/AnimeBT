# 无染色底板的应用内 Liquid Glass 验收

本轮按“全透明、不添加遮挡”的要求，移除组件的材质染色与阅读底板。只修改本地 GUI、着色器和相关验证工具；未修改搜索、资源归属、AI 解析、磁链或 Torrent 业务代码，未执行 Git 发布操作。

## 根因与修复

1. `glass.frag` 原先在采样后混入材质底色、灰色前表面反射，并对中央执行亮度范围重映射。这些步骤均已删除。当前直接传递采样 RGB 和 Alpha，只保留可调光学模糊、中心透镜位移及边缘 Fresnel/高光。
2. 输出保留预乘 Alpha，不再无条件生成 Alpha=1 的替代底板；取消菜单强制 mip 采样和最小模糊半径。
3. `GlassSurface` 删除硬件/软件回退阅读矩形；`GlassThemeManager` 禁用材质染色、亮度限制和模态暗幕。软件渲染为透明降级，不宣称具有折射。
4. `GlassPopupFrame` 的 MultiEffect 同时绘制了阴影源实心矩形。已删除整套重复源和效果，而非调低其透明度。
5. 移除封面上的深色遮罩、海报占位底色、首页图标按钮底色以及开关/复选框轨道填色。保留封面本身、文字、图标和状态指示点。
6. 菜单、资源文字等增加仅贴合字形的描边，不添加文字背景。原语义颜色和解析逻辑不变。
7. 透射固定为 100%；原持久化滑块现标为“玻璃柔化”，继续控制模糊与透镜参数，不再偷偷恢复材质染色。原用户配置键保留。

标题栏、搜索框、按钮、海报背景、资源卡片、筛选器、菜单、工具提示、设置和 AI 弹窗均通过共享组件应用上述管线。捕获仍是应用内 ambient → scene → dialog 的分层纹理，消费者不参与自身采样；没有桌面捕获。

## 实际 GUI 证据

运行 `tools/verify_graphite_theme.py` 以及 `--stripes`：实际加载 Main.qml，使用已有真实 Bangumi 封面缓存与明确标注的离线资源样本。并非线上搜索数量验证，未发起 Bangumi/BT 请求。

- 海报、列表、资源详情、来源区、菜单、下拉、设置、AI 弹窗、深浅色和小窗口均已截图；100% 与 150% 缩放均已运行，QML 警告为 0。
- 高对比黑白条纹放在实际 `glassBackdropLayer` 中。实际标题栏、搜索框、筛选器、资源卡片中央均保留 0–255 的黑白范围，证明不存在将两端压成灰色的中央底板。
- 资源卡片中央关闭/开启折射的红通道平均差为 24.57/255；背景移动后为 88.79/255，确认采样实时更新。数值为指定横向采样段，不代表每个像素均位移。
- [条纹折射截图](../artifacts/full-transmission-stripes/stripe-refracted.png)
- [实际像素报告](../artifacts/full-transmission-stripes/report.json)
- [深色列表](../artifacts/graphite-theme/dark-list.png)、[海报](../artifacts/graphite-theme/dark-posters.png)、[详情](../artifacts/graphite-theme/dark-details.png)
- [设置](../artifacts/graphite-theme/dark-settings.png)、[AI 弹窗](../artifacts/graphite-theme/dark-ai.png)、[浅色设置](../artifacts/graphite-theme/light-settings.png)

## 测试与性能

完整 unittest 回归：100 项通过，26.403 秒。旧测试中要求实心阅读底板的断言已改为检查底板不存在；保留真实位移、动态采样、菜单对比度、配置持久化与业务回归检查。

千条离线资源、滚动同时调整光学参数并打开设置，Direct3D 11：

| 场景 | UI 帧间隔中位数 | P95 |
| --- | ---: | ---: |
| 列表浅色 | 13.68 ms | 28.12 ms |
| 列表深色 | 15.14 ms | 25.10 ms |
| 海报详情浅色 | 15.33 ms | 27.82 ms |
| 海报详情深色 | 15.54 ms | 25.69 ms |

来自 FrameAnimation 墙钟间隔，并非 GPU 时间戳或硬件显示帧率；存在长帧，不宣称锁定 60FPS。[原始数据](../artifacts/glass-transparency/application-benchmark.json)。

## 真实限制

- 完全透射允许后方文字和封面参与显示，复杂背景下文字可能互相干扰。字形描边可以改善，但不能保证任意黑白背景上的所有文字均满足 AA；本轮遵守“不加遮挡”，没有重新加入阅读底板来伪造达标。
- 玻璃透射的是应用内画面。主窗口的石墨/浅色环境背景仍存在；不透视其他 Windows 窗口或桌面。
- 软件渲染不支持该 Shader 折射；系统文件选择器仍由 Windows 绘制。
- 本轮未重新打包旧 EXE；从源码重新启动才能看到修改：`.venv/Scripts/python.exe -m animebt.gui`。
