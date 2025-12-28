#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os as _os, sys as _sys, subprocess as _subprocess, venv as _venv

# 自动创建并进入同目录虚拟环境 whisper_env，并确保依赖
_BASE_DIR = _os.path.dirname(_os.path.abspath(__file__))
_VENV_DIR = _os.path.join(_BASE_DIR, 'whisper_env')
_IS_WIN = (_sys.platform == 'win32')
_PY_BIN = _os.path.join(_VENV_DIR, 'Scripts' if _IS_WIN else 'bin', 'python.exe' if _IS_WIN else 'python3')
_PIP_BIN = _os.path.join(_VENV_DIR, 'Scripts' if _IS_WIN else 'bin', 'pip.exe' if _IS_WIN else 'pip')

def _in_venv():
    return _sys.prefix != _sys.base_prefix

def _ensure_venv_and_deps():
    if not _os.path.exists(_os.path.join(_VENV_DIR, 'pyvenv.cfg')):
        _venv.create(_VENV_DIR, with_pip=True)
    # 升级 pip 工具并安装依赖（非致命失败不抛异常）
    _subprocess.run([_PY_BIN, '-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'], check=False)
    reqs = ['openai-whisper', 'torch', 'pysrt', 'requests']
    _subprocess.run([_PIP_BIN, 'install', *reqs], check=False)

def _relaunch_inside_venv():
    _os.execv(_PY_BIN, [_PY_BIN, __file__, *_sys.argv[1:]])

if not _in_venv():
    try:
        _ensure_venv_and_deps()
        _relaunch_inside_venv()
    except Exception as e:
        print(f'自动创建/安装虚拟环境失败: {e}')
        print('请手动执行:')
        print('  cd ~/Documents/优化设计\\ 四年级上册（福建专版）')
        print('  python3 -m venv whisper_env && source whisper_env/bin/activate')
        print('  pip install openai-whisper torch pysrt requests')
"""
Whisper 工具 - 完整功能实现版本 (AI API增强 - UI Key输入版)
核心功能：
1. 语音转字幕：使用本地 Whisper 模型。
2. 字幕翻译：使用 DeepSeek API 进行高质量双语翻译。
3. 分镜/Prompt 生成：使用 DeepSeek API 对字幕内容进行总结，并生成 AI 视频/图片提示词 (JSON/CSV格式)。
4. UI 优化：支持 API Key UI 输入、多功能选项卡、实时进度和日志。
"""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import datetime
import threading
import os
import subprocess
import sys
import json
import csv
import requests # 用于调用 DeepSeek API

# 核心依赖：需要安装 pip install openai-whisper torch pysrt requests
try:
    import whisper
    import pysrt
except ImportError:
    whisper = None
    pysrt = None

