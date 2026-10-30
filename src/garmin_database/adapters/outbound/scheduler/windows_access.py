"""Small privileged registration helper, separate from the ordinary desktop."""

import ctypes
import getpass
import os
import subprocess
from pathlib import Path


def elevate(command):
    from ctypes import wintypes

    class Execute(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", ctypes.c_ulong),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIcon", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    data = Execute()
    data.cbSize, data.fMask, data.lpVerb = ctypes.sizeof(data), 0x40, "runas"
    data.lpFile, data.lpParameters, data.nShow = (
        command[0],
        subprocess.list2cmdline(command[1:]),
        1,
    )
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(Execute)]
    shell.ShellExecuteExW.restype = wintypes.BOOL
    if not shell.ShellExecuteExW(ctypes.byref(data)):
        raise PermissionError("Nie potwierdzono operacji administracyjnej")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    try:
        kernel.WaitForSingleObject(data.hProcess, 0xFFFFFFFF)
        code = wintypes.DWORD()
        kernel.GetExitCodeProcess(data.hProcess, ctypes.byref(code))
        if code.value:
            raise RuntimeError("Nie udało się zastosować zadania Windows")
    finally:
        kernel.CloseHandle(data.hProcess)


def prepare_paths(config, config_path):
    """Only the service account, SYSTEM and administrators can read auth files."""
    operator = (
        config.status_reader
        or os.environ.get("USERDOMAIN", ".") + "\\" + getpass.getuser()
    )
    state, auth = Path(config.state_dir), Path(config.session_path).parent
    system = Path(os.environ.get("WINDIR", "C:/Windows")).resolve()
    for path in (state, auth, Path(config.data_dir), Path(config_path).parent):
        resolved = path.resolve()
        if resolved.parent == resolved or resolved.is_relative_to(system):
            raise ValueError("Wybierz wydzielony katalog kolektora")
    for directory in (state, auth, Path(config.data_dir)):
        directory.mkdir(parents=True, exist_ok=True)
    rules = [
        (
            Path(config_path).parent,
            [config.run_as + ":(OI)(CI)R", operator + ":(OI)(CI)M"],
        ),
        (state, [config.run_as + ":(OI)(CI)M", operator + ":(OI)(CI)R"]),
        (auth, [config.run_as + ":(OI)(CI)F"]),
    ]
    for path, grants in rules:
        result = subprocess.run(
            [
                "icacls.exe",
                str(path),
                "/inheritance:r",
                "/grant:r",
                "*S-1-5-18:(OI)(CI)F",
                "*S-1-5-32-544:(OI)(CI)F",
                *grants,
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise PermissionError(
                "Nie udało się ograniczyć dostępu do plików kolektora"
            )
    result = subprocess.run(
        ["icacls.exe", config.data_dir, "/grant", config.run_as + ":(OI)(CI)M"],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise PermissionError("Konto kolektora nie ma dostępu do katalogu danych")
