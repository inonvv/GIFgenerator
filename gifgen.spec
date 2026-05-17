# pyinstaller --clean gifgen.spec
# Produces dist/GIFGenerator.exe — a single-file Windows GUI bundle.

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

ctk_datas = collect_data_files('customtkinter')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('vendor/ffmpeg.exe', 'vendor'),
        ('vendor/yt-dlp.exe', 'vendor'),
    ] + ctk_datas,
    hiddenimports=[
        'qrcode',
        'qrcode.image.pil',
        'PIL.Image',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GIFGenerator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
