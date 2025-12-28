# -*- coding: utf-8 -*-
"""
优化版：FFmpeg 批量切割工具（Tkinter + DeepSeek API）
主要改进：
1. 完善 DeepSeek API 实际调用逻辑
2. 增强错误处理和用户提示
3. 优化线程安全的 UI 更新
4. 添加 AI 分析进度反馈
5. 支持多种 AI 输入模式（文本描述、时间点提取）
"""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import os
import re
import threading
import sys
import shlex
import json

# 如果需要实际调用 DeepSeek API，需要安装：pip install requests
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ---------- 时间函数 ----------
def time_to_seconds(time_str):
    """将 HH:MM:SS,mmm 或 H:MM:SS.mmm 等格式时间转为秒(float)"""
    if not time_str:
        return 0.0
    s = time_str.strip().replace('.', ',')
    m = re.match(r'(\d+):(\d{1,2}):(\d{1,2})([.,](\d{1,3}))?$', s)
    if not m:
        raise ValueError(f"时间格式错误: {time_str}")
    H = int(m.group(1))
    M = int(m.group(2))
    S = int(m.group(3))
    ms = int((m.group(5) or '0').ljust(3, '0'))
    return H * 3600 + M * 60 + S + ms / 1000.0

def seconds_to_time_str(seconds):
    if seconds <= 0:
        return "00:00:00,000"
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_seconds = total_ms // 1000
    H = total_seconds // 3600
    M = (total_seconds % 3600) // 60
    S = total_seconds % 60
    return f"{H:02}:{M:02}:{S:02},{ms:03}"

def format_time_for_filename(t_str):
    if not t_str:
        return "00_00_00"
    t = t_str.split(',')[0].split('.')[0]
    return t.replace(':', '_')

# ---------- SRT 解析 ----------
def parse_srt_file(srt_path):
    """解析 SRT，返回 [{'start_str','end_str','start_sec','end_sec','duration','text'}, ...]"""
    with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    pattern = re.compile(r'(\d+)\s*\n\s*([0-9:,.\- >]+)\s*-->\s*([0-9:,.\- >]+)\s*\n(.*?)(?=\n\s*\n|\Z)', re.DOTALL)
    segments = []
    for m in pattern.finditer(content):
        idx = m.group(1)
        start_str = m.group(2).strip()
        end_str = m.group(3).strip()
        text = m.group(4).strip().replace('\n', ' ')
        try:
            start_sec = time_to_seconds(start_str)
            end_sec = time_to_seconds(end_str)
        except Exception:
            continue
        if end_sec <= start_sec:
            continue
        segments.append({
            'start_str': start_str,
            'end_str': end_str,
            'start_sec': start_sec,
            'end_sec': end_sec,
            'duration': end_sec - start_sec,
            'text': text
        })
    return segments

