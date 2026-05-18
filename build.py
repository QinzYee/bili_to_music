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
    """清理旧的构建文件"""
    print("清理旧的构建文件...")
    for d in [DIST_DIR, OUTPUT_DIR, "build"]:
        if os.path.exists(d):
            shutil.rmtree(d)
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def copy_qt_plugins():
    """手动复制必要的 Qt 插件，确保程序能正常启动"""
    print("复制 Qt 插件...")
    
    try:
        import PySide6
        pyside6_dir = os.path.dirname(PySide6.__file__)
    except ImportError:
        print("警告: 无法找到 PySide6")
        return
    
    target_plugins_dir = os.path.join(BUILD_DIR, "_internal", "PySide6", "plugins")
    
    required_plugins = [
        "platforms",
        "styles",
        "iconengines",
        "imageformats",
    ]
    
    for plugin_dir in required_plugins:
        src_dir = os.path.join(pyside6_dir, "plugins", plugin_dir)
        dst_dir = os.path.join(target_plugins_dir, plugin_dir)
        
        if os.path.exists(src_dir):
            os.makedirs(dst_dir, exist_ok=True)
            for item in os.listdir(src_dir):
                src_item = os.path.join(src_dir, item)
                dst_item = os.path.join(dst_dir, item)
                if os.path.isfile(src_item):
                    shutil.copy2(src_item, dst_item)
                elif os.path.isdir(src_item):
                    shutil.copytree(src_item, dst_item, dirs_exist_ok=True)
            print(f"  已复制: {plugin_dir}")


def create_pyinstaller_spec():
    """创建 PyInstaller spec 文件"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources/ffmpeg.exe', 'resources'),
        ('resources/icon.ico', 'resources'),
        ('resources/图文教程.md', 'resources'),
        ('resources/提取bv图文教程1.png', 'resources'),
        ('resources/提取bv图文教程2.png', 'resources'),
        ('resources/界面预览.png', 'resources'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtQuick',
        'PySide6.QtQml',
        'PySide6.QtSql',
        'PySide6.QtTest',
        'PySide6.QtXml',
        'PySide6.QtXmlPatterns',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
        'PySide6.QtNetwork',
        'PySide6.QtPrintSupport',
        'PySide6.QtHelp',
        'PySide6.QtUiTools',
        'PySide6.QtDesigner',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='APP_NAME',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='APP_NAME',
)
'''.replace('APP_NAME', APP_NAME)

    with open(f"{APP_NAME}.spec", 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print(f"已创建 {APP_NAME}.spec 文件")


def build_with_spec():
    """使用 spec 文件构建"""
    print("使用 PyInstaller 构建程序...")
    cmd = ["pyinstaller", "--clean", f"{APP_NAME}.spec"]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise Exception("PyInstaller 构建失败")


def create_readme_in_package():
    """在打包目录中创建使用说明"""
    readme_content = '''B站视频音频下载工具
================

使用说明：
1. 双击 {APP_NAME}.exe 运行程序
2. 在链接输入框粘贴B站视频链接（支持多个）
3. 点击"解析全部"按钮
4. 可在任务列表中修改下载的P范围和文件标题
5. 选择保存目录和下载格式
6. 点击"批量下载"开始下载

注意：
- mp3格式需要ffmpeg（已包含在程序中）
- 本工具仅供学习使用，请遵守相关法律法规
- 下载内容版权归原作者所有
'''.replace('{APP_NAME}', APP_NAME)

    readme_path = os.path.join(BUILD_DIR, "使用说明.txt")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)


def verify_resources():
    """验证资源文件是否正确打包"""
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
    
    platforms_dir = os.path.join(BUILD_DIR, "_internal", "PySide6", "plugins", "platforms")
    if os.path.exists(platforms_dir) and os.path.exists(os.path.join(platforms_dir, "qwindows.dll")):
        print("[OK] Qt 平台插件")
    else:
        print("[X] Qt 平台插件缺失")
        all_found = False
    
    return all_found


def create_zip():
    """创建压缩包"""
    print(f"创建压缩包: {ZIP_NAME}...")
    zip_path = os.path.join(OUTPUT_DIR, ZIP_NAME)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BUILD_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.join(APP_NAME, os.path.relpath(file_path, BUILD_DIR))
                zf.write(file_path, arcname)

    print(f"压缩包已创建: {os.path.abspath(zip_path)}")
    zip_size = os.path.getsize(zip_path) / 1024 / 1024
    print(f"压缩包大小: {zip_size:.2f} MB")
    return zip_path


def main():
    try:
        clean_old_build()
        create_pyinstaller_spec()
        build_with_spec()
        copy_qt_plugins()
        create_readme_in_package()
        
        if not verify_resources():
            print("警告: 部分资源文件未找到！")
        
        create_zip()
        print("\n构建完成！")
        print(f"压缩包位置: {os.path.abspath(os.path.join(OUTPUT_DIR, ZIP_NAME))}")
        print("解压缩后即可使用！")
        
    except Exception as e:
        print(f"\n构建失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
