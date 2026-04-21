import os

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QProgressBar, QRadioButton, QButtonGroup,
    QFileDialog, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QSpinBox,
)
from PySide6.QtCore import QThread, Signal, Qt

from core.bilibili_api import extract_bvid, get_video_info, get_audio_url
from core.downloader import download_file
from core.audio_utils import convert_audio, is_ffmpeg_available
from utils.filename_utils import build_filename
from config import DEFAULT_SAVE_DIR, DEFAULT_FORMAT, MAX_WORKERS


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

                bvid = info["bvid"]
                title = info["title"]
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

            self.log.emit("全部任务下载完成!")
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
        self.setMinimumSize(700, 650)
        self.resize(750, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)

        title_label = QLabel("B站视频音频下载工具")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 6px;")
        layout.addWidget(title_label)

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

        layout.addWidget(QLabel("任务列表:"))
        self.task_table = QTableWidget(0, 5)
        self.task_table.setHorizontalHeaderLabels(["标题", "起始P", "结束P", "总P数", "状态"])
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.task_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.task_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.task_table.setColumnWidth(1, 65)
        self.task_table.setColumnWidth(2, 65)
        self.task_table.setColumnWidth(3, 55)
        self.task_table.setColumnWidth(4, 80)
        self.task_table.setMinimumHeight(150)
        self.task_table.verticalHeader().setVisible(False)
        layout.addWidget(self.task_table)

        table_btn_layout = QHBoxLayout()
        self.remove_btn = QPushButton("删除选中")
        self.remove_btn.setFixedHeight(28)
        self.remove_btn.clicked.connect(self._on_remove_selected)
        table_btn_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("清空列表")
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.clicked.connect(self._on_clear_list)
        table_btn_layout.addWidget(self.clear_btn)
        table_btn_layout.addStretch()
        layout.addLayout(table_btn_layout)

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
        self.radio_m4a = QRadioButton("m4a (推荐，无需转码)")
        self.radio_mp3 = QRadioButton("mp3 (需要ffmpeg转码)")
        self.radio_m4a.setChecked(True)
        fmt_group = QButtonGroup(self)
        fmt_group.addButton(self.radio_m4a)
        fmt_group.addButton(self.radio_mp3)
        fmt_layout.addWidget(self.radio_m4a)
        fmt_layout.addWidget(self.radio_mp3)
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

    def _log(self, msg: str):
        self.log_text.append(msg)

    def _choose_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if dir_path:
            self.dir_input.setText(dir_path)

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

            start_spin = QSpinBox()
            start_spin.setMinimum(1)
            start_spin.setMaximum(9999)
            start_spin.setValue(1)
            self.task_table.setCellWidget(row, 1, start_spin)

            end_spin = QSpinBox()
            end_spin.setMinimum(1)
            end_spin.setMaximum(9999)
            end_spin.setValue(1)
            self.task_table.setCellWidget(row, 2, end_spin)

            total_item = QTableWidgetItem("-")
            total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
            total_item.setTextAlignment(Qt.AlignCenter)
            self.task_table.setItem(row, 3, total_item)

            status_item = QTableWidgetItem("解析中...")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self.task_table.setItem(row, 4, status_item)

            self._pending_parse += 1

            worker = ParseWorker(url, str(row))
            worker.finished.connect(self._on_parse_finished)
            worker.error.connect(self._on_parse_error)
            worker.start()
            setattr(self, f"_parse_worker_{row}", worker)

        self._log(f"正在解析 {len(urls)} 个链接...")

    def _on_parse_finished(self, info: dict, row_id: str):
        row = int(row_id)
        total_pages = len(info["pages"])

        self.task_table.item(row, 0).setText(info["title"])
        self.task_table.item(row, 3).setText(str(total_pages))
        self.task_table.item(row, 4).setText("已解析")

        end_spin = self.task_table.cellWidget(row, 2)
        if end_spin:
            end_spin.setValue(total_pages)
            end_spin.setMaximum(total_pages)

        start_spin = self.task_table.cellWidget(row, 1)
        if start_spin:
            start_spin.setMaximum(total_pages)

        self.video_infos[row] = info

        self._log(f"解析成功: {info['title']} (共{total_pages}P)")

        self._pending_parse -= 1
        if self._pending_parse <= 0:
            self.parse_btn.setEnabled(True)
            self.download_btn.setEnabled(True)
            self._log("全部解析完成!")

    def _on_parse_error(self, err: str, row_id: str):
        row = int(row_id)
        self.task_table.item(row, 0).setText("解析失败")
        self.task_table.item(row, 4).setText("失败")
        self._log(f"第{row + 1}行解析失败: {err}")

        self._pending_parse -= 1
        if self._pending_parse <= 0:
            self.parse_btn.setEnabled(True)
            has_valid = any(row in self.video_infos for row in range(self.task_table.rowCount()))
            self.download_btn.setEnabled(has_valid)
            self._log("解析完成（部分失败）")

    def _on_remove_selected(self):
        rows = set(item.row() for item in self.task_table.selectedItems())
        for row in sorted(rows, reverse=True):
            if row in self.video_infos:
                del self.video_infos[row]
            self.task_table.removeRow(row)
        self.video_infos = self._rebuild_info_map()
        self.download_btn.setEnabled(len(self.video_infos) > 0)

    def _on_clear_list(self):
        self.task_table.setRowCount(0)
        self.video_infos.clear()
        self.download_btn.setEnabled(False)

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

        fmt = "m4a" if self.radio_m4a.isChecked() else "mp3"

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

            start_spin = self.task_table.cellWidget(row, 1)
            end_spin = self.task_table.cellWidget(row, 2)

            if start_spin is None or end_spin is None:
                continue

            start_p = start_spin.value()
            end_p = end_spin.value()

            if start_p > end_p:
                self._log(f"第{row + 1}行P范围无效，跳过")
                continue

            tasks.append({
                "info": self.video_infos[row],
                "start_p": start_p,
                "end_p": end_p,
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