# ---------- DeepSeek API 调用 ----------
def call_deepseek_api(api_key, instruction, media_info, append_log_cb):
    """
    实际调用 DeepSeek API 进行视频分析
    返回: list of {'start_str', 'end_str', 'text'} 或 None（失败时）
    """
    if not HAS_REQUESTS:
        append_log_cb("错误：未安装 requests 库，无法调用 DeepSeek API")
        append_log_cb("请运行：pip install requests")
        return None
    
    if not api_key:
        append_log_cb("错误：API Key 为空")
        return None
    
    try:
        # DeepSeek API endpoint（根据实际文档调整）
        url = "https://api.deepseek.com/v1/chat/completions"
        
        # 构建提示词
        prompt = f"""请分析以下视频信息，根据用户指令提取关键片段的时间点。

用户指令：{instruction}

视频信息：
- 文件名：{media_info.get('filename', 'unknown')}
- 时长：{media_info.get('duration', 'unknown')}

请以 JSON 格式返回片段列表，格式如下：
[
  {{"start": "00:00:10,000", "end": "00:00:20,500", "description": "片段描述"}},
  {{"start": "00:00:35,000", "end": "00:00:45,000", "description": "片段描述"}}
]

注意：
1. 时间格式必须是 HH:MM:SS,mmm
2. 确保 end 时间大于 start 时间
3. 只返回 JSON 数组，不要其他文字"""

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        append_log_cb("正在调用 DeepSeek API...")
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        if response.status_code != 200:
            append_log_cb(f"API 调用失败：HTTP {response.status_code}")
            append_log_cb(f"响应：{response.text[:200]}")
            return None
        
        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        # 解析 JSON 响应
        append_log_cb("API 返回内容：")
        append_log_cb(content[:300] + "..." if len(content) > 300 else content)
        
        # 提取 JSON 数组
        json_match = re.search(r'\[[\s\S]*\]', content)
        if not json_match:
            append_log_cb("警告：无法从 AI 响应中提取 JSON 数据")
            return None
        
        segments_data = json.loads(json_match.group(0))
        
        # 转换为标准格式
        segments = []
        for item in segments_data:
            if 'start' in item and 'end' in item:
                segments.append({
                    'start_str': item['start'],
                    'end_str': item['end'],
                    'text': item.get('description', item.get('text', ''))
                })
        
        append_log_cb(f"成功解析 {len(segments)} 个片段")
        return segments
        
    except requests.RequestException as e:
        append_log_cb(f"网络请求错误：{e}")
        return None
    except json.JSONDecodeError as e:
        append_log_cb(f"JSON 解析错误：{e}")
        return None
    except Exception as e:
        append_log_cb(f"未知错误：{e}")
        return None

