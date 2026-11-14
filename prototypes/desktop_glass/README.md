# Windows 桌面 Liquid Glass 独立原型

本目录是独立原型，不由 AnimeBT 正式 GUI 导入。正式 GUI 已回滚到应用内玻璃版本；本目录不会在应用启动时运行。

## 运行

在项目根目录执行（Windows x64、当前 Qt 6.12.0）：

```powershell
.venv/Scripts/python.exe prototypes/desktop_glass/build.py
.venv/Scripts/python.exe prototypes/desktop_glass/run.py
```

构建使用已经安装的 MinGW-w64 g++ 和 WinRT 头文件；可通过 `ANIMEBT_PROTO_CXX` 指定编译器。不下载 SDK、不安装系统组件。GUI 默认关闭捕获，点击 **Enable desktop capture** 才开始；关闭窗口或点击 **Stop capture** 会关闭 WGC，并恢复窗口的捕获可见性。无需编译即可运行本机已生成的 DLL，但它是本地构建产物，不作为正式发行包。

以下命令明确授权在独立全屏测试窗口后方捕获受控图案，并保存合成图案的渲染证明图：

```powershell
.venv/Scripts/python.exe prototypes/desktop_glass/run.py --test-pattern --exercise --seconds 16 --proof
.venv/Scripts/python.exe prototypes/desktop_glass/verify.py
```

`--proof` 必须与 `--test-pattern` 配合；普通启动不保存桌面帧。不要将证明模式改成私人桌面录制工具。运行验收会短暂显示全屏测试图案并移动独立原型窗口。

## 实际数据路径

```text
真实显示器 / DWM 后方窗口
  → Windows.Graphics.Capture / CreateForMonitor
  → CreateFreeThreaded 双缓冲帧池（系统捕获线程）
  → Qt 渲染线程 TryGetNextFrame
  → 同一个 Qt D3D11 设备上的 CopyResource
  → GPU BGRA → RGBA 转换
  → QSGD3D11Texture::fromNative
  → QSGSimpleTextureNode / ShaderEffectSource
  → AnimeBT 现有 GlassSurface / GLSL-QSB
```

WGC 的桌面帧通常为 BGRA8，而 Qt 的公开原生导入接口只支持 RGBA。本原型首轮虽收到帧但输出无图案；通过单次合成像素诊断定位后，增加 GPU 格式转换，才获得正确的真实桌面折射。没有使用 CPU QImage 每帧上传或 GDI 截图。

WGC 帧在复制后立即关闭；显示纹理由本模块持有。D3D11.1 `SwapDeviceContextState` 隔离原生转换与 Qt 的图形状态，时间戳采用异步环形查询，不阻塞等待 GPU。窗口物理客户区坐标来自 `ClientToScreen`，不把逻辑 DIP 当作捕获纹理像素。

最终 Shader 复用现有曲面位移、模糊、Fresnel 与厚度阴影。整个表面采样真实桌面；阅读区域另外使用现有亮度保护。原型不是生产界面布局：透明光学测试区故意保留复杂背景，不代表已经验证任意桌面文字的阅读体验。

## 自身排除、权限和回退

- 捕获前设置并检查 `WDA_EXCLUDEFROMCAPTURE`。失败就不启动捕获。要求 Windows 10 2004 或更新系统，不接受旧系统的黑色遮罩行为。
- 不请求取消系统捕获边框，也不修改系统权限策略。Win32 `CreateForMonitor` 在显式操作后选择当前监视器；当前原型未添加系统选择器。系统不支持或拒绝访问时显示应用内材质。
- 此排除属性不是只针对本应用的过滤器：其他兼容的截图、录屏和屏幕共享也可能看不到本窗口。因此没有将该方案默认集成进正式 GUI；不能宣称第三方捕获工具行为完全一致。
- 普通截图可能无法截到原型。证明图使用 Qt 自身渲染目标读回，且仅在受控测试模式显式启用。测试单次读取一个 BGRA 像素用于诊断；截图也涉及有限次 GPU 读回。**常态逐帧路径没有 GPU→CPU→GPU 图像往返**，并不宣称整个测试完全没有读回。
- 关闭捕获立即关闭 WGC，并恢复显示亲和性。初始四秒没有帧、捕获 API 错误、设备移除或持续超出运行预算会回退。静态桌面没有新帧不被误判为失败。
- 原型一次处理一个显示器。移入另一显示器会重建捕获；跨越显示器边界时使用应用内回退，不错误拉伸上一显示器纹理。当前没有多显示器拼接。

## 验证与当前限制

实际数据与截图见 [技术验收报告](REPORT.md)。Qt 原生纹理 API 没有 PySide 绑定；为避免安装完整 SDK，本原型通过 ctypes 调用已验证的 Qt 6.12.0 Windows x64 导出符号，并通过 shiboken 包装纹理。启动严格检查 Qt 版本及符号，失败则回退。

该 ABI 桥接和 Python Scene Graph 回调是原型限制，不是正式插件接口。渲染采用 basic loop，避免 Python GIL 与线程化 Scene Graph 回调死锁。正式集成前应改成匹配同一 Qt SDK 构建的 C++ QML 插件，再验证 threaded loop、渲染资源销毁和长期稳定性。不要删除版本检查来适配其他 Qt 版本。

HDR、不同 GPU 之间的显示器切换、真实设备丢失、热插拔、锁屏和第三方会议软件录屏尚未完成实机验收。系统可能在 WGC 内部执行额外跨适配器复制；这里只保证本模块不持续做 CPU 图像上传，不保证系统驱动零复制。

## 官方接口资料

- [Microsoft：Windows.Graphics.Capture](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture)
- [Microsoft：CreateFreeThreaded](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture.direct3d11captureframepool.createfreethreaded)
- [Microsoft：SetWindowDisplayAffinity](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity)
- [Microsoft：捕获边框与权限](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture.graphicscapturesession.isborderrequired)
- [Qt：QSGD3D11Texture::fromNative](https://doc.qt.io/qt-6.12/qnativeinterface-qsgd3d11texture.html)
- [Qt：QQuickWindow 原生图形集成](https://doc.qt.io/qt-6.12/qquickwindow.html)
