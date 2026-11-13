
<div align="center">
  <img src="animebt/gui/assets/icon.png" width="90" alt="AnimeBT Logo">

  <h1>AnimeBT</h1>

  <p>
    <a href="https://github.com/Akalin10/AnimeBT/releases/download/v1.1.1/AnimeBT-1.1.1-Windows-x64.zip">下载 Windows x64 版</a>
    ·
    <a href="https://github.com/Akalin10/AnimeBT/releases">Releases</a>
    ·
    <a href="docs/guide.md">使用指南</a>
  </p>
</div>


## 功能

- **GUI**：支持海报模式和列表模式。海报模式通过 Bangumi 查找作品，展示已确认有资源的条目；列表模式直接按关键词检索 BT 来源。资源页保留原始标题，支持筛选、复制磁链和保存 Torrent。
- ~~**TUI**：在终端按关键词检索多个 BT 来源，在同一张表中浏览和排序结果。~~
- 两种界面均支持复制磁链和保存 Torrent 文件。GUI 还提供浅色与深色主题、四档海报尺寸，以及可关闭的启动动画。
- GUI 可选用 OpenAI 兼容 API 辅助解析资源标题。解析结果经过本地校验，用于标题展示。

## 检索流程

### 🎴 海报模式

🔎 **搜索动画** → 🎞️ **选择海报** → 📦 **查看资源**

- 🌸 **作品搜索**：通过 Bangumi 查找动画，展示对应海报。
- 🌐 **多源检索**：使用作品名称及别名搜索多个 BT 来源。
- 🎯 **精准匹配**：识别季度、剧场版、OVA 等，过滤不相关资源。
- 📚 **合集识别**：仅展示确认包含目标作品的合集。
- 🔗 **智能去重**：合并重复资源，保留全部来源信息。

### 📋 列表模式

⌨️ **输入关键词** → 🌐 **多源搜索** → 📃 **浏览资源**

- 🚀 **直接搜索**：无需 Bangumi，直接检索 BT 来源。
- ⚡ **实时加载**：边搜索边显示结果，无需等待全部完成。
- 🔍 **深入搜索**：补查更多历史资源。
- 🗂️ **筛选排序**：按集数、分辨率、字幕组、时间等条件查找资源。
- 🧲 **快速获取**：复制磁力链接或保存 Torrent 文件。

⚙️ **模式切换**：在设置中选择「海报模式」或「列表模式」，默认使用海报模式。

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

~~### 终端界面~~

~~在源码目录中使用 Python 3.11 或更新版本运行：~~

~~```powershell~~
~~python -m pip install .~~
~~python -m animebt~~
~~```~~

~~在搜索框输入关键词。选中资源后，按 Ctrl+C 复制磁链，按 Ctrl+S 保存 Torrent 文件。完整快捷键见[使用指南](docs/guide.md)。~~

## 源码运行与构建

### 🚀 运行与构建

**💻 运行 GUI 源码**

在 Windows 项目根目录执行：

```powershell
python -m pip install ".[gui]"
python -m animebt.gui
```

**📦 构建 Windows x64 发布包**

使用 64 位 Python 执行：

```powershell
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -Python python
```

## 其他文档

- [使用指南](docs/guide.md)
- [更新记录](CHANGELOG.md)

仅检索和获取有权访问的资源，并遵守适用的版权法律与来源站点规则。