# ---------- 获取视频信息 ----------
def get_media_duration(file_path):
    """使用 ffprobe 获取视频时长"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            duration_sec = float(result.stdout.strip())
            return seconds_to_time_str(duration_sec)
    except Exception:
        pass
    return "unknown"

# ---------- 后台切割逻辑 ----------
def run_cutting_logic(input_path, output_dir, segment_entries, append_log_cb, 
                      update_progress_cb, enable_button_cb, set_status_cb, 
                      compress_output, ss_before, name_tmpl):
    """执行实际的视频切割任务"""
    append_log_cb("—— 开始任务 ——")
    if not os.path.exists(input_path):
        append_log_cb("输入文件不存在: " + input_path)
        set_status_cb("错误: 输入文件不存在")
        enable_button_cb(True, "开始执行")
        return

    os.makedirs(output_dir, exist_ok=True)

    # 读取并校验时间段
    valid_entries = []
    for i, e in enumerate(segment_entries):
        s = e['start'].get().strip()
        t = e['end'].get().strip()
        text_preview = e['text'].get().strip() if e.get('text') else ''
        if not s and not t:
            continue
        try:
            start_sec = time_to_seconds(s)
            end_sec = time_to_seconds(t)
        except Exception as ex:
            append_log_cb(f"第 {i+1} 行时间格式错误，跳过: {ex}")
            continue
        if start_sec >= end_sec:
            append_log_cb(f"第 {i+1} 行起始 >= 结束，跳过")
            continue
        valid_entries.append({
            'start_str': s, 'end_str': t, 'start_sec': start_sec,
            'duration': end_sec - start_sec, 'index': i, 'text': text_preview
        })

    total = len(valid_entries)
    if total == 0:
        append_log_cb("没有有效的切割片段，任务结束。")
        set_status_cb("就绪")
        enable_button_cb(True, "开始执行")
        return

    update_progress_cb(0, total)
    success_count = 0

    input_base = os.path.splitext(os.path.basename(input_path))[0]
    input_ext = os.path.splitext(input_path)[1].lower()
    is_audio = input_ext in ['.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg']

    for idx, entry in enumerate(valid_entries, start=1):
        start_name = format_time_for_filename(entry['start_str'])
        end_name = format_time_for_filename(entry['end_str'])
        
        try:
            output_stem = name_tmpl.format(
                base=input_base,
                ext=input_ext.lstrip('.'),
                idx=idx,
                start=start_name,
                end=end_name,
            )
        except Exception:
            output_stem = f"{input_base}_{start_name}-{end_name}"
        
        output_filename = f"{output_stem}{input_ext}"
        output_path = os.path.join(output_dir, output_filename)

        # 避免重名
        base_output = output_path
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.splitext(base_output)[0] + f"_{counter}" + input_ext
            counter += 1

        # 构建 FFmpeg 命令
        if compress_output:
            if is_audio:
                command = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-ss', str(entry['start_sec']),
                    '-t', str(entry['duration']),
                    '-vn', '-acodec', 'aac', '-b:a', '128k',
                    output_path
                ]
            else:
                command = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-ss', str(entry['start_sec']),
                    '-t', str(entry['duration']),
                    '-vcodec', 'libx264', '-crf', '23', '-preset', 'medium',
                    '-acodec', 'aac', '-b:a', '128k',
                    output_path
                ]
        else:
            if ss_before:
                command = [
                    'ffmpeg', '-y', '-ss', str(entry['start_sec']), '-i', input_path,
                    '-t', str(entry['duration']), '-c', 'copy', output_path
                ]
            else:
                command = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-ss', str(entry['start_sec']), '-t', str(entry['duration']),
                    '-c', 'copy', output_path
                ]

        append_log_cb(f"[{idx}/{total}] 开始导出: {os.path.basename(output_path)}")
        append_log_cb("命令: " + " ".join(shlex.quote(c) for c in command))

        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE, bufsize=1)
            while True:
                line = process.stderr.readline()
                if not line:
                    break
                try:
                    decoded = line.decode('utf-8', errors='ignore').rstrip()
                    # 只显示关键信息，避免日志过长
                    if 'time=' in decoded or 'error' in decoded.lower():
                        append_log_cb(decoded)
                except:
                    pass
            
            ret = process.wait()
            if ret == 0:
                success_count += 1
                append_log_cb(f"✓ 已完成: {os.path.basename(output_path)}")
            else:
                append_log_cb(f"✗ 导出失败（返回码 {ret}）: {os.path.basename(output_path)}")
        except Exception as e:
            append_log_cb(f"执行 FFmpeg 时出错: {e}")

        update_progress_cb(success_count, total)

    append_log_cb("—— 任务结束 ——")
    if success_count == total:
        set_status_cb(f"完成：成功导出 {success_count}/{total} 个片段")
    elif success_count > 0:
        set_status_cb(f"部分完成：{success_count}/{total}")
    else:
        set_status_cb("全部失败")
    enable_button_cb(True, "开始执行")

# ---------- GUI 主类 ----------
class CutterApp:
    def __init__(self, master):
        self.master = master
        master.title("音视频无损批量切割工具（含 AI 辅助）")
        master.geometry("1100x800")

        self.max_segments = 50
        self.time_entries = []

        # DeepSeek API 变量
        self.deepseek_enabled_var = tk.BooleanVar(value=False)
        self.deepseek_api_key = tk.StringVar(value="")
        self.deepseek_instruction = tk.StringVar(
            value="提取视频中的精彩片段，每个片段5-15秒"
        )

        # 检查 ffmpeg
        try:
            subprocess.run(['ffmpeg', '-version'], check=True, 
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception:
            messagebox.showwarning("注意", "未检测到 ffmpeg，请先安装并加入系统 PATH。")

        self._build_ui()

    def _build_ui(self):
        self.main_frame = tk.Frame(self.master, padx=10, pady=10)
        self.main_frame.pack(fill='both', expand=True)

        # 路径组
        path_frame = tk.Frame(self.main_frame)
        path_frame.pack(fill='x', pady=(0,6))
        tk.Label(path_frame, text="输入文件:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky='w')
        self.input_path_entry = tk.Entry(path_frame)
        self.input_path_entry.grid(row=0, column=1, sticky='ew', padx=5)
        tk.Button(path_frame, text="浏览", command=self._browse_input_file, 
                 bg='#3498db', fg='white').grid(row=0, column=2, padx=4)

        tk.Label(path_frame, text="输出目录:", font=('Arial', 10, 'bold')).grid(
            row=1, column=0, sticky='w')
        self.save_path_entry = tk.Entry(path_frame)
        self.save_path_entry.grid(row=1, column=1, sticky='ew', padx=5, pady=4)
        tk.Button(path_frame, text="浏览", command=self._browse_save_path, 
                 bg='#2ecc71', fg='white').grid(row=1, column=2, padx=4)

        tk.Label(path_frame, text="命名模板:", font=('Arial', 10, 'bold')).grid(
            row=2, column=0, sticky='w')
        self.name_template_entry = tk.Entry(path_frame)
        self.name_template_entry.grid(row=2, column=1, sticky='ew', padx=5, pady=4)
        self.name_template_entry.insert(0, "{base}_{idx:03d}_{start}-{end}")
        tk.Label(path_frame, text="可用: {base} {ext} {idx} {start} {end}", 
                font=('Arial', 8), fg='gray').grid(row=2, column=2, sticky='w', padx=4)

        path_frame.grid_columnconfigure(1, weight=1)
        # 顶部右侧显眼的“开始执行”按钮
        top_ops = tk.Frame(path_frame)
        top_ops.grid(row=0, column=3, rowspan=3, sticky='ne', padx=(8,0))
        self.run_button = tk.Button(
            top_ops,
            text="🚀 开始执行",
            bg='#27ae60', fg='white',
            command=self._start_cutting_threaded,
            font=('Arial', 13, 'bold'), padx=22, pady=8
        )
        self.run_button.pack(anchor='ne')
        path_frame.grid_columnconfigure(3, weight=0)

        # DeepSeek AI 功能区
        deepseek_frame = tk.LabelFrame(self.main_frame, 
                                       text="🤖 AI 辅助切割（DeepSeek 驱动）", 
                                       padx=10, pady=10, font=('Arial', 10, 'bold'))
        deepseek_frame.pack(fill='x', pady=8)

        row1 = tk.Frame(deepseek_frame)
        row1.pack(fill='x', pady=2)
        
        self.enable_ai_check = tk.Checkbutton(
            row1, text="启用 AI 分析", variable=self.deepseek_enabled_var,
            command=self._toggle_deepseek_fields, font=('Arial', 10)
        )
        self.enable_ai_check.pack(side='left', padx=5)

        tk.Label(row1, text="API Key:", font=('Arial', 9)).pack(side='left', padx=(20,2))
        self.api_key_entry = tk.Entry(row1, textvariable=self.deepseek_api_key, 
                                      show='●', width=35)
        self.api_key_entry.pack(side='left', padx=2)
        
        if not HAS_REQUESTS:
            tk.Label(row1, text="⚠ 需安装 requests 库", fg='orange', 
                    font=('Arial', 8)).pack(side='left', padx=10)

        row2 = tk.Frame(deepseek_frame)
        row2.pack(fill='x', pady=(8,2))
        tk.Label(row2, text="分析指令:", font=('Arial', 9)).pack(side='left', padx=5)
        self.instruction_entry = tk.Entry(row2, textvariable=self.deepseek_instruction)
        self.instruction_entry.pack(side='left', fill='x', expand=True, padx=5)
        
        self.ai_analyze_btn = tk.Button(row2, text="🔍 AI 分析", 
                                        command=self._run_ai_analysis_only,
                                        bg='#9b59b6', fg='white', 
                                        font=('Arial', 9, 'bold'))
        self.ai_analyze_btn.pack(side='left', padx=5)

        self._toggle_deepseek_fields()

        # 时间操作按钮
        control_frame = tk.Frame(self.main_frame)
        control_frame.pack(fill='x', pady=(4,6))
        left_ops = tk.Frame(control_frame)
        left_ops.pack(side='left')
        tk.Button(left_ops, text="+ 添加行", command=self._add_row).pack(
            side='left', padx=4)
        tk.Button(left_ops, text="- 删除末行", command=self._remove_last_row).pack(
            side='left', padx=4)
        tk.Button(left_ops, text="↓ 导入 SRT", command=self._import_srt_file, 
                 bg='#9b59b6', fg='white').pack(side='left', padx=4)
        tk.Button(left_ops, text="🗑 清空全部", command=self._clear_all_rows,
                 bg='#e74c3c', fg='white').pack(side='left', padx=4)

        # 中间滚动区（时间行）
        canvas_frame = tk.Frame(self.main_frame)
        canvas_frame.pack(fill='both', expand=True)

        self.canvas = tk.Canvas(canvas_frame, borderwidth=1, relief='sunken', height=280)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.v_scroll = tk.Scrollbar(canvas_frame, orient='vertical', 
                                    command=self.canvas.yview)
        self.v_scroll.pack(side='right', fill='y')
        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        self.rows_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0,0), window=self.rows_frame, anchor='nw')

        self.rows_frame.bind("<Configure>", 
                           lambda e: self.canvas.configure(
                               scrollregion=self.canvas.bbox("all")))
        
        # 鼠标滚轮支持
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

        # 表头
        self.rows_frame.grid_columnconfigure(0, weight=0, minsize=40)
        self.rows_frame.grid_columnconfigure(1, weight=0, minsize=180)
        self.rows_frame.grid_columnconfigure(2, weight=0, minsize=180)
        self.rows_frame.grid_columnconfigure(3, weight=1, minsize=300)

        hdr = tk.Frame(self.rows_frame, bg='#34495e', relief='ridge', borderwidth=1)
        hdr.grid(row=0, column=0, columnspan=4, sticky='ew', pady=(0,2))
        tk.Label(hdr, text="#", width=5, bg='#34495e', fg='white',
                font=('Arial', 10, 'bold'), anchor='w').pack(side='left', padx=(5,0))
        tk.Label(hdr, text="起始时间 (HH:MM:SS,mmm)", width=24, bg='#34495e', 
                fg='white', font=('Arial', 10, 'bold'), anchor='w').pack(
                    side='left', padx=(10,0))
        tk.Label(hdr, text="结束时间 (HH:MM:SS,mmm)", width=24, bg='#34495e', 
                fg='white', font=('Arial', 10, 'bold'), anchor='w').pack(
                    side='left', padx=(10,0))
        tk.Label(hdr, text="片段描述 / 字幕预览", bg='#34495e', fg='white',
                font=('Arial', 10, 'bold'), anchor='w').pack(
                    side='left', padx=(10,0), fill='x', expand=True)

        # 初始化行
        for i in range(6):
            self._add_row(init=(i==0))

        # 运行区
        run_frame = tk.Frame(self.main_frame)
        run_frame.pack(fill='x', pady=(8,6))
        
        toggles = tk.Frame(run_frame)
        toggles.pack(side='left')
        self.ss_before_var = tk.BooleanVar(value=False)
        tk.Checkbutton(toggles, text="快速切割（-ss 前置）", 
                      variable=self.ss_before_var).pack(side='left', padx=8)
        self.compress_var = tk.BooleanVar(value=False)
        tk.Checkbutton(toggles, text="压缩输出", 
                      variable=self.compress_var).pack(side='left')

        # 执行按钮已移动到顶部路径区域，此处不再重复放置

        self.progress_bar = ttk.Progressbar(self.main_frame, mode='determinate')
        self.progress_bar.pack(fill='x', pady=(4,4))

        # 日志区
        log_frame = tk.Frame(self.main_frame)
        log_frame.pack(fill='both', expand=True)
        
        log_header = tk.Frame(log_frame)
        log_header.pack(fill='x')
        tk.Label(log_header, text="📋 运行日志", font=('Arial', 10, 'bold')).pack(
            side='left', anchor='w')
        tk.Button(log_header, text="清空", command=self._clear_log,
                 font=('Arial', 8)).pack(side='right', padx=2)
        
        self.log_text = tk.Text(log_frame, height=12, state='disabled', 
                               wrap='none', font=('Consolas', 9))
        self.log_text.pack(fill='both', expand=True)
        
        h_scroll = tk.Scrollbar(log_frame, orient='horizontal', 
                               command=self.log_text.xview)
        h_scroll.pack(fill='x')
        self.log_text.configure(xscrollcommand=h_scroll.set)

        # 状态栏
        self.status_label = tk.Label(self.main_frame, text="状态: 就绪", 
                                     anchor='w', fg='gray', font=('Arial', 9))
        self.status_label.pack(fill='x', pady=(4,0))

    def _toggle_deepseek_fields(self):
        state = tk.NORMAL if self.deepseek_enabled_var.get() else tk.DISABLED
        self.api_key_entry.config(state=state)
        self.instruction_entry.config(state=state)
        self.ai_analyze_btn.config(state=state)

    def _run_ai_analysis_only(self):
        """单独运行 AI 分析（不立即切割）"""
        # 检查 requests 库
        if not HAS_REQUESTS:
            messagebox.showerror("缺少依赖", 
                               "AI 功能需要 requests 库支持\n\n"
                               "请在命令行运行：\npip install requests")
            return
        
        input_path = self.input_path_entry.get().strip()
        if not input_path or not os.path.exists(input_path):
            messagebox.showwarning("警告", "请先选择有效的输入文件")
            return
        
        self._set_status("AI 分析中...")
        self.ai_analyze_btn.config(state=tk.DISABLED, text="分析中...")
        
        thread = threading.Thread(target=self._ai_analysis_thread, daemon=True)
        thread.start()

    def _ai_analysis_thread(self):
        """AI 分析线程"""
        input_path = self.input_path_entry.get().strip()
        api_key = self.deepseek_api_key.get().strip()
        instruction = self.deepseek_instruction.get().strip()
        
        self._append_log("=" * 50)
        self._append_log("🤖 开始 AI 分析")
        self._append_log(f"指令: {instruction}")
        
        # 获取媒体信息
        media_info = {
            'filename': os.path.basename(input_path),
            'duration': get_media_duration(input_path)
        }
        self._append_log(f"文件: {media_info['filename']}")
        self._append_log(f"时长: {media_info['duration']}")
        
        # 调用 API
        segments = call_deepseek_api(api_key, instruction, media_info, self._append_log)
        
        if segments and len(segments) > 0:
            self._clear_and_fill_time_entries(segments)
            self._append_log(f"✓ 成功生成 {len(segments)} 个片段")
            self._set_status(f"AI 分析完成：{len(segments)} 个片段")
            
            def re_enable():
                self.ai_analyze_btn.config(state=tk.NORMAL, text="🔍 AI 分析")
            self.master.after(0, re_enable)
        else:
            self._append_log("✗ AI 分析未返回有效结果")
            self._set_status("AI 分析失败")
            
            def re_enable():
                self.ai_analyze_btn.config(state=tk.NORMAL, text="🔍 AI 分析")
                messagebox.showwarning("AI 分析", "未能从 AI 获取有效片段，请检查：\n"
                                     "1. API Key 是否正确\n"
                                     "2. 网络连接是否正常\n"
                                     "3. 指令是否明确")
            self.master.after(0, re_enable)
        
        self._append_log("=" * 50)

    def _clear_and_fill_time_entries(self, segments):
        """清空并填充时间行"""
        def _do():
            needed = min(len(segments), self.max_segments)
            while len(self.time_entries) < needed:
                self._add_row()
            
            # 清空所有行
            for e in self.time_entries:
                e['start'].delete(0, tk.END)
                e['end'].delete(0, tk.END)
                e['text'].delete(0, tk.END)
            
            # 填入新数据
            for i, seg in enumerate(segments[:self.max_segments]):
                self.time_entries[i]['start'].insert(0, seg['start_str'])
                self.time_entries[i]['end'].insert(0, seg['end_str'])
                text_content = seg.get('text', f"片段 {i+1}")[:200]
                self.time_entries[i]['text'].insert(0, text_content)
            
            # 滚动到顶部
            self.canvas.yview_moveto(0)
        
        self.master.after(0, _do)

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            delta = 0
            if hasattr(event, 'delta'):
                delta = int(event.delta)
            if sys.platform == 'darwin':
                self.canvas.yview_scroll(int(-1 * delta), "units")
            else:
                self.canvas.yview_scroll(int(-1 * (delta / 120)), "units")

    def _browse_input_file(self):
        filetypes = [
            ("音视频文件", "*.mp4 *.mp3 *.mov *.mkv *.wav *.flac *.aac *.m4a"),
            ("所有文件", "*.*")
        ]
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            self.input_path_entry.delete(0, tk.END)
            self.input_path_entry.insert(0, filename)

    def _browse_save_path(self):
        dirname = filedialog.askdirectory()
        if dirname:
            self.save_path_entry.delete(0, tk.END)
            self.save_path_entry.insert(0, dirname)

    def _add_row(self, init=False):
        current = len(self.time_entries)
        if current >= self.max_segments:
            messagebox.showwarning("限制", f"已达到最大段数 {self.max_segments}")
            return
        
        row = len(self.time_entries) + 1
        r = row
        
        lbl = tk.Label(self.rows_frame, text=str(row), width=5, anchor='w')
        lbl.grid(row=r, column=0, padx=(5,2), pady=2, sticky='w')
        
        start = tk.Entry(self.rows_frame, width=24)
        start.grid(row=r, column=1, padx=2, pady=2, sticky='ew')
        
        end = tk.Entry(self.rows_frame, width=24)
        end.grid(row=r, column=2, padx=2, pady=2, sticky='ew')
        
        text_preview = tk.Entry(self.rows_frame)
        text_preview.grid(row=r, column=3, padx=2, pady=2, sticky='ew')
        
        if init:
            start.insert(0, "00:00:00,000")
            end.insert(0, "00:00:10,000")
            text_preview.insert(0, "示例片段（手动修改或使用 AI 生成）")

        # 失焦自动格式化
        start.bind('<FocusOut>', lambda e: self._normalize_time_entry(start))
        end.bind('<FocusOut>', lambda e: self._normalize_time_entry(end))
        
        self.time_entries.append({
            'label': lbl, 'start': start, 'end': end, 'text': text_preview
        })

    def _normalize_time_entry(self, entry):
        """格式化时间输入"""
        val = entry.get().strip()
        if not val:
            return
        try:
            v = val.replace('。', '.').replace('，', ',').replace('：', ':')
            v = v.replace('.', ',')
            parts = v.split(',')
            hms = parts[0].split(':')
            hms = [p.zfill(2) for p in hms]
            while len(hms) < 3:
                hms.insert(0, '00')
            hms = hms[-3:]
            ms = (parts[1] if len(parts) > 1 else '000')
            ms = (ms + '000')[:3]
            norm = f"{hms[0]}:{hms[1]}:{hms[2]},{ms}"
            _ = time_to_seconds(norm)
            entry.delete(0, tk.END)
            entry.insert(0, norm)
        except Exception:
            pass

    def _remove_last_row(self):
        if not self.time_entries:
            return
        e = self.time_entries.pop()
        e['label'].destroy()
        e['start'].destroy()
        e['end'].destroy()
        e['text'].destroy()

    def _clear_all_rows(self):
        """清空所有时间输入"""
        if not messagebox.askyesno("确认", "确定要清空所有时间输入吗？"):
            return
        for e in self.time_entries:
            e['start'].delete(0, tk.END)
            e['end'].delete(0, tk.END)
            e['text'].delete(0, tk.END)
        self._append_log("已清空所有时间输入")

    def _import_srt_file(self):
        """导入 SRT 字幕文件"""
        input_path = self.input_path_entry.get().strip()
        if not input_path:
            messagebox.showwarning("警告", "请先选择原始输入媒体文件")
            return
        
        srt_path = filedialog.askopenfilename(
            title="选择 SRT 文件",
            filetypes=[("SRT", "*.srt"), ("所有文件", "*.*")]
        )
        if not srt_path:
            return
        
        try:
            segments = parse_srt_file(srt_path)
            if not segments:
                messagebox.showwarning("警告", "SRT 中未找到有效段落")
                return
            
            self._clear_and_fill_time_entries(segments)
            self._append_log(f"✓ 从 SRT 导入 {min(len(segments), self.max_segments)} 个片段")
            self._set_status(f"成功导入 {min(len(segments), self.max_segments)} 个片段")
        except Exception as e:
            messagebox.showerror("导入错误", f"SRT 导入失败: {e}")
            self._append_log(f"✗ SRT 导入失败: {e}")

    def _clear_log(self):
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')

    def _append_log(self, text):
        """线程安全的日志追加"""
        def _do():
            self.log_text.configure(state='normal')
            self.log_text.insert('end', text + '\n')
            self.log_text.see('end')
            self.log_text.configure(state='disabled')
        self.master.after(0, _do)

    def _enable_button(self, enabled, text):
        """线程安全的按钮状态控制"""
        def _do():
            state = tk.NORMAL if enabled else tk.DISABLED
            if enabled:
                self.run_button.config(state=state, text="🚀 开始执行", bg='#27ae60', fg='white', cursor='')
            else:
                # 执行中禁用按钮并置灰
                self.run_button.config(state=state, text="⏳ 执行中...", bg='#95a5a6', fg='white', cursor='watch')
        self.master.after(0, _do)

    def _set_status(self, text):
        """线程安全的状态栏更新"""
        def _do():
            fg = 'gray'
            bg = self.main_frame.cget('bg')
            if any(k in text for k in ("运行", "进行", "切割", "分析")):
                fg, bg = ('white', '#2980b9')
            if any(k in text for k in ("完成", "成功")):
                fg, bg = ('white', '#27ae60')
            if any(k in text for k in ("部分",)):
                fg, bg = ('#2c3e50', '#f39c12')
            if any(k in text for k in ("失败", "错误")):
                fg, bg = ('white', '#c0392b')
            if any(k in text for k in ("就绪",)):
                fg, bg = ('#555', '#ecf0f1')
            self.status_label.config(text="状态: " + text, fg=fg, bg=bg)
        self.master.after(0, _do)

    def _update_progress(self, value, maximum):
        """线程安全的进度条更新"""
        def _do():
            try:
                self.progress_bar['maximum'] = maximum
                self.progress_bar['value'] = value
            except Exception:
                pass
        self.master.after(0, _do)

    def _start_cutting_threaded(self):
        """启动切割任务"""
        input_path = self.input_path_entry.get().strip()
        save_path = self.save_path_entry.get().strip()
        
        if not input_path or not save_path:
            messagebox.showwarning("警告", "请填写输入文件和保存目录")
            return
        
        if not os.path.exists(input_path):
            messagebox.showwarning("警告", "输入文件不存在")
            return

        name_template = self.name_template_entry.get().strip()
        if not name_template:
            name_template = "{base}_{idx:03d}_{start}-{end}"

        # 检查是否启用 AI 且未分析
        if self.deepseek_enabled_var.get():
            # 如果启用了 AI 但没有 requests 库
            if not HAS_REQUESTS:
                messagebox.showwarning("提示", 
                                     "已启用 AI 但缺少 requests 库\n"
                                     "将使用手动输入的时间进行切割")
            else:
                has_time = any((e['start'].get().strip() or e['end'].get().strip()) 
                              for e in self.time_entries)
                if not has_time:
                    if messagebox.askyesno("AI 分析", 
                                          "启用了 AI 但未生成时间点。\n是否先运行 AI 分析？"):
                        self._run_ai_analysis_only()
                        return
        
        # 常规模式检查
        has_time = any((e['start'].get().strip() or e['end'].get().strip()) 
                      for e in self.time_entries)
        if not has_time:
            messagebox.showwarning("警告", "请先输入时间或导入 SRT 或运行 AI 分析")
            return

        # 启动切割
        self._enable_button(False, "执行中...")
        self._update_progress(0, 1)
        self._set_status("切割运行中")
        
        thread = threading.Thread(
            target=run_cutting_logic,
            args=(
                input_path, save_path, self.time_entries,
                self._append_log, self._update_progress,
                self._enable_button, self._set_status,
                self.compress_var.get(), self.ss_before_var.get(),
                name_template
            ),
            daemon=True
        )
        thread.start()

# ---------- 入口 ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = CutterApp(root)
    root.mainloop()
