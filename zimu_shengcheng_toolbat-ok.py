# -*- coding: utf-8 -*-
"""
视频静音处理 + 自动字幕生成工具（优化版）

功能：
- 批量处理视频文件
- 可选生成静音视频或保留原音频
- 自动生成 SRT 字幕文件
- 使用 Whisper 进行语音识别
- 自动检测依赖并提供安装选项

[+] UI 修复：
- 修复了主窗口宽度不足时，“选择...”按钮被挤出界面的问题。
- 将路径输入框改为动态拉伸，确保按钮始终可见。
- 增加了窗口默认宽度。
"""

import os
import sys
import site
import pathlib

# 优先加载脚本同目录下的 .venv（无需手动激活）
try:
    _base_dir = pathlib.Path(__file__).resolve().parent
    _venv_dir = _base_dir / ".venv"
    if _venv_dir.exists():
        if sys.platform == "win32":
            _sp = _venv_dir / "Lib" / "site-packages"
        else:
            _sp = next(((_venv_dir / "lib").glob("python*/site-packages")))
        if _sp.exists():
            site.addsitedir(str(_sp))
            os.environ.setdefault("VIRTUAL_ENV", str(_venv_dir))
            bin_dir = _venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
except Exception:
    # 软失败，不影响后续逻辑
    pass

# 可选：导入失败时自动安装依赖（使用清华镜像），避免手工处理
def _ensure_package(pkg_spec: str):
    name = pkg_spec.split("==")[0].split(">=")[0].split("<=")[0].replace("-", "_")
    try:
        __import__(name)
        return
    except Exception:
        try:
            import subprocess
            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                "-i",
                "https://pypi.tuna.tsinghua.edu.cn/simple",
                pkg_spec,
            ])
        except Exception as _e:
            # 安装失败时不阻断启动，后续正常的依赖检测逻辑仍会提示
            sys.stderr.write(f"[warn] 自动安装 {pkg_spec} 失败：{_e}\n")

# 仅在未安装时尝试安装，避免额外等待
for _spec in ("numpy>=2", "ffmpeg-python"):
    _ensure_package(_spec)
import threading
import subprocess
import traceback
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import shutil
import platform

# 可选依赖库（不再使用 moviepy）
try:
    import ffmpeg  # ffmpeg-python
except ImportError:
    ffmpeg = None

try:
    import whisper
except ImportError:
    whisper = None

# 优先尝试 faster-whisper（兼容 Python 3.13，无需 PyTorch）
try:
    from faster_whisper import WhisperModel as FWWhisperModel
except Exception:
    FWWhisperModel = None

# ----------------------------
# 依赖安装函数
# ----------------------------
def install_dependencies_async(progress_var, log_func, on_done=None):
    def run():
        try:
            # 允许配置的镜像列表（默认先用系统源，失败自动尝试镜像）
            mirrors = [
                None,  # 使用系统默认源
                "https://pypi.tuna.tsinghua.edu.cn/simple",
                "https://mirrors.aliyun.com/pypi/simple",
            ]

            def _pip_install(pkgs):
                last_err = None
                for idx, mirror in enumerate(mirrors):
                    try:
                        if mirror:
                            log_func(f"使用镜像源安装: {mirror}")
                            cmd = [sys.executable, "-m", "pip", "install", "--index-url", mirror, *pkgs]
                        else:
                            log_func("使用默认源安装依赖...")
                            cmd = [sys.executable, "-m", "pip", "install", *pkgs]
                        subprocess.run(cmd, check=True)
                        return True
                    except Exception as e:
                        last_err = e
                        log_func(f"安装失败，尝试下一个源（{e}）")
                if last_err:
                    raise last_err
                return False

            # 优先使用 faster-whisper，避免 torch 兼容性问题（macOS/新版本Python）
            prefer_faster = True

            progress_var.set("正在安装依赖，请稍候（可能需要几分钟）...")

            # 先确保基础工具最新（容错，不因失败中断）
            try:
                for base_pkg in ("pip", "setuptools", "wheel"):
                    for mirror in mirrors:
                        try:
                            if mirror:
                                subprocess.run([sys.executable, "-m", "pip", "install", "-U", "--index-url", mirror, base_pkg], check=True)
                            else:
                                subprocess.run([sys.executable, "-m", "pip", "install", "-U", base_pkg], check=True)
                            break
                        except Exception:
                            continue
            except Exception:
                pass

            # 安装 ffmpeg-python（可选，方便调用；实际仍依赖系统 ffmpeg）
            log_func("开始安装 ffmpeg-python ...")
            _pip_install(["ffmpeg-python"])  # 若已安装会跳过

            # 优先尝试 faster-whisper（不再自动安装 torch，减少失败面）
            installed = False
            try:
                log_func("开始安装 faster-whisper ...")
                _pip_install(["faster-whisper"])  # 无 torch 依赖
                installed = True
            except Exception as e:
                log_func(f"faster-whisper 安装失败：{e}")
                log_func("如需使用 openai-whisper，请手动安装：pip install openai-whisper torch")

            progress_var.set("✅ 依赖安装完成")
            log_func("✅ 依赖安装完成")
            if callable(on_done):
                try:
                    on_done()
                except Exception:
                    pass
        except Exception as e:
            progress_var.set(f"❌ 安装失败: {e}")
            log_func(f"❌ 安装失败: {e}")
    threading.Thread(target=run, daemon=True).start()

