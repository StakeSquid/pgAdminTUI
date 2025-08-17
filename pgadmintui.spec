# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('databases.yaml.example', '.'),
    ],
    hiddenimports=[
        'textual',
        'textual.widgets',
        'textual.widgets._tab_pane',
        'textual.widgets._tabbed_content',
        'textual.widgets._header',
        'textual.widgets._footer',
        'textual.widgets._static',
        'textual.widgets._label',
        'textual.widgets._tree',
        'textual.widgets._data_table',
        'textual.widgets._text_area',
        'textual.widgets._button',
        'textual.widgets._input',
        'textual.widgets._select',
        'textual.widgets._switch',
        'textual.containers',
        'psycopg',
        'psycopg_binary',
        'psycopg_pool',
        'asyncpg',
        'yaml',
        'click',
        'keyring',
        'keyring.backends',
        'python_dotenv',
        'dotenv',
        'rich',
        'pandas',
        'tabulate',
        'openpyxl',
        'src.core',
        'src.core.connection_manager',
        'src.core.query_executor',
        'src.core.filter_manager',
        'src.ui',
        'src.ui.widgets',
        'src.ui.widgets.simple_filter_dialog',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'pytest_asyncio',
        'mypy',
        'black',
        'flake8',
        'pytest_cov',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

import sys

# Determine the executable name based on platform
exe_name = 'pgadmintui'
if sys.platform == 'win32':
    exe_name = 'pgadmintui.exe'

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)