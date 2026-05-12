import sys
import os
import subprocess
import shutil
import json
import ctypes
import webbrowser
import math
import tempfile
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, QTimer
from PyQt5.QtWidgets import QSizePolicy

APP_VERSION = "V5.2"
APP_TITLE = f"多功能圖片影音製作器-影像、音樂與轉場自由搭配{APP_VERSION} (Made by 阿剛老師)"


class FFmpegError(RuntimeError):
    pass


if getattr(sys, 'frozen', False):
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ['PATH']


def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def add_internal_binary_paths():
    candidate_dirs = [
        get_resource_path(os.path.join("ffmpeg", "bin")),
        get_resource_path("ffmpeg"),
        get_resource_path("."),
    ]
    existing_dirs = [path for path in candidate_dirs if os.path.isdir(path)]
    if existing_dirs:
        os.environ["PATH"] = os.pathsep.join(existing_dirs + [os.environ.get("PATH", "")])


def hidden_subprocess_kwargs():
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def run_media_command(cmd):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **hidden_subprocess_kwargs(),
    )


add_internal_binary_paths()


def get_media_duration(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        result = run_media_command(cmd)
        if result.returncode != 0:
            return None
        duration = float(result.stdout.strip())
        return duration
    except Exception:
        return None


def get_video_dimensions(file_path):
    """取得影片或圖片的寬度與高度"""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", file_path
        ]
        result = run_media_command(cmd)
        if result.returncode == 0:
            dims = result.stdout.strip().split('x')
            if len(dims) == 2:
                return int(dims[0]), int(dims[1])
    except Exception:
        pass
    return None, None


def ceil_seconds(duration, default=1):
    try:
        return max(1, int(math.ceil(float(duration))))
    except Exception:
        return default


def run_ffmpeg(cmd, description):
    result = run_media_command(cmd)
    if result.returncode != 0:
        error_text = (result.stderr or result.stdout or "").strip()
        if len(error_text) > 2000:
            error_text = error_text[-2000:]
        raise FFmpegError(f"{description}失敗。\n\n指令：{' '.join(cmd)}\n\n錯誤訊息：\n{error_text}")
    return result


def concat_file_line(file_path):
    safe_path = os.path.abspath(file_path).replace("\\", "/").replace("'", "\\'")
    return f"file '{safe_path}'\n"


def ffmpeg_filter_escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace(",", "\\,")
        .replace("%", "\\%")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def get_subtitle_font_path():
    # 優先使用粗體字型，確保字幕清晰可讀
    candidates = [
        get_resource_path(os.path.join("fonts", "NotoSansTC-Bold.ttf")),   # 打包進 exe 的 Bold 靜態版（若有）
        get_resource_path(os.path.join("fonts", "NotoSansTC-Bold.otf")),
        r"C:\Windows\Fonts\msjhbd.ttc",                                     # 微軟正黑體 Bold（Windows 內建）
        get_resource_path(os.path.join("fonts", "NotoSansTC-VF.ttf")),     # 可變字型 fallback
        r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\mingliu.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[3]  # 預設回傳可變字型路徑


def build_video_filter(width, height, add_subtitle=False, subtitle_text="", subtitle_color="white", fontsize="20", position="bottom", show_box=False, box_color="black", box_opacity=0.5):
    filter_chain = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    if add_subtitle and subtitle_text:
        font_path = get_subtitle_font_path().replace("\\", "/")
        if len(font_path) > 1 and font_path[1] == ':':
            font_path = font_path[0] + '\\:' + font_path[2:]
        
        if position == "center":
            y_pos = "(h-text_h)/2"
        else:
            y_pos = "h-(text_h*2)"
            
        box_str = ""
        if show_box:
            # 使用小數點表示透明度 (0.0 ~ 1.0)，這是 ffmpeg 最通用的寫法
            box_str = f":box=1:boxcolor={box_color}@{box_opacity}:boxborderw=5"

        filter_chain += (
            f",drawtext=fontfile='{font_path}':text='{ffmpeg_filter_escape(subtitle_text)}':"
            f"fontcolor={subtitle_color}:fontsize={fontsize}:borderw=2:bordercolor=black:"
            f"x=(w-text_w)/2:y={y_pos}{box_str}"
        )
    return filter_chain


def media_has_audio(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type", "-of", "csv=p=0", file_path
        ]
        result = run_media_command(cmd)
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def get_temp_dir():
    base_dir = os.getcwd()
    temp_dir = os.path.join(base_dir, "temp")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    return temp_dir


def format_time(seconds):
    """將秒數格式化為 mm:ss.t"""
    seconds = max(0.0, float(seconds))
    m = int(seconds) // 60
    s = int(seconds) % 60
    t = int((seconds - int(seconds)) * 10)
    return f"{m:02d}:{s:02d}.{t}"



# ===============================
# 帶時間軸的預覽播放視窗
# ===============================
class VideoPreviewPlayer(QtWidgets.QDialog):
    """
    獨立的影片預覽播放視窗，帶有可拖曳的時間軸。
    使用 ffplay 播放；拖動時間軸時會重新從指定位置開始播放。
    關閉時可選擇把目前播放位置設為起點或終點（回傳給 VideoEditDialog）。
    """

    # 回傳信號：(action, seconds)
    # action: "start" / "end" / None
    set_position = QtCore.pyqtSignal(str, float)

    def __init__(self, file_path, play_start, play_end, total_duration, parent=None):
        super().__init__(parent, QtCore.Qt.Window)
        self.file_path       = file_path
        self.play_start      = play_start      # 裁切起點
        self.play_end        = play_end        # 裁切終點
        self.total_duration  = total_duration
        self._ffplay_proc    = None
        self._playing        = False
        self._cur_pos        = play_start      # 目前播放位置（秒）
        self._play_start_sec = play_start
        self._play_start_wall = None           # 系統時間戳
        self._slider_dragging = False

        self.setWindowTitle(f"▶ 預覽播放 — {os.path.basename(file_path)}")
        self.setMinimumSize(680, 120)
        self.resize(720, 140)

        # ── UI ──────────────────────────────────────────────────────────
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)

        # 時間軸滑桿
        slider_row = QtWidgets.QHBoxLayout()
        self.lbl_cur = QtWidgets.QLabel(format_time(play_start))
        self.lbl_cur.setMinimumWidth(65)
        self.lbl_cur.setStyleSheet("font-weight:bold; font-size:13px;")
        slider_row.addWidget(self.lbl_cur)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(max(1, int(total_duration * 10)))
        self.slider.setValue(int(play_start * 10))
        self.slider.setToolTip("拖曳可跳至指定位置重新播放")
        slider_row.addWidget(self.slider, stretch=1)

        self.lbl_end = QtWidgets.QLabel(format_time(total_duration))
        self.lbl_end.setMinimumWidth(65)
        self.lbl_end.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        slider_row.addWidget(self.lbl_end)
        layout.addLayout(slider_row)

        # 進度條（純顯示用，不可互動）
        self.progress = QtWidgets.QProgressBar()
        self.progress.setMaximum(max(1, int((play_end - play_start) * 100)))
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        layout.addWidget(self.progress)

        # 按鈕列
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_play = QtWidgets.QPushButton("▶ 播放")
        self.btn_play.setStyleSheet("background:#2d6fa5; color:white; font-weight:bold; padding:6px 14px;")
        
        self.btn_pause = QtWidgets.QPushButton("⏸ 暫停")
        self.btn_pause.setEnabled(False)
        
        self.btn_stop = QtWidgets.QPushButton("⏹ 停止")
        self.btn_stop.setEnabled(False)

        self.btn_set_start = QtWidgets.QPushButton("⬅ 設為起點")
        self.btn_set_end   = QtWidgets.QPushButton("設為終點 ➡")
        btn_close = QtWidgets.QPushButton("✖ 關閉")

        btn_row.addWidget(self.btn_play)
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_stop)
        btn_row.addSpacing(20)
        btn_row.addWidget(self.btn_set_start)
        btn_row.addWidget(self.btn_set_end)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        # ── 計時器 ──────────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._on_tick)

        # ── 視窗同步計時器（用於將 ffplay 視窗貼合在此視窗上方） ────────
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(15)
        self._sync_timer.timeout.connect(self._sync_ffplay_window)
        self._ffplay_title = ""

        # ── 連接 ────────────────────────────────────────────────────────
        self.btn_play.clicked.connect(self._do_play)
        self.btn_pause.clicked.connect(self._do_pause)
        self.btn_stop.clicked.connect(self._do_stop)
        self.btn_set_start.clicked.connect(self._emit_start)
        self.btn_set_end.clicked.connect(self._emit_end)
        btn_close.clicked.connect(self.close)

        self.slider.sliderPressed.connect(self._on_slider_press)
        self.slider.sliderReleased.connect(self._on_slider_release)
        self.slider.valueChanged.connect(self._on_slider_value)

        # 開啟後自動播放
        QtCore.QTimer.singleShot(100, self._do_play)

    # ── 播放控制 ─────────────────────────────────────────────────────────
    def _do_play(self, from_pos=None):
        """從 from_pos（秒）開始播放；None 表示從目前位置"""
        self._kill_ffplay()
        import time as _time
        start = from_pos if from_pos is not None else self._cur_pos
        start = max(self.play_start, min(start, self.play_end - 0.1))
        duration = self.play_end - start
        if duration <= 0:
            return

        self._ffplay_title = f"▶ 預覽_{id(self)}_{start}"
        cmd = [
            "ffplay",
            "-noborder",    # 隱藏邊框，方便貼合
            "-ss",          f"{start:.3f}",
            "-t",           f"{duration:.3f}",
            "-x",           "640",
            "-y",           "360",
            "-window_title", self._ffplay_title,
            "-autoexit",
            self.file_path
        ]
        try:
            self._ffplay_proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._play_start_sec  = start
            self._play_start_wall = _time.time()
            self._playing = True
            self.btn_play.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self._timer.start()
            self._sync_timer.start() # 開始同步視窗位置
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "播放失敗", str(e))

    def _do_pause(self):
        """暫停播放：停止 ffplay 但保留目前的播放位置"""
        self._kill_ffplay()
        self._timer.stop()
        self._sync_timer.stop()
        self._playing = False
        self.btn_play.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def _do_stop(self):
        """停止播放：停止 ffplay 並回到裁切起點"""
        self._kill_ffplay()
        self._timer.stop()
        self._sync_timer.stop()
        self._playing = False
        self._cur_pos = self.play_start
        self._update_slider_display(self._cur_pos)
        self.btn_play.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)

    def _kill_ffplay(self):
        self._sync_timer.stop()
        if self._ffplay_proc and self._ffplay_proc.poll() is None:
            try:
                self._ffplay_proc.terminate()
            except Exception:
                pass
        self._ffplay_proc = None

    def _sync_ffplay_window(self):
        """利用 Windows API 將 ffplay 視窗強制定位在此視窗上方"""
        if os.name != "nt":
            return
        
        hwnd = ctypes.windll.user32.FindWindowW(None, self._ffplay_title)
        if hwnd:
            # 計算貼合位置：在控制視窗的正上方，水平置中
            rect = self.frameGeometry()
            dlg_x = rect.x()
            dlg_y = rect.y()
            dlg_w = rect.width()
            
            ff_w = 640
            ff_h = 360
            ff_x = dlg_x + (dlg_w - ff_w) // 2
            ff_y = dlg_y - ff_h
            
            # 如果上方超出螢幕，則貼在頂部
            if ff_y < 0:
                ff_y = 0
            
            # SWP_NOZORDER=0x0004, SWP_SHOWWINDOW=0x0040
            ctypes.windll.user32.SetWindowPos(hwnd, 0, ff_x, ff_y, ff_w, ff_h, 0x0004 | 0x0040)

    def showEvent(self, event):
        """顯示時確保視窗下方有足夠空間顯示控制列，上方留給影片"""
        super().showEvent(event)
        # 如果視窗太靠上，自動往下移動 360 像素
        if self.y() < 360:
            self.move(self.x(), self.y() + 360)

    # ── 計時器 tick ──────────────────────────────────────────────────────
    def _on_tick(self):
        import time as _time
        if not self._playing:
            self._timer.stop()
            self._sync_timer.stop()
            return

        # 偵測 ffplay 是否結束
        if self._ffplay_proc and self._ffplay_proc.poll() is not None:
            self._ffplay_proc = None
            self._playing = False
            self._timer.stop()
            self._sync_timer.stop()
            self._cur_pos = self.play_end
            self.btn_play.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self._update_slider_display(self.play_end)
            return

        elapsed = _time.time() - (self._play_start_wall or _time.time())
        pos = min(self._play_start_sec + elapsed, self.play_end)
        self._cur_pos = pos
        if not self._slider_dragging:
            self._update_slider_display(pos)

    def _update_slider_display(self, pos):
        self.lbl_cur.setText(format_time(pos))
        self.slider.blockSignals(True)
        self.slider.setValue(int(pos * 10))
        self.slider.blockSignals(False)
        elapsed_in_clip = max(0, pos - self.play_start)
        self.progress.setValue(int(elapsed_in_clip * 100))

    # ── 滑桿互動 ─────────────────────────────────────────────────────────
    def _on_slider_press(self):
        self._slider_dragging = True

    def _on_slider_value(self, val):
        t = val / 10.0
        self.lbl_cur.setText(format_time(t))

    def _on_slider_release(self):
        self._slider_dragging = False
        new_pos = self.slider.value() / 10.0
        self._cur_pos = new_pos
        # 重新從此位置播放
        self._do_play(from_pos=new_pos)

    # ── 設為起點 / 終點 ──────────────────────────────────────────────────
    def _emit_start(self):
        self.set_position.emit("start", self._cur_pos)
        QtWidgets.QMessageBox.information(
            self, "已設定", f"已將 {format_time(self._cur_pos)} 設為起點。"
        )

    def _emit_end(self):
        self.set_position.emit("end", self._cur_pos)
        QtWidgets.QMessageBox.information(
            self, "已設定", f"已將 {format_time(self._cur_pos)} 設為終點。"
        )

    # ── 關閉時清理 ────────────────────────────────────────────────────────
    def closeEvent(self, event):
        self._kill_ffplay()
        self._timer.stop()
        event.accept()

