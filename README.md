# Whisper 字幕工具集

一套基于 OpenAI Whisper 的视频字幕处理工具，支持语音识别、字幕翻译、AI 分镜生成等功能。

## 🎯 快速选择：我该用哪个工具？

| 你的需求 | 推荐工具 | 原因 |
|---------|---------|------|
| 单个视频生成字幕 + 翻译 | `whisper_tool_optimized_ai.py` | 功能全面，支持翻译和分镜 |
| 大批量视频生成字幕（不需要翻译） | `zimu_shengcheng_toolbat-ok.py` | 批量处理效率高 |
| 需要 AI 分镜脚本 | `whisper_tool_optimized_ai.py` | 独有的分镜生成功能 |
| 需要自定义翻译语言（如翻译成日语） | `whisper_tool_optimized_ai.py` | 支持自定义目标语言 |
| 需要生成静音视频 | `zimu_shengcheng_toolbat-ok.py` | 支持去除音轨 |
| 只是想试试看 | `whisper_tool_optimized_ai.py` | 界面友好，功能最全 |

**简单来说**:
- 🎬 **精细处理、需要翻译** → 用 `whisper_tool_optimized_ai.py`
- 📦 **批量处理、只要字幕** → 用 `zimu_shengcheng_toolbat-ok.py`

---

## 📦 包含工具

### 1. Whisper 智能字幕工具 (AI 增强版) ⭐ 推荐
**文件**: `whisper_tool_optimized_ai.py`  
**适用场景**: 单个或少量视频的精细化字幕处理，需要翻译和 AI 分镜功能

**这个软件是做什么的？**
这是一个功能最全面的字幕处理工具，提供图形界面操作。它可以把视频/音频转成字幕文件，然后用 AI 翻译成其他语言，还能自动生成视频分镜脚本。

**具体能做什么？**

#### 📝 功能 1: 语音转字幕
- **输入**: 视频文件（MP4/MOV/AVI 等）或音频文件（MP3/WAV/M4A）
- **输出**: SRT 字幕文件（带时间轴的文本文件）
- **用途**: 把视频里的说话内容自动识别成文字，生成字幕
- **示例**: 上传一个讲座视频 → 自动生成中文字幕文件

#### 🌐 功能 2: 字幕翻译（需要 DeepSeek API Key）
- **输入**: SRT 字幕文件
- **输出**: 双语字幕文件（原文+译文）
- **用途**: 把已有的字幕翻译成其他语言，支持中英互译或自定义语言
- **示例**: 
  - 中文字幕 → 中英双语字幕
  - 英文字幕 → 英中双语字幕
  - 中文字幕 → 中日双语字幕（自定义）

#### 🎬 功能 3: AI 分镜生成（需要 DeepSeek API Key）
- **输入**: SRT 字幕文件
- **输出**: JSON 或 CSV 格式的分镜脚本
- **用途**: 根据字幕内容自动生成视频分镜描述和 AI 绘图提示词
- **示例**: 字幕文件 → 每个场景的总结 + Midjourney/Stable Diffusion 提示词

#### ⚙️ 特色功能
- **转录后自动翻译**: 语音转字幕完成后，自动翻译成指定语言
- **自定义翻译目标**: 不限于中英文，可以翻译成任何语言（日语、韩语、法语等）
- **配置记忆**: 自动保存你的设置（输出路径、API Key、翻译偏好等）
- **图形界面**: 不需要敲命令，点点鼠标就能用

---

### 2. 视频批量处理工具
**文件**: `zimu_shengcheng_toolbat-ok.py`  
**适用场景**: 大批量视频处理，只需要生成字幕，不需要翻译功能

**这个软件是做什么的？**
这是一个专门用于批量处理视频的工具。如果你有一整个文件夹的视频需要生成字幕，用这个工具最合适。它还可以顺便生成静音版视频（去掉音轨）。

**具体能做什么？**