# ----------------------------
# 模型加载函数
# ----------------------------
def load_whisper_model_async(model_name, model_container, progress_var, log_func):
    def run():
        try:
            # 强制优先使用 faster-whisper；指定下载缓存目录到家目录，避免空格路径问题
            from pathlib import Path
            cache_dir = Path.home() / ".cache" / "faster-whisper"
            cache_dir.mkdir(parents=True, exist_ok=True)

            if FWWhisperModel is not None:
                log_func(f"正在加载 Faster-Whisper 模型: {model_name}（首次加载会下载到 {cache_dir}）...")
                progress_var.set(f"正在加载 {model_name} 模型，请稍候...")
                model_container['model'] = (
                    "faster",
                    FWWhisperModel(
                        model_name,
                        device="cpu",
                        compute_type="int8",
                        download_root=str(cache_dir),
                    ),
                )
                progress_var.set(f"✅ 模型 {model_name} 已就绪（Faster-Whisper）")
                log_func(f"✅ Faster-Whisper 模型 {model_name} 加载完成（缓存目录：{cache_dir}）")
            else:
                if whisper is None:
                    log_func("❌ 未检测到 faster-whisper 或 openai-whisper。请点击'安装依赖'或手动安装：pip install faster-whisper")
                    progress_var.set("请点击'安装依赖'按钮安装 faster-whisper")
                    return
                log_func(f"正在加载 Whisper 模型: {model_name}（首次加载会下载模型文件）...")
                progress_var.set(f"正在加载 {model_name} 模型，请稍候...")
                # openai-whisper 默认缓存于 ~/.cache/whisper
                model_container['model'] = ("openai", whisper.load_model(model_name))
                progress_var.set(f"✅ 模型 {model_name} 已就绪（openai-whisper）")
                log_func(f"✅ Whisper 模型 {model_name} 加载完成")
        except Exception as e:
            progress_var.set(f"❌ 模型加载失败: {e}")
            log_func(f"❌ 模型加载失败: {e}\n{traceback.format_exc()}")
    threading.Thread(target=run, daemon=True).start()