# ===============================
# 影片編輯對話框（雙擊影片後開啟）
# ===============================
class VideoEditDialog(QtWidgets.QDialog):
    """
    雙擊影片清單項目後開啟的剪輯對話框。
    使用 ffmpeg 抽幀顯示畫面（避免 DirectShow 黑畫面問題），
    用 ffplay 開啟外部視窗播放預覽。

    功能：
      - 拖曳「預覽位置」滑桿 → 即時抽幀顯示該秒畫面
      - 按「▶ ffplay 播放預覽」→ 外部視窗播放指定裁切區間
      - 拖曳起點/終點滑桿設定裁切區間
      - 拖曳分割點滑桿 + 按「確認分割」→ 分割成兩段
    """

    def __init__(self, file_path, trim_start=0.0, trim_end=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.total_duration = get_media_duration(file_path) or 1.0
        self.trim_start = max(0.0, trim_start)
        self.trim_end = trim_end if trim_end is not None else self.total_duration
        self.trim_end = min(self.trim_end, self.total_duration)
        self.split_time = None
        self._frame_tmp = None
        self._preview_sec = self.trim_start

        # 防抖 timer：滑桿停止移動後 300ms 才抽幀
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._extract_and_show_frame)

        self.setWindowTitle(f"影片剪輯 — {os.path.basename(file_path)}")
        self.setMinimumSize(820, 660)
        self._build_ui()
        self._connect_signals()
        # 開啟時先顯示起點畫面
        self._extract_and_show_frame()

    # ------------------------------------------------------------------
    # UI 建構
    # ------------------------------------------------------------------
    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(8)

        # ── 幀預覽 + 右側說明欄 ──────────────────────────────────
        preview_outer = QtWidgets.QHBoxLayout()

        self.frame_label = QtWidgets.QLabel()
        self.frame_label.setFixedSize(560, 315)
        self.frame_label.setStyleSheet("background:#111; border:1px solid #555;")
        self.frame_label.setAlignment(QtCore.Qt.AlignCenter)
        self.frame_label.setText("載入畫面中…")
        preview_outer.addWidget(self.frame_label)

        info_col = QtWidgets.QVBoxLayout()
        info_col.setSpacing(10)

        self.lbl_preview_time = QtWidgets.QLabel(f"預覽：{format_time(self._preview_sec)}")
        self.lbl_preview_time.setStyleSheet("font-size:14px; font-weight:bold;")
        info_col.addWidget(self.lbl_preview_time)

        self.lbl_total = QtWidgets.QLabel(f"總長：{format_time(self.total_duration)}")
        self.lbl_total.setStyleSheet("color:#555;")
        info_col.addWidget(self.lbl_total)

        info_col.addSpacing(8)
        lbl_hint = QtWidgets.QLabel(
            "拖曳下方「預覽位置」滑桿\n"
            "可即時查看該時間點畫面。\n\n"
            "按「▶ 播放預覽」會開啟\n"
            "一個帶有時間軸的播放視窗。\n\n"
            "您可以在播放視窗中拖曳\n"
            "進度，或將目前播放位置\n"
            "直接設為起點/終點。\n\n"
            "每個滑桿旁的\n「← 設為預覽位置」\n"
            "可快速把目前預覽幀\n設為起點/終點/分割點。"
        )
        lbl_hint.setStyleSheet("color:#444; font-size:12px;")
        lbl_hint.setWordWrap(True)
        info_col.addWidget(lbl_hint)
        info_col.addStretch()

        self.btn_ffplay = QtWidgets.QPushButton("▶ 播放預覽")
        self.btn_ffplay.setStyleSheet(
            "background:#2d6fa5; color:white; font-weight:bold; padding:8px;"
        )
        self.btn_ffplay.clicked.connect(self._on_ffplay)
        info_col.addWidget(self.btn_ffplay)

        preview_outer.addLayout(info_col)
        main_layout.addLayout(preview_outer)

        # ── 預覽位置滑桿 ────────────────────────────────────────────
        seek_box = QtWidgets.QGroupBox("📍 預覽位置（拖曳可即時查看畫面）")
        seek_layout = QtWidgets.QHBoxLayout(seek_box)
        self.seek_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.seek_slider.setMinimum(0)
        self.seek_slider.setMaximum(max(1, int(self.total_duration * 10)))
        self.seek_slider.setValue(int(self._preview_sec * 10))
        self.seek_slider.setToolTip("拖曳可預覽該時間點的畫面")
        seek_layout.addWidget(self.seek_slider)
        self.lbl_seek_time = QtWidgets.QLabel(format_time(self._preview_sec))
        self.lbl_seek_time.setMinimumWidth(65)
        seek_layout.addWidget(self.lbl_seek_time)
        main_layout.addWidget(seek_box)

        # ── 起點 / 終點 ────────────────────────────────────────────
        trim_box = QtWidgets.QGroupBox("✂ 設定裁切區間（起點 / 終點）")
        trim_layout = QtWidgets.QVBoxLayout(trim_box)

        # 起點
        start_row = QtWidgets.QHBoxLayout()
        start_row.addWidget(QtWidgets.QLabel("起點："))
        self.start_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.start_slider.setMinimum(0)
        self.start_slider.setMaximum(max(1, int(self.total_duration * 10)))
        self.start_slider.setValue(int(self.trim_start * 10))
        start_row.addWidget(self.start_slider, stretch=1)
        self.lbl_start = QtWidgets.QLabel(format_time(self.trim_start))
        self.lbl_start.setMinimumWidth(65)
        start_row.addWidget(self.lbl_start)
        btn_set_start = QtWidgets.QPushButton("← 設為預覽位置")
        btn_set_start.clicked.connect(self._set_start_to_preview)
        start_row.addWidget(btn_set_start)
        trim_layout.addLayout(start_row)

        # 終點
        end_row = QtWidgets.QHBoxLayout()
        end_row.addWidget(QtWidgets.QLabel("終點："))
        self.end_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.end_slider.setMinimum(0)
        self.end_slider.setMaximum(max(1, int(self.total_duration * 10)))
        self.end_slider.setValue(int(self.trim_end * 10))
        end_row.addWidget(self.end_slider, stretch=1)
        self.lbl_end = QtWidgets.QLabel(format_time(self.trim_end))
        self.lbl_end.setMinimumWidth(65)
        end_row.addWidget(self.lbl_end)
        btn_set_end = QtWidgets.QPushButton("← 設為預覽位置")
        btn_set_end.clicked.connect(self._set_end_to_preview)
        end_row.addWidget(btn_set_end)
        trim_layout.addLayout(end_row)

        main_layout.addWidget(trim_box)

        # ── 分割區 ─────────────────────────────────────────────────
        split_box = QtWidgets.QGroupBox("✂ 分割影片（分成兩段）")
        split_layout = QtWidgets.QVBoxLayout(split_box)

        split_row = QtWidgets.QHBoxLayout()
        split_row.addWidget(QtWidgets.QLabel("分割點："))
        self.split_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.split_slider.setMinimum(0)
        self.split_slider.setMaximum(max(1, int(self.total_duration * 10)))
        self.split_slider.setValue(max(1, int(self.total_duration * 10 / 2)))
        split_row.addWidget(self.split_slider, stretch=1)
        self.lbl_split = QtWidgets.QLabel(format_time(self.total_duration / 2))
        self.lbl_split.setMinimumWidth(65)
        split_row.addWidget(self.lbl_split)
        btn_set_split = QtWidgets.QPushButton("← 設為預覽位置")
        btn_set_split.clicked.connect(self._set_split_to_preview)
        split_row.addWidget(btn_set_split)
        split_layout.addLayout(split_row)

        split_hint = QtWidgets.QLabel(
            "按下「確認分割」後，影片將在此時間點被分割成兩段並自動加入清單。"
        )
        split_hint.setStyleSheet("color:#555; font-size:12px;")
        split_layout.addWidget(split_hint)

        self.btn_split_confirm = QtWidgets.QPushButton("✂ 確認分割（分成兩段）")
        self.btn_split_confirm.setStyleSheet(
            "background-color:#c87020; color:white; font-weight:bold; padding:6px;"
        )
        self.btn_split_confirm.clicked.connect(self._on_split_confirm)
        split_layout.addWidget(self.btn_split_confirm)

        main_layout.addWidget(split_box)

        # ── 底部按鈕 ───────────────────────────────────────────────
        bottom_row = QtWidgets.QHBoxLayout()
        self.btn_ok = QtWidgets.QPushButton("✔ 套用裁切設定")
        self.btn_ok.setStyleSheet(
            "background-color:#2d6fa5; color:white; font-weight:bold; padding:8px 16px;"
        )
        self.btn_cancel = QtWidgets.QPushButton("✖ 取消")
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_ok)
        bottom_row.addWidget(self.btn_cancel)
        main_layout.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # 信號連接
    # ------------------------------------------------------------------
    def _connect_signals(self):
        self.seek_slider.valueChanged.connect(self._on_seek_changed)
        self.start_slider.valueChanged.connect(self._on_start_changed)
        self.end_slider.valueChanged.connect(self._on_end_changed)
        self.split_slider.valueChanged.connect(self._on_split_changed)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    # ------------------------------------------------------------------
    # 幀預覽（ffmpeg 抽幀）
    # ------------------------------------------------------------------
    def _on_seek_changed(self, val):
        t = val / 10.0
        self._preview_sec = t
        self.lbl_seek_time.setText(format_time(t))
        self.lbl_preview_time.setText(f"預覽：{format_time(t)}")
        self._debounce_timer.start()

    def _extract_and_show_frame(self):
        sec = self._preview_sec
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png")
        os.close(tmp_fd)
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{sec:.3f}",
            "-i", self.file_path,
            "-frames:v", "1",
            "-q:v", "2",
            tmp_path
        ]
        try:
            result = run_media_command(cmd)
            if result.returncode == 0 and os.path.exists(tmp_path):
                pix = QtGui.QPixmap(tmp_path)
                if not pix.isNull():
                    pix = pix.scaled(
                        self.frame_label.width(),
                        self.frame_label.height(),
                        QtCore.Qt.KeepAspectRatio,
                        QtCore.Qt.SmoothTransformation
                    )
                    self.frame_label.setPixmap(pix)
                else:
                    self.frame_label.setText("無法顯示畫面")
            else:
                self.frame_label.setText("抽幀失敗")
        except Exception as e:
            self.frame_label.setText(f"錯誤：{e}")
        finally:
            if self._frame_tmp and os.path.exists(self._frame_tmp):
                try:
                    os.remove(self._frame_tmp)
                except Exception:
                    pass
            self._frame_tmp = tmp_path

    # ------------------------------------------------------------------
    # ffplay 內嵌播放
    # ------------------------------------------------------------------
    def _on_ffplay(self):
        """開啟帶時間軸的獨立預覽播放視窗"""
        if self.trim_end - self.trim_start <= 0:
            QtWidgets.QMessageBox.warning(self, "警告", "裁切區間長度為 0，請調整起點/終點。")
            return
        dlg = VideoPreviewPlayer(
            self.file_path,
            play_start=self.trim_start,
            play_end=self.trim_end,
            total_duration=self.total_duration,
            parent=self
        )
        def _on_set_pos(action, sec):
            if action == "start":
                self.start_slider.setValue(int(sec * 10))
            elif action == "end":
                self.end_slider.setValue(int(sec * 10))
        dlg.set_position.connect(_on_set_pos)
        dlg.show()   # 非阻塞，讓兩個視窗可同時操作

    def _on_start_changed(self, val):
        t = val / 10.0
        if t >= self.trim_end:
            t = max(0.0, self.trim_end - 0.1)
            self.start_slider.blockSignals(True)
            self.start_slider.setValue(int(t * 10))
            self.start_slider.blockSignals(False)
        self.trim_start = t
        self.lbl_start.setText(format_time(t))

    def _on_end_changed(self, val):
        t = val / 10.0
        if t <= self.trim_start:
            t = min(self.total_duration, self.trim_start + 0.1)
            self.end_slider.blockSignals(True)
            self.end_slider.setValue(int(t * 10))
            self.end_slider.blockSignals(False)
        self.trim_end = t
        self.lbl_end.setText(format_time(t))

    def _set_start_to_preview(self):
        self.start_slider.setValue(int(self._preview_sec * 10))

    def _set_end_to_preview(self):
        self.end_slider.setValue(int(self._preview_sec * 10))

    # ------------------------------------------------------------------
    # 分割
    # ------------------------------------------------------------------
    def _on_split_changed(self, val):
        t = val / 10.0
        self.lbl_split.setText(format_time(t))

    def _set_split_to_preview(self):
        self.split_slider.setValue(int(self._preview_sec * 10))

    def _on_split_confirm(self):
        t = self.split_slider.value() / 10.0
        if t <= 0.5 or t >= self.total_duration - 0.5:
            QtWidgets.QMessageBox.warning(
                self, "分割失敗",
                "分割點距影片頭尾至少需要 0.5 秒，請重新選擇。"
            )
            return
        self.split_time = t
        self.accept()

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self._debounce_timer.stop()
        if self._frame_tmp and os.path.exists(self._frame_tmp):
            try:
                os.remove(self._frame_tmp)
            except Exception:
                pass
        super().closeEvent(event)

    def get_result(self):
        return self.trim_start, self.trim_end, self.split_time


