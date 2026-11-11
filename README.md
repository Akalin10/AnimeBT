
<div align="center">
  <img src="animebt/gui/assets/icon.png" width="90" alt="AnimeBT Logo">

  <h1>AnimeBT</h1>

  <p>
    <a href="https://github.com/Akalin10/AnimeBT/releases/download/v1.1.0/AnimeBT-1.1.0-Windows-x64.zip">下载 Windows x64 版</a>
    ·
    <a href="https://github.com/Akalin10/AnimeBT/releases">Releases</a>
    ·
    <a href="docs/guide.md">使用指南</a>
  </p>
</div>


## 功能

- **GUI**：通过 Bangumi 查找动画作品，以海报展示已确认有资源的条目。资源页显示原始标题和来源，支持按集数、分辨率、字幕组以及独立资源或合集筛选。
- **TUI**：在终端按关键词检索多个 BT 来源，在同一张表中浏览和排序结果。
- 两种界面均支持复制磁链和保存 Torrent 文件。GUI 还提供浅色与深色主题、四档海报尺寸，以及可关闭的启动动画。
- GUI 可选用 OpenAI 兼容 API 辅助解析资源标题。解析结果经过本地校验，用于标题展示。

## 资源来源

TUI 和 GUI 共用八个来源：Anime Garden、Mikan（蜜柑计划）、ACG.RIP、萌番组、DMHY（动漫花园）、ACGNX、KissSub（爱恋动漫）和 Comicat（漫猫动漫 BT）。

GUI 默认还启用 Nyaa、Tokyo Toshokan 和 MioBT，共 11 个来源。MioBT 适配器从近期订阅条目中筛选资源。各来源的检索范围和限制见[来源覆盖与测试](docs/search-audit.md)。

## 检索流程

GUI 先从 Bangumi 获取作品条目，再用作品名称和登记的别名分别查询 BT 来源。候选资源收集后，根据片名、季度、作品类型和集数等证据核验归属。合集须有证据表明包含目标作品，才能在对应页面显示。通过核验的重复资源会合并，并保留来源信息。

TUI 直接使用输入的关键词检索 BT 来源，汇总结果。

## 界面预览

### 海报搜索结果

![AnimeBT 海报搜索结果](docs/showcase/anime-posters.png)

### 资源详情

![AnimeBT 资源详情页，显示筛选项、原始标题和来源](docs/showcase/resources.png)

<details>
<summary>浅色、深色与启动画面</summary>

| 浅色首页 | 深色首页 |
| --- | --- |
| ![浅色首页](docs/showcase/home-light.png) | ![深色首页](docs/showcase/home-dark.png) |

![AnimeBT 全窗口启动画面](docs/showcase/startup.png)

</details>

## 安装与使用

### Windows 图形界面

下载并解压 Windows x64 ZIP，运行解压目录中的 `AnimeBT.exe`。发布包可直接运行，无需安装 Python。

输入动画名称后按 Enter 或点击「搜索」。点击海报打开资源详情。左键点击资源缩略图可复制磁链，右键菜单可保存 Torrent 文件。

### 终端界面

在源码目录中使用 Python 3.11 或更新版本运行：

```powershell
python -m pip install .
python -m animebt
```

在搜索框输入关键词。选中资源后，按 Ctrl+C 复制磁链，按 Ctrl+S 保存 Torrent 文件。完整快捷键见[使用指南](docs/guide.md)。

## 源码运行与构建

在 Windows 上运行 GUI 源码：

```powershell
python -m pip install ".[gui]"
python -m animebt.gui
```

在 Windows x64 上使用 64 位 Python 构建发布包：

```powershell
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -Python python
```

构建产物位于 `dist/`，包括程序目录、ZIP 和 SHA-256 校验文件。

## 其他文档

- [使用与构建指南](docs/guide.md)
- [更新记录](CHANGELOG.md)

仅检索和获取有权访问的资源，并遵守适用的版权法律与来源站点规则。