# ----------------------------
# SRT 时间格式化
# ----------------------------
def format_srt_time(seconds):
    """将秒数转换为 SRT 时间格式 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# ----------------------------
# 核心处理函数
# ----------------------------
def process_video(input_path, output_folder, keep_audio, model, log_func, index, total):
    """
    处理单个视频文件
    - 生成字幕文件
    - 可选生成静音视频
    """
    temp_audio = None
    name = None
    
    try:
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)
        
        log_func(f"[{index}/{total}] 开始处理: {name}")
        
        # 检查依赖
        if ffmpeg is None and shutil.which('ffmpeg') is None:
            raise RuntimeError("未检测到 ffmpeg-python 或 ffmpeg 可执行文件")
        if model is None:
            raise RuntimeError("Whisper 模型未加载")

        # 1. 导出音频用于识别（通过 ffmpeg 提取）
        temp_audio = os.path.join(output_folder, f"{name}_temp.wav")
        log_func(f"[{index}/{total}] 正在提取音频...")
        try:
            # 优先使用 ffmpeg-python，如果不可用则退回到 ffmpeg CLI
            if ffmpeg is not None:
                (
                    ffmpeg
                    .input(input_path)
                    .output(temp_audio, ac=1, ar=16000, vn=None, loglevel='error')
                    .overwrite_output()
                    .run()
                )
            else:
                subprocess.run([
                    'ffmpeg', '-y', '-i', input_path, '-vn', '-ac', '1', '-ar', '16000', temp_audio
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"提取音频失败: {e}")
        
        # 2. 语音识别（兼容 faster-whisper 与 openai-whisper）
        log_func(f"[{index}/{total}] 正在识别语音（可能较慢）...")
        engine, mdl = model if isinstance(model, tuple) else ("openai", model)
        segments = []
        if engine == "faster":
            try:
                fw_segments, info = mdl.transcribe(temp_audio, language="zh", beam_size=5)
                for seg in fw_segments:
                    segments.append({
                        'start': float(seg.start or 0),
                        'end': float(seg.end or 0),
                        'text': seg.text.strip() if getattr(seg, 'text', None) else ''
                    })
            except Exception as e:
                raise RuntimeError(f"Faster-Whisper 识别失败: {e}")
        else:
            try:
                result = mdl.transcribe(temp_audio, language='zh')
                segments = result.get('segments', [])
            except Exception as e:
                raise RuntimeError(f"openai-whisper 识别失败: {e}")
        
        # 3. 生成 SRT 字幕文件
        output_srt_path = os.path.join(output_folder, f"{name}.srt")
        with open(output_srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, start=1):
                start = seg.get('start', 0)
                end = seg.get('end', start)
                text = (seg.get('text') or '').strip()
                f.write(f"{i}\n")
                f.write(f"{format_srt_time(start)} --> {format_srt_time(end)}\n")
                f.write(f"{text}\n\n")
        
        log_func(f"[{index}/{total}] ✅ 字幕生成完成: {name}.srt ({len(segments)} 个片段)")
        
        # 4. 如果需要生成静音视频（通过 ffmpeg 去除音轨）
        if not keep_audio:
            output_video_path = os.path.join(output_folder, f"{name}_mute{ext}")
            log_func(f"[{index}/{total}] 正在导出静音视频...")
            try:
                if ffmpeg is not None:
                    (
                        ffmpeg
                        .input(input_path)
                        .output(output_video_path, an=None, vcodec='libx264', loglevel='error')
                        .overwrite_output()
                        .run()
                    )
                else:
                    subprocess.run([
                        'ffmpeg', '-y', '-i', input_path, '-an', '-vcodec', 'libx264', output_video_path
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"导出静音视频失败: {e}")
            log_func(f"[{index}/{total}] ✅ 静音视频生成完成: {name}_mute{ext}")
        
        return True
        
    except Exception as e:
        log_func(f"[{index}/{total}] ❌ 处理失败: {name or filename} - {e}")
        return False
        
    finally:
        # 清理资源
        # 删除临时音频文件
        if temp_audio and os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except Exception:
                pass

# ----------------------------
# 批量处理函数
# ----------------------------
def start_batch_processing(input_folder, output_folder, keep_audio, model_container, progress_var, log_func):
    """批量处理文件夹中的所有视频"""
    
    if not input_folder or not output_folder:
        messagebox.showwarning("提示", "请选择输入和输出文件夹")
        return
    
    if not os.path.exists(input_folder):
        messagebox.showerror("错误", "输入文件夹不存在")
        return
    
    if not os.path.exists(output_folder):
        try:
            os.makedirs(output_folder, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法创建输出文件夹: {e}")
            return
    
    model = model_container.get('model')
    if model is None:
        messagebox.showerror("错误", "请先加载 Whisper 模型")
        return
    
    # 支持的视频格式
    video_exts = ('.mp4', '.mov', '.mkv', '.avi', '.flv', '.wmv', '.mpg', '.mpeg', '.m4v', '.webm')
    videos = [f for f in os.listdir(input_folder) if f.lower().endswith(video_exts)]
    
    if not videos:
        messagebox.showwarning("提示", f"输入文件夹内没有视频文件\n支持格式: {', '.join(video_exts)}")
        return
    
    log_func(f"=" * 60)
    log_func(f"开始批量处理，共 {len(videos)} 个视频文件")
    log_func(f"输入目录: {input_folder}")
    log_func(f"输出目录: {output_folder}")
    log_func(f"模式: {'仅生成字幕' if keep_audio else '生成字幕+静音视频'}")
    log_func(f"=" * 60)
    
    progress_var.set(f"开始处理 {len(videos)} 个视频...")
    
    def run():
        total = len(videos)
        success_count = 0
        failure_count = 0
        
        for i, video in enumerate(videos, start=1):
            video_path = os.path.join(input_folder, video)
            if process_video(video_path, output_folder, keep_audio, model, log_func, i, total):
                success_count += 1
            else:
                failure_count += 1
        
        # 完成总结
        log_func(f"=" * 60)
        log_func(f"✅ 全部处理完成！成功: {success_count}, 失败: {failure_count}")
        log_func(f"=" * 60)
        
        if failure_count == 0:
            progress_var.set(f"✅ 全部处理完成！共 {success_count} 个文件")
        else:
            progress_var.set(f"✅ 处理完成！成功 {success_count} 个，失败 {failure_count} 个")
    
    threading.Thread(target=run, daemon=True).start()

# ----------------------------
# 自动检测依赖
# ----------------------------
def auto_detect_dependencies(log_func, progress_var, model_container, model_var):
    """启动时自动检测已安装的依赖"""
    log_func("正在检测系统依赖...")
    
    deps = []
    
    # 检测 ffmpeg 相关
    if ffmpeg is not None:
        deps.append("✓ ffmpeg-python 已安装")
    else:
        deps.append("✗ ffmpeg-python 未安装（可选）")
    
    # 检测 Whisper（优先 faster-whisper）
    if FWWhisperModel is not None:
        deps.append("✓ Faster-Whisper 已安装")
        log_func(f"检测到 Faster-Whisper，正在自动加载 {model_var.get()} 模型...")
        load_whisper_model_async(model_var.get(), model_container, progress_var, log_func)
    elif whisper is not None:
        deps.append("✓ Whisper 已安装")
        log_func(f"检测到 Whisper，正在自动加载 {model_var.get()} 模型...")
        load_whisper_model_async(model_var.get(), model_container, progress_var, log_func)
    else:
        deps.append("✗ Whisper/Faster-Whisper 未安装")
    
    # 检测 FFmpeg（尝试自动加入常见安装路径到 PATH）
    ffmpeg_ok = True
    def _ffmpeg_in_path():
        return shutil.which('ffmpeg') is not None

    if not _ffmpeg_in_path():
        # 尝试常见路径
        sysname = platform.system()
        candidates = []
        if sysname == 'Darwin':  # macOS Homebrew 常见位置
            candidates += [
                '/opt/homebrew/bin',
                '/usr/local/bin',
            ]
        elif sysname == 'Windows':
            program_files = os.environ.get('ProgramFiles', r'C:\\Program Files')
            program_files_x86 = os.environ.get('ProgramFiles(x86)', r'C:\\Program Files (x86)')
            candidates += [
                os.path.join(program_files, 'ffmpeg', 'bin'),
                os.path.join(program_files_x86, 'ffmpeg', 'bin'),
                r'C:\\ffmpeg\\bin',
            ]
        else:  # Linux 常见位置
            candidates += ['/usr/bin', '/usr/local/bin']

        for p in candidates:
            if os.path.isdir(p) and shutil.which('ffmpeg', path=p):
                os.environ['PATH'] = p + os.pathsep + os.environ.get('PATH', '')
                break

    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=3)
        deps.append("✓ FFmpeg 已安装")
    except Exception:
        ffmpeg_ok = False
        deps.append("✗ FFmpeg 未安装或不可用")
    
    for dep in deps:
        log_func(dep)
    
    if all("✓" in d for d in deps):
        progress_var.set("✅ 所有依赖就绪")
    else:
        missing = [d for d in deps if "✗" in d]
        progress_var.set(f"⚠️ 部分依赖缺失，请点击'安装依赖'按钮")
        # 若 FFmpeg 缺失，给出安装引导
        if not ffmpeg_ok:
            ui_hint = (
                "未检测到 FFmpeg。\n"
                "macOS: 使用 Homebrew 安装 -> brew install ffmpeg\n"
                "Windows: 下载静态包 -> https://www.gyan.dev/ffmpeg/builds/ ，解压并将 bin 目录加入 PATH\n"
                "Linux: apt-get install ffmpeg 或使用对应发行版包管理器\n"
            )
            log_func(ui_hint)
            try:
                # 弹窗指引
                messagebox.showinfo(
                    "FFmpeg 安装指引",
                    "未检测到 FFmpeg。\n\n"
                    "macOS: 用 Homebrew 安装 -> brew install ffmpeg\n"
                    "Windows: 下载静态包 -> gyan.dev/ffmpeg/builds/ 并将 bin 加入 PATH\n"
                    "Linux: apt/yum 安装 ffmpeg 或使用发行版包管理器"
                )
            except Exception:
                pass

# ----------------------------
# 主界面
# ----------------------------
def main():
    root = tk.Tk()
    root.title("视频静音处理 + 自动字幕生成工具（增强版）")
    # 【修改】增加了默认窗口宽度
    root.geometry("800x650") 
    
    model_container = {'model': None}
    
    # ========== 顶部：模型设置区域 ==========
    frame_top = ttk.LabelFrame(root, text="模型设置")
    frame_top.pack(fill="x", padx=10, pady=8)
    
    ttk.Label(frame_top, text="Whisper 模型:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
    model_var = tk.StringVar(value="small")
    model_combo = ttk.Combobox(
        frame_top, 
        textvariable=model_var, 
        values=["tiny", "base", "small", "medium", "large"],
        state="readonly",
        width=12
    )
    model_combo.grid(row=0, column=1, padx=8, pady=8)
    
    btn_load_model = ttk.Button(
        frame_top, 
        text="加载模型",
        width=15
    )
    btn_load_model.grid(row=0, column=2, padx=8, pady=8)
    
    btn_install_deps = ttk.Button(
        frame_top,
        text="安装依赖",
        width=15
    )
    btn_install_deps.grid(row=0, column=3, padx=8, pady=8)
    
    # ========== 中部：文件选择区域 ==========
    frame_mid = ttk.LabelFrame(root, text="文件选择")
    frame_mid.pack(fill="x", padx=10, pady=8)
    
    # 【修改】配置第 1 列（输入框列）为动态拉伸
    frame_mid.columnconfigure(1, weight=1) 
    
    input_path = tk.StringVar()
    output_path = tk.StringVar()
    
    # 定义选择函数
    def select_input():
        path = filedialog.askdirectory(title="选择视频输入文件夹")
        if path:
            input_path.set(path)
    
    def select_output():
        path = filedialog.askdirectory(title="选择输出文件夹")
        if path:
            output_path.set(path)
    
    # 输入文件夹
    ttk.Label(frame_mid, text="输入视频文件夹:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
    # 【修改】移除了 fixed width=65, 添加了 sticky="we" 使其拉伸
    ttk.Entry(frame_mid, textvariable=input_path).grid(row=0, column=1, padx=8, pady=6, sticky="we") 
    ttk.Button(frame_mid, text="选择...", command=select_input).grid(row=0, column=2, padx=8, pady=6)
    
    # 输出文件夹
    ttk.Label(frame_mid, text="输出文件夹:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
    # 【修改】移除了 fixed width=65, 添加了 sticky="we" 使其拉伸
    ttk.Entry(frame_mid, textvariable=output_path).grid(row=1, column=1, padx=8, pady=6, sticky="we")
    ttk.Button(frame_mid, text="选择...", command=select_output).grid(row=1, column=2, padx=8, pady=6)
    
    # 选项
    keep_audio = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        frame_mid,
        text="仅生成字幕（不生成静音视频）",
        variable=keep_audio
    ).grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=10)
    
    # 开始处理按钮
    def start_processing():
        start_batch_processing(
            input_path.get(),
            output_path.get(),
            keep_audio.get(),
            model_container,
            progress_var,
            ui_log
        )
    
    ttk.Button(
        frame_mid,
        text="开始处理",
        command=start_processing
    ).grid(row=3, column=0, columnspan=3, pady=12)
    
    # ========== 底部：状态和日志区域 ==========
    frame_bot = ttk.LabelFrame(root, text="状态 / 日志")
    frame_bot.pack(fill="both", expand=True, padx=10, pady=8)
    
    progress_var = tk.StringVar(value="正在检测依赖...")
    ttk.Label(frame_bot, textvariable=progress_var, foreground="blue", wraplength=700).pack(anchor="w", padx=8, pady=6)
    
    # 日志文本框
    log_frame = ttk.Frame(frame_bot)
    log_frame.pack(fill="both", expand=True, padx=8, pady=6)
    
    log_text = tk.Text(log_frame, height=18, wrap="word")
    log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=log_text.yview)
    log_text.configure(yscrollcommand=log_scrollbar.set)
    
    log_text.pack(side="left", fill="both", expand=True)
    log_scrollbar.pack(side="right", fill="y")
    
    # UI 日志函数
    def ui_log(msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_text.insert("end", f"[{timestamp}] {msg}\n")
        log_text.see("end")
        root.update_idletasks()
    
    # 初始说明
    ui_log("=" * 60)
    ui_log("视频静音处理 + 自动字幕生成工具")
    ui_log("功能: 批量处理视频，自动生成 SRT 字幕文件")
    ui_log("支持格式: MP4, MOV, MKV, AVI, FLV, WMV, MPG, MPEG, M4V, WEBM")
    ui_log("=" * 60)
    
    # 绑定按钮事件
    btn_load_model.config(
        command=lambda: load_whisper_model_async(
            model_var.get(), model_container, progress_var, ui_log
        )
    )
    
    btn_install_deps.config(
        command=lambda: install_dependencies_async(progress_var, ui_log)
    )
    
    # 启动后自动检测依赖，并在缺失时自动安装
    def detect_and_auto_install():
        def _post_detect():
            # 检查缺失项提示文本中是否包含 ✗
            text = log_text.get("1.0", "end")
            missing = ("✗ Whisper" in text) or ("✗ Faster-Whisper" in text) or ("✗ ffmpeg-python" in text)
            # 仅对 Python 包做自动安装；FFmpeg 仍需用户自行安装
            if missing:
                ui_log("检测到部分依赖缺失，正在自动安装 Python 依赖...")
                def after_install():
                    ui_log("依赖安装完成，正在自动加载模型...")
                    load_whisper_model_async(model_var.get(), model_container, progress_var, ui_log)
                install_dependencies_async(progress_var, ui_log, on_done=after_install)
            else:
                # 若依赖齐全，直接尝试加载模型
                load_whisper_model_async(model_var.get(), model_container, progress_var, ui_log)

        auto_detect_dependencies(ui_log, progress_var, model_container, model_var)
        # 稍等日志刷出后判断并自动安装
        root.after(200, _post_detect)

    root.after(500, detect_and_auto_install)
    
    root.mainloop()

if __name__ == "__main__":
    main()
