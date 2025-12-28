# Whisper 字幕工具集

一套基于 OpenAI Whisper 的视频字幕处理工具，支持语音识别、字幕翻译、AI 分镜生成等功能。

## 📦 包含工具

### 1. Whisper 智能字幕工具 (AI 增强版)
**文件**: `whisper_tool_optimized_ai.py`

功能最全面的字幕处理工具，集成 DeepSeek AI 能力。

**核心功能**:
- 🎤 **语音转字幕**: 使用 Whisper 模型进行高精度语音识别
- 🌐 **智能翻译**: 支持 DeepSeek API 翻译，可自定义目标语言
- 🎬 **AI 分镜生成**: 自动生成视频分镜脚本和 AI 提示词
- ⚙️ **转录后自动翻译**: 支持多种翻译模式（中文/英文/自定义）
- 💾 **配置持久化**: 自动保存设置和 API Key

**特色**:
- 支持自定义翻译目标语言
- 每个功能页面独立的输出路径设置
- 完整的 UI 界面，操作简单直观

---

### 2. 视频批量处理工具
**文件**: `zimu_shengcheng_toolbat-ok.py`

专注于批量视频处理和字幕生成。

**核心功能**:
- 📹 **批量视频处理**: 一次处理整个文件夹的视频
- 🔇 **静音视频生成**: 可选生成去除音轨的视频
- 📝 **自动字幕生成**: 使用 Whisper/Faster-Whisper 生成 SRT 字幕
- 🛠️ **自动依赖管理**: 自动检测和安装所需依赖

**特色**:
- 支持 Faster-Whisper（无需 PyTorch，更快更轻量）
- 自动虚拟环境管理
- 适合大批量视频处理

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
├── whisper_tool_optimized_ai.py      # AI 增强版字幕工具（主力）
├── whisper_tool_optimized_副本.py     # 基础版（功能较少，可删除）
├── zimu_shengcheng_toolbat-ok.py     # 批量视频处理工具
├── whisper_tool_config.json          # 配置文件（自动生成）
├── README_KEY.md                      # API Key 说明
├── .env.example                       # 环境变量示例
└── README.md                          # 本文件
```

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
