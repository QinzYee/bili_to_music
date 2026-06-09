import os
import re
from bs4 import BeautifulSoup
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QProgressBar, QRadioButton, QButtonGroup,
    QFileDialog, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QSpinBox,
    QStackedWidget, QFrame, QDialog, QScrollArea, QGraphicsView, QGraphicsScene
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QGuiApplication, QPixmap

from core.bilibili_api import extract_bvid, get_video_info, get_audio_url
from core.downloader import download_file
from core.audio_utils import convert_audio, is_ffmpeg_available
from utils.filename_utils import build_filename
from config import DEFAULT_SAVE_DIR, DEFAULT_FORMAT, RESOURCE_DIR


class ImageViewerDialog(QDialog):
    """图片查看对话框，支持放大缩小"""
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.scale = 1.0
        self._setup_ui()
        self._load_image()
    
    def _setup_ui(self):
        self.setWindowTitle("图片查看")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        zoom_in_btn = QPushButton("🔍 放大 (+)")
        zoom_in_btn.setFixedHeight(30)
        zoom_in_btn.clicked.connect(self._zoom_in)
        toolbar_layout.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("🔍 缩小 (-)")
        zoom_out_btn.setFixedHeight(30)
        zoom_out_btn.clicked.connect(self._zoom_out)
        toolbar_layout.addWidget(zoom_out_btn)
        
        reset_btn = QPushButton("🔄 重置")
        reset_btn.setFixedHeight(30)
        reset_btn.clicked.connect(self._reset_zoom)
        toolbar_layout.addWidget(reset_btn)
        
        toolbar_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(100)
        close_btn.setFixedHeight(30)
        close_btn.clicked.connect(self.accept)
        toolbar_layout.addWidget(close_btn)
        
        layout.addLayout(toolbar_layout)
        
        # 图片显示区域
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        layout.addWidget(self.view)
    
    def _load_image(self):
        if os.path.exists(self.image_path):
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                self.pixmap_item = self.scene.addPixmap(pixmap)
                self._update_scale()
    
    def _zoom_in(self):
        self.scale *= 1.2
        self._update_scale()
    
    def _zoom_out(self):
        self.scale *= 0.8
        self._update_scale()
    
    def _reset_zoom(self):
        self.scale = 1.0
        self._update_scale()
    
    def _update_scale(self):
        if hasattr(self, 'pixmap_item'):
            self.pixmap_item.setScale(self.scale)
    
    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self._zoom_in()
        else:
            self._zoom_out()


class ClickableImageLabel(QLabel):
    """可点击的图片标签"""
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border: 1px solid #ddd; padding: 5px;")
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            viewer = ImageViewerDialog(self.image_path, self.window())
            viewer.exec()
        super().mousePressEvent(event)


