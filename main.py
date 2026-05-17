import sys
import os
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, qInstallMessageHandler, QtMsgType
from gui.main_window import MainWindow


def log_to_file(message):
    """将错误信息记录到文件"""
    try:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except:
        pass


def exception_hook(exctype, value, tb):
    """全局异常捕获"""
    error_msg = ''.join(traceback.format_exception(exctype, value, tb))
    print(error_msg)
    log_to_file(error_msg)
    
    # 尝试显示错误消息框
    try:
        msg = f"程序发生未处理的异常：\n\n{str(value)}\n\n详细信息已保存到日志文件。"
        QMessageBox.critical(None, "严重错误", msg)
    except:
        pass
    
    sys.__excepthook__(exctype, value, tb)


def qt_message_handler(msg_type, context, msg):
    """Qt 消息处理"""
    log_msg = f"Qt {msg_type}: {msg}"
    if msg_type == QtMsgType.QtCriticalMsg or msg_type == QtMsgType.QtFatalMsg:
        log_to_file(log_msg)
    print(log_msg)


def main():
    # 安装异常和消息处理器
    sys.excepthook = exception_hook
    qInstallMessageHandler(qt_message_handler)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        error_msg = f"程序启动失败: {e}\n{traceback.format_exc()}"
        print(error_msg)
        log_to_file(error_msg)
        QMessageBox.critical(None, "启动错误", f"程序启动失败：\n{str(e)}")


if __name__ == "__main__":
    main()
