# AnimeBT 使用与构建指南

[返回项目首页](../README.md)

~~## TUI~~

~~![AnimeBT TUI](screenshot.png)~~

~~终端版使用原有八个 BT 来源。使用 Python 3.11 或更新版本，在源码目录运行：~~

~~```powershell~~
~~python -m pip install .~~
~~python -m animebt~~
~~```~~

~~- 点击表头排序。~~
~~- Ctrl+C 复制磁链；Ctrl+S 保存种子。~~
~~- Ctrl+O 设置目录和主题；Ctrl+R 刷新；Ctrl+Q 退出。~~
~~- 配置、缓存、日志自动创建于 `%LOCALAPPDATA%/AnimeBT`。~~

## 从源码运行 Windows GUI

## 安装与使用

### 启动 AnimeBT

在项目根目录运行：

```bash
python -m pip install ".[gui]"
python -m animebt.gui
```

安装完成后，也可以通过 `animebt-gui` 启动。

支持 Windows 窗口拖动、尺寸调整及浅色、深色主题切换。

### 搜索模式

AnimeBT 提供两种搜索模式，可在右上角设置中切换，默认使用海报模式。

**海报模式**

通过 Bangumi 搜索动画作品，以海报形式展示已确认存在 BT 资源的条目。

- 根据作品关系、季度和集数核验资源归属。
- 支持合集识别、资源筛选及历史资源补查。
- 点击海报即可查看对应作品的 BT 资源。

**列表模式**

无需经过 Bangumi，直接从 BT 来源检索资源。

- 支持多来源并行搜索与增量加载。
- 支持普通搜索和深入搜索。
- 自动合并重复资源，保留来源信息。
- 单个来源失败不影响其他来源。

两种模式均支持资源筛选、排序、磁链复制和 Torrent 保存。

### 资源操作

在资源列表中：

- **左键点击磁铁图标**：复制磁力链接。
- **右键点击资源**：复制原始标题、复制磁链或保存 Torrent 文件。
- **筛选与排序**：按分类、季度、集数、分辨率、字幕组等条件查找资源。

注意：部分资源需要先获取 Torrent 文件，才能解析出磁力链接。

### AI 智能整理

AnimeBT 支持通过 OpenAI 兼容 API 对资源标题进行智能整理。

开启后，大模型会根据原标题中实际存在的信息，统一整理发布组、作品名称、季度、集数、分辨率、编码和字幕等字段，并应用语义着色。

关闭后，完整显示未经格式化、无语义着色的原始标题。

可在右上角设置中配置 API 地址、模型及 API Key。AI 功能为可选项，不影响基本资源搜索。

### 其他说明

- 海报模式依赖 Bangumi 获取动画信息，由于 Bangumi 被墙，建议使用列表模式。
- 各 BT 来源的检索范围可能不同，部分历史资源不一定能完整获取。
- AnimeBT 只负责资源检索与磁链获取，不提供内置 BT 下载或在线播放功能。
  
## 构建与测试

在 Windows x64 上安装 64 位 Python，在项目目录执行：

```powershell
python -m pip install ".[gui]"
python -m unittest discover -s tests -q
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -Python python
```

仅用于有权获取的资源，请遵守版权法律和来源站点规则。
