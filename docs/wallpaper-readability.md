# 壁纸文字阴影与背景亮度

## 文字

壁纸实际生效时，共享 ShadowText/ShadowLabel 使用低透明度、单像素偏移的 Text.Raised 字形阴影：深色主题使用黑色，浅色主题使用白色轻投影。壁纸上的旧整圈 Outline 改为此样式；没有整段文字的离屏模糊、粗描边或发光效果。普通不透明主题不新增阴影，非壁纸场景保留原样。

覆盖窗口标题、搜索标题/输入/占位文字、正文、资源信息、海报说明、按钮、筛选器、设置、AI 弹窗、菜单和工具提示。输入框使用被裁切的 displayText 影子，沿用密码遮掩；基线与原输入文字仅差一像素，不复制为错位的第二行文字。原字体、原文、语义着色及操作逻辑不变。

## 背景亮度

壁纸设置内新增 0–100 背景亮度滑块，默认 100，实时更新、自动保存至 wallpaperBrightness，关闭时刷新未落盘值，重启恢复。两个主题共用此数值。

等效黑色遮罩不透明度为 `0.6 × (1 - brightness/100)`：

- 100：遮罩 0%，保留原图，不增亮、不泛白。
- 0：遮罩 60%，非黑 RGB 保留原值的 40%，不把普通图片压成纯黑。

为避免额外纹理/遮罩层，在 wallpaper.frag 中进行等效黑色合成。只处理壁纸纹理 RGB，不改变其 alpha、透明孔洞及适应模式留白，不改变前景文字、图标、面板边缘或窗口透明度。玻璃读取调暗后的真实壁纸。Clear/Tinted 仍单独控制共享高斯模糊，亮度遮罩不参与伪造 Tinted。

## 实际验收

完整 unittest：104 项通过（45.860 秒）。新增 test_gui_wallpaper_brightness.py，实际 Windows/D3D11 Main.qml 使用纯白、纯黑和复杂图案的本地图片，分别检查浅色/深色及亮度 0/100：

- 纯白图片：最大值像素 255，最低档约 102，符合 60% 黑色遮罩；未泛白。
- 纯黑图片：两端均为 0，未擅自增亮黑色内容。
- 复杂图片：最低档采样 RGB 为原值约 40%，色彩及细节仍保留。
- 同一前景资源标题在两个亮度端点的独立图像哈希相同，opacity=1。
- 搜索框的阴影基线实测只偏移 1px，防止重影。
- 实际鼠标拖动读取到 25、50、75、100 连续递增；验证范围钳制、关闭保存和重启恢复 37.5。
- 壁纸关闭/普通主题下新阴影关闭；现有壁纸、主题、检索、AI、筛选、资源操作回归通过。

原始数据：[report.json](../artifacts/wallpaper-brightness/report.json)。

## 截图

- [背景亮度设置](../artifacts/wallpaper-brightness/settings.png)
- [复杂壁纸深色原亮度](../artifacts/wallpaper-brightness/complex-dark-100.png)
- [复杂壁纸深色较暗](../artifacts/wallpaper-brightness/complex-dark-0.png)
- [白色壁纸深色原亮度](../artifacts/wallpaper-brightness/white-dark-100.png)
- [白色壁纸深色较暗](../artifacts/wallpaper-brightness/white-dark-0.png)
- [黑色壁纸浅色](../artifacts/wallpaper-brightness/black-light-100.png)

这些是实际 GUI 的本地图片/离线资源样本截图，不冒充线上检索数据。

## 修改与实际限制

修改共享主题、Main.qml、WallpaperBackground.qml、wallpaper.frag/qsb、文字控件及页面的文字声明；新增 ShadowText.qml、ShadowLabel.qml 和回归测试。现有 QML/QSB 包含规则覆盖新增组件。未改搜索、AI 解析、筛选、磁链、Torrent 业务代码，未提交或发布。

轻阴影不能保证任意极端底色都有足够对比：纯白背景配深色主题白字仍建议降低背景亮度；纯黑背景配浅色主题深字仍存在对比限制，可切换深色主题。亮度仅调暗，不会增亮原本为黑色的图像；未增加实心阅读底板或自动改字色来掩盖限制。软件渲染继续使用已有默认背景降级。

旧 EXE 未重新打包，需要从本地源码重启查看。