# ===============================
# 自訂圖片/影片項目 Widget
# ===============================
class ImageItemWidget(QtWidgets.QWidget):
    removeRequested = QtCore.pyqtSignal()
    audioUploaded = QtCore.pyqtSignal()

    def __init__(self, file_path, default_duration=5, mainwindow=None,
                 trim_start=0.0, trim_end=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.image_audio_path = None
        self.mainwindow = mainwindow
        self.manual_subtitle = ""

        ext = os.path.splitext(file_path)[1].lower()
        video_exts = ['.mp4', '.avi', '.mov', '.mkv']
        if ext in video_exts:
            self.is_video = True
            raw_duration = get_media_duration(file_path) or default_duration
        else:
            self.is_video = False
            raw_duration = default_duration

        self.raw_video_duration = raw_duration if self.is_video else None

        self.trim_start = trim_start
        self.trim_end = trim_end if trim_end is not None else raw_duration

        if self.is_video:
            effective = self.trim_end - self.trim_start
            self.base_duration = ceil_seconds(effective, default_duration)
        else:
            self.base_duration = ceil_seconds(raw_duration, default_duration)
        self.duration = self.base_duration

        # ── 版面 ──────────────────────────────────────────────────
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # 預覽縮圖
        preview_container = QtWidgets.QWidget()
        preview_container.setFixedSize(80, 60)
        stack_layout = QtWidgets.QStackedLayout(preview_container)
        stack_layout.setStackingMode(QtWidgets.QStackedLayout.StackAll)

        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setFixedSize(80, 60)
        pixmap = QtGui.QPixmap(file_path)
        if pixmap.isNull():
            pixmap = QtGui.QPixmap(80, 60)
            pixmap.fill(QtGui.QColor("black"))
            painter = QtGui.QPainter(pixmap)
            painter.setPen(QtCore.Qt.white)
            painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, "影片")
            painter.end()
        else:
            pixmap = pixmap.scaled(80, 60, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        stack_layout.addWidget(self.preview_label)

        self.seq_label = QtWidgets.QLabel("")
        self.seq_label.setStyleSheet(
            "color: white; background-color: rgba(0,0,0,0.5); font-weight: bold; padding:2px;"
        )
        self.seq_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        stack_layout.addWidget(self.seq_label)
        self.seq_label.raise_()

        if self.is_video:
            self.video_badge = QtWidgets.QLabel("🎬")
            self.video_badge.setStyleSheet(
                "color: white; background-color: rgba(0,0,120,0.7); font-size:16px; padding:1px;"
            )
            self.video_badge.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
            stack_layout.addWidget(self.video_badge)
            self.video_badge.raise_()

        main_layout.addWidget(preview_container)

        # 資訊區
        info_layout = QtWidgets.QVBoxLayout()
        short_name = os.path.basename(file_path)[:15]
        self.file_label = QtWidgets.QLabel(short_name)
        self.file_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.file_label)

        if self.is_video:
            self.trim_info_label = QtWidgets.QLabel(self._trim_info_text())
            self.trim_info_label.setStyleSheet("color:#2266cc; font-size:11px;")
            info_layout.addWidget(self.trim_info_label)
            hint = QtWidgets.QLabel("（連點兩下可剪輯）")
            hint.setStyleSheet("color:#888; font-size:11px;")
            info_layout.addWidget(hint)

        # 持續時間
        duration_layout = QtWidgets.QHBoxLayout()
        duration_layout.addWidget(QtWidgets.QLabel("持續時間："))
        self.spinBox = QtWidgets.QSpinBox()
        self.spinBox.setMinimum(1)
        self.spinBox.setMaximum(3600)
        self.spinBox.setValue(self.duration)
        self.spinBox.setSuffix(" 秒")
        duration_layout.addWidget(self.spinBox)
        info_layout.addLayout(duration_layout)
        self.spinBox.valueChanged.connect(lambda v: setattr(self, 'duration', v))

        # 上傳音訊 / 字幕
        audio_layout = QtWidgets.QHBoxLayout()
        self.btn_upload_audio = QtWidgets.QPushButton("🔊 上傳音訊")
        self.btn_upload_audio.clicked.connect(self.toggleAudio)
        audio_layout.addWidget(self.btn_upload_audio)
        self.audio_label = QtWidgets.QLabel("")
        self.subtitle_edit = QtWidgets.QLineEdit()
        self.subtitle_edit.setPlaceholderText("請輸入字幕文字")
        self.subtitle_edit.editingFinished.connect(self.onSubtitleEditingFinished)
        
        # 個別字幕設定：位置與大小
        self.lbl_item_pos = QtWidgets.QLabel("位置:")
        self.combo_item_pos = QtWidgets.QComboBox()
        self.combo_item_pos.addItems(["下方", "畫面中央"])
        self.combo_item_pos.setFixedWidth(80)
        
        self.lbl_item_size = QtWidgets.QLabel("大小:")
        self.spin_item_size = QtWidgets.QSpinBox()
        self.spin_item_size.setRange(10, 500)
        self.spin_item_size.setFixedWidth(60)

        # 初始化時繼承主視窗目前的設定
        if self.mainwindow:
            self.combo_item_pos.setCurrentText(self.mainwindow.combobox_subtitle_pos.currentText())
            self.spin_item_size.setValue(self.mainwindow.spinbox_fontsize.value())
        else:
            self.spin_item_size.setValue(70)

        audio_layout.addWidget(self.audio_label)
        audio_layout.addWidget(self.subtitle_edit)
        audio_layout.addWidget(self.lbl_item_pos)
        audio_layout.addWidget(self.combo_item_pos)
        audio_layout.addWidget(self.lbl_item_size)
        audio_layout.addWidget(self.spin_item_size)
        
        audio_layout.addStretch()
        info_layout.addLayout(audio_layout)
        self.audio_label.setVisible(False)
        self.subtitle_edit.setVisible(False)
        self.lbl_item_pos.setVisible(False)
        self.combo_item_pos.setVisible(False)
        self.lbl_item_size.setVisible(False)
        self.spin_item_size.setVisible(False)

        if self.is_video:
            self.btn_upload_audio.setDisabled(True)
            self.btn_upload_audio.setText("影片不支援")
            self.spinBox.setDisabled(True)

        main_layout.addLayout(info_layout)
        main_layout.addStretch()

        self.btn_remove = QtWidgets.QPushButton("🗑️")
        self.btn_remove.setObjectName("dangerButton")
        self.btn_remove.clicked.connect(self.requestRemoval)
        main_layout.addWidget(self.btn_remove)

        self.updateSubtitleDisplay()

    def _trim_info_text(self):
        if self.is_video:
            return f"裁切：{format_time(self.trim_start)} ～ {format_time(self.trim_end)}"
        return ""

    def update_trim_info(self):
        if self.is_video and hasattr(self, 'trim_info_label'):
            self.trim_info_label.setText(self._trim_info_text())

    def updateSubtitleDisplay(self):
        show_sub = False
        if self.image_audio_path:
            self.audio_label.setText(os.path.basename(self.image_audio_path))
            self.audio_label.setVisible(True)
            self.subtitle_edit.setVisible(False)
            show_sub = True
        else:
            if self.mainwindow and self.mainwindow.checkbox_subtitle.isChecked():
                self.audio_label.setVisible(False)
                self.subtitle_edit.setVisible(True)
                show_sub = True
            else:
                self.audio_label.setVisible(False)
                self.subtitle_edit.setVisible(False)
                show_sub = False
        
        # 同步顯示/隱藏位置與大小設定
        self.lbl_item_pos.setVisible(show_sub)
        self.combo_item_pos.setVisible(show_sub)
        self.lbl_item_size.setVisible(show_sub)
        self.spin_item_size.setVisible(show_sub)

    def onSubtitleEditingFinished(self):
        self.manual_subtitle = self.subtitle_edit.text().strip()

    def toggleAudio(self):
        if self.image_audio_path:
            self.removeAudio()
        else:
            self.uploadAudio()
        self.updateSubtitleDisplay()

    def uploadAudio(self):
        fd = QtWidgets.QFileDialog(self, "選擇圖片專屬音訊檔", "", "Audio Files (*.mp3 *.wav *.ogg)")
        fd.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        if fd.exec_():
            audio_file = fd.selectedFiles()[0]
            duration = get_media_duration(audio_file)
            if duration is None:
                QtWidgets.QMessageBox.warning(self, "錯誤", "無法取得音訊長度！")
                return
            self.base_duration = ceil_seconds(duration)
            effective_duration = (
                self.base_duration + 1
                if self.mainwindow and self.mainwindow.combo_transition.currentText() != "無轉場"
                else self.base_duration
            )
            self.spinBox.setValue(effective_duration)
            self.image_audio_path = audio_file
            self.btn_upload_audio.setText("❌ ")
            self.spinBox.setDisabled(True)
            self.audioUploaded.emit()
            self.updateSubtitleDisplay()

    def removeAudio(self):
        self.image_audio_path = None
        self.spinBox.setValue(self.base_duration)
        self.spinBox.setDisabled(False)
        self.btn_upload_audio.setText("🔊 上傳音訊")
        self.audioUploaded.emit()
        self.updateSubtitleDisplay()

    def requestRemoval(self):
        self.removeRequested.emit()


