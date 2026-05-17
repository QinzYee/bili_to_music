import os
import shutil
import subprocess
import zipfile
from datetime import datetime

APP_NAME = "BilibiliAudioDownloader"
APP_VERSION = "1.0.0"
DIST_DIR = "dist"
BUILD_DIR = os.path.join(DIST_DIR, APP_NAME)
OUTPUT_DIR = "output"
ZIP_NAME = f"{APP_NAME}_v{APP_VERSION}_{datetime.now().strftime('%Y%m%d')}.zip"


def clean_old_build():
    print("清理旧的构建文件...")
    for d in [DIST_DIR, OUTPUT_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def build_pyinstaller():
    print("使用PyInstaller构建程序...")
    cmd = [
        "pyinstaller",
        "main.py",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", APP_NAME,
        "--icon", "resources/icon.ico",
        "--add-data", "resources/ffmpeg.exe;resources",
        "--add-data", "resources/icon.ico;resources",
        "--add-data", "resources/图文教程.md;resources",
        "--add-data", "resources/提取bv图文教程1.png;resources",
        "--add-data", "resources/提取bv图文教程2.png;resources",
        "--add-data", "resources/界面预览.png;resources",
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise Exception("PyInstaller构建失败")


def create_zip():
    print(f"创建压缩包: {ZIP_NAME}...")
    zip_path = os.path.join(OUTPUT_DIR, ZIP_NAME)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BUILD_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.join(APP_NAME, os.path.relpath(file_path, BUILD_DIR))
                zf.write(file_path, arcname)

    print(f"压缩包已创建: {os.path.abspath(zip_path)}")
    return zip_path


def create_readme_in_package():
    readme_content = """B站视频音频下载工具
================

使用说明：
1. 双击 {APP_NAME}.exe 运行程序
2. 在链接输入框粘贴B站视频链接（支持多个）
3. 点击"解析全部"按钮
4. 可在任务列表中修改下载的P范围和文件标题
5. 选择保存目录和下载格式
6. 点击"批量下载"开始下载

注意：
- mp3格式需要ffmpeg（已包含在resources目录中）
- 本工具仅供学习使用，请遵守相关法律法规
- 下载内容版权归原作者所有
""".format(APP_NAME=APP_NAME)

    readme_path = os.path.join(BUILD_DIR, "使用说明.txt")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)


def main():
    try:
        clean_old_build()
        build_pyinstaller()
        create_readme_in_package()
        create_zip()
        print("\n构建完成！")
        print(f"压缩包位置: {os.path.abspath(os.path.join(OUTPUT_DIR, ZIP_NAME))}")
        print("解压缩后即可使用！")
    except Exception as e:
        print(f"\n构建失败: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
