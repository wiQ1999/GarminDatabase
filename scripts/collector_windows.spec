# Windows CLI and scheduled entry share one set of libraries, without Qt/MCP.
import ssl
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

root = Path(SPECPATH).parent
datas, binaries, hiddenimports = collect_all("psycopg_binary")
for package in ("garmin_database", "garmin_fit_sdk", "fitdecode", "tzdata"):
    datas += collect_data_files(package)
for package in ("garminconnect", "garmin-fit-sdk", "fitdecode"):
    datas += copy_metadata(package)
pem = Path(ssl.__file__).with_name("codex-rejected-cas.pem")
if pem.is_file():
    datas.append((str(pem), "."))

a = Analysis(
    [str(root / "scripts/entrypoints/collector.py")],
    pathex=[], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["PySide6", "mcp"], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
options = dict(
    exclude_binaries=True, debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None,
    icon=[str(root / "src/garmin_database/resources/app-icon.ico")],
)
cli = EXE(pyz, a.scripts, [], name="GarminDatabaseCollector", console=True, **options)
task = EXE(
    pyz, a.scripts, [], name="GarminDatabaseCollectorTask", console=False,
    disable_windowed_traceback=True, **options,
)
coll = COLLECT(
    cli, task, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[],
    name="GarminDatabaseCollector",
)
