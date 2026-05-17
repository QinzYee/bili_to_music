import os
import re
import tempfile
import webbrowser
import sys
from bs4 import BeautifulSoup
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QProgressBar, QRadioButton, QButtonGroup,
    QFileDialog, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QSpinBox,
    QStackedWidget, QSplitter, QFrame, QDialog, QScrollArea, QGraphicsView, QGraphicsScene, QApplication
)
from PySide6.QtCore import QThread, Signal, Qt, QSize
from PySide6.QtGui import QGuiApplication, QClipboard, QPixmap, QImage

from core.bilibili_api import extract_bvid, get_video_info, get_audio_url
from core.downloader import download_file
from core.audio_utils import convert_audio, is_ffmpeg_available
from utils.filename_utils import build_filename
from config import DEFAULT_SAVE_DIR, DEFAULT_FORMAT, MAX_WORKERS


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
    """图文教程对话框 - 读取真实MD文件"""
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
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), 'resources')
        else:
            return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources')
    
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
    
    def _load_tutorial_from_md(self):
        """从MD文件加载教程内容"""
        md_path = os.path.join(self._get_resource_path(), "图文教程.md")
        
        if not os.path.exists(md_path):
            self._add_paragraph("教程文件未找到！")
            self.content_layout.addStretch()
            return
        
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析MD
            lines = content.split('\n')
            list_stack = []  # 跟踪列表状态
            
            for line in lines:
                line = line.rstrip()
                
                # 空行
                if not line:
                    continue
                
                # 标题
                if line.startswith('#'):
                    level = len(line) - len(line.lstrip('#'))
                    text = line.lstrip('#').strip()
                    self._add_heading(text, level)
                    list_stack = []
                
                # 分隔线
                elif line.startswith('***') or line.startswith('---'):
                    self._add_divider()
                    list_stack = []
                
                # 图片
                elif line.startswith('!['):
                    # 解析 ![alt](filename.png)
                    img_match = re.search(r'!\[.*?\]\((.*?)\)', line)
                    if img_match:
                        img_name = img_match.group(1)
                        self._add_image(img_name)
                    list_stack = []
                
                # 有序列表
                elif re.match(r'^\d+\.', line):
                    num = int(line.split('.')[0])
                    text = line.split('.', 1)[1].strip()
                    self._add_list_item(text, True, num)
                    list_stack.append('ordered')
                
                # 无序列表
                elif line.startswith('- ') or line.startswith('* '):
                    text = line[2:].strip()
                    self._add_list_item(text, False)
                    list_stack.append('unordered')
                
                # FAQ Q
                elif line.startswith('Q:'):
                    q_text = line.replace('Q:', '').strip()
                    list_stack = ['faq_q', q_text]
                
                # FAQ A
                elif line.startswith('A:'):
                    a_text = line.replace('A:', '').strip()
                    if list_stack and list_stack[0] == 'faq_q':
                        self._add_faq(list_stack[1], a_text)
                        list_stack = []
                
                # 普通段落
                else:
                    self._add_paragraph(line)
                    list_stack = []
            
            self.content_layout.addStretch()
            
        except Exception as e:
            self._add_paragraph(f"加载教程失败: {str(e)}")
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
                    if self.fmt == "m4a":
                        if os.path.isfile(tmp_path):
                            os.replace(tmp_path, save_path)
                    else:
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
        self._setup_ui()

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
        self.nav_btn1.setStyleSheet("" if index != 0 else "background-color: #4CAF50; color: white; font-weight: bold;")
        self.nav_btn2.setStyleSheet("" if index != 1 else "background-color: #4CAF50; color: white; font-weight: bold;")

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

    def _on_parse_bv(self):
        html_content = self.html_input.toPlainText().strip()
        
        if not html_content:
            QMessageBox.warning(self, "提示", "请先粘贴HTML源码！")
            return

        self.bv_status_label.setText("正在解析...")
        
        try:
            results = self._extract_bv_from_html(html_content)
            
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

    def _on_copy_bv(self):
        results = self._extract_bv_from_html(self.html_input.toPlainText())
        if results:
            urls = '\n'.join([item['url'] for item in results])
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(urls)
            self.bv_status_label.setText("已复制全部链接到剪贴板！")

    def _on_load_bv(self):
        results = self._extract_bv_from_html(self.html_input.toPlainText())
        if results:
            urls = '\n'.join([item['url'] for item in results])
            self.url_input.setPlainText(urls)
            self._switch_page(0)
            self.bv_status_label.setText(f"已载入 {len(results)} 个链接到解析下载页面！")

    def _log(self, msg: str):
        self.log_text.append(msg)

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
            setattr(self, f"_parse_worker_{row}", worker)

        self._update_task_count()
        self._log(f"正在解析 {len(urls)} 个链接...")

    def _on_parse_finished(self, info: dict, row_id: str):
        row = int(row_id)
        total_pages = len(info["pages"])

        self.task_table.item(row, 0).setText(info["title"])
        self.task_table.item(row, 4).setText(str(total_pages))
        self.task_table.item(row, 5).setText("已解析")

        end_spin = self.task_table.cellWidget(row, 3)
        if end_spin:
            end_spin.setValue(total_pages)
            end_spin.setMaximum(total_pages)

        start_spin = self.task_table.cellWidget(row, 2)
        if start_spin:
            start_spin.setMaximum(total_pages)

        self.video_infos[row] = info

        self._log(f"解析成功: {info['title']} (共{total_pages}P)")

        self._pending_parse -= 1
        if self._pending_parse <= 0:
            self.parse_btn.setEnabled(True)
            self.download_btn.setEnabled(True)
            self._log(f"{self._total_parse}个已解析完成！")

    def _on_parse_error(self, err: str, row_id: str):
        row = int(row_id)
        self.task_table.item(row, 0).setText("解析失败")
        self.task_table.item(row, 5).setText("失败")
        self._log(f"第{row + 1}行解析失败: {err}")

        self._pending_parse -= 1
        if self._pending_parse <= 0:
            self.parse_btn.setEnabled(True)
            has_valid = any(row in self.video_infos for row in range(self.task_table.rowCount()))
            self.download_btn.setEnabled(has_valid)
            self._log(f"{self._total_parse}个已解析完成（部分失败）")

    def _on_remove_selected(self):
        rows = set(item.row() for item in self.task_table.selectedItems())
        for row in sorted(rows, reverse=True):
            if row in self.video_infos:
                del self.video_infos[row]
            self.task_table.removeRow(row)
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
        for row in range(self.task_table.rowCount()):
            old_key = None
            for k, v in self.video_infos.items():
                if self.task_table.item(row, 0) and v["title"] == self.task_table.item(row, 0).text():
                    old_key = k
                    break
            if old_key is not None and old_key in self.video_infos:
                new_map[row] = self.video_infos[old_key]
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