# ===============================
# 自訂背景音樂項目 Widget
# ===============================
class MusicItemWidget(QtWidgets.QWidget):
    removeRequested = QtCore.pyqtSignal()

    def __init__(self, music_path, parent=None):
        super().__init__(parent)
        self.music_path = music_path
        self.music_length = get_media_duration(music_path) or 0
        self.total_seconds = ceil_seconds(self.music_length) if self.music_length > 0 else 1
        layout = QtWidgets.QVBoxLayout(self)
        top_layout = QtWidgets.QHBoxLayout()
        short_name = os.path.basename(music_path)[:15]
        self.label = QtWidgets.QLabel(short_name)
        top_layout.addWidget(self.label)
        self.total_label = QtWidgets.QLabel(f"總長：{self.total_seconds} 秒")
        self.total_label.setObjectName("metaLabel")
        top_layout.addWidget(self.total_label)
        top_layout.addStretch()
        self.btn_remove = QtWidgets.QPushButton("🗑️")
        self.btn_remove.setObjectName("dangerButton")
        self.btn_remove.clicked.connect(self.requestRemoval)
        top_layout.addWidget(self.btn_remove)
        layout.addLayout(top_layout)

        interval_layout = QtWidgets.QHBoxLayout()
        interval_layout.addWidget(QtWidgets.QLabel("起始秒數："))
        self.startSpin = QtWidgets.QSpinBox()
        self.startSpin.setMinimum(0)
        self.startSpin.setMaximum(max(0, self.total_seconds - 1))
        self.startSpin.setValue(0)
        self.startSpin.setSuffix(" 秒")
        interval_layout.addWidget(self.startSpin)
        interval_layout.addWidget(QtWidgets.QLabel("結束秒數："))
        self.endSpin = QtWidgets.QSpinBox()
        self.endSpin.setMinimum(1)
        self.endSpin.setMaximum(self.total_seconds)
        self.endSpin.setValue(self.total_seconds)
        self.endSpin.setSuffix(" 秒")
        interval_layout.addWidget(self.endSpin)
        self.btn_preview = QtWidgets.QPushButton("▶️ 試聽")
        self.btn_preview.clicked.connect(self.previewSegment)
        interval_layout.addWidget(self.btn_preview)
        self.btn_stop = QtWidgets.QPushButton("⏹️ 停止")
        self.btn_stop.clicked.connect(self.stopSegment)
        interval_layout.addWidget(self.btn_stop)
        layout.addLayout(interval_layout)

        self.startSpin.valueChanged.connect(lambda v: self.endSpin.setMinimum(v + 1))
        self.player = QMediaPlayer(self)

    def previewSegment(self):
        start_sec = self.startSpin.value()
        end_sec = self.endSpin.value()
        duration_ms = (end_sec - start_sec) * 1000
        url = QUrl.fromLocalFile(self.music_path)
        self.player.setMedia(QMediaContent(url))
        self.player.setPosition(start_sec * 1000)
        self.player.play()
        QTimer.singleShot(duration_ms, self.player.pause)

    def stopSegment(self):
        self.player.stop()

    def requestRemoval(self):
        self.removeRequested.emit()


# ===============================
# 支援滾動的訊息對話框
# ===============================
def showScrollableMessage(title, message, parent=None):
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(title)
    layout = QtWidgets.QVBoxLayout(dlg)
    text_edit = QtWidgets.QTextEdit()
    text_edit.setReadOnly(True)
    text_edit.setText(message)
    layout.addWidget(text_edit)
    btn = QtWidgets.QPushButton("確定")
    btn.clicked.connect(dlg.accept)
    layout.addWidget(btn)
    dlg.resize(400, 300)
    dlg.exec_()


