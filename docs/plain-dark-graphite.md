# 普通深色：石墨黑主题

仅在 `GlassTheme.plainDark = dark && !liquidGlass` 时生效。普通浅色、玻璃浅色和玻璃深色沿用既有值，未修改 Shader、采样、模糊、折射参数或渲染开关。

## 修改文件

- `animebt/gui/qml/GlassTheme.qml`：普通深色背景 #19191c、卡片/控件 #252529、主文字 #f2f0f3、次文字 #bbb8c0、强调色 #e998bd；以低对比中性边线替换亮蓝边线。普通深色控件/卡片圆角调整为 10/16，其他组合保持原值。
- `GlassSurface.qml`：仅普通深色悬停使用细粉色边线。
- `ResourcePage.qml`：仅普通深色资源行使用共享主题的中性底色及悬停态；其他组合仍调用原 AI 展示背景接口。未修改 AI 解析或着色。
- `GlassSwitch.qml`：仅普通深色开关轨道使用中性灰/柔粉状态色。
- `Main.qml`：仅普通深色搜索主按钮使用柔粉底色与深色文字，保留其他组合的原配色、布局、字体和交互。

## 实际验证

- 完整 unittest：102 项通过，29.188 秒。
- 新增 `tests/test_gui_plain_dark_palette.py` 与 `tests/fixtures/protected_theme_palette.json`，对修改前普通浅色、玻璃浅色、玻璃深色的各 50 项主题参数逐项精确比较，全部相同；普通深色主要底色 Alpha=1，中性色 RGB 差不超过 9，四组正文/强调文字对比度至少 4.5:1。
- 实际 Windows/D3D11 主窗口：列表、海报、资源详情、来源区、下拉、右键菜单、设置、AI 弹窗、深浅色及小窗口均运行截图。普通模式玻璃/环境光 Shader=0，三路背景采样为空，可见普通底板均为 Alpha=1，QML 警告为 0。
- 四种组合均已运行并检查。保留前后截图：`artifacts/plain-dark-redesign/before`。受保护组合 20 张截图中，15 张最大通道差不超过 2/255；其余存在异步封面加载、弹窗背景采样或工具提示时序差异，不能声称全部截图逐像素相同。主题参数精确回归和稳定页面对照均通过。
- 截图使用真实本地封面缓存与明确标注的离线资源，不冒充实时搜索或 API 验证。

## 截图

- [普通深色列表](../artifacts/plain-theme/dark-list.png)
- [普通深色海报/设置](../artifacts/plain-theme/dark-settings.png)
- [普通深色详情](../artifacts/plain-theme/dark-details.png)
- [普通深色下拉](../artifacts/plain-theme/dark-dropdown.png)
- [普通浅色](../artifacts/plain-theme/light-settings.png)
- [玻璃深色](../artifacts/graphite-theme/dark-settings.png)
- [玻璃浅色](../artifacts/graphite-theme/light-settings.png)

没有增加参考图中的主题色选择器等功能；按要求保留现有布局和字体，因此不宣称与参考图逐像素一致。未发现本次主题范围内的阻塞问题。未重新打包旧 EXE，需重新启动源码版查看。仅本地修改，无分支、提交、PR、推送或 Release。
