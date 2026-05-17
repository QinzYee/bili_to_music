import os
import shutil
import zipfile
from datetime import datetime

APP_NAME = "BilibiliAudioDownloader"
APP_VERSION = "1.0.0"
BUILD_DIR = os.path.join("dist", APP_NAME)
OUTPUT_DIR = "output"
ZIP_NAME = f"{APP_NAME}_v{APP_VERSION}_{datetime.now().strftime('%Y%m%d')}.zip"

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 验证资源文件
print("验证资源文件...")
required_files = [
    "resources/ffmpeg.exe",
    "resources/icon.ico",
    "resources/图文教程.md",
    "resources/提取bv图文教程1.png",
    "resources/提取bv图文教程2.png",
    "resources/界面预览.png",
]

all_found = True
for f in required_files:
    full_path = os.path.join(BUILD_DIR, "_internal", f)
    if os.path.exists(full_path):
        print(f"[OK] {f}")
    else:
        print(f"[X] {f} (未找到)")
        all_found = False

if all_found:
    print("所有资源文件验证通过！")
else:
    print("部分资源文件缺失！")

# 创建使用说明
readme_content = """B站视频音频下载工具
================

使用说明：
1. 双击 BilibiliAudioDownloader.exe 运行程序
2. 在链接输入框粘贴B站视频链接（支持多个）
3. 点击"解析全部"按钮
4. 可在任务列表中修改下载的P范围和文件标题
5. 选择保存目录和下载格式
6. 点击"批量下载"开始下载

注意：
- mp3格式需要ffmpeg（已包含在程序中）
- 本工具仅供学习使用，请遵守相关法律法规
- 下载内容版权归原作者所有
"""

readme_path = os.path.join(BUILD_DIR, "使用说明.txt")
with open(readme_path, 'w', encoding='utf-8') as f:
    f.write(readme_content)
print(f"已创建使用说明: {readme_path}")

# 创建压缩包
print(f"\n创建压缩包: {ZIP_NAME}...")
zip_path = os.path.join(OUTPUT_DIR, ZIP_NAME)

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(BUILD_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.join(APP_NAME, os.path.relpath(file_path, BUILD_DIR))
            zf.write(file_path, arcname)

print(f"\n构建完成！")
print(f"压缩包位置: {os.path.abspath(zip_path)}")
zip_size = os.path.getsize(zip_path) / 1024 / 1024
print(f"压缩包大小: {zip_size:.2f} MB")
print("解压缩后即可使用！")