#### 📹 功能 1: 批量生成字幕
- **输入**: 一个文件夹，里面有多个视频文件
- **输出**: 每个视频对应的 SRT 字幕文件
- **用途**: 一次性处理大量视频，自动识别语音生成字幕
- **示例**: 
  - 文件夹里有 50 个课程视频 → 一键生成 50 个字幕文件
  - 支持格式: MP4, MOV, MKV, AVI, FLV, WMV, MPG, MPEG, M4V, WEBM

#### 🔇 功能 2: 生成静音视频（可选）
- **输入**: 视频文件
- **输出**: 去除音轨的静音视频 + SRT 字幕文件
- **用途**: 如果你需要无声版视频（比如配合字幕使用），可以勾选此功能
- **示例**: 原视频.mp4 → 原视频_mute.mp4（无声） + 原视频.srt（字幕）

#### 🛠️ 特色功能
- **自动依赖安装**: 首次运行会自动检测并安装所需的 Python 库
- **支持 Faster-Whisper**: 比标准 Whisper 更快，不需要安装 PyTorch（体积小）
- **虚拟环境管理**: 自动创建独立的 Python 环境，不影响系统
- **进度显示**: 实时显示处理进度和日志

#### ⚠️ 注意
- **不支持翻译**: 这个工具只生成原始语言的字幕，不能翻译
- **不支持分镜**: 没有 AI 分镜生成功能
- **批量优先**: 适合一次处理很多文件，单个文件建议用工具 1

---

### 3. Whisper 字幕工具（基础版）
**文件**: `whisper_tool_optimized_副本.py`  
**状态**: ⚠️ 不推荐使用（功能已被 AI 增强版完全覆盖）

**这个软件是做什么的？**
这是 AI 增强版的早期版本，功能较少。

**与 AI 增强版的区别**:
- ❌ 不支持自定义翻译目标语言（只能中英互译）
- ❌ 转录后自动翻译功能简化
- ❌ 部分页面缺少独立的路径选择器
- ❌ 配置不保存 API Key

**建议**: 直接使用 `whisper_tool_optimized_ai.py`，功能更全面

---

## 🚀 快速开始

### 环境要求
- Python 3.8+
- FFmpeg（系统级安装）

### 安装依赖

#### 方式 1: 使用 AI 增强版工具
```bash
# 运行工具后点击"修复环境"按钮自动安装
python3 whisper_tool_optimized_ai.py
```

#### 方式 2: 手动安装
```bash
# 创建虚拟环境
python3 -m venv whisper_env
source whisper_env/bin/activate  # macOS/Linux
# whisper_env\Scripts\activate  # Windows

# 安装依赖
pip install openai-whisper torch pysrt requests ffmpeg-python

# 或使用清华镜像加速
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple openai-whisper torch pysrt requests ffmpeg-python
```

### FFmpeg 安装

**macOS**:
```bash
brew install ffmpeg
```

**Windows**:
1. 下载: https://www.gyan.dev/ffmpeg/builds/
2. 解压并将 `bin` 目录添加到系统 PATH

**Linux**:
```bash
sudo apt-get install ffmpeg  # Ubuntu/Debian
sudo yum install ffmpeg      # CentOS/RHEL
```

---

## 📖 使用说明

### Whisper 智能字幕工具

1. **启动工具**:
   ```bash
   python3 whisper_tool_optimized_ai.py
   ```

2. **加载模型**:
   - 选择模型大小（推荐 `small` 或 `medium`）
   - 点击"加载模型"按钮

3. **语音转字幕**:
   - 切换到"语音转字幕"标签
   - 添加视频/音频文件
   - 设置输出目录
   - 点击"开始转录"

4. **字幕翻译**:
   - 在顶部输入 DeepSeek API Key
   - 切换到"字幕翻译"标签
   - 添加 SRT 字幕文件
   - 选择翻译目标语言
   - 点击"开始翻译"

5. **分镜生成**:
   - 切换到"分镜生成"标签
   - 添加 SRT 字幕文件
   - 选择导出格式（JSON/CSV）
   - 点击"生成并导出分镜"

### 视频批量处理工具

1. **启动工具**:
   ```bash
   python3 zimu_shengcheng_toolbat-ok.py
   ```

