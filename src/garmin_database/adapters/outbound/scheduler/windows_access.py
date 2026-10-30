"""Small privileged registration helper, separate from the ordinary desktop."""

import ctypes
import getpass
import os
import subprocess
from pathlib import Path


def grant_batch_logon(account):
    """Grant the task account its required logon right without replacing policy."""
    from ctypes import wintypes

    class UnicodeString(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", wintypes.LPWSTR),
        ]

    class ObjectAttributes(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.ULONG),
            ("RootDirectory", wintypes.HANDLE),
            ("ObjectName", ctypes.POINTER(UnicodeString)),
            ("Attributes", wintypes.ULONG),
            ("SecurityDescriptor", wintypes.LPVOID),
            ("SecurityQualityOfService", wintypes.LPVOID),
        ]

    api = ctypes.WinDLL("advapi32", use_last_error=True)
    lookup = api.LookupAccountNameW
    lookup.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    lookup.restype = wintypes.BOOL
    size, domain_size, kind = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
    lookup(
        None,
        account,
        None,
        ctypes.byref(size),
        None,
        ctypes.byref(domain_size),
        ctypes.byref(kind),
    )
    if not size.value:
        raise PermissionError("Nie można rozpoznać konta zadania Windows")
    sid = ctypes.create_string_buffer(size.value)
    domain = ctypes.create_unicode_buffer(max(1, domain_size.value))
    if not lookup(
        None,
        account,
        sid,
        ctypes.byref(size),
        domain,
        ctypes.byref(domain_size),
        ctypes.byref(kind),
    ):
        raise PermissionError("Nie można rozpoznać konta zadania Windows")
    attributes = ObjectAttributes()
    attributes.Length = ctypes.sizeof(attributes)
    handle = wintypes.HANDLE()
    api.LsaOpenPolicy.argtypes = [
        ctypes.POINTER(UnicodeString),
        ctypes.POINTER(ObjectAttributes),
        wintypes.ULONG,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    api.LsaOpenPolicy.restype = wintypes.LONG
    # POLICY_LOOKUP_NAMES | POLICY_CREATE_ACCOUNT: add a single account right.
    if api.LsaOpenPolicy(None, ctypes.byref(attributes), 0x810, ctypes.byref(handle)):
        raise PermissionError("Nie można otworzyć zasad logowania Windows")
    api.LsaAddAccountRights.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        ctypes.POINTER(UnicodeString),
        wintypes.ULONG,
    ]
    api.LsaAddAccountRights.restype = wintypes.LONG
    api.LsaClose.argtypes = [wintypes.HANDLE]
    api.LsaClose.restype = wintypes.LONG
    name = "SeBatchLogonRight"
    buffer = ctypes.create_unicode_buffer(name)
    width = ctypes.sizeof(ctypes.c_wchar)
    right = UnicodeString(
        len(name) * width, (len(name) + 1) * width, ctypes.cast(buffer, wintypes.LPWSTR)
    )
    try:
        if api.LsaAddAccountRights(handle, sid, ctypes.byref(right), 1):
            raise PermissionError("Nie można przyznać prawa logowania wsadowego")
    finally:
        api.LsaClose(handle)


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
    same_account = config.run_as.casefold() == operator.casefold()
    rules = [
        (
            Path(config_path),
            [operator + ":M"] + ([] if same_account else [config.run_as + ":R"]),
        ),
        (
            state,
            [config.run_as + ":(OI)(CI)M"]
            + ([] if same_account else [operator + ":(OI)(CI)R"]),
        ),
        (auth, [config.run_as + ":(OI)(CI)F"]),
    ]
    if config.settings_path:
        # Shared non-secret settings only; never grant access to GUI auth files.
        rules.append(
            (
                Path(config.settings_path),
                [operator + ":M"] + ([] if same_account else [config.run_as + ":R"]),
            )
        )
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