class ImprovedWhisperUI:
    # DeepSeek API 相关配置
    DEEPSEEK_API_BASE = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL = "deepseek-chat" # 或 deepseek-coder

    def __init__(self, master):
        self.master = master
        master.title("Whisper 智能字幕工具 - AI增强版")
        # 稍微增加高度以容纳新的 API Key 输入框
        master.geometry("1100x850") 
        
        # 数据
        self.input_files_transcription = []
        self.input_files_translation = []
        self.input_files_storyboard = []
        # 输出目录（SRT保存路径）：不写死默认路径。默认为空，需用户选择并可保存到任意路径。
        self.output_dir = ''
        self.model_loaded = False
        self.model_name = tk.StringVar(value="small")
        self.model = None
        
        # 【新增】用于存储 API Key 的 StringVar 与 API 优先开关
        # 优先读取环境变量，如果没有，则为空
        initial_key = os.getenv('DEEPSEEK_API_KEY', '')
        self.api_key_var = tk.StringVar(value=initial_key)
        # API 优先：开启时优先使用 DeepSeek API
        self.api_prefer_var = tk.BooleanVar(value=True)

        # 翻译目标设置（应用于“翻译”页与转录页自动翻译）
        # mode: auto(自动判断中↔英), zh(中文), en(英文), custom(自定义)
        self.translate_target_mode = tk.StringVar(value='auto')
        self.translate_target_custom = tk.StringVar(value='')
        # 转录页自动翻译开关：off/zh/en（向后兼容，默认off改为遵循新的选择器状态）
        self.auto_translate_mode = tk.StringVar(value='off')
        
        # 配置持久化文件路径（与脚本同目录）
        try:
            self._base_dir = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            self._base_dir = os.getcwd()
        self._config_path = os.path.join(self._base_dir, 'whisper_tool_config.json')

        self._setup_ui()

        # 尝试加载上次保存的配置（输出目录等）
        self._load_config()
        # 若未配置输出目录，则设置为默认目录 ~/Documents/whisper_outputs
        try:
            if not self.output_dir:
                default_out = os.path.expanduser('~/Documents/whisper_outputs')
                self.output_dir = default_out
                # 立即持久化，避免下次仍为空
                self._save_config()
            # 确保目录存在并更新显示
            p = Path(self.output_dir).expanduser()
            p.mkdir(parents=True, exist_ok=True)
            display_text = str(p) if len(str(p)) <= 60 else (p.anchor + "…" + str(p)[-40:])
            self.output_dir_label.config(text=display_text, fg='black')
        except Exception:
            pass
    
    def _setup_ui(self):
        """设置改进的UI"""
        self._create_toolbar()
        self._create_notebook()
        self._create_statusbar()

    def _create_toolbar(self):
        """创建顶部工具栏，【新增 API Key 输入框】"""
        toolbar = tk.Frame(self.master, relief='raised', bd=1)
        toolbar.pack(side='top', fill='x', padx=5, pady=5)
        
        # --- 第一行：模型设置 ---
        model_frame = tk.Frame(toolbar)
        model_frame.pack(fill='x', padx=5, pady=2)

        tk.Label(model_frame, text="模型:").pack(side='left', padx=(0, 5))
        model_options = ['tiny', 'base', 'small', 'medium', 'large']
        ttk.Combobox(
            model_frame, 
            textvariable=self.model_name, 
            values=model_options, 
            width=10,
            state='readonly'
        ).pack(side='left', padx=5)
        
        self.model_status_label = tk.Label(
            model_frame, 
            text="● 模型未加载",
            fg='red',
            font=('Arial', 10, 'bold')
        )
        self.model_status_label.pack(side='left', padx=10)

        tk.Button(
            model_frame,
            text="⚙️ 加载模型",
            command=self.load_model,
            bg='#4CAF50',
            fg='white',
            padx=15
        ).pack(side='left', padx=5)

        # 新增：手动修复环境按钮（创建/升级 venv 并安装依赖）
        tk.Button(
            model_frame,
            text="🛠 修复环境",
            command=self.repair_environment,
            bg='#1976d2',
            fg='white',
            padx=15
        ).pack(side='left', padx=5)
        
        # --- 第二行：API Key 和 输出目录 ---
        config_frame = tk.Frame(toolbar)
        config_frame.pack(fill='x', padx=5, pady=5)
        
        # 左侧：API Key 输入 + API优先开关
        api_key_frame = tk.Frame(config_frame)
        api_key_frame.pack(side='left', padx=5)
        tk.Label(api_key_frame, text="DeepSeek API Key:").pack(side='left')
        self.api_key_entry = tk.Entry(
            api_key_frame,
            textvariable=self.api_key_var,
            width=50,
            show='*' # 隐藏密钥
        )
        self.api_key_entry.pack(side='left', padx=5)
        # 显示/隐藏密钥
        def _toggle_key():
            cur = self.api_key_entry.cget('show')
            self.api_key_entry.config(show='' if cur == '*' else '*')
            eye_btn.config(text='🙈' if cur == '' else '👁️')
        eye_btn = tk.Button(api_key_frame, text='👁️', command=_toggle_key)
        eye_btn.pack(side='left')

        # API 优先开关
        def _toggle_api_prefer():
            # Checkbutton 会自动切换变量，这里只记录日志并保存
            state = '开' if self.api_prefer_var.get() else '关'
            self.log(f"[设置] API优先：{state}")
            self._save_config()
        self.api_prefer_btn = tk.Checkbutton(
            api_key_frame,
            text='API优先',
            variable=self.api_prefer_var,
            command=_toggle_api_prefer
        )
        self.api_prefer_btn.pack(side='left', padx=(8,0))
        
        # 中间：翻译目标设置（全局）
        translate_frame = tk.Frame(config_frame)
        translate_frame.pack(side='left', padx=15)
        tk.Label(translate_frame, text="翻译成:").pack(side='left')
        translate_options = [
            ('自动', 'auto'),
            ('中文', 'zh'),
            ('英文', 'en'),
            ('自定义', 'custom')
        ]
        self.translate_mode_combo = ttk.Combobox(
            translate_frame,
            values=[t[0] for t in translate_options],
            state='readonly',
            width=8
        )
        # 同步组合框与内部值
        def _sync_mode_to_combo(*_):
            mapping = {'auto': '自动', 'zh': '中文', 'en': '英文', 'custom': '自定义'}
            self.translate_mode_combo.set(mapping.get(self.translate_target_mode.get(), '自动'))
        def _sync_combo_to_mode(event=None):
            reverse = {'自动': 'auto', '中文': 'zh', '英文': 'en', '自定义': 'custom'}
            self.translate_target_mode.set(reverse.get(self.translate_mode_combo.get(), 'auto'))
            self._save_config()
            _toggle_custom_entry()
        self.translate_target_mode.trace_add('write', lambda *_: _sync_mode_to_combo())
        self.translate_mode_combo.bind('<<ComboboxSelected>>', _sync_combo_to_mode)
        _sync_mode_to_combo()
        self.translate_mode_combo.pack(side='left', padx=5)
        # 自定义目标语言输入
        self.custom_lang_entry = tk.Entry(translate_frame, textvariable=self.translate_target_custom, width=10)
        self.custom_lang_entry.pack(side='left', padx=(5,0))
        def _toggle_custom_entry():
            state = 'normal' if self.translate_target_mode.get() == 'custom' else 'disabled'
            self.custom_lang_entry.config(state=state)
        _toggle_custom_entry()
        def _on_custom_change(*_):
            self._save_config()
        self.translate_target_custom.trace_add('write', _on_custom_change)

        # 右侧：输出目录（SRT保存路径）
        output_frame = tk.Frame(config_frame)
        output_frame.pack(side='right', padx=5)

        tk.Label(output_frame, text="SRT保存路径:").pack(side='left')
        self.output_dir_label = tk.Label(
            output_frame,
            text="未设置",
            fg='gray',
            width=30,
            anchor='w',
            relief='sunken',
            bd=1
        )
        self.output_dir_label.pack(side='left', padx=5)
        
        tk.Button(
            output_frame,
            text="📂 选择",
            command=self.select_output_dir
        ).pack(side='left')

        # 新增：快速打开输出目录按钮
        tk.Button(
            output_frame,
            text="🔎 打开",
            command=self.open_output_dir
        ).pack(side='left', padx=(5,0))

    def repair_environment(self):
        """手动修复运行环境：确保 whisper_env 存在并安装依赖。"""
        def _task():
            base_dir = os.path.dirname(os.path.abspath(__file__))
            venv_dir = os.path.join(base_dir, 'whisper_env')
            is_win = (sys.platform == 'win32')
            py_bin = os.path.join(venv_dir, 'Scripts' if is_win else 'bin', 'python.exe' if is_win else 'python3')
            pip_bin = os.path.join(venv_dir, 'Scripts' if is_win else 'bin', 'pip.exe' if is_win else 'pip')

            self.log("[环境] 开始修复/初始化虚拟环境...")
            try:
                # 创建虚拟环境（如果不存在）
                if not os.path.exists(os.path.join(venv_dir, 'pyvenv.cfg')):
                    self.log("[环境] 正在创建 whisper_env ...")
                    import venv
                    venv.create(venv_dir, with_pip=True)

                # 升级 pip 工具
                self.log("[环境] 升级 pip/setuptools/wheel ...")
                subprocess.run([py_bin, '-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'], check=False)

                # 安装依赖
                self.log("[环境] 安装依赖：openai-whisper, torch, pysrt, requests ...")
                reqs = ['openai-whisper', 'torch', 'pysrt', 'requests']
                install_proc = subprocess.run([pip_bin, 'install', *reqs], capture_output=True, text=True)
                if install_proc.returncode != 0:
                    self.log("[环境] 直接安装失败，尝试使用清华源加速...")
                    subprocess.run([pip_bin, 'install', '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple', *reqs], check=True)

                self.log("[环境] 修复完成。如非在虚拟环境中运行，请重新启动脚本。")
                messagebox.showinfo("修复完成", "环境修复完成。若当前不在虚拟环境内，建议重新运行脚本以生效。")
            except Exception as e:
                self.log(f"[环境] 修复失败: {e}")
                messagebox.showerror("修复失败", f"环境修复失败：{e}")

        threading.Thread(target=_task, daemon=True).start()

    def _create_notebook(self):
        """创建选项卡"""
        notebook = ttk.Notebook(self.master)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        tab1 = self._create_transcription_tab(notebook)
        notebook.add(tab1, text="  🎤 语音转字幕  ")
        
        tab2 = self._create_translation_tab(notebook)
        notebook.add(tab2, text="  🌐 字幕翻译  ")
        
        tab3 = self._create_storyboard_tab(notebook)
        notebook.add(tab3, text="  🎬 分镜生成  ")
        
        tab4 = self._create_log_tab(notebook)
        notebook.add(tab4, text="  📋 运行日志  ")

    def _create_transcription_tab(self, parent):
        """创建转录选项卡"""
        tab = tk.Frame(parent)

        # 顶部路径选择行（位于转录大按钮上方）
        path_row = tk.Frame(tab)
        path_row.pack(fill='x', padx=10, pady=(10, 0))
        tk.Label(path_row, text="SRT保存路径:").pack(side='left')
        self.output_dir_label_transcribe = tk.Label(
            path_row,
            text=self.output_dir if self.output_dir else "未设置",
            fg='black' if self.output_dir else 'gray',
            width=50,
            anchor='w',
            relief='sunken',
            bd=1
        )
        self.output_dir_label_transcribe.pack(side='left', padx=5)
        def _select_and_sync_output_dir_transcribe():
            self.select_output_dir()
            try:
                p = Path(self.output_dir).expanduser() if self.output_dir else None
                if p:
                    display_text = str(p) if len(str(p)) <= 70 else (p.anchor + "…" + str(p)[-55:])
                    self.output_dir_label_transcribe.config(text=display_text, fg='black')
                else:
                    self.output_dir_label_transcribe.config(text='未设置', fg='gray')
            except Exception:
                pass
        tk.Button(path_row, text="📂 选择", command=_select_and_sync_output_dir_transcribe).pack(side='left', padx=(5,0))
        tk.Button(path_row, text="🔎 打开", command=self.open_output_dir).pack(side='left', padx=(5,0))

        # 顶部大按钮区（更显眼的开始/仅选中按钮）
        header_actions = tk.Frame(tab)
        header_actions.pack(fill='x', padx=10, pady=(10, 0))
        
        self._btn_transcribe_start_big = tk.Button(
            header_actions,
            text="▶️ 开始转录",
            command=self.start_transcription_thread,
            bg='#2e7d32',
            fg='white',
            font=('Arial', 14, 'bold'),
            padx=36,
            pady=12
        )
        self._btn_transcribe_start_big.pack(side='left', padx=5)

        self._btn_transcribe_selected_big = tk.Button(
            header_actions,
            text="⏸️ 仅转录选中",
            command=lambda: self.start_transcription_thread(selected_only=True),
            font=('Arial', 12, 'bold'),
            padx=24,
            pady=10
        )
        self._btn_transcribe_selected_big.pack(side='left', padx=5)
        
        info = tk.LabelFrame(tab, text="操作步骤", padx=10, pady=10)
        info.pack(fill='x', padx=10, pady=10)
        
        steps = ["1️⃣ 点击'添加媒体文件'选择视频/音频", "2️⃣ 确认已加载模型（顶部绿色状态）", "3️⃣ 确认已设置输出目录", "4️⃣ 点击'开始转录'生成字幕文件"]
        for step in steps:
            tk.Label(info, text=step, anchor='w').pack(fill='x', pady=2)
        
        # 自动翻译设置（转录后处理）
        auto_frame = tk.LabelFrame(tab, text="转录后自动翻译", padx=10, pady=10)
        auto_frame.pack(fill='x', padx=10, pady=(0,10))
        tk.Label(auto_frame, text="开启自动翻译:").pack(side='left')
        self.auto_translate_combo = ttk.Combobox(
            auto_frame,
            values=['关闭', '中文', '英文', '跟随全局设置'],
            state='readonly',
            width=12
        )
        # 同步自动翻译选择
        def _sync_auto_to_combo(*_):
            mapping = {'off': '关闭', 'zh': '中文', 'en': '英文', 'follow': '跟随全局设置'}
            self.auto_translate_combo.set(mapping.get(self.auto_translate_mode.get(), '关闭'))
        def _sync_combo_to_auto(event=None):
            reverse = {'关闭': 'off', '中文': 'zh', '英文': 'en', '跟随全局设置': 'follow'}
            self.auto_translate_mode.set(reverse.get(self.auto_translate_combo.get(), 'off'))
            self._save_config()
        self.auto_translate_mode.trace_add('write', lambda *_: _sync_auto_to_combo())
        self.auto_translate_combo.bind('<<ComboboxSelected>>', _sync_combo_to_auto)
        _sync_auto_to_combo()
        self.auto_translate_combo.pack(side='left', padx=10)

        list_frame = tk.LabelFrame(tab, text="媒体文件列表", padx=10, pady=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        btn_row = tk.Frame(list_frame)
        btn_row.pack(fill='x', pady=(0, 10))
        
        tk.Button(
            btn_row,
            text="➕ 添加媒体文件",
            command=lambda: self.add_files('transcription'),
            bg='#2196F3',
            fg='white',
            padx=20
        ).pack(side='left', padx=5)
        
        tk.Button(
            btn_row,
            text="🗑️ 清空列表",
            command=lambda: self.clear_list('transcription')
        ).pack(side='left', padx=5)
        
        tk.Label(btn_row, text="文件数量:").pack(side='right', padx=5)
        self.trans_count_label = tk.Label(btn_row, text="0", fg='blue', font=('Arial', 10, 'bold'))
        self.trans_count_label.pack(side='right')
        
        list_container = tk.Frame(list_frame)
        list_container.pack(fill='both', expand=True)
        
        self.trans_listbox = tk.Listbox(list_container, selectmode=tk.EXTENDED)
        self.trans_listbox.pack(side='left', fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(list_container, command=self.trans_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.trans_listbox.config(yscrollcommand=scrollbar.set)
        
        options = tk.Frame(list_frame)
        options.pack(fill='x', pady=10)
        
        self.auto_translate_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            options,
            text="✨ 转录后自动生成中英双语字幕 (使用 Whisper translate 模式)",
            variable=self.auto_translate_var,
            font=('Arial', 10)
        ).pack(anchor='w')
        
        execute_frame = tk.Frame(list_frame)
        execute_frame.pack(fill='x', pady=10)
        
        self._btn_transcribe_start = tk.Button(
            execute_frame,
            text="▶️ 开始转录",
            command=self.start_transcription_thread,
            bg='#4CAF50',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=30,
            pady=10
        )
        self._btn_transcribe_start.pack(side='left', padx=5)
        
        self._btn_transcribe_selected = tk.Button(
            execute_frame,
            text="⏸️ 仅转录选中",
            command=lambda: self.start_transcription_thread(selected_only=True),
            padx=20,
            pady=10
        )
        self._btn_transcribe_selected.pack(side='left', padx=5)
        
        self.trans_progress = ttk.Progressbar(execute_frame, mode='determinate')
        self.trans_progress.pack(side='right', fill='x', expand=True, padx=10)
        
        return tab

    def _create_translation_tab(self, parent):
        """创建翻译选项卡"""
        tab = tk.Frame(parent)

        # 顶部大按钮区
        # 在翻译页内单独放置一个 SRT 保存路径选择行（位于翻译大按钮上方一行）
        path_row = tk.Frame(tab)
        path_row.pack(fill='x', padx=10, pady=(10, 0))
        tk.Label(path_row, text="SRT保存路径:").pack(side='left')
        self.output_dir_label_trans = tk.Label(
            path_row,
            text=self.output_dir if self.output_dir else "未设置",
            fg='black' if self.output_dir else 'gray',
            width=50,
            anchor='w',
            relief='sunken',
            bd=1
        )
        self.output_dir_label_trans.pack(side='left', padx=5)
        
        def _select_and_sync_output_dir():
            self.select_output_dir()
            # 同步翻译页标签显示
            try:
                p = Path(self.output_dir).expanduser() if self.output_dir else None
                if p:
                    display_text = str(p) if len(str(p)) <= 70 else (p.anchor + "…" + str(p)[-55:])
                    self.output_dir_label_trans.config(text=display_text, fg='black')
                else:
                    self.output_dir_label_trans.config(text='未设置', fg='gray')
            except Exception:
                pass
        tk.Button(path_row, text="📂 选择", command=_select_and_sync_output_dir).pack(side='left', padx=(5,0))
        tk.Button(path_row, text="🔎 打开", command=self.open_output_dir).pack(side='left', padx=(5,0))

        header_actions = tk.Frame(tab)
        header_actions.pack(fill='x', padx=10, pady=(10, 0))
        
        self._btn_translate_start_big = tk.Button(
            header_actions,
            text="▶️ 开始翻译",
            command=self.start_translation_thread,
            bg='#ef6c00',
            fg='white',
            font=('Arial', 14, 'bold'),
            padx=36,
            pady=12
        )
        self._btn_translate_start_big.pack(side='left', padx=5)

        self._btn_translate_selected_big = tk.Button(
            header_actions,
            text="⏸️ 仅翻译选中",
            command=lambda: self.start_translation_thread(selected_only=True),
            font=('Arial', 12, 'bold'),
            padx=24,
            pady=10
        )
        self._btn_translate_selected_big.pack(side='left', padx=5)
        
        info = tk.LabelFrame(tab, text="操作步骤", padx=10, pady=10)
        info.pack(fill='x', padx=10, pady=10)
        
        steps = [
            "1️⃣ 点击'添加字幕文件'选择 .srt 文件",
            "2️⃣ 顶部设置 DeepSeek API Key 与‘翻译成’目标（可自定义）",
            "3️⃣ 选择输出目录",
            "4️⃣ 点击'开始翻译'生成双语字幕"
        ]
        for step in steps:
            tk.Label(info, text=step, anchor='w').pack(fill='x', pady=2)
        
        list_frame = tk.LabelFrame(tab, text="字幕文件列表", padx=10, pady=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        btn_row = tk.Frame(list_frame)
        btn_row.pack(fill='x', pady=(0, 10))
        
        tk.Button(
            btn_row,
            text="➕ 添加字幕文件 (.srt)",
            command=lambda: self.add_files('translation'),
            bg='#2196F3',
            fg='white',
            padx=20
        ).pack(side='left', padx=5)
        
        tk.Button(
            btn_row,
            text="🗑️ 清空列表",
            command=lambda: self.clear_list('translation')
        ).pack(side='left', padx=5)
        
        tk.Label(btn_row, text="文件数量:").pack(side='right', padx=5)
        self.trans_srt_count_label = tk.Label(btn_row, text="0", fg='blue', font=('Arial', 10, 'bold'))
        self.trans_srt_count_label.pack(side='right')
        
        list_container = tk.Frame(list_frame)
        list_container.pack(fill='both', expand=True)
        
        self.translate_listbox = tk.Listbox(list_container, selectmode=tk.EXTENDED)
        self.translate_listbox.pack(side='left', fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(list_container, command=self.translate_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.translate_listbox.config(yscrollcommand=scrollbar.set)
        
        execute_frame = tk.Frame(list_frame)
        execute_frame.pack(fill='x', pady=10)
        
        self._btn_translate_start = tk.Button(
            execute_frame,
            text="▶️ 开始翻译",
            command=self.start_translation_thread,
            bg='#FF9800',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=30,
            pady=10
        )
        self._btn_translate_start.pack(side='left', padx=5)
        
        self._btn_translate_selected = tk.Button(
            execute_frame,
            text="⏸️ 仅翻译选中",
            command=lambda: self.start_translation_thread(selected_only=True),
            padx=20,
            pady=10
        )
        self._btn_translate_selected.pack(side='left', padx=5)
        
        self.translate_progress = ttk.Progressbar(execute_frame, mode='determinate')
        self.translate_progress.pack(side='right', fill='x', expand=True, padx=10)
        
        return tab

    def _create_storyboard_tab(self, parent):
        """创建分镜选项卡"""
        tab = tk.Frame(parent)

        # 顶部路径选择行（位于分镜大按钮上方）
        path_row = tk.Frame(tab)
        path_row.pack(fill='x', padx=10, pady=(10, 0))
        tk.Label(path_row, text="SRT保存路径:").pack(side='left')
        self.output_dir_label_story = tk.Label(
            path_row,
            text=self.output_dir if self.output_dir else "未设置",
            fg='black' if self.output_dir else 'gray',
            width=50,
            anchor='w',
            relief='sunken',
            bd=1
        )
        self.output_dir_label_story.pack(side='left', padx=5)
        def _select_and_sync_output_dir_story():
            self.select_output_dir()
            try:
                p = Path(self.output_dir).expanduser() if self.output_dir else None
                if p:
                    display_text = str(p) if len(str(p)) <= 70 else (p.anchor + "…" + str(p)[-55:])
                    self.output_dir_label_story.config(text=display_text, fg='black')
                else:
                    self.output_dir_label_story.config(text='未设置', fg='gray')
            except Exception:
                pass
        tk.Button(path_row, text="📂 选择", command=_select_and_sync_output_dir_story).pack(side='left', padx=(5,0))
        tk.Button(path_row, text="🔎 打开", command=self.open_output_dir).pack(side='left', padx=(5,0))

        # 顶部大按钮区
        header_actions = tk.Frame(tab)
        header_actions.pack(fill='x', padx=10, pady=(10, 0))
        
        self._btn_story_start_big = tk.Button(
            header_actions,
            text="🎬 生成并导出分镜",
            command=self.generate_storyboard_thread,
            bg='#6a1b9a',
            fg='white',
            font=('Arial', 14, 'bold'),
            padx=36,
            pady=12
        )
        self._btn_story_start_big.pack(side='left', padx=5)
        
        info = tk.LabelFrame(tab, text="操作步骤", padx=10, pady=10)
        info.pack(fill='x', padx=10, pady=10)
        
        steps = [
            "1️⃣ 添加字幕文件（.srt）",
            "2️⃣ 确认已在顶部输入 DeepSeek API Key",
            "3️⃣ 选择导出格式",
            "4️⃣ 生成并导出分镜 (使用 DeepSeek API 总结)"
        ]
        for step in steps:
            tk.Label(info, text=step, anchor='w').pack(fill='x', pady=2)
        
        list_frame = tk.LabelFrame(tab, text="字幕文件列表", padx=10, pady=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        btn_row = tk.Frame(list_frame)
        btn_row.pack(fill='x', pady=(0, 10))
        
        tk.Button(
            btn_row,
            text="➕ 添加字幕文件",
            command=lambda: self.add_files('storyboard'),
            bg='#2196F3',
            fg='white',
            padx=20
        ).pack(side='left', padx=5)
        
        tk.Button(
            btn_row,
            text="🗑️ 清空列表",
            command=lambda: self.clear_list('storyboard')
        ).pack(side='left', padx=5)
        
        tk.Label(btn_row, text="文件数量:").pack(side='right', padx=5)
        self.story_count_label = tk.Label(btn_row, text="0", fg='blue', font=('Arial', 10, 'bold'))
        self.story_count_label.pack(side='right')
        
        list_container = tk.Frame(list_frame)
        list_container.pack(fill='both', expand=True)
        
        self.storyboard_listbox = tk.Listbox(list_container, selectmode=tk.EXTENDED)
        self.storyboard_listbox.pack(side='left', fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(list_container, command=self.storyboard_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.storyboard_listbox.config(yscrollcommand=scrollbar.set)
        
        export_frame = tk.LabelFrame(list_frame, text="导出设置", padx=10, pady=10)
        export_frame.pack(fill='x', pady=10)
        
        self.export_format = tk.StringVar(value='json')
        tk.Radiobutton(
            export_frame,
            text="📄 JSON 格式（推荐，适合AI调用）",
            variable=self.export_format,
            value='json'
        ).pack(anchor='w', pady=2)
        
        tk.Radiobutton(
            export_frame,
            text="📊 CSV 格式（适合Excel编辑）",
            variable=self.export_format,
            value='csv'
        ).pack(anchor='w', pady=2)
        
        execute_frame = tk.Frame(list_frame)
        execute_frame.pack(fill='x', pady=10)
        
        self._btn_story_start = tk.Button(
            execute_frame,
            text="🎬 生成并导出分镜",
            command=self.generate_storyboard_thread,
            bg='#9C27B0',
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=30,
            pady=10
        )
        self._btn_story_start.pack(side='left', padx=5)
        
        self.story_progress = ttk.Progressbar(execute_frame, mode='determinate')
        self.story_progress.pack(side='right', fill='x', expand=True, padx=10)
        
        return tab

    def _create_log_tab(self, parent):
        """创建日志选项卡"""
        tab = tk.Frame(parent)
        
        toolbar = tk.Frame(tab)
        toolbar.pack(fill='x', padx=10, pady=5)
        
        tk.Button(toolbar, text="🗑️ 清空日志", command=self.clear_log).pack(side='left', padx=5)
        tk.Button(toolbar, text="💾 保存日志", command=self.save_log).pack(side='left', padx=5)
        
        log_container = tk.Frame(tab)
        log_container.pack(fill='both', expand=True, padx=10, pady=5)

        self.log_text = tk.Text(
            log_container,
            state='disabled',
            bg='#1e1e1e',
            fg='#d4d4d4',
            font=('Consolas', 9),
            wrap='none'
        )
        self.log_text.pack(side='left', fill='both', expand=True)

        log_scrollbar_y = tk.Scrollbar(log_container, command=self.log_text.yview)
        log_scrollbar_y.pack(side='right', fill='y')
        self.log_text.config(yscrollcommand=log_scrollbar_y.set)
        log_scrollbar_x = tk.Scrollbar(tab, orient='horizontal', command=self.log_text.xview)
        log_scrollbar_x.pack(fill='x', padx=10)
        self.log_text.config(xscrollcommand=log_scrollbar_x.set)
        # 复制全部按钮
        tk.Button(tab, text="📋 复制全部", command=lambda: (self.master.clipboard_clear(), self.master.clipboard_append(self.log_text.get('1.0','end')))).pack(anchor='e', padx=10, pady=(0,10))
        
        return tab

    def _create_statusbar(self):
        """创建状态栏"""
        statusbar = tk.Frame(self.master, relief='sunken', bd=1)
        statusbar.pack(side='bottom', fill='x')
        
        self.status_label = tk.Label(
            statusbar,
            text="就绪",
            anchor='w',
            padx=10
        )
        self.status_label.pack(side='left', fill='x', expand=True)
        
        tk.Label(
            statusbar,
            text="v2.2 (DeepSeek AI)",
            fg='gray',
            padx=10
        ).pack(side='right')

    # ========== 数据管理和设置 ==========

    def load_model(self):
        """加载 Whisper 模型"""
        if whisper is None:
            messagebox.showerror("错误", "缺少核心依赖！请运行: pip install openai-whisper torch pysrt")
            return
        
        self.log("▶️ 正在加载 Whisper 模型...")
        self.master.config(cursor="wait")
        model_name = self.model_name.get()

        def load_target():
            nonlocal model_name
            try:
                self.model = whisper.load_model(model_name)
                self.model_loaded = True
                self.model_status_label.config(text=f"● 模型已加载 ({model_name})", fg='green')
                self.log(f"✅ Whisper 模型 '{model_name}' 加载成功！")
                self.master.after(0, lambda: messagebox.showinfo("成功", f"模型 '{model_name}' 加载完成！"))
            except Exception as e:
                self.model_status_label.config(text="● 模型加载失败", fg='red')
                self.log(f"❌ 模型加载失败: {e}")
                self.master.after(0, lambda: messagebox.showerror("错误", f"模型加载失败: {e}"))
            finally:
                self.master.after(0, lambda: self.master.config(cursor=""))
        
        threading.Thread(target=load_target).start()

    def select_output_dir(self):
        """选择/创建输出目录（兼容中文/空格路径，自动校验与创建）。"""
        try:
            # 设置初始目录为当前目录或上次选择的目录
            initial_dir = self.output_dir if self.output_dir else os.getcwd()
            # 先尝试选择已存在目录；若用户想要新建，后续提供新建逻辑
            directory = filedialog.askdirectory(
                title="选择输出目录",
                mustexist=True,
                initialdir=initial_dir
            )
        except Exception as e:
            messagebox.showerror("错误", f"目录选择器出错：{e}")
            return
        if not directory:
            return  # 用户取消

        try:
            p = Path(directory).expanduser()
        except Exception as e:
            messagebox.showerror("路径错误", f"无法解析路径：{directory}\n{e}")
            return

        # 若目录不存在，提示是否创建
        if not p.exists():
            create = messagebox.askyesno("创建目录", f"目录不存在：\n{p}\n\n是否创建？")
            if not create:
                return
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showerror("创建失败", f"无法创建目录：{p}\n{e}")
                return
        elif not p.is_dir():
            messagebox.showerror("无效路径", f"不是目录：{p}")
            return

        # 写权限快速自检
        try:
            testfile = (p / ".whisper_write_test").resolve()
            testfile.write_text("ok", encoding="utf-8")
            try:
                testfile.unlink()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("无写入权限", f"该目录无法写入：{p}\n{e}")
            return

        # 成功：保存并更新显示（保持全路径以避免歧义）
        p = p.resolve()
        self.output_dir = str(p)
        display_text = str(p) if len(str(p)) <= 60 else (p.anchor + "…" + str(p)[-40:])
        self.output_dir_label.config(text=display_text, fg='black')
        self.log(f"输出目录: {p}")

        # 保存配置
        self._save_config()

    def open_output_dir(self):
        """在系统文件管理器中打开当前输出目录"""
        if not self.output_dir:
            messagebox.showwarning("提示", "请先选择输出目录。")
            return
        try:
            p = Path(self.output_dir)
            if not p.exists():
                messagebox.showerror("错误", f"输出目录不存在: {p}")
                return
            
            self.log(f"正在打开输出目录: {p}")
            
            # macOS 使用 'open'；Windows 使用 os.startfile；Linux 使用 xdg-open
            if os.name == 'nt':
                os.startfile(str(p))
            elif sys.platform == 'darwin':
                subprocess.run(["open", str(p)], check=True)
            else:
                subprocess.run(["xdg-open", str(p)], check=True)
                
            self.log(f"✅ 已打开输出目录: {p}")
        except Exception as e:
            error_msg = f"无法打开目录: {e}"
            self.log(f"❌ {error_msg}")
            messagebox.showerror("错误", error_msg)

    def add_files(self, tab_name):
        """添加文件到列表"""
        if tab_name == 'transcription':
            files = filedialog.askopenfilenames(title="选择媒体文件", filetypes=[("媒体文件", "*.mp4 *.mp3 *.wav *.m4a *.mov")])
            listbox = self.trans_listbox
            file_list = self.input_files_transcription
            count_label = self.trans_count_label
        elif tab_name == 'translation' or tab_name == 'storyboard':
            files = filedialog.askopenfilenames(title="选择字幕文件", filetypes=[("字幕文件", "*.srt")])
            listbox = self.translate_listbox if tab_name == 'translation' else self.storyboard_listbox
            file_list = self.input_files_translation if tab_name == 'translation' else self.input_files_storyboard
            count_label = self.trans_srt_count_label if tab_name == 'translation' else self.story_count_label
        else:
            return

        if files:
            for f in files:
                if f not in file_list:
                    listbox.insert('end', f)
                    file_list.append(f)
            count_label.config(text=str(len(file_list)))
            self.log(f"添加了 {len(files)} 个文件到 {tab_name} 列表")

    def clear_list(self, tab_name):
        """清空文件列表"""
        if tab_name == 'transcription':
            self.trans_listbox.delete(0, 'end')
            self.input_files_transcription = []
            self.trans_count_label.config(text="0")
        elif tab_name == 'translation':
            self.translate_listbox.delete(0, 'end')
            self.input_files_translation = []
            self.trans_srt_count_label.config(text="0")
        elif tab_name == 'storyboard':
            self.storyboard_listbox.delete(0, 'end')
            self.input_files_storyboard = []
            self.story_count_label.config(text="0")
        self.log(f"已清空 {tab_name} 列表")

    # ========== 配置持久化 ==========
    # 旧版配置读写实现已被统一版本替代
    
    # ========== 转录功能 ==========
    
    def start_transcription_thread(self, selected_only=False):
        """在独立线程中启动转录"""
        if not self.model_loaded:
            messagebox.showwarning("警告", "请先加载模型！")
            return
        if not self.output_dir:
            messagebox.showwarning("警告", "请先选择输出目录！")
            return

        file_list = []
        if selected_only:
            for i in self.trans_listbox.curselection():
                file_list.append(self.trans_listbox.get(i))
        else:
            file_list = self.input_files_transcription

        if not file_list:
            messagebox.showwarning("警告", "列表为空或未选中文件！")
            return
        
        self.log(f"▶️ 开始转录 {len(file_list)} 个文件...")
        self.master.config(cursor="wait")
        self.trans_progress.config(value=0, maximum=len(file_list))
        # 禁用按钮
        try:
            self._btn_transcribe_start.config(state=tk.DISABLED, text='正在转录…')
            self._btn_transcribe_selected.config(state=tk.DISABLED)
            self._btn_transcribe_start_big.config(state=tk.DISABLED, text='正在转录…')
            self._btn_transcribe_selected_big.config(state=tk.DISABLED)
        except Exception:
            pass
        threading.Thread(target=self._run_transcription, args=(file_list,)).start()

    def _run_transcription(self, file_list):
        """实际转录逻辑"""
        try:
            output_dir = Path(self.output_dir)
            # 确保输出目录存在
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log(f"❌ 无法创建输出目录: {e}")
            self.master.after(0, lambda: messagebox.showerror("错误", f"无法创建输出目录: {e}"))
            return
            
        auto_translate = self.auto_translate_var.get()
        
        for i, input_file in enumerate(file_list):
            try:
                p_in = Path(input_file)
                self._set_status(f"正在转录 {p_in.name}...")
                self.log(f"--- ({i+1}/{len(file_list)}) 开始处理: {p_in.name} ---")

                result = self.model.transcribe(str(p_in), verbose=False)
                
                language = result.get('language', '未知')
                self.log(f"识别到语言: {language.upper()}")
                
                srt_path_raw = output_dir / f"{p_in.stem}_{language.lower()}.srt"
                subtitles = self._segments_to_srt(result['segments'])
                subtitles.save(str(srt_path_raw), encoding='utf-8')
                self.log(f"✅ 原始字幕已保存: {srt_path_raw.name}")
                self.log(f"📂 可在此处找到: {srt_path_raw}")

                # 新自动翻译策略：依据自动翻译选择器
                auto_mode = self.auto_translate_mode.get()
                if auto_mode != 'off':
                    # 解析目标语言选择
                    if auto_mode == 'follow':
                        # 跟随全局设置
                        global_mode = self.translate_target_mode.get()
                        if global_mode == 'zh':
                            target = 'zh'
                        elif global_mode == 'en':
                            target = 'en'
                        elif global_mode == 'custom':
                            # Whisper 本地 translate 仅支持翻译到英文。自定义时退化为 API 翻译。
                            target = 'api'
                        else:
                            # auto: 若不是英文则翻译到英文
                            target = 'en'
                    else:
                        target = auto_mode  # zh/en

                    if target in ('zh', 'en'):
                        # Whisper 本地 translate 只能翻到英文。若目标为中文则走 API 生成双语。
                        if target == 'en':
                            if language.lower() != 'english':
                                self.log("🌐 自动翻译 -> 英文 (Whisper translate)")
                                translation_result = self.model.transcribe(str(p_in), task="translate", verbose=False)
                                srt_path_bilingual = output_dir / f"{p_in.stem}_BILINGUAL_WHISPER.srt"
                                bilingual_subs = self._create_bilingual_srt(subtitles, translation_result['segments'])
                                bilingual_subs.save(str(srt_path_bilingual), encoding='utf-8')
                                self.log(f"✅ 双语字幕 (Whisper) 已保存: {srt_path_bilingual.name}")
                                self.log(f"📂 可在此处找到: {srt_path_bilingual}")
                            else:
                                self.log("ℹ️ 源语言已是英文，跳过 Whisper 自动翻译。")
                        else:  # target == 'zh'
                            self.log("🌐 自动翻译 -> 中文 (使用 DeepSeek API)")
                            # 使用 API 逐句翻译为中文
                            subs_raw = subtitles
                            bilingual_subs = pysrt.SubRipFile()
                            for sub in subs_raw:
                                text_to_translate = sub.text.strip().replace('\n', ' ')
                                translated_text = self._deepseek_translate(text_to_translate, '中文') if text_to_translate else ''
                                new_text = f"{sub.text}\n{translated_text}"
                                bilingual_subs.append(pysrt.SubRipItem(sub.index, start=sub.start, end=sub.end, text=new_text))
                            srt_path_bilingual = output_dir / f"{p_in.stem}_BILINGUAL_API_ZH.srt"
                            bilingual_subs.save(str(srt_path_bilingual), encoding='utf-8')
                            self.log(f"✅ 双语字幕 (API->中文) 已保存: {srt_path_bilingual.name}")
                            self.log(f"📂 可在此处找到: {srt_path_bilingual}")
                    else:
                        # 自定义或跟随(自定义) -> 走 API
                        target_lang_name = (self.translate_target_custom.get() or '').strip() or '英文'
                        self.log(f"🌐 自动翻译 -> {target_lang_name} (使用 DeepSeek API)")
                        subs_raw = subtitles
                        bilingual_subs = pysrt.SubRipFile()
                        for sub in subs_raw:
                            text_to_translate = sub.text.strip().replace('\n', ' ')
                            translated_text = self._deepseek_translate(text_to_translate, target_lang_name) if text_to_translate else ''
                            new_text = f"{sub.text}\n{translated_text}"
                            bilingual_subs.append(pysrt.SubRipItem(sub.index, start=sub.start, end=sub.end, text=new_text))
                        safe_suffix = target_lang_name.replace('/', '_').replace('\\', '_')
                        srt_path_bilingual = output_dir / f"{p_in.stem}_BILINGUAL_API_{safe_suffix}.srt"
                        bilingual_subs.save(str(srt_path_bilingual), encoding='utf-8')
                        self.log(f"✅ 双语字幕 (API->{target_lang_name}) 已保存: {srt_path_bilingual.name}")
                        self.log(f"📂 可在此处找到: {srt_path_bilingual}")

            except Exception as e:
                self.log(f"❌ 处理文件 {p_in.name} 失败: {e}")

            self.trans_progress.config(value=i + 1)
        
        self.master.after(0, lambda: self.master.config(cursor=""))
        def _done():
            try:
                self._btn_transcribe_start.config(state=tk.NORMAL, text='▶️ 开始转录')
                self._btn_transcribe_selected.config(state=tk.NORMAL)
                self._btn_transcribe_start_big.config(state=tk.NORMAL, text='▶️ 开始转录')
                self._btn_transcribe_selected_big.config(state=tk.NORMAL)
            except Exception:
                pass
            self.log("🎉 所有转录任务完成！")
            messagebox.showinfo("完成", "所有转录和字幕生成任务已完成！")
        self.master.after(0, _done)

    def _segments_to_srt(self, segments):
        """将 Whisper segments 转换为 pysrt 对象"""
        subs = pysrt.SubRipFile()
        for i, segment in enumerate(segments):
            start_time = self._format_time(segment['start'])
            end_time = self._format_time(segment['end'])
            sub = pysrt.SubRipItem(i + 1, start=start_time, end=end_time, text=segment['text'].strip())
            subs.append(sub)
        return subs
    
    def _format_time(self, time_s):
        """格式化时间（秒）为 SRT 格式"""
        time_obj = datetime.datetime.fromtimestamp(time_s) - datetime.datetime.fromtimestamp(0)
        minutes, seconds = divmod(time_obj.seconds, 60)
        hours, minutes = divmod(minutes, 60)
        ms = time_obj.microseconds // 1000
        return pysrt.SubRipTime(hours=hours, minutes=minutes, seconds=seconds, milliseconds=ms)

    def _create_bilingual_srt(self, subs_raw, segments_translated):
        """合并原始和翻译字幕为双语 SRT"""
        if len(subs_raw) != len(segments_translated):
             self.log("⚠️ 原始字幕和翻译字幕段落数量不匹配，可能导致合并错位！")
        
        bilingual_subs = pysrt.SubRipFile()
        for i, sub in enumerate(subs_raw):
            try:
                translated_text = segments_translated[i]['text'].strip()
                new_text = f"{sub.text}\n{translated_text}"
                new_sub = pysrt.SubRipItem(sub.index, start=sub.start, end=sub.end, text=new_text)
                bilingual_subs.append(new_sub)
            except IndexError:
                 bilingual_subs.append(sub)
        
        return bilingual_subs

    # ========== 翻译功能 (使用 DeepSeek API) ==========

    def _deepseek_api_call(self, system_prompt, user_prompt):
        """调用 DeepSeek Chat API 的通用方法"""
        # 【核心修改】从 UI 变量中获取 API Key
        api_key = self.api_key_var.get().strip()
        if not api_key:
            self.log("❌ 错误: DeepSeek API Key 为空。请在顶部输入框填写 Key。")
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": self.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False
        }
        
        try:
            response = requests.post(self.DEEPSEEK_API_BASE, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            if 'choices' in data and data['choices']:
                return data['choices'][0]['message']['content'].strip()
            return None

        except requests.exceptions.HTTPError as e:
            self.log(f"❌ DeepSeek API HTTP 错误: {e}. Status: {response.status_code}. Response: {response.text[:100]}...")
            return None
        except requests.exceptions.RequestException as e:
            self.log(f"❌ DeepSeek API 请求失败: {e}")
            return None
        except Exception as e:
            self.log(f"❌ DeepSeek API 解析/未知错误: {e}")
            return None

    def _deepseek_translate(self, text, target_lang):
        """使用 DeepSeek API 翻译文本"""
        
        system_prompt = f"你是一个专业的字幕翻译员，请将用户提供的文本翻译成{target_lang}。只返回翻译后的文本，不要添加任何解释、标签或额外内容。"
        user_prompt = f"请翻译以下字幕文本：\n\n{text}"
        
        translated_text = self._deepseek_api_call(system_prompt, user_prompt)
        
        return translated_text if translated_text else f"[翻译失败]"

    def start_translation_thread(self, selected_only=False):
        """在独立线程中启动翻译"""
        if not self.api_key_var.get().strip():
            messagebox.showwarning("警告", "请先在顶部输入 DeepSeek API Key！")
            return
        if not self.output_dir:
            messagebox.showwarning("警告", "请先选择输出目录！")
            return
        
        file_list = []
        if selected_only:
            for i in self.translate_listbox.curselection():
                file_list.append(self.translate_listbox.get(i))
        else:
            file_list = self.input_files_translation

        if not file_list:
            messagebox.showwarning("警告", "列表为空或未选中文件！")
            return
        
        mode = 'API' if self.api_prefer_var.get() else '本地(占位)'
        self.log(f"▶️ 开始翻译 {len(file_list)} 个字幕文件 (优先模式: {mode})")
        self.master.config(cursor="wait")
        self.translate_progress.config(value=0, maximum=len(file_list))
        try:
            self._btn_translate_start.config(state=tk.DISABLED, text='正在翻译…')
            self._btn_translate_selected.config(state=tk.DISABLED)
            # 同步禁用顶部大按钮
            self._btn_translate_start_big.config(state=tk.DISABLED, text='正在翻译…')
            self._btn_translate_selected_big.config(state=tk.DISABLED)
        except Exception:
            pass
        threading.Thread(target=self._run_translation, args=(file_list,)).start()

    def _run_translation(self, file_list):
        """实际翻译逻辑 (在线程中运行)"""
        try:
            output_dir = Path(self.output_dir)
            # 确保输出目录存在
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log(f"❌ 无法创建输出目录: {e}")
            self.master.after(0, lambda: messagebox.showerror("错误", f"无法创建输出目录: {e}"))
            return
        
        for i, input_file in enumerate(file_list):
            try:
                p_in = Path(input_file)
                self._set_status(f"正在翻译 {p_in.name}...")
                self.log(f"--- ({i+1}/{len(file_list)}) 开始翻译: {p_in.name} ---")

                # 1. 读取字幕文件
                subs_raw = pysrt.open(str(p_in), encoding='utf-8')
                
                # 2. 确定翻译目标语言（尊重全局选择器）
                mode = self.translate_target_mode.get()
                if mode == 'auto':
                    is_chinese = any('\u4e00' <= char <= '\u9fff' for sub in subs_raw for char in sub.text)
                    target_lang = "英文" if is_chinese else "中文"
                    source_lang = "中文" if is_chinese else "英文"
                elif mode == 'zh':
                    target_lang = "中文"
                    # 简单估计源语言用于日志
                    is_chinese = any('\u4e00' <= char <= '\u9fff' for sub in subs_raw for char in sub.text)
                    source_lang = "中文" if is_chinese else "非中文"
                elif mode == 'en':
                    target_lang = "英文"
                    is_chinese = any('\u4e00' <= char <= '\u9fff' for sub in subs_raw for char in sub.text)
                    source_lang = "中文" if is_chinese else "非中文"
                else:  # custom
                    custom = (self.translate_target_custom.get() or '').strip()
                    target_lang = custom if custom else "英文"
                    is_chinese = any('\u4e00' <= char <= '\u9fff' for sub in subs_raw for char in sub.text)
                    source_lang = "中文" if is_chinese else "非中文"
                
                translated_subs = pysrt.SubRipFile()
                
                self.log(f"🌐 源语言估计: {source_lang}，翻译目标: {target_lang}")
                
                # 3. 逐句翻译：按优先模式决定
                for sub in subs_raw:
                    # 去除空行，避免 API 浪费
                    text_to_translate = sub.text.strip().replace('\n', ' ')
                    if not text_to_translate:
                        translated_text = ""
                    else:
                        if self.api_prefer_var.get():
                            translated_text = self._deepseek_translate(text_to_translate, target_lang)
                        else:
                            # 预留：本地翻译逻辑（当前占位为原文回填）
                            translated_text = text_to_translate
                        
                    # 4. 创建新的双语字幕条目
                    new_text = f"{sub.text}\n{translated_text}"
                    translated_sub = pysrt.SubRipItem(sub.index, start=sub.start, end=sub.end, text=new_text)
                    translated_subs.append(translated_sub)
                    
                    self._set_status(f"正在翻译 {p_in.name}: 第 {sub.index} 句")

                # 5. 保存翻译后的双语字幕
                suffix = 'DeepSeek' if self.api_prefer_var.get() else 'Local'
                output_path = output_dir / f"{p_in.stem}_Bilingual_{suffix}.srt"
                translated_subs.save(str(output_path), encoding='utf-8')
                self.log(f"✅ 双语字幕已保存: {output_path.name}")
                self.log(f"📂 可在此处找到: {output_path}")

            except Exception as e:
                self.log(f"❌ 翻译文件 {p_in.name} 失败: {e}")

            self.translate_progress.config(value=i + 1)
        
        self.master.after(0, lambda: self.master.config(cursor=""))
        def _done():
            try:
                self._btn_translate_start.config(state=tk.NORMAL, text='▶️ 开始翻译')
                self._btn_translate_selected.config(state=tk.NORMAL)
                self._btn_translate_start_big.config(state=tk.NORMAL, text='▶️ 开始翻译')
                self._btn_translate_selected_big.config(state=tk.NORMAL)
            except Exception:
                pass
            self.log("🎉 所有翻译任务完成！")
            messagebox.showinfo("完成", "所有字幕翻译任务已完成！")
        self.master.after(0, _done)

    # ========== 分镜功能 (使用 DeepSeek API) ==========

    def _deepseek_summarize_and_prompt(self, subtitle_text_batch):
        """使用 DeepSeek API 总结文本并生成 AI Prompt"""
        
        system_prompt = (
            "你是一位专业的视频编辑和 AI 艺术提示词（Prompt）设计师。你将接收一段字幕文本，"
            "你的任务是：1. 总结这段文本的**核心内容/场景**。 2. 基于总结，为 AI 视频或图片生成工具设计一个**电影级（Cinematic）Prompt**。 "
            "请严格以 **JSON 格式**输出，结构如下：{\"summary\": \"...\", \"ai_prompt\": \"...\"}。确保输出内容只有 JSON 对象。"
        )
        user_prompt = f"请处理以下字幕文本：\n\n---\n{subtitle_text_batch}\n---"
        
        try:
            result = self._deepseek_api_call(system_prompt, user_prompt)
            if result:
                # 尝试解析 JSON (去除可能存在的Markdown代码块标记)
                result = result.strip().strip('`').strip()
                if result.startswith('json'):
                    result = result[4:].strip()
                return json.loads(result)
            return None
        except json.JSONDecodeError:
            self.log(f"❌ 分镜生成 API 返回结果不是有效 JSON。尝试移除代码块标记后解析失败。")
            return None

    def generate_storyboard_thread(self):
        """在独立线程中启动分镜生成"""
        if not self.api_key_var.get().strip():
            messagebox.showwarning("警告", "请先在顶部输入 DeepSeek API Key！")
            return
        if not self.output_dir:
            messagebox.showwarning("警告", "请先选择输出目录！")
            return

        file_list = self.input_files_storyboard
        if not file_list:
            messagebox.showwarning("警告", "列表为空！请添加字幕文件。")
            return

        fmt = self.export_format.get()
        self.log(f"▶️ 开始生成分镜脚本 ({fmt.upper()} 格式，使用 DeepSeek AI)...")
        self.master.config(cursor="wait")
        self.story_progress.config(value=0, maximum=len(file_list))
        try:
            self._btn_story_start.config(state=tk.DISABLED, text='正在生成…')
            self._btn_story_start_big.config(state=tk.DISABLED, text='正在生成…')
        except Exception:
            pass
        threading.Thread(target=self._run_storyboard_generation, args=(file_list, fmt)).start()

    def _run_storyboard_generation(self, file_list, export_format):
        """实际分镜生成逻辑 (在线程中运行)"""
        try:
            output_dir = Path(self.output_dir)
            # 确保输出目录存在
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log(f"❌ 无法创建输出目录: {e}")
            self.master.after(0, lambda: messagebox.showerror("错误", f"无法创建输出目录: {e}"))
            return
        
        # 设定字幕合并批次大小
        BATCH_SIZE = 10 
        
        for i, input_file in enumerate(file_list):
            try:
                p_in = Path(input_file)
                self._set_status(f"正在生成分镜 {p_in.name}...")
                self.log(f"--- ({i+1}/{len(file_list)}) 开始生成分镜: {p_in.name} ---")

                subs = pysrt.open(str(p_in), encoding='utf-8')
                storyboard_data = []
                
                # 按批次进行总结和提示词生成
                for j in range(0, len(subs), BATCH_SIZE):
                    batch = subs[j:j + BATCH_SIZE]
                    
                    # 拼接字幕文本
                    subtitle_text_batch = "\n".join([sub.text.strip().replace('\n', ' ') for sub in batch])
                    
                    self.log(f"正在分析第 {j//BATCH_SIZE + 1} 个批次 (共 {len(batch)} 句)...")
                    
                    # 调用 DeepSeek API
                    ai_result = self._deepseek_summarize_and_prompt(subtitle_text_batch)
                    
                    if ai_result:
                        # 使用批次的第一句作为时间锚点
                        first_sub = batch[0]
                        last_sub = batch[-1]
                        
                        storyboard_item = {
                            "scene_id": j // BATCH_SIZE + 1,
                            "timestamp_start": first_sub.start.to_time().strftime("%H:%M:%S.%f")[:-3],
                            "timestamp_end": last_sub.end.to_time().strftime("%H:%M:%S.%f")[:-3],
                            "text_summary": ai_result.get("summary", "N/A"),
                            "ai_prompt_suggestion": ai_result.get("ai_prompt", "N/A"),
                            "duration_sec": last_sub.end.total_seconds() - first_sub.start.total_seconds()
                        }
                        storyboard_data.append(storyboard_item)

                    self._set_status(f"分镜生成中 {p_in.name}: 完成 {j + len(batch)} 句")


                # 导出文件
                # 修复 with_suffix 误用，改为安全拼接
                if export_format == 'json':
                    output_path = output_dir / f"{p_in.stem}_DeepSeek_Storyboard.json"
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(storyboard_data, f, ensure_ascii=False, indent=4)
                elif export_format == 'csv':
                    output_path = output_dir / f"{p_in.stem}_DeepSeek_Storyboard.csv"
                    if storyboard_data:
                        fieldnames = storyboard_data[0].keys()
                        with open(output_path, 'w', encoding='utf-8', newline='') as f:
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                            writer.writerows(storyboard_data)
                
                self.log(f"✅ 分镜脚本已保存: {output_path.name} ({len(storyboard_data)}个场景)")
                self.log(f"📂 可在此处找到: {output_path}")

            except Exception as e:
                self.log(f"❌ 分镜生成失败: {e}")

            self.story_progress.config(value=i + 1)

        self.master.after(0, lambda: self.master.config(cursor=""))
        def _done():
            try:
                self._btn_story_start.config(state=tk.NORMAL, text='🎬 生成并导出分镜')
                self._btn_story_start_big.config(state=tk.NORMAL, text='🎬 生成并导出分镜')
            except Exception:
                pass
            self.log("🎉 所有分镜生成任务完成！")
            messagebox.showinfo("完成", "所有分镜脚本已生成！")
        self.master.after(0, _done)
    
    # ========== 日志和状态方法 ==========

    def log(self, message):
        """添加日志（线程安全）"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        def _do():
            self.log_text.config(state='normal')
            self.log_text.insert('end', f"[{timestamp}] {message}\n")
            self.log_text.see('end')
            self.log_text.config(state='disabled')
            # 状态栏颜色
            color = 'gray'
            if any(k in message for k in ("开始", "正在", "处理中")):
                color = '#2980b9'
            if any(k in message for k in ("完成", "成功", "已保存")):
                color = '#27ae60'
            if any(k in message for k in ("部分",)):
                color = '#e67e22'
            if any(k in message for k in ("失败", "错误", "❌")):
                color = '#c0392b'
            self.status_label.config(text=message, fg=color)
        self.master.after(0, _do)
    
    def clear_log(self):
        """清空日志"""
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')
        self.log("日志已清空")
    
    def save_log(self):
        """保存日志"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt")]
        )
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get('1.0', 'end'))
                self.master.after(0, lambda: messagebox.showinfo("成功", "日志已保存"))
                self.log(f"日志已保存到: {Path(filepath).name}")
            except Exception as e:
                self.master.after(0, lambda: messagebox.showerror("错误", f"保存日志失败: {e}"))

    def _set_status(self, text):
        """更新状态栏 (线程安全)"""
        def _do():
            color = 'gray'
            if any(k in text for k in ("开始", "正在", "处理中", "转录中", "翻译", "生成")):
                color = '#2980b9'
            if any(k in text for k in ("完成", "成功")):
                color = '#27ae60'
            if any(k in text for k in ("部分",)):
                color = '#e67e22'
            if any(k in text for k in ("失败", "错误")):
                color = '#c0392b'
            self.status_label.config(text="状态: " + text, fg=color)
        # 使用 after(0) 确保在主线程更新 UI
        self.master.after(0, _do)

    # ========== 配置的加载与保存 ==========
    def _load_config(self):
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                self.output_dir = cfg.get('output_dir', self.output_dir)
                self.api_prefer_var.set(cfg.get('api_prefer', self.api_prefer_var.get()))
                self.api_key_var.set(cfg.get('api_key', self.api_key_var.get()))
                self.translate_target_mode.set(cfg.get('translate_target_mode', self.translate_target_mode.get()))
                self.translate_target_custom.set(cfg.get('translate_target_custom', self.translate_target_custom.get()))
                self.auto_translate_mode.set(cfg.get('auto_translate_mode', self.auto_translate_mode.get()))
        except Exception as e:
            self.log(f"⚠️ 加载配置失败: {e}")

    def _save_config(self):
        try:
            cfg = {
                'output_dir': self.output_dir,
                'api_prefer': self.api_prefer_var.get(),
                'api_key': self.api_key_var.get(),
                'translate_target_mode': self.translate_target_mode.get(),
                'translate_target_custom': self.translate_target_custom.get(),
                'auto_translate_mode': self.auto_translate_mode.get()
            }
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"⚠️ 保存配置失败: {e}")
        
# 主程序
if __name__ == "__main__":
    if whisper is None or pysrt is None:
        print("警告：缺少核心依赖 (whisper, torch, pysrt)。转录功能将受限。")
        print("请运行: pip install openai-whisper torch pysrt requests")
    
    root = tk.Tk()
    app = ImprovedWhisperUI(root)
    root.mainloop()