2. **配置**:
   - 选择 Whisper 模型
   - 点击"加载模型"
   - 选择输入视频文件夹
   - 选择输出文件夹
   - 勾选"仅生成字幕"（如不需要静音视频）

3. **开始处理**:
   - 点击"开始处理"
   - 等待批量处理完成

---

## 🔑 DeepSeek API Key 获取

1. 访问 [DeepSeek 官网](https://platform.deepseek.com/)
2. 注册账号并登录
3. 进入 API Keys 页面
4. 创建新的 API Key
5. 复制 Key 并粘贴到工具中

---

## 📁 项目结构

```
.
├── whisper_tool_optimized_ai.py      # ⭐ AI 增强版字幕工具（推荐使用）
├── whisper_tool_optimized_副本.py     # 基础版（不推荐，功能已被 AI 版覆盖）
├── zimu_shengcheng_toolbat-ok.py     # 批量视频处理工具
├── AI版video_audio_cutter_1023.py    # 视频音频剪辑工具（另一个独立工具）
├── whisper_tool_config.json          # 配置文件（自动生成）
├── README_KEY.md                      # API Key 说明
├── .env.example                       # 环境变量示例
└── README.md                          # 本文件
```

**文件说明**:
- **推荐使用**: `whisper_tool_optimized_ai.py` + `zimu_shengcheng_toolbat-ok.py`
- **可以删除**: `whisper_tool_optimized_副本.py`（已过时）

---

## ⚙️ 配置文件

工具会自动在同目录下生成 `whisper_tool_config.json` 保存配置:
- 输出目录路径
- API Key（可选）
- 翻译设置
- API 优先模式

---

## 🎯 支持的格式

### 输入格式
- **视频**: MP4, MOV, MKV, AVI, FLV, WMV, MPG, MPEG, M4V, WEBM
- **音频**: MP3, WAV, M4A
- **字幕**: SRT

### 输出格式
- **字幕**: SRT (UTF-8 编码)
- **分镜**: JSON, CSV

---

## 💡 使用建议

1. **模型选择**:
   - `tiny/base`: 速度快，精度较低，适合快速测试
   - `small`: **推荐**，平衡速度和精度
   - `medium`: 精度高，速度较慢
   - `large`: 最高精度，需要较多内存和时间

2. **翻译质量**:
   - DeepSeek API 翻译质量优于 Whisper 内置翻译
   - 建议开启"API 优先"模式

3. **批量处理**:
   - 大批量视频建议使用 `zimu_shengcheng_toolbat-ok.py`
   - 单个文件精细处理使用 `whisper_tool_optimized_ai.py`

---

## 🐛 常见问题

### 1. 模型加载失败
- 检查网络连接（首次使用需下载模型）
- 尝试使用"修复环境"功能
- 手动安装依赖: `pip install openai-whisper torch`

### 2. FFmpeg 错误
- 确认 FFmpeg 已正确安装: `ffmpeg -version`
- macOS 用户检查 Homebrew 安装
- Windows 用户检查 PATH 环境变量

### 3. API 调用失败
- 检查 API Key 是否正确
- 确认网络可访问 DeepSeek API
- 查看日志获取详细错误信息

### 4. 中文路径问题
- 工具已支持中文路径和文件名
- 如遇问题，尝试使用英文路径

---

## 📝 开发说明

### 代码重复分析
详见 `code_analysis.md`，主要发现:
- `whisper_tool_optimized_ai.py` 和 `whisper_tool_optimized_副本.py` 重复度 90%+
- 建议删除副本，保留 AI 版

### 建议整合方案
1. **保留**: `whisper_tool_optimized_ai.py` (功能最全)
2. **保留**: `zimu_shengcheng_toolbat-ok.py` (批量处理专用)
3. **删除**: `whisper_tool_optimized_副本.py` (已被 AI 版替代)

---

## 📄 许可证

本项目仅供个人学习和使用。

---

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) - 语音识别模型
- [DeepSeek](https://www.deepseek.com/) - AI 翻译和分镜生成
- [FFmpeg](https://ffmpeg.org/) - 视频处理

---

## 📮 联系方式

如有问题或建议，欢迎提交 Issue。