class TutorialDialog(QDialog):
    """图文教程对话框 - 读取真实MD文件，渲染结果缓存为类变量"""
    _cached_tokens = None
    _cached_mtime = None
    _cached_md_path = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_tutorial_from_md()
    
    def _setup_ui(self):
        self.setWindowTitle("📖 图文教程")
        self.setMinimumSize(800, 700)
        self.resize(900, 800)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("B站视频音频下载工具 - 图文教程")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; padding: 10px; color: #333;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 内容容器
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(15)
        self.content_layout.setContentsMargins(25, 20, 25, 20)
        
        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll)
        
        # 关闭按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(100)
        close_btn.setFixedHeight(35)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
    
    def _get_resource_path(self):
        """获取资源目录路径"""
        return RESOURCE_DIR
    
    def _add_heading(self, text, level):
        """添加标题"""
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setText(text)
        if level == 1:
            label.setStyleSheet("font-size: 22px; font-weight: bold; color: #222; padding: 12px 0 8px 0;")
        elif level == 2:
            label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4CAF50; padding: 10px 0 6px 0; border-bottom: 2px solid #4CAF50; margin-top: 10px;")
        elif level == 3:
            label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333; padding: 8px 0 4px 0;")
        elif level == 4:
            label.setStyleSheet("font-size: 14px; font-weight: 600; color: #444; padding: 6px 0 2px 0;")
        label.setWordWrap(True)
        self.content_layout.addWidget(label)
    
    def _add_paragraph(self, text):
        """添加段落"""
        label = QLabel()
        # 使用纯文本格式，避免HTML标签被解析
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setText(text)
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 14px; color: #555; line-height: 1.8; padding: 4px 0;")
        self.content_layout.addWidget(label)
    
    def _add_list_item(self, text, is_ordered=False, index=0):
        """添加列表项"""
        prefix = f"{index}." if is_ordered else "•"
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setText(f"{prefix} {text}")
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 14px; color: #555; line-height: 1.8; padding: 3px 0 3px 20px;")
        self.content_layout.addWidget(label)
    
    def _add_image(self, image_name):
        """添加可点击的图片"""
        img_path = os.path.join(self._get_resource_path(), image_name)
        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                # 最大显示宽度
                max_width = 750
                if pixmap.width() > max_width:
                    pixmap = pixmap.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)
                
                img_label = ClickableImageLabel(img_path)
                img_label.setPixmap(pixmap)
                img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                img_label.setStyleSheet("padding: 10px 0;")
                
                # 添加提示文字
                hint_label = QLabel("👆 点击图片可放大查看")
                hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                hint_label.setStyleSheet("font-size: 12px; color: #888; padding-bottom: 10px;")
                
                self.content_layout.addWidget(img_label)
                self.content_layout.addWidget(hint_label)
    
    def _add_divider(self):
        """添加分隔线"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #ddd; margin: 20px 0;")
        self.content_layout.addWidget(line)
    
    def _add_faq(self, question, answer):
        """添加FAQ条目"""
        q_label = QLabel()
        q_label.setTextFormat(Qt.TextFormat.PlainText)
        q_label.setText(f"❓ {question}")
        q_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #333; padding: 8px 0 4px 0;")
        self.content_layout.addWidget(q_label)
        
        a_label = QLabel()
        a_label.setTextFormat(Qt.TextFormat.PlainText)
        a_label.setText(f"💡 {answer}")
        a_label.setWordWrap(True)
        a_label.setStyleSheet("font-size: 14px; color: #666; line-height: 1.8; padding: 4px 0 12px 25px;")
        self.content_layout.addWidget(a_label)
    
    @classmethod
    def _parse_tokens_from_md(cls, md_path):
        """解析 MD 文件为 token 列表（带类级缓存，文件未变则复用）"""
        try:
            mtime = os.path.getmtime(md_path)
        except OSError:
            return None
        if (
            cls._cached_tokens is not None
            and cls._cached_md_path == md_path
            and cls._cached_mtime == mtime
        ):
            return cls._cached_tokens

        tokens = []
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            list_stack = []

            for line in lines:
                line = line.rstrip()

                if not line:
                    continue

                if line.startswith('#'):
                    level = len(line) - len(line.lstrip('#'))
                    text = line.lstrip('#').strip()
                    tokens.append(('heading', text, level))
                    list_stack = []

                elif line.startswith('***') or line.startswith('---'):
                    tokens.append(('divider',))
                    list_stack = []

                elif line.startswith('!['):
                    img_match = re.search(r'!\[.*?\]\((.*?)\)', line)
                    if img_match:
                        tokens.append(('image', img_match.group(1)))
                    list_stack = []

                elif re.match(r'^\d+\.', line):
                    num = int(line.split('.')[0])
                    text = line.split('.', 1)[1].strip()
                    tokens.append(('list_ordered', text, num))
                    list_stack.append('ordered')

                elif line.startswith('- ') or line.startswith('* '):
                    text = line[2:].strip()
                    tokens.append(('list_unordered', text))
                    list_stack.append('unordered')

                elif line.startswith('Q:'):
                    q_text = line.replace('Q:', '').strip()
                    list_stack = ['faq_q', q_text]

                elif line.startswith('A:'):
                    a_text = line.replace('A:', '').strip()
                    if list_stack and list_stack[0] == 'faq_q':
                        tokens.append(('faq', list_stack[1], a_text))
                        list_stack = []

                else:
                    tokens.append(('paragraph', line))
                    list_stack = []

        except Exception:
            return None

        cls._cached_tokens = tokens
        cls._cached_mtime = mtime
        cls._cached_md_path = md_path
        return tokens

    def _load_tutorial_from_md(self):
        """从MD文件加载教程内容（优先使用缓存 token）"""
        md_path = os.path.join(self._get_resource_path(), "图文教程.md")

        if not os.path.exists(md_path):
            debug_info = f"教程文件未找到！\n尝试路径: {md_path}\n资源目录: {self._get_resource_path()}"
            self._add_paragraph(debug_info)
            self.content_layout.addStretch()
            return

        tokens = self._parse_tokens_from_md(md_path)

        if tokens is None:
            self._add_paragraph("加载教程失败: 无法读取或解析教程文件")
            self.content_layout.addStretch()
            return

        # 根据 token 构建 UI
        for token in tokens:
            t = token[0]
            if t == 'heading':
                self._add_heading(token[1], token[2])
            elif t == 'divider':
                self._add_divider()
            elif t == 'image':
                self._add_image(token[1])
            elif t == 'list_ordered':
                self._add_list_item(token[1], True, token[2])
            elif t == 'list_unordered':
                self._add_list_item(token[1], False)
            elif t == 'faq':
                self._add_faq(token[1], token[2])
            elif t == 'paragraph':
                self._add_paragraph(token[1])

        self.content_layout.addStretch()


class ParseWorker(QThread):
    finished = Signal(dict, str)
    error = Signal(str, str)

    def __init__(self, url: str, row_id: str):
        super().__init__()
        self.url = url
        self.row_id = row_id

    def run(self):
        try:
            bvid = extract_bvid(self.url)
            if not bvid:
                self.error.emit("无法从链接中提取BV号", self.row_id)
                return
            info = get_video_info(bvid)
            self.finished.emit(info, self.row_id)
        except Exception as e:
            self.error.emit(f"解析失败: {e}", self.row_id)


# 最大日志行数
MAX_LOG_LINES = 500


class BatchDownloadWorker(QThread):
    progress = Signal(float, float, float, float, float)
    log = Signal(str)
    task_progress = Signal(int, int)
    finished = Signal(bool, str)

    def __init__(self, tasks: list, save_dir: str, fmt: str):
        super().__init__()
        self.tasks = tasks
        self.save_dir = save_dir
        self.fmt = fmt
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            total_tasks = len(self.tasks)
            for task_idx, task in enumerate(self.tasks):
                if self._is_cancelled:
                    self.log.emit("下载已取消")
                    self.finished.emit(False, "用户取消")
                    return

                info = task["info"]
                start_p = task["start_p"]
                end_p = task["end_p"]
                custom_title = task.get("custom_title")

                bvid = info["bvid"]
                original_title = info["title"]
                title = custom_title if custom_title else original_title
                all_pages = info["pages"]
                total_pages = len(all_pages)

                self.log.emit(f"[{task_idx + 1}/{total_tasks}] 开始下载: {title}")

                pages_to_download = [
                    p for p in all_pages
                    if start_p <= p["page"] <= end_p
                ]

                if not pages_to_download:
                    self.log.emit(f"[{task_idx + 1}/{total_tasks}] 没有需要下载的分P，跳过")
                    self.task_progress.emit(task_idx + 1, total_tasks)
                    continue

                for page_info in pages_to_download:
                    if self._is_cancelled:
                        self.log.emit("下载已取消")
                        self.finished.emit(False, "用户取消")
                        return

                    page_num = page_info["page"]
                    cid = page_info["cid"]
                    part_name = page_info["part"]

                    self.log.emit(f"  获取 P{page_num} 音频流...")

                    audio_url = get_audio_url(bvid, cid)

                    filename = build_filename(title, part_name, page_num, total_pages, self.fmt)
                    save_path = os.path.join(self.save_dir, filename)

                    if os.path.isfile(save_path):
                        self.log.emit(f"  P{page_num} 已存在，跳过: {filename}")
                        continue

                    tmp_path = save_path + ".tmp"

                    self.log.emit(f"  下载 P{page_num}: {filename}")

                    def on_progress(percent, downloaded, total, speed, remaining):
                        self.progress.emit(percent, downloaded, total, speed, remaining)

                    download_file(audio_url, tmp_path, on_progress)

                    if self._is_cancelled:
                        if os.path.isfile(tmp_path):
                            os.remove(tmp_path)
                        self.log.emit("下载已取消")
                        self.finished.emit(False, "用户取消")
                        return

                    self.log.emit(f"  转换 P{page_num}...")
                    convert_audio(tmp_path, save_path, self.fmt)

                    self.log.emit(f"  P{page_num} 完成: {filename}")

                self.task_progress.emit(task_idx + 1, total_tasks)
                self.log.emit(f"[{task_idx + 1}/{total_tasks}] {title} 下载完成")

            self.log.emit("全部任务下载完成！")
            self.finished.emit(True, "下载完成")

        except Exception as e:
            self.log.emit(f"下载出错: {e}")
            self.finished.emit(False, str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.video_infos = {}
        self.download_worker = None
        self._parse_workers = []  # 跟踪所有解析工作线程
        self._bv_cache = None     # 缓存 BV 解析结果，避免重复解析 HTML
        self._setup_ui()
        self._apply_stylesheet()
    
    def closeEvent(self, event):
        """窗口关闭时清理资源"""
        try:
            # 取消下载
            if self.download_worker and self.download_worker.isRunning():
                self.download_worker.cancel()
                self.download_worker.wait()

            # 保留解析线程引用，让Qt自然处理
            event.accept()
        except Exception as e:
            print(f"关闭窗口时出错: {e}")
            event.accept()

    def _apply_stylesheet(self):
        """应用全局样式表"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6fa;
            }
            QLabel {
                font-size: 13px;
                color: #2d3436;
            }
            QPushButton {
                font-size: 13px;
                padding: 6px 16px;
                border: 1px solid #dcdde1;
                border-radius: 4px;
                background-color: #fafafa;
                color: #2d3436;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #bbb;
            }
            QPushButton:pressed {
                background-color: #ddd;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #999;
                border-color: #e0e0e0;
            }
            QLineEdit, QTextEdit, QSpinBox {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                padding: 4px 6px;
                background-color: white;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
                border-color: #4CAF50;
            }
            QTableWidget {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                background-color: white;
                gridline-color: #f0f0f0;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QHeaderView::section {
                background-color: #fafafa;
                border: none;
                border-bottom: 2px solid #e0e0e0;
                padding: 8px 6px;
                font-size: 12px;
                font-weight: bold;
                color: #555;
            }
            QProgressBar {
                border: 1px solid #dcdde1;
                border-radius: 6px;
                text-align: center;
                font-size: 12px;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 5px;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QSplitter::handle {
                background-color: #dcdde1;
                width: 2px;
                height: 2px;
            }
        """)

    def _setup_ui(self):
        self.setWindowTitle("B站视频音频下载工具")
        self.setMinimumSize(800, 700)
        self.resize(900, 750)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)

        title_label = QLabel("B站视频音频下载工具")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 6px;")
        main_layout.addWidget(title_label)

        nav_layout = QHBoxLayout()
        self.nav_btn1 = QPushButton("解析下载")
        self.nav_btn1.setFixedHeight(35)
        self.nav_btn1.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.nav_btn1.clicked.connect(lambda: self._switch_page(0))
        nav_layout.addWidget(self.nav_btn1)

        self.nav_btn2 = QPushButton("获取BV号")
        self.nav_btn2.setFixedHeight(35)
        self.nav_btn2.clicked.connect(lambda: self._switch_page(1))
        nav_layout.addWidget(self.nav_btn2)
        
        nav_layout.addStretch()
        
        self.help_btn = QPushButton("📖 图文教程")
        self.help_btn.setFixedHeight(35)
        self.help_btn.clicked.connect(self._open_tutorial)
        nav_layout.addWidget(self.help_btn)

        main_layout.addLayout(nav_layout)

        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        self._create_page1()
        self._create_page2()

        self.stacked_widget.setCurrentIndex(0)

    def _switch_page(self, index):
        self.stacked_widget.setCurrentIndex(index)
        # 活动按钮样式
        active_style = "background-color: #4CAF50; color: white; font-weight: bold; border-radius: 4px; border: none;"
        # 非活动按钮样式（保留明确的视觉状态）
        inactive_style = "background-color: #fafafa; color: #555; border: 1px solid #dcdde1; border-radius: 4px;"
        self.nav_btn1.setStyleSheet(active_style if index == 0 else inactive_style)
        self.nav_btn2.setStyleSheet(active_style if index == 1 else inactive_style)

    def _create_page1(self):
        page1 = QWidget()
        layout = QVBoxLayout(page1)
        layout.setSpacing(8)

        # 确保默认保存目录存在
        os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)

        layout.addWidget(QLabel("视频链接（每行一个）:"))
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText(
            "请输入B站视频链接，每行一个，例如:\n"
            "https://www.bilibili.com/video/BVxxxxxx\n"
            "https://www.bilibili.com/video/BVyyyyyy"
        )
        self.url_input.setFixedHeight(80)
        layout.addWidget(self.url_input)

        url_btn_layout = QHBoxLayout()
        self.parse_btn = QPushButton("解析全部")
        self.parse_btn.setFixedHeight(32)
        self.parse_btn.clicked.connect(self._on_parse_all)
        url_btn_layout.addWidget(self.parse_btn)
        url_btn_layout.addStretch()
        layout.addLayout(url_btn_layout)

        # 任务列表标题和统计
        task_header_layout = QHBoxLayout()
        task_header_layout.addWidget(QLabel("任务列表:"))
        self.task_count_label = QLabel("共 0 个任务")
        self.task_count_label.setStyleSheet("color: #666;")
        task_header_layout.addWidget(self.task_count_label)
        task_header_layout.addStretch()
        layout.addLayout(task_header_layout)

        # 任务表格容器，使用QFrame来确保边界清晰
        table_container = QFrame()
        table_container.setFrameShape(QFrame.Shape.StyledPanel)
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.task_table = QTableWidget(0, 6)
        self.task_table.setHorizontalHeaderLabels(["标题", "修改后标题", "起始P", "结束P", "总P数", "状态"])
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.task_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.task_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.task_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.task_table.setColumnWidth(2, 65)
        self.task_table.setColumnWidth(3, 65)
        self.task_table.setColumnWidth(4, 55)
        self.task_table.setColumnWidth(5, 80)
        self.task_table.setMinimumHeight(150)
        self.task_table.verticalHeader().setVisible(False)
        table_layout.addWidget(self.task_table)
        layout.addWidget(table_container)

        # 按钮容器，设置足够的边距确保不与表格重叠
        button_container = QWidget()
        table_btn_layout = QHBoxLayout(button_container)
        table_btn_layout.setContentsMargins(0, 10, 0, 10)  # 增加上下边距
        table_btn_layout.setSpacing(10)  # 增加按钮间距
        self.remove_btn = QPushButton("删除选中")
        self.remove_btn.setFixedSize(100, 28)
        self.remove_btn.clicked.connect(self._on_remove_selected)
        table_btn_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("清空列表")
        self.clear_btn.setFixedSize(100, 28)
        self.clear_btn.clicked.connect(self._on_clear_list)
        table_btn_layout.addWidget(self.clear_btn)
        table_btn_layout.addStretch()
        layout.addWidget(button_container)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("保存目录:"))
        self.dir_input = QLineEdit(DEFAULT_SAVE_DIR)
        dir_layout.addWidget(self.dir_input)
        self.dir_btn = QPushButton("选择")
        self.dir_btn.setFixedWidth(60)
        self.dir_btn.clicked.connect(self._choose_dir)
        dir_layout.addWidget(self.dir_btn)
        layout.addLayout(dir_layout)

        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("下载格式:"))
        self.radio_mp3 = QRadioButton("mp3 (需要ffmpeg转码)")
        self.radio_m4a = QRadioButton("m4a (无需转码)")
        self.radio_mp3.setChecked(True)
        fmt_group = QButtonGroup(self)
        fmt_group.addButton(self.radio_mp3)
        fmt_group.addButton(self.radio_m4a)
        fmt_layout.addWidget(self.radio_mp3)
        fmt_layout.addWidget(self.radio_m4a)
        fmt_layout.addStretch()
        layout.addLayout(fmt_layout)

        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("批量下载")
        self.download_btn.setFixedHeight(36)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._on_batch_download)
        btn_layout.addWidget(self.download_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(120)
        layout.addWidget(self.log_text)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

        self.stacked_widget.addWidget(page1)

    def _create_page2(self):
        page2 = QWidget()
        layout = QVBoxLayout(page2)
        layout.setSpacing(8)

        layout.addWidget(QLabel("收藏夹HTML源码（用于提取BV号）:"))
        self.html_input = QTextEdit()
        self.html_input.setPlaceholderText(
            "请在此处粘贴B站收藏夹页面的HTML源码...\n\n"
            "获取方法：\n"
            "1. 在浏览器中打开B站收藏夹页面\n"
            "2. 按F12打开开发者工具\n"
            "3. 在Elements标签页中，右键<html>标签\n"
            "4. 选择Copy -> Copy outerHTML\n"
            "5. 粘贴到这里，点击解析BV号\n"
            "\n提示：翻页后重复以上步骤获取更多视频"
        )
        self.html_input.setMinimumHeight(180)
        layout.addWidget(self.html_input)

        html_btn_layout = QHBoxLayout()
        self.parse_bv_btn = QPushButton("解析BV号")
        self.parse_bv_btn.setFixedHeight(32)
        self.parse_bv_btn.clicked.connect(self._on_parse_bv)
        html_btn_layout.addWidget(self.parse_bv_btn)

        self.clear_bv_btn = QPushButton("清空")
        self.clear_bv_btn.setFixedHeight(32)
        self.clear_bv_btn.clicked.connect(self._on_clear_bv)
        html_btn_layout.addWidget(self.clear_bv_btn)
        html_btn_layout.addStretch()
        layout.addLayout(html_btn_layout)

        layout.addWidget(QLabel("解析结果:"))
        self.bv_result_text = QTextEdit()
        self.bv_result_text.setReadOnly(True)
        self.bv_result_text.setMinimumHeight(150)
        self.bv_result_text.setPlaceholderText("解析到的BV号将显示在这里...")
        layout.addWidget(self.bv_result_text)

        result_btn_layout = QHBoxLayout()
        self.copy_bv_btn = QPushButton("复制全部")
        self.copy_bv_btn.setFixedHeight(32)
        self.copy_bv_btn.clicked.connect(self._on_copy_bv)
        self.copy_bv_btn.setEnabled(False)
        result_btn_layout.addWidget(self.copy_bv_btn)

        self.load_bv_btn = QPushButton("载入到解析下载")
        self.load_bv_btn.setFixedHeight(32)
        self.load_bv_btn.clicked.connect(self._on_load_bv)
        self.load_bv_btn.setEnabled(False)
        result_btn_layout.addWidget(self.load_bv_btn)
        result_btn_layout.addStretch()
        layout.addLayout(result_btn_layout)

        self.bv_status_label = QLabel("就绪")
        layout.addWidget(self.bv_status_label)

        self.stacked_widget.addWidget(page2)

    def _extract_bv_from_html(self, html_content):
        soup = BeautifulSoup(html_content, 'lxml')
        
        # 使用CSS选择器定位a标签
        selector = '#app > main > div.space-favlist > div.favlist-main > div.fav-list-main > div.items > div > div > div > div.bili-video-card__cover > a'
        a_tags = soup.select(selector)
        
        bv_pattern = r'BV[0-9A-Za-z]{10}'
        results = []
        seen_bvs = set()
        
        for a_tag in a_tags:
            href = a_tag.get('href', '')
            bv_match = re.search(bv_pattern, href)
            if bv_match:
                bv = bv_match.group(0)
                if bv not in seen_bvs:
                    seen_bvs.add(bv)
                    results.append({
                        'bv': bv,
                        'url': f'https://www.bilibili.com/video/{bv}'
                    })
        
        return results

    def _parse_bv_from_html(self):
        """解析 BV 号（带缓存），返回列表或从缓存读取"""
        html_content = self.html_input.toPlainText().strip()
        if not html_content:
            return None
        # 仅在内容变化时重新解析
        if self._bv_cache and self._bv_cache.get("html") == html_content:
            return self._bv_cache.get("results", [])
        results = self._extract_bv_from_html(html_content)
        self._bv_cache = {"html": html_content, "results": results}
        return results

    def _on_parse_bv(self):
        html_content = self.html_input.toPlainText().strip()

        if not html_content:
            QMessageBox.warning(self, "提示", "请先粘贴HTML源码！")
            return

        self.bv_status_label.setText("正在解析...")

        try:
            results = self._parse_bv_from_html() or []

            if not results:
                self.bv_result_text.setPlainText("未找到BV号")
                self.bv_status_label.setText("未找到BV号")
                self.copy_bv_btn.setEnabled(False)
                self.load_bv_btn.setEnabled(False)
                return

            display_text = f"找到 {len(results)} 个BV号：\n"
            display_text += "=" * 50 + "\n\n"

            for i, item in enumerate(results, 1):
                display_text += f"{i}. BV号: {item['bv']}\n"
                display_text += f"   链接: {item['url']}\n\n"

            self.bv_result_text.setPlainText(display_text)
            self.bv_status_label.setText(f"解析完成，找到 {len(results)} 个BV号")
            self.copy_bv_btn.setEnabled(True)
            self.load_bv_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"解析失败: {str(e)}")
            self.bv_status_label.setText("解析失败")

    def _on_clear_bv(self):
        self.html_input.clear()
        self.bv_result_text.clear()
        self.copy_bv_btn.setEnabled(False)
        self.load_bv_btn.setEnabled(False)
        self.bv_status_label.setText("就绪")
        self._bv_cache = None

    def _on_copy_bv(self):
        results = self._parse_bv_from_html() or []
        if results:
            urls = '\n'.join([item['url'] for item in results])
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(urls)
            self.bv_status_label.setText("已复制全部链接到剪贴板！")

    def _on_load_bv(self):
        results = self._parse_bv_from_html() or []
        if results:
            urls = '\n'.join([item['url'] for item in results])
            self.url_input.setPlainText(urls)
            self._switch_page(0)
            self.bv_status_label.setText(f"已载入 {len(results)} 个链接到解析下载页面！")

    def _log(self, msg: str):
        self.log_text.append(msg)
        # 限制日志行数，防止内存无限增长
        if self.log_text.document().blockCount() > MAX_LOG_LINES:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # 删除残留的换行符

    def _choose_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if dir_path:
            self.dir_input.setText(dir_path)

    def _update_task_count(self):
        """更新任务数量显示"""
        count = self.task_table.rowCount()
        self.task_count_label.setText(f"共 {count} 个任务")

    def _on_parse_all(self):
        text = self.url_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入视频链接")
            return

        urls = [line.strip() for line in text.splitlines() if line.strip()]
        if not urls:
            QMessageBox.warning(self, "提示", "请输入视频链接")
            return

        self.parse_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self._pending_parse = 0
        self._total_parse = len(urls)

        # 批量插入时暂停界面重绘，提升性能
        self.task_table.setUpdatesEnabled(False)
        try:
            for url in urls:
                row = self.task_table.rowCount()
                self.task_table.insertRow(row)

                title_item = QTableWidgetItem("解析中...")
                title_item.setFlags(title_item.flags() & ~Qt.ItemIsEditable)
                self.task_table.setItem(row, 0, title_item)

                custom_title_item = QTableWidgetItem("")
                self.task_table.setItem(row, 1, custom_title_item)

                start_spin = QSpinBox()
                start_spin.setMinimum(1)
                start_spin.setMaximum(9999)
                start_spin.setValue(1)
                self.task_table.setCellWidget(row, 2, start_spin)

                end_spin = QSpinBox()
                end_spin.setMinimum(1)
                end_spin.setMaximum(9999)
                end_spin.setValue(1)
                self.task_table.setCellWidget(row, 3, end_spin)

                total_item = QTableWidgetItem("-")
                total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
                total_item.setTextAlignment(Qt.AlignCenter)
                self.task_table.setItem(row, 4, total_item)

                status_item = QTableWidgetItem("解析中...")
                status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
                self.task_table.setItem(row, 5, status_item)

                self._pending_parse += 1

                worker = ParseWorker(url, str(row))
                worker.finished.connect(self._on_parse_finished)
                worker.error.connect(self._on_parse_error)
                worker.start()

                # 保存到列表中，保持引用但不主动删除
                self._parse_workers.append(worker)
        finally:
            # 恢复界面重绘
            self.task_table.setUpdatesEnabled(True)

        self._update_task_count()
        self._log(f"正在解析 {len(urls)} 个链接...")

    def _on_parse_complete(self):
        """解析全部完成时的统一处理"""
        self.parse_btn.setEnabled(True)
        has_valid = len(self.video_infos) > 0
        self.download_btn.setEnabled(has_valid)
        # 清理已完成的 worker 引用
        self._parse_workers = [
            w for w in self._parse_workers
            if w.isRunning()
        ]

    def _on_parse_finished(self, info: dict, row_id: str):
        try:
            row = int(row_id)

            # 安全检查
            if row < 0 or row >= self.task_table.rowCount():
                self._log(f"警告: 无效的行号 {row}")
                return

            total_pages = len(info.get("pages", []))

            title_item = self.task_table.item(row, 0)
            if title_item:
                title_item.setText(info.get("title", "未知标题"))
                title_item.setData(Qt.UserRole, info.get("bvid", ""))  # 存储 BV 号作为唯一标识

            total_pages_item = self.task_table.item(row, 4)
            if total_pages_item:
                total_pages_item.setText(str(total_pages))

            status_item = self.task_table.item(row, 5)
            if status_item:
                status_item.setText("已解析")

            end_spin = self.task_table.cellWidget(row, 3)
            if end_spin:
                end_spin.setValue(total_pages)
                end_spin.setMaximum(max(1, total_pages))  # 确保至少有1页

            start_spin = self.task_table.cellWidget(row, 2)
            if start_spin:
                start_spin.setMaximum(max(1, total_pages))

            self.video_infos[row] = info

            self._log(f"解析成功: {info.get('title', '未知')} (共{total_pages}P)")
        except Exception as e:
            self._log(f"处理解析结果时出错: {e}")
            import traceback
            self._log(f"错误详情: {traceback.format_exc()}")
        finally:
            # 更新解析状态
            self._pending_parse -= 1
            if self._pending_parse <= 0:
                self._on_parse_complete()
                self._log(f"{self._total_parse}个已解析完成！")

    def _on_parse_error(self, err: str, row_id: str):
        try:
            row = int(row_id)

            if 0 <= row < self.task_table.rowCount():
                title_item = self.task_table.item(row, 0)
                if title_item:
                    title_item.setText("解析失败")
                status_item = self.task_table.item(row, 5)
                if status_item:
                    status_item.setText("失败")

            self._log(f"第{row + 1}行解析失败: {err}")
        except Exception as e:
            self._log(f"处理解析错误时出错: {e}")
        finally:
            # 更新解析状态
            self._pending_parse -= 1
            if self._pending_parse <= 0:
                self._on_parse_complete()
                self._log(f"{self._total_parse}个已解析完成（部分失败）")

    def _on_remove_selected(self):
        rows = set(item.row() for item in self.task_table.selectedItems())
        if not rows:
            return
        self.task_table.setUpdatesEnabled(False)
        try:
            for row in sorted(rows, reverse=True):
                if row in self.video_infos:
                    del self.video_infos[row]
                self.task_table.removeRow(row)
        finally:
            self.task_table.setUpdatesEnabled(True)
        self.video_infos = self._rebuild_info_map()
        self.download_btn.setEnabled(len(self.video_infos) > 0)
        self._update_task_count()

    def _on_clear_list(self):
        self.task_table.setRowCount(0)
        self.video_infos.clear()
        self.download_btn.setEnabled(False)
        self._update_task_count()

    def _rebuild_info_map(self):
        new_map = {}
        try:
            # 先创建一个 BV 号到信息的映射
            bv_to_info = {}
            for v in self.video_infos.values():
                if isinstance(v, dict) and "bvid" in v:
                    bv_to_info[v["bvid"]] = v
            
            for row in range(self.task_table.rowCount()):
                try:
                    title_item = self.task_table.item(row, 0)
                    if title_item:
                        bvid = title_item.data(Qt.UserRole)
                        if bvid and bvid in bv_to_info:
                            new_map[row] = bv_to_info[bvid]
                except Exception as e:
                    self._log(f"处理第 {row} 行时出错: {e}")
                    continue
        except Exception as e:
            self._log(f"重建信息映射时出错: {e}")
            import traceback
            self._log(f"错误详情: {traceback.format_exc()}")
        return new_map

    def _on_batch_download(self):
        if not self.video_infos:
            QMessageBox.warning(self, "提示", "请先解析视频")
            return

        save_dir = self.dir_input.text().strip()
        if not save_dir:
            QMessageBox.warning(self, "提示", "请选择保存目录")
            return

        fmt = "mp3" if self.radio_mp3.isChecked() else "m4a"

        if fmt == "mp3" and not is_ffmpeg_available():
            reply = QMessageBox.question(
                self, "提示",
                "未检测到 ffmpeg，mp3 格式需要 ffmpeg 进行转码。\n"
                "是否改用 m4a 格式？（m4a 无需转码，音质更好）",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                fmt = "m4a"
                self.radio_m4a.setChecked(True)
            else:
                return

        os.makedirs(save_dir, exist_ok=True)

        tasks = []
        for row in range(self.task_table.rowCount()):
            if row not in self.video_infos:
                continue

            start_spin = self.task_table.cellWidget(row, 2)
            end_spin = self.task_table.cellWidget(row, 3)

            if start_spin is None or end_spin is None:
                continue

            start_p = start_spin.value()
            end_p = end_spin.value()

            custom_title_item = self.task_table.item(row, 1)
            custom_title = custom_title_item.text().strip() if custom_title_item else ""

            if start_p > end_p:
                self._log(f"第{row + 1}行P范围无效，跳过")
                continue

            tasks.append({
                "info": self.video_infos[row],
                "start_p": start_p,
                "end_p": end_p,
                "custom_title": custom_title,
            })

        if not tasks:
            QMessageBox.warning(self, "提示", "没有有效的下载任务")
            return

        self.download_btn.setEnabled(False)
        self.parse_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)

        self.download_worker = BatchDownloadWorker(tasks, save_dir, fmt)
        self.download_worker.log.connect(self._log)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.task_progress.connect(self._on_task_progress)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.start()

    def _on_download_progress(self, percent, downloaded, total, speed, remaining):
        self.progress_bar.setValue(int(percent))
        speed_mb = speed / 1024 / 1024
        if remaining > 60:
            remain_str = f"{remaining / 60:.1f}分钟"
        else:
            remain_str = f"{remaining:.0f}秒"
        self.status_label.setText(
            f"下载中: {percent:.1f}% | 速度: {speed_mb:.2f} MB/s | 剩余: {remain_str}"
        )

    def _on_task_progress(self, current, total):
        self.status_label.setText(f"任务进度: {current}/{total}")

    def _on_download_finished(self, success: bool, msg: str):
        self.download_btn.setEnabled(True)
        self.parse_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("全部下载完成")
        else:
            self.status_label.setText(f"下载结束: {msg}")

    def _on_cancel(self):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            self._log("正在取消下载...")
    
    def _open_tutorial(self):
        """打开图文教程"""
        dialog = TutorialDialog(self)
        dialog.exec()
