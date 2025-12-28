使用说明（API Key 与运行）

1) 不要在源码中硬编码密钥。请使用环境变量：

- macOS/Linux 临时设置：
  export DEEPSEEK_API_KEY="sk-xxxx"

- 或使用 OPENAI_API_KEY 名称：
  export OPENAI_API_KEY="sk-xxxx"

2) 也可复制 .env.example 为 .env 并填入密钥，然后在终端加载：

  set -a
  source .env
  set +a

3) CLI 示例：

  python3 智能切割不成熟只能去掉声音.py --cli --input 输入.mp4 --out 输出目录 --deepseek \
    --min_silence_len 400 --silence_thresh -45 --keep_silence 150 --min_speech_len 700 --merge_gap 250 \
    --keep-audio   # 如需保留原音频

4) 参数建议：

- 中文音频建议先用 VAD 切段，DeepSeek 仅做辅助；可适当提高 keep_silence 以免切口太“硬”。
- 如果仅需“去掉声音”，不启用 DeepSeek，使用 `--keep-audio` 与否控制静音或保留原声。

5) 依赖：确保已安装 ffmpeg、pydub、soundfile、numpy、requests、tkinter。

