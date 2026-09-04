# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPEC).resolve().parents[2]
# Öncelik build/ altına açılmış bağımsız CPython dağıtımıdır; yoksa derlemeyi
# yürüten Python'ın kendi Tcl/Tk dosyaları kullanılır.
python_root = root / "build" / "python" / "cpython-3.12.13-windows-x86_64-none"
if python_root.exists():
    tcl_root = root / "build" / "tcl86"
    tk_root = root / "build" / "tk86"
else:
    python_root = Path(sys.base_prefix)
    tcl_root = python_root / "tcl" / "tcl8.6"
    tk_root = python_root / "tcl" / "tk8.6"
os.environ["TCL_LIBRARY"] = str(tcl_root)
os.environ["TK_LIBRARY"] = str(tk_root)

a = Analysis(
    [str(root / "packaging" / "windows" / "entrypoint.py")],
    pathex=[str(root / "src")],
    binaries=[
        (str(python_root / "DLLs" / "_tkinter.pyd"), "."),
        (str(python_root / "DLLs" / "tcl86t.dll"), "."),
        (str(python_root / "DLLs" / "tk86t.dll"), "."),
    ],
    datas=[
        (str(python_root / "Lib" / "tkinter"), "tkinter"),
        (str(tcl_root), "_tcl_data"),
        (str(tk_root), "_tk_data"),
        (str(root / "src" / "okul_zili" / "assets"), "okul_zili/assets"),
        (str(root / "LICENSE"), "."),
        (str(root / "NOTICE"), "."),
        (str(root / "README.md"), "."),
        (str(root / "KURULUM.md"), "."),
        (str(root / "DONANIM.md"), "."),
        (str(root / "KULLANIM.md"), "."),
        (str(root / "SORUN-GIDERME.md"), "."),
        (str(root / "MIMARI.md"), "."),
        (str(root / "SURUM-NOTLARI.md"), "."),
        (str(root / "BAGIMLILIKLAR.md"), "."),
        (str(root / "GEREKSINIM-IZLENEBILIRLIK.md"), "."),
        (str(root / "SAHA-KABUL.md"), "."),
        (str(root / "SES-KAYNAKLARI.md"), "."),
        (str(root / "THIRD_PARTY_LICENSES"), "THIRD_PARTY_LICENSES"),
        *collect_data_files("customtkinter"),
        # Saat dilimi verisi: Windows'ta zoneinfo yalnız tzdata paketinden okur (D11).
        *collect_data_files("tzdata"),
    ],
    hiddenimports=["tkinter", "miniaudio", "_cffi_backend", "PIL.Image", "PIL.ImageDraw", "six", "six.moves", "tzdata", *collect_submodules("pystray")],
    runtime_hooks=[str(root / "packaging" / "windows" / "runtime-tk.py")],
    noarchive=False,
)
pyz = PYZ(a.pure)
# build.ps1 make_version_info.py ile üretir; elle PyInstaller çağrısında yoksa atlanır.
version_file = root / "build" / "version_info.txt"
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OkulZili",
    console=False,
    disable_windowed_traceback=False,
    icon=str(root / "assets" / "branding" / "okul-zili.ico"),
    version=str(version_file) if version_file.exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="OkulZili-Windows-x64",
)