# ===============================
# 主視窗
# ===============================
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        icon_path = get_resource_path("ico.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))
        self.resize(1150, 720)
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        if not self.check_ffmpeg():
            sys.exit(1)
        self.initUI()
        self.applyStyles()
        self.checkbox_subtitle.stateChanged.connect(self.onSubtitleCheckboxChanged)

    def _on_subtitle_pos_changed(self):
        new_pos = self.combobox_subtitle_pos.currentText()
        if new_pos == "畫面中央":
            new_size = 200
        else:
            new_size = 70
        
        self.spinbox_fontsize.blockSignals(True)
        self.spinbox_fontsize.setValue(new_size)
        self.spinbox_fontsize.blockSignals(False)

        # 一次全設定：更新所有清單項目的位置與大小
        for i in range(self.imageListWidget.count()):
            widget = self.imageListWidget.itemWidget(self.imageListWidget.item(i))
            if widget:
                widget.combo_item_pos.setCurrentText(new_pos)
                widget.spin_item_size.setValue(new_size)

    def _on_global_fontsize_changed(self, val):
        # 一次全設定：更新所有清單項目的字體大小
        for i in range(self.imageListWidget.count()):
            widget = self.imageListWidget.itemWidget(self.imageListWidget.item(i))
            if widget:
                widget.spin_item_size.setValue(val)

    def onSubtitleCheckboxChanged(self):
        for i in range(self.imageListWidget.count()):
            widget = self.imageListWidget.itemWidget(self.imageListWidget.item(i))
            if widget:
                widget.updateSubtitleDisplay()

    def initUI(self):
        top_button_layout = QtWidgets.QHBoxLayout()
        self.btn_new = QtWidgets.QPushButton("🆕 開啟新檔")
        self.btn_new.clicked.connect(self.newProject)
        top_button_layout.addWidget(self.btn_new)

        self.btn_open = QtWidgets.QPushButton("📂 開啟舊檔")
        self.btn_open.clicked.connect(self.openProject)
        top_button_layout.addWidget(self.btn_open)

        self.btn_save = QtWidgets.QPushButton("💾 另存新檔")
        self.btn_save.clicked.connect(self.saveProject)
        top_button_layout.addWidget(self.btn_save)
        top_button_layout.addStretch()

        main_layout = QtWidgets.QVBoxLayout(self.central_widget)
        main_layout.addLayout(top_button_layout)

        media_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(media_layout, 4)
        output_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(output_layout, 1)

        image_group = QtWidgets.QGroupBox("圖片/影片設定（影片可連點兩下剪輯）")
        image_layout = QtWidgets.QVBoxLayout(image_group)

        all_duration_layout = QtWidgets.QHBoxLayout()
        all_duration_layout.addWidget(QtWidgets.QLabel("設定全部(僅適用於圖片)："))
        self.allDurationSpinBox = QtWidgets.QSpinBox()
        self.allDurationSpinBox.setMinimum(1)
        self.allDurationSpinBox.setMaximum(3600)
        self.allDurationSpinBox.setValue(7)
        self.allDurationSpinBox.setSuffix(" 秒")
        all_duration_layout.addWidget(self.allDurationSpinBox)
        btn_set_all = QtWidgets.QPushButton("⚙️ 設定全部")
        btn_set_all.clicked.connect(self.setAllDurations)
        all_duration_layout.addWidget(btn_set_all)
        all_duration_layout.addStretch()
        image_layout.addLayout(all_duration_layout)

        self.imageListWidget = QtWidgets.QListWidget()
        self.imageListWidget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.imageListWidget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        image_layout.addWidget(self.imageListWidget)

        # 雙擊事件：影片才開啟剪輯對話框
        self.imageListWidget.itemDoubleClicked.connect(self._on_image_item_double_clicked)

        btn_import_images = QtWidgets.QPushButton("🖼️/📹 匯入圖片/影片")
        btn_import_images.clicked.connect(self.importImages)
        image_layout.addWidget(btn_import_images)
        media_layout.addWidget(image_group, 3)  # 寬度佔 3/5

        self.imageListWidget.model().rowsMoved.connect(self.updateImageSeq)

        music_group = QtWidgets.QGroupBox("音樂設定")
        music_layout = QtWidgets.QVBoxLayout(music_group)
        self.musicListWidget = QtWidgets.QListWidget()
        self.musicListWidget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.musicListWidget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        music_layout.addWidget(self.musicListWidget)
        btn_import_music = QtWidgets.QPushButton("🎵 匯入背景音樂")
        btn_import_music.clicked.connect(self.importMusic)
        music_layout.addWidget(btn_import_music)

        volume_layout = QtWidgets.QHBoxLayout()
        volume_layout.addWidget(QtWidgets.QLabel("音樂音量："))
        self.volumeSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.volumeSlider.setMinimum(0)
        self.volumeSlider.setMaximum(100)
        self.volumeSlider.setValue(100)
        volume_layout.addWidget(self.volumeSlider)
        self.volumeSpinBox = QtWidgets.QSpinBox()
        self.volumeSpinBox.setMinimum(0)
        self.volumeSpinBox.setMaximum(100)
        self.volumeSpinBox.setValue(100)
        volume_layout.addWidget(self.volumeSpinBox)
        self.volumeSlider.valueChanged.connect(lambda v: self.volumeSpinBox.setValue(v))
        self.volumeSpinBox.valueChanged.connect(lambda v: self.volumeSlider.setValue(v))
        music_layout.addLayout(volume_layout)

        # ── 字幕設定 (第一行) ──────────────────────────────────
        sub_row1 = QtWidgets.QHBoxLayout()
        self.checkbox_subtitle = QtWidgets.QCheckBox("啟用字幕")
        sub_row1.addWidget(self.checkbox_subtitle)
        
        sub_row1.addWidget(QtWidgets.QLabel("顏色:"))
        self.combobox_fontcolor = QtWidgets.QComboBox()
        self.combobox_fontcolor.addItems(["白色", "黃色", "淡綠色", "粉紅色"])
        sub_row1.addWidget(self.combobox_fontcolor)
        
        sub_row1.addWidget(QtWidgets.QLabel("位置:"))
        self.combobox_subtitle_pos = QtWidgets.QComboBox()
        self.combobox_subtitle_pos.addItems(["下方", "畫面中央"])
        self.combobox_subtitle_pos.currentIndexChanged.connect(self._on_subtitle_pos_changed)
        sub_row1.addWidget(self.combobox_subtitle_pos)

        sub_row1.addWidget(QtWidgets.QLabel("文字大小:"))
        self.spinbox_fontsize = QtWidgets.QSpinBox()
        self.spinbox_fontsize.setRange(10, 500)
        self.spinbox_fontsize.setValue(70)
        self.spinbox_fontsize.valueChanged.connect(self._on_global_fontsize_changed)
        sub_row1.addWidget(self.spinbox_fontsize)
        sub_row1.addStretch()
        music_layout.addLayout(sub_row1)

        # ── 字幕背景設定 (第二行) ────────────────────────────────
        sub_row2 = QtWidgets.QHBoxLayout()
        self.checkbox_sub_box = QtWidgets.QCheckBox("文字背景")
        self.checkbox_sub_box.setChecked(False)
        sub_row2.addWidget(self.checkbox_sub_box)
        
        sub_row2.addWidget(QtWidgets.QLabel("背景色:"))
        self.combobox_box_color = QtWidgets.QComboBox()
        self.combobox_box_color.addItems(["黑色", "藍色", "深灰色", "紅色"])
        sub_row2.addWidget(self.combobox_box_color)
        
        sub_row2.addWidget(QtWidgets.QLabel("透明度:"))
        self.spinbox_box_opacity = QtWidgets.QSpinBox()
        self.spinbox_box_opacity.setRange(0, 100)
        self.spinbox_box_opacity.setValue(50)
        self.spinbox_box_opacity.setSuffix("%")
        sub_row2.addWidget(self.spinbox_box_opacity)
        sub_row2.addStretch()
        music_layout.addLayout(sub_row2)

        media_layout.addWidget(music_group, 2)  # 寬度佔 2/5
        
        # 強制設定佈局比例，確保 3:2 生效
        media_layout.setStretch(0, 3)
        media_layout.setStretch(1, 2)
        
        # 讓圖片設定區在垂直方向佔更多空間，音樂區縮小
        main_layout.setStretch(1, 4) # media_layout 所在層級原本是 4，這裡確認 stretch 比例

        output_group = QtWidgets.QGroupBox("影片輸出設定")
        form_layout = QtWidgets.QFormLayout(output_group)
        ratio_layout = QtWidgets.QHBoxLayout()
        self.radio_orig_ratio = QtWidgets.QRadioButton("原始比例")
        self.radio_16_9 = QtWidgets.QRadioButton("16:9")
        self.radio_16_9.setChecked(True)
        self.radio_4_3 = QtWidgets.QRadioButton("4:3")
        ratio_layout.addWidget(self.radio_orig_ratio)
        ratio_layout.addWidget(self.radio_16_9)
        ratio_layout.addWidget(self.radio_4_3)
        form_layout.addRow("比例：", ratio_layout)
        self.combo_resolution = QtWidgets.QComboBox()
        self.combo_resolution.addItems(["原始解析度", "480P", "720P", "1080P", "2K", "4K"])
        form_layout.addRow("解析度：", self.combo_resolution)
        self.combo_transition = QtWidgets.QComboBox()
        transition_options = [
            "無轉場", "重疊混合轉場", "向左滑入轉場", "擦除左側轉場",
            "圓形展開轉場", "像素化轉場", "黑色淡出", "白色淡出",
            "向上滑入", "向下滑入", "擦除右側"
        ]
        self.combo_transition.addItems(transition_options)
        form_layout.addRow("轉場效果：", self.combo_transition)
        self.combo_transition.currentIndexChanged.connect(self.updateGlobalSettings)
        
        self.checkbox_video_transition = QtWidgets.QCheckBox("影片間套用轉場 (耗時較長)")
        self.checkbox_video_transition.setChecked(True)
        form_layout.addRow("", self.checkbox_video_transition)

        output_layout.addWidget(output_group)
        output_layout.addStretch()

        self.btn_export = QtWidgets.QPushButton("🎞️ 匯出影片")
        self.btn_export.setMinimumHeight(40)
        self.btn_export.clicked.connect(self.exportVideo)
        output_layout.addWidget(self.btn_export)

    # ------------------------------------------------------------------
    # 雙擊影片剪輯
    # ------------------------------------------------------------------
    def _on_image_item_double_clicked(self, item):
        widget = self.imageListWidget.itemWidget(item)
        if widget is None or not widget.is_video:
            return
        self._open_video_edit_dialog(item, widget)

    def _open_video_edit_dialog(self, list_item, widget):
        dlg = VideoEditDialog(
            widget.file_path,
            trim_start=widget.trim_start,
            trim_end=widget.trim_end,
            parent=self
        )
        result = dlg.exec_()
        trim_start, trim_end, split_time = dlg.get_result()

        if result != QtWidgets.QDialog.Accepted:
            return

        if split_time is not None:
            self._split_video_item(list_item, widget, split_time)
        else:
            widget.trim_start = trim_start
            widget.trim_end = trim_end
            effective_sec = trim_end - trim_start
            widget.base_duration = ceil_seconds(effective_sec)
            new_dur = widget.base_duration
            if self.combo_transition.currentText() != "無轉場":
                new_dur = widget.base_duration + 1
            widget.spinBox.blockSignals(True)
            widget.spinBox.setValue(new_dur)
            widget.spinBox.blockSignals(False)
            widget.duration = new_dur
            widget.update_trim_info()
            list_item.setSizeHint(widget.sizeHint())

    def _split_video_item(self, list_item, widget, split_time):
        src = widget.file_path
        row = self.imageListWidget.row(list_item)
        
        # 取得原本的裁切範圍
        original_start = widget.trim_start
        original_end   = widget.trim_end

        # 移除原本的項目
        self.imageListWidget.takeItem(row)

        # 建立第一段：起點為原本起點，終點為分割點
        item1 = QtWidgets.QListWidgetItem()
        w1 = ImageItemWidget(src, mainwindow=self, trim_start=original_start, trim_end=split_time)
        w1.removeRequested.connect(lambda ww=w1: self.removeImageItem(ww))
        w1.audioUploaded.connect(self.updateGlobalSettings)
        item1.setSizeHint(w1.sizeHint())
        self.imageListWidget.insertItem(row, item1)
        self.imageListWidget.setItemWidget(item1, w1)

        # 建立第二段：起點為分割點，終點為原本終點
        item2 = QtWidgets.QListWidgetItem()
        w2 = ImageItemWidget(src, mainwindow=self, trim_start=split_time, trim_end=original_end)
        w2.removeRequested.connect(lambda ww=w2: self.removeImageItem(ww))
        w2.audioUploaded.connect(self.updateGlobalSettings)
        item2.setSizeHint(w2.sizeHint())
        self.imageListWidget.insertItem(row + 1, item2)
        self.imageListWidget.setItemWidget(item2, w2)

        self.updateImageSeq()
        self.updateGlobalSettings()
        
        # 強制讓新產生的項目顯示字幕輸入框（如果已啟用字幕）
        w1.updateSubtitleDisplay()
        w2.updateSubtitleDisplay()

        QtWidgets.QMessageBox.information(
            self, "分割完成",
            f"影片已在 {format_time(split_time)} 處分割為兩段標記！\n"
            "（兩段皆指向原檔，僅調整裁切起點與終點）"
        )

    # ------------------------------------------------------------------
    # 樣式
    # ------------------------------------------------------------------
    def applyStyles(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #f3f7fb;
                color: #172033;
                font-size: 13px;
            }
            QGroupBox {
                font: bold 14px;
                color: #102033;
                border: 1px solid #9db7d3;
                border-radius: 6px;
                margin-top: 12px;
                background-color: #ffffff;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                background-color: #ffffff;
                color: #102033;
            }
            QLabel, QCheckBox, QRadioButton {
                color: #172033;
            }
            QLabel#metaLabel {
                color: #53606f;
                font-weight: normal;
                padding-left: 8px;
            }
            QListWidget {
                background-color: #ffffff;
                color: #172033;
                border: 1px solid #b7c8da;
                border-radius: 4px;
                selection-background-color: #2f6fab;
                selection-color: #ffffff;
            }
            QListWidget::item {
                background-color: #ffffff;
                color: #172033;
                padding: 2px;
            }
            QListWidget::item:selected {
                background-color: #dbeafe;
                color: #102033;
            }
            QPushButton {
                background-color: #d7e8f8;
                color: #102033;
                border: 1px solid #8fb1d1;
                padding: 7px 10px;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #c4dcf2;
                border-color: #6d9fca;
            }
            QPushButton:pressed {
                background-color: #abcbe8;
            }
            QPushButton:disabled {
                background-color: #e5e9ef;
                color: #6f7a89;
                border-color: #ccd3dc;
            }
            QPushButton#dangerButton {
                background-color: #f06b6b;
                color: #ffffff;
                border-color: #cc4f4f;
            }
            QPushButton#dangerButton:hover {
                background-color: #df5c5c;
            }
            QLineEdit, QSpinBox, QComboBox, QTextEdit {
                background-color: #ffffff;
                color: #172033;
                border: 1px solid #aebfd1;
                border-radius: 4px;
                padding: 4px;
                selection-background-color: #2f6fab;
                selection-color: #ffffff;
            }
            QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
                background-color: #e8edf3;
                color: #53606f;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #172033;
                selection-background-color: #dbeafe;
                selection-color: #102033;
                border: 1px solid #aebfd1;
            }
            QProgressDialog, QMessageBox, QDialog {
                background-color: #f3f7fb;
                color: #172033;
            }
            QSpinBox {
                max-width: 90px;
            }
            QSlider::groove:horizontal {
                background: #c7d7e8;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #2f6fab;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)

    # ------------------------------------------------------------------
    # 其餘功能
    # ------------------------------------------------------------------
    def setAllDurations(self):
        new_duration = self.allDurationSpinBox.value()
        for i in range(self.imageListWidget.count()):
            item = self.imageListWidget.item(i)
            widget = self.imageListWidget.itemWidget(item)
            if widget and not widget.image_audio_path and not widget.is_video:
                widget.base_duration = new_duration
                if self.combo_transition.currentText() != "無轉場":
                    widget.spinBox.setValue(new_duration + 1)
                    widget.duration = new_duration + 1
                else:
                    widget.spinBox.setValue(new_duration)
                    widget.duration = new_duration
                widget.spinBox.setDisabled(False)

    def newProject(self):
        self.imageListWidget.clear()
        self.musicListWidget.clear()
        self.allDurationSpinBox.setValue(7)
        self.volumeSlider.setValue(100)
        self.volumeSpinBox.setValue(100)
        self.radio_16_9.setChecked(True)
        self.combo_resolution.setCurrentText("480P")
        self.combo_transition.setCurrentText("無轉場")

    def importImages(self):
        fd = QtWidgets.QFileDialog(
            self, "選擇圖片/影片", "",
            "Images/Videos (*.png *.jpg *.jpeg *.bmp *.mp4 *.avi *.mov *.mkv)"
        )
        fd.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        if fd.exec_():
            for path in fd.selectedFiles():
                self.addImageItem(path)
            self.updateImageSeq()
            self.updateGlobalSettings()

    def addImageItem(self, file_path, trim_start=0.0, trim_end=None):
        item = QtWidgets.QListWidgetItem()
        widget = ImageItemWidget(file_path, mainwindow=self,
                                 trim_start=trim_start, trim_end=trim_end)
        widget.removeRequested.connect(lambda w=widget: self.removeImageItem(w))
        widget.audioUploaded.connect(self.updateGlobalSettings)
        item.setSizeHint(widget.sizeHint())
        self.imageListWidget.addItem(item)
        self.imageListWidget.setItemWidget(item, widget)
        self.updateImageSeq()

    def removeImageItem(self, widget):
        for i in range(self.imageListWidget.count()):
            item = self.imageListWidget.item(i)
            if self.imageListWidget.itemWidget(item) == widget:
                self.imageListWidget.takeItem(i)
                break
        self.updateGlobalSettings()
        self.updateImageSeq()

    def updateImageSeq(self):
        for i in range(self.imageListWidget.count()):
            widget = self.imageListWidget.itemWidget(self.imageListWidget.item(i))
            if widget:
                widget.seq_label.setText(f"{i+1}.")

    def importMusic(self):
        fd = QtWidgets.QFileDialog(self, "選擇背景音樂檔", "", "Audio Files (*.mp3 *.wav *.ogg)")
        fd.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        if fd.exec_():
            for path in fd.selectedFiles():
                self.addMusicItem(path)

    def addMusicItem(self, music_path):
        item = QtWidgets.QListWidgetItem()
        widget = MusicItemWidget(music_path)
        widget.removeRequested.connect(lambda w=widget: self.removeMusicItem(w))
        item.setSizeHint(widget.sizeHint())
        self.musicListWidget.addItem(item)
        self.musicListWidget.setItemWidget(item, widget)

    def removeMusicItem(self, widget):
        for i in range(self.musicListWidget.count()):
            item = self.musicListWidget.item(i)
            if self.musicListWidget.itemWidget(item) == widget:
                self.musicListWidget.takeItem(i)
                break

    def updateGlobalSettings(self):
        for i in range(self.imageListWidget.count()):
            widget = self.imageListWidget.itemWidget(self.imageListWidget.item(i))
            if widget:
                if not widget.is_video:
                    if widget.image_audio_path:
                        if self.combo_transition.currentText() != "無轉場":
                            widget.spinBox.setValue(widget.base_duration + 1)
                            widget.duration = widget.base_duration + 1
                        else:
                            widget.spinBox.setValue(widget.base_duration)
                            widget.duration = widget.base_duration
                        widget.spinBox.setDisabled(True)
                    else:
                        if self.combo_transition.currentText() != "無轉場":
                            widget.spinBox.setValue(widget.base_duration + 1)
                            widget.duration = widget.base_duration + 1
                            widget.spinBox.setDisabled(True)
                        else:
                            widget.spinBox.setValue(widget.base_duration)
                            widget.duration = widget.base_duration
                            widget.spinBox.setDisabled(False)
                else:
                    # 影片也要同步更新持續時間（為了轉場）
                    if self.combo_transition.currentText() != "無轉場":
                        widget.spinBox.setValue(widget.base_duration + 1)
                        widget.duration = widget.base_duration + 1
                    else:
                        widget.spinBox.setValue(widget.base_duration)
                        widget.duration = widget.base_duration
                    widget.spinBox.setDisabled(True)
                widget.updateSubtitleDisplay()

    def check_ffmpeg(self):
        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            msg = ("系統中沒有找到 ffmpeg 與 ffprobe，請先安裝 ffmpeg。<br><br>"
                   "請參考以下文章進行安裝：<br>"
                   "<a href='https://kentxchang.blogspot.com/2024/12/ffmpegffmpeg.html'>"
                   "https://kentxchang.blogspot.com/2024/12/ffmpegffmpeg.html</a>")
            box = QtWidgets.QMessageBox()
            box.setIcon(QtWidgets.QMessageBox.Warning)
            box.setWindowTitle("錯誤")
            box.setTextFormat(QtCore.Qt.RichText)
            box.setText(msg)
            box.exec_()
            return False
        return True

    # ------------------------------------------------------------------
    # 匯出影片
    # ------------------------------------------------------------------
    def exportVideo(self):
        if not self.check_ffmpeg():
            return

        subtitle_color_mapping = {
            "白色": "white", "黃色": "yellow", "淡綠色": "lightgreen", "粉紅色": "pink"
        }
        subtitle_color = subtitle_color_mapping.get(self.combobox_fontcolor.currentText(), "white")

        image_items = []
        total_duration = 0
        for i in range(self.imageListWidget.count()):
            widget = self.imageListWidget.itemWidget(self.imageListWidget.item(i))
            if widget:
                if widget.image_audio_path:
                    subtitle_text = os.path.splitext(os.path.basename(widget.image_audio_path))[0]
                else:
                    subtitle_text = widget.subtitle_edit.text().strip()
                
                # 取得該項目的個別字幕設定
                item_pos = "bottom" if widget.combo_item_pos.currentText() == "下方" else "center"
                item_size = str(widget.spin_item_size.value())

                if widget.image_audio_path and self.combo_transition.currentText() != "無轉場":
                    current_duration = widget.spinBox.value()
                    widget.duration = current_duration
                    temp_dir = get_temp_dir()
                    silence_file = os.path.join(temp_dir, "silence0.5.mp3")
                    if not os.path.exists(silence_file):
                        cmd_silence = [
                            "ffmpeg", "-y",
                            "-f", "lavfi",
                            "-i", "anullsrc=r=44100:cl=stereo",
                            "-t", "0.5",
                            "-c:a", "libmp3lame",
                            silence_file
                        ]
                        run_ffmpeg(cmd_silence, "建立轉場靜音音訊")
                    new_audio_file = os.path.join(temp_dir, f"modified_audio_{i}.mp3")
                    cmd_concat_audio = [
                        "ffmpeg", "-y",
                        "-i", silence_file,
                        "-i", widget.image_audio_path,
                        "-i", silence_file,
                        "-filter_complex",
                        "[0:a][1:a][2:a]concat=n=3:v=0:a=1,aresample=44100[a]",
                        "-map", "[a]",
                        "-ac", "2",
                        "-ar", "44100",
                        "-c:a", "libmp3lame",
                        new_audio_file
                    ]
                    run_ffmpeg(cmd_concat_audio, "合成圖片專屬音訊")
                    image_items.append((
                        widget.file_path, current_duration, new_audio_file,
                        widget.is_video, subtitle_text,
                        widget.trim_start, widget.trim_end,
                        item_pos, item_size
                    ))
                else:
                    current_duration = widget.spinBox.value()
                    widget.duration = current_duration
                    image_items.append((
                        widget.file_path, current_duration, widget.image_audio_path,
                        widget.is_video, subtitle_text,
                        widget.trim_start, widget.trim_end,
                        item_pos, item_size
                    ))
                total_duration += widget.spinBox.value()

        if not image_items:
            QtWidgets.QMessageBox.warning(self, "警告", "請先匯入至少一個圖片/影片。")
            return

        trimmed_music_files = []
        for i in range(self.musicListWidget.count()):
            item = self.musicListWidget.item(i)
            widget = self.musicListWidget.itemWidget(item)
            if widget:
                start_sec = widget.startSpin.value()
                end_sec = widget.endSpin.value()
                full_length = widget.music_length
                if abs(end_sec - full_length) < 0.1:
                    trimmed_music_files.append(widget.music_path)
                else:
                    temp_dir = get_temp_dir()
                    trimmed_file = os.path.join(temp_dir, f"trimmed_music_{i}.m4a")
                    cmd_trim = [
                        "ffmpeg", "-y",
                        "-ss", str(start_sec),
                        "-to", str(end_sec),
                        "-i", widget.music_path,
                        "-ac", "2",
                        "-ar", "44100",
                        "-c:a", "aac",
                        trimmed_file
                    ]
                    run_ffmpeg(cmd_trim, "裁切背景音樂")
                    trimmed_music_files.append(trimmed_file)

        # ── 決定輸出比例與解析度 ──────────────────────────────────
        # 預設值
        width, height = 854, 480
        ratio_display = "16:9"
        
        # 取得第一個素材的資訊（用於「原始」選項）
        first_w, first_h = None, None
        if image_items:
            first_w, first_h = get_video_dimensions(image_items[0][0])

        # 1. 決定比例
        if self.radio_orig_ratio.isChecked():
            if first_w and first_h:
                ratio_display = f"原始 ({first_w}:{first_h})"
            else:
                ratio_display = "原始 (未知，改用 16:9)"
        elif self.radio_16_9.isChecked():
            ratio_display = "16:9"
        else:
            ratio_display = "4:3"

        # 2. 決定解析度
        resolution_str = self.combo_resolution.currentText()
        if resolution_str == "原始解析度":
            if first_w and first_h:
                width, height = first_w, first_h
            else:
                width, height = 1280, 720
                resolution_str = "原始解析度 (失敗，改用 720P)"
        else:
            # 查表
            r_key = "16:9" if not self.radio_4_3.isChecked() else "4:3"
            resolution_map = {
                "16:9": {
                    "480P": "854x480", "720P": "1280x720", "1080P": "1920x1080",
                    "2K": "2560x1444", "4K": "3840x2160"
                },
                "4:3": {
                    "480P": "640x480", "720P": "960x720", "1080P": "1440x1080",
                    "2K": "2048x1536", "4K": "2560x1920"
                }
            }
            res_val = resolution_map.get(r_key, resolution_map["16:9"]).get(resolution_str, "854x480")
            width_str, height_str = res_val.split('x')
            width, height = int(width_str), int(height_str)

        target_resolution = f"{width}x{height}"

        output_path = os.path.join(os.getcwd(), "output_video.mp4")
        temp_dir = get_temp_dir()
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "錯誤",
                    f"無法覆蓋舊的輸出檔，請先關閉正在播放的影片。\n\n{e}"
                )
                return

        progress_dialog = QtWidgets.QProgressDialog("影片匯出中...", "取消", 0, 100, self)
        progress_dialog.setWindowTitle("匯出進度")
        progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        progress_dialog.setMinimumWidth(600)  # 加大寬度
        progress_dialog.show()
        QtWidgets.QApplication.processEvents()

        segment_files = []
        total_steps = len(image_items) + 3
        current_step = 0

        # 字幕背景設定
        sub_box_mapping = {"黑色": "black", "藍色": "blue", "深灰色": "darkgray", "紅色": "red"}
        show_sub_box = self.checkbox_sub_box.isChecked()
        sub_box_color = sub_box_mapping.get(self.combobox_box_color.currentText(), "black")
        sub_box_opacity = self.spinbox_box_opacity.value() / 100.0

        for idx, (file_path, duration, audio_file, is_video, subtitle_text,
                  trim_start, trim_end, item_pos, item_size) in enumerate(image_items):
            seg_file = os.path.join(temp_dir, f"segment_{idx}.mp4")
            segment_files.append(seg_file)
            
            filter_chain = build_video_filter(
                width, height,
                self.checkbox_subtitle.isChecked(),
                subtitle_text, subtitle_color,
                item_size,
                item_pos,
                show_sub_box,
                sub_box_color,
                sub_box_opacity
            )
            if is_video:
                has_audio = media_has_audio(file_path)
                # 重要：為了轉場，讀取輸入素材時必須包含額外的 1 秒（由 duration 決定）
                # 不要使用 -to trim_end，改用 -t duration
                base_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(trim_start),
                    "-t", str(duration),
                    "-i", file_path,
                ]
                if has_audio:
                    cmd = base_cmd + [
                        "-map", "0:v:0",
                        "-map", "0:a:0",
                        "-vf", filter_chain,
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        "-ac", "2",
                        "-ar", "44100",
                        "-r", "30",
                        "-pix_fmt", "yuv420p",
                        "-t", str(duration),
                        "-shortest",
                        seg_file
                    ]
                else:
                    cmd = base_cmd + [
                        "-f", "lavfi",
                        "-t", str(duration),
                        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-vf", filter_chain,
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        "-ac", "2",
                        "-ar", "44100",
                        "-r", "30",
                        "-pix_fmt", "yuv420p",
                        "-t", str(duration),
                        "-shortest",
                        seg_file
                    ]
            else:
                if audio_file:
                    cmd = [
                        "ffmpeg", "-y",
                        "-loop", "1",
                        "-t", str(duration),
                        "-i", file_path,
                        "-i", audio_file,
                        "-filter_complex",
                        f"[0:v]{filter_chain}[v];[1:a]apad,atrim=0:{duration},aresample=44100[a]",
                        "-map", "[v]",
                        "-map", "[a]",
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        "-ac", "2",
                        "-ar", "44100",
                        "-r", "30",
                        "-pix_fmt", "yuv420p",
                        "-t", str(duration),
                        seg_file
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y",
                        "-loop", "1",
                        "-t", str(duration),
                        "-i", file_path,
                        "-f", "lavfi",
                        "-t", str(duration),
                        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                        "-vf", filter_chain,
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        "-ac", "2",
                        "-ar", "44100",
                        "-r", "30",
                        "-pix_fmt", "yuv420p",
                        "-shortest",
                        seg_file
                    ]
            run_ffmpeg(cmd, f"建立第 {idx + 1} 段影片")
            current_step += 1
            progress_dialog.setValue(int(current_step / total_steps * 100))
            QtWidgets.QApplication.processEvents()
            if progress_dialog.wasCanceled():
                QtWidgets.QMessageBox.warning(self, "取消", "影片匯出已取消。")
                return

        # 決定是否啟用轉場處理
        use_transition = (self.combo_transition.currentText() != "無轉場" and len(segment_files) > 1)
        # 如果使用者未勾選「影片間套用轉場」，且清單中有包含影片，則可決定是否要降級為無轉場（或簡單串接）
        # 這裡實作邏輯：若沒勾選，且「當前或下一個」項目是影片，則該處不使用 xfade
        
        if use_transition:
            transition_video = os.path.join(temp_dir, "transition_video.mp4")
            cmd = ["ffmpeg", "-y"]
            for seg in segment_files:
                cmd.extend(["-i", seg])
            
            filter_complex = ""
            for i in range(len(image_items)):
                filter_complex += f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,fps=30,format=yuv420p[v{i}];"
                filter_complex += f"[{i}:a]asetpts=PTS-STARTPTS[a{i}];"
            
            current_v = "v0"
            current_a = "a0"
            current_offset = float(image_items[0][1])
            
            transition_mapping = {
                "重疊混合轉場": "fade", "向左滑入轉場": "slideleft", "擦除左側轉場": "wipeleft",
                "圓形展開轉場": "circleopen", "像素化轉場": "pixelize", "黑色淡出": "fadeblack",
                "白色淡出": "fadewhite", "向上滑入": "slideup", "向下滑入": "slidedown", "擦除右側": "wiperight"
            }
            transition_effect = transition_mapping.get(self.combo_transition.currentText(), "fade")
            
            # 是否強制對影片間也使用轉場
            apply_to_video = self.checkbox_video_transition.isChecked()

            actual_segments_to_concat = []
            
            # 簡化實作：如果勾選了 apply_to_video，則全部走 xfade
            # 如果沒勾選，則只有在「兩者皆非影片」時才走 xfade？ 
            # 考量使用者需求：「目前只要影片接影片，好像都不會有轉場效果」，這表示原本的程式碼可能在某處過濾了。
            # 但我看現有程式碼並沒有過濾 is_video，它是一律對 segment_files 做處理。
            # 問題可能出在影片長度不足或 pts 處理。
            
            # 改進：如果使用者「沒勾選」影片間轉場，我們就退回到 concat 模式（較快且穩定）
            # 如果「有勾選」，則全部使用 xfade（包含影片接影片）
            
            if not apply_to_video:
                # 檢查清單中是否有影片，如果有，則強迫不使用 xfade (走 concat) 以節省時間
                has_any_video = any(item[3] for item in image_items)
                if has_any_video:
                    use_transition = False

        if use_transition:
            # 原本的 xfade 邏輯
            for i in range(1, len(segment_files)):
                offset_xfade = current_offset - 1
                out_v = f"vout{i}"
                out_a = f"aout{i}"
                filter_complex += (
                    f"[{current_v}][v{i}]xfade=transition={transition_effect}"
                    f":duration=1:offset={offset_xfade}[{out_v}];"
                )
                filter_complex += f"[{current_a}][a{i}]acrossfade=d=1[cross{i}];"
                current_v = out_v
                current_a = f"cross{i}"
                current_offset += float(image_items[i][1]) - 1
            
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", f"[{current_v}]",
                "-map", f"[{current_a}]",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-shortest",
                transition_video
            ])
            run_ffmpeg(cmd, "合成轉場影片")
            concat_video = transition_video
        else:
            # 走 concat 模式
            concat_video = os.path.join(temp_dir, "combined_video.mp4")
            segments_txt = os.path.join(temp_dir, "segments.txt")
            with open(segments_txt, "w", encoding="utf-8") as f:
                for seg in segment_files:
                    f.write(concat_file_line(seg))
            cmd_concat = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", segments_txt,
                "-c", "copy",
                concat_video
            ]
            run_ffmpeg(cmd_concat, "串接所有影片片段")
            if os.path.exists(segments_txt):
                os.remove(segments_txt)

        current_step += 1
        progress_dialog.setValue(int(current_step / total_steps * 100))
        QtWidgets.QApplication.processEvents()
        if progress_dialog.wasCanceled():
            QtWidgets.QMessageBox.warning(self, "取消", "影片匯出已取消。")
            return

        combined_audio = None
        if trimmed_music_files:
            if len(trimmed_music_files) == 1:
                combined_audio = trimmed_music_files[0]
            else:
                audio_list_txt = os.path.join(temp_dir, "audio_list.txt")
                with open(audio_list_txt, "w", encoding="utf-8") as f:
                    for a in trimmed_music_files:
                        f.write(concat_file_line(a))
                combined_audio = os.path.join(temp_dir, "combined_audio.m4a")
                cmd_audio = [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", audio_list_txt,
                    "-ac", "2",
                    "-ar", "44100",
                    "-c:a", "aac",
                    combined_audio
                ]
                run_ffmpeg(cmd_audio, "合併背景音樂")
                os.remove(audio_list_txt)

        current_step += 1
        progress_dialog.setValue(int(current_step / total_steps * 100))
        QtWidgets.QApplication.processEvents()
        if progress_dialog.wasCanceled():
            QtWidgets.QMessageBox.warning(self, "取消", "影片匯出已取消。")
            return

        music_volume = self.volumeSlider.value() / 100.0
        if combined_audio:
            cmd_merge = [
                "ffmpeg", "-y",
                "-i", concat_video,
                "-stream_loop", "-1",
                "-i", combined_audio,
                "-filter_complex",
                f"[1:a]volume={music_volume}[bgm];[0:a][bgm]amix=inputs=2:duration=shortest",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                output_path
            ]
        else:
            cmd_merge = [
                "ffmpeg", "-y",
                "-i", concat_video,
                "-c", "copy",
                output_path
            ]
        run_ffmpeg(cmd_merge, "輸出最終影片")
        current_step += 1
        progress_dialog.setValue(int(current_step / total_steps * 100))
        QtWidgets.QApplication.processEvents()

        progress_dialog.close()

        if os.path.exists(output_path):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print("刪除 temp 資料夾時發生錯誤:", e)
        else:
            print("最終合成檔案未生成，保留 temp 資料夾以便偵錯。")

        # ── 匯出完成自定義對話框 ──────────────────────────────────
        final_dlg = QtWidgets.QDialog(self)
        final_dlg.setWindowTitle("匯出完成")
        final_layout = QtWidgets.QVBoxLayout(final_dlg)
        
        info_text = (
            f"影片已成功輸出！\n\n"
            f"檔案路徑：{output_path}\n"
            f"輸出比例：{ratio_display}\n"
            f"解析度：{target_resolution}\n"
            f"總影片時長：{total_duration} 秒\n\n"
            f"圖片/影片細節：\n"
            + "\n".join([
                f"{os.path.basename(p)[:15]}：{d}秒"
                + (f" [裁切 {format_time(ts)}～{format_time(te)}]" if iv else "")
                for p, d, _, iv, _, ts, te, _, _ in image_items
            ])
            + (
                f"\n\n背景音樂：\n"
                + "\n".join([os.path.basename(a) for a in trimmed_music_files])
                if trimmed_music_files else "\n\n(無背景音樂)"
            )
        )
        
        text_edit = QtWidgets.QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setText(info_text)
        final_layout.addWidget(text_edit)
        
        btn_row = QtWidgets.QHBoxLayout()
        btn_play_final = QtWidgets.QPushButton("▶ 播放影片")
        btn_folder_final = QtWidgets.QPushButton("📁 開啟資料夾")
        btn_ok_final = QtWidgets.QPushButton("確定")
        
        # 美化按鈕樣式
        btn_play_final.setStyleSheet("background:#2d6fa5; color:white; font-weight:bold; padding:8px 15px;")
        btn_folder_final.setStyleSheet("background:#f3f7fb; color:#102033; padding:8px 15px;")
        btn_ok_final.setMinimumWidth(80)
        
        btn_row.addWidget(btn_play_final)
        btn_row.addWidget(btn_folder_final)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok_final)
        final_layout.addLayout(btn_row)
        
        def _open_video():
            try:
                os.startfile(output_path)
            except Exception as e:
                QtWidgets.QMessageBox.warning(final_dlg, "錯誤", f"無法開啟影片：{e}")

        def _open_folder():
            try:
                folder = os.path.dirname(os.path.abspath(output_path))
                os.startfile(folder)
            except Exception as e:
                QtWidgets.QMessageBox.warning(final_dlg, "錯誤", f"無法開啟資料夾：{e}")

        btn_play_final.clicked.connect(_open_video)
        btn_folder_final.clicked.connect(_open_folder)
        btn_ok_final.clicked.connect(final_dlg.accept)
        
        final_dlg.resize(600, 450)
        final_dlg.exec_()

    # ------------------------------------------------------------------
    # 存檔 / 開檔
    # ------------------------------------------------------------------
    def saveProject(self):
        fd = QtWidgets.QFileDialog(self, "另存新檔", "", "Project Files (*.json)")
        fd.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        if fd.exec_():
            filePath = fd.selectedFiles()[0]
            project = {}
            images = []
            for i in range(self.imageListWidget.count()):
                widget = self.imageListWidget.itemWidget(self.imageListWidget.item(i))
                if widget:
                    images.append({
                        "file_path": widget.file_path,
                        "duration": widget.duration,
                        "image_audio_path": widget.image_audio_path,
                        "base_duration": widget.base_duration,
                        "manual_subtitle": widget.subtitle_edit.text(),
                        "trim_start": widget.trim_start,
                        "trim_end": widget.trim_end,
                        "subtitle_pos": widget.combo_item_pos.currentText(),
                        "subtitle_size": widget.spin_item_size.value(),
                    })
            project["images"] = images
            music = []
            for i in range(self.musicListWidget.count()):
                widget = self.musicListWidget.itemWidget(self.musicListWidget.item(i))
                if widget:
                    music.append({
                        "music_path": widget.music_path,
                        "start": widget.startSpin.value(),
                        "end": widget.endSpin.value()
                    })
            project["music"] = music
            settings = {
                "ratio": "16:9" if self.radio_16_9.isChecked() else "4:3",
                "resolution": self.combo_resolution.currentText(),
                "volume": self.volumeSlider.value(),
                "transition": self.combo_transition.currentText(),
                "video_transition": self.checkbox_video_transition.isChecked(),
                "sub_box": self.checkbox_sub_box.isChecked(),
                "sub_box_color": self.combobox_box_color.currentText(),
                "sub_box_opacity": self.spinbox_box_opacity.value()
            }
            project["settings"] = settings
            try:
                with open(filePath, "w", encoding="utf-8") as f:
                    json.dump(project, f, ensure_ascii=False, indent=4)
                QtWidgets.QMessageBox.information(self, "存檔完成", f"專案已儲存至 {filePath}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "存檔錯誤", str(e))

    def openProject(self):
        fd = QtWidgets.QFileDialog(self, "開啟舊檔", "", "Project Files (*.json)")
        fd.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        if fd.exec_():
            filePath = fd.selectedFiles()[0]
            try:
                with open(filePath, "r", encoding="utf-8") as f:
                    project = json.load(f)
                self.imageListWidget.clear()
                self.musicListWidget.clear()
                for img in project.get("images", []):
                    item = QtWidgets.QListWidgetItem()
                    raw_dur = img.get("base_duration", img["duration"])
                    trim_start = img.get("trim_start", 0.0)
                    trim_end = img.get("trim_end", None)
                    widget = ImageItemWidget(
                        img["file_path"],
                        default_duration=raw_dur,
                        mainwindow=self,
                        trim_start=trim_start,
                        trim_end=trim_end
                    )
                    widget.duration = img["duration"]
                    widget.base_duration = raw_dur
                    widget.combo_item_pos.setCurrentText(img.get("subtitle_pos", "下方"))
                    widget.spin_item_size.setValue(img.get("subtitle_size", 70))
                    
                    if img.get("image_audio_path"):
                        widget.image_audio_path = img["image_audio_path"]
                        widget.spinBox.setValue(img["duration"])
                        widget.audio_label.setText(os.path.basename(img["image_audio_path"]))
                        widget.btn_upload_audio.setText("❌ ")
                        widget.spinBox.setDisabled(True)
                    else:
                        widget.subtitle_edit.setText(img.get("manual_subtitle", ""))
                    widget.removeRequested.connect(lambda w=widget: self.removeImageItem(w))
                    item.setSizeHint(widget.sizeHint())
                    self.imageListWidget.addItem(item)
                    self.imageListWidget.setItemWidget(item, widget)
                for m in project.get("music", []):
                    item = QtWidgets.QListWidgetItem()
                    widget = MusicItemWidget(m["music_path"])
                    widget.startSpin.setValue(m.get("start", 0))
                    widget.endSpin.setValue(m.get("end", widget.total_seconds))
                    widget.removeRequested.connect(lambda w=widget: self.removeMusicItem(w))
                    item.setSizeHint(widget.sizeHint())
                    self.musicListWidget.addItem(item)
                    self.musicListWidget.setItemWidget(item, widget)
                settings = project.get("settings", {})
                if settings.get("ratio", "16:9") == "16:9":
                    self.radio_16_9.setChecked(True)
                else:
                    self.radio_4_3.setChecked(True)
                self.combo_resolution.setCurrentText(settings.get("resolution", "480P"))
                self.volumeSlider.setValue(settings.get("volume", 100))
                self.combo_transition.setCurrentText(settings.get("transition", "無轉場"))
                self.checkbox_video_transition.setChecked(settings.get("video_transition", True))
                self.checkbox_sub_box.setChecked(settings.get("sub_box", False))
                self.combobox_box_color.setCurrentText(settings.get("sub_box_color", "黑色"))
                self.spinbox_box_opacity.setValue(settings.get("sub_box_opacity", 50))
                self.updateGlobalSettings()
                self.updateImageSeq()
                QtWidgets.QMessageBox.information(self, "開檔完成", f"專案已載入 {filePath}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "開檔錯誤", str(e))


# ===============================
# 全域例外處理
# ===============================
import ctypes


def show_unhandled_error(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    message = str(exc_value) or exc_type.__name__
    QtWidgets.QMessageBox.critical(None, "程式錯誤", message)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def main():
    myappid = 'mycompany.myproduct.subproduct.version'
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    icon_path = get_resource_path("ico.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))
    sys.excepthook = show_unhandled_error
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
