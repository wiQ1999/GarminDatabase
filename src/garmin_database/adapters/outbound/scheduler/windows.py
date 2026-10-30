"""Task Scheduler registration using an OS credential dialog and memory-only pipe."""

import ctypes
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from math import gcd

NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"


def credential(account):
    from ctypes import wintypes

    class Info(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hwndParent", wintypes.HWND),
            ("pszMessageText", wintypes.LPCWSTR),
            ("pszCaptionText", wintypes.LPCWSTR),
            ("hbmBanner", wintypes.HANDLE),
        ]

    info = Info(
        ctypes.sizeof(Info),
        None,
        "Poświadczenia konta zadania GarminDatabase",
        "GarminDatabase",
        None,
    )
    user, password, save = (
        ctypes.create_unicode_buffer(account, 514),
        ctypes.create_unicode_buffer(257),
        wintypes.BOOL(False),
    )
    try:
        prompt = ctypes.windll.credui.CredUIPromptForCredentialsW
        prompt.argtypes = [
            ctypes.POINTER(Info),
            wintypes.LPCWSTR,
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            wintypes.ULONG,
            wintypes.LPWSTR,
            wintypes.ULONG,
            ctypes.POINTER(wintypes.BOOL),
            wintypes.DWORD,
        ]
        prompt.restype = wintypes.DWORD
        code = prompt(
            ctypes.byref(info),
            "GarminDatabaseCollector",
            None,
            0,
            user,
            len(user),
            password,
            len(password),
            ctypes.byref(save),
            0x40000 | 0x80 | 0x2,
        )
        if code:
            raise RuntimeError("Nie potwierdzono poświadczeń konta zadania")
        if user.value.casefold() != account.casefold():
            raise ValueError("Poświadczenia muszą należeć do skonfigurowanego konta")
        return password.value
    finally:
        ctypes.memset(ctypes.addressof(password), 0, ctypes.sizeof(password))


class WindowsScheduler:
    def __init__(self, command, config_path, *, run=subprocess.run, prompt=credential):
        self.command, self.config_path, self.run, self.prompt = (
            command,
            str(config_path),
            run,
            prompt,
        )

    def name(self, config):
        return "GarminDatabase-" + config.instance

    def render(self, config):
        if not config.run_as:
            raise ValueError("Wybierz konto zadania Windows")
        ET.register_namespace("", NS)
        root = ET.Element("Task", version="1.2", xmlns=NS)

        def add(parent, name, text=None):
            element = ET.SubElement(parent, name)
            element.text = text
            return element

        add(
            add(root, "RegistrationInfo"),
            "Description",
            "GarminDatabase " + config.revision,
        )
        trigger = add(add(root, "Triggers"), "TimeTrigger")
        repeat = add(trigger, "Repetition")
        interval = config.interval_minutes
        # Task Scheduler caps repetition at 31 days; guard longer periods locally.
        if interval > 31 * 24 * 60:
            interval = gcd(interval, 24 * 60)
        add(repeat, "Interval", f"PT{interval}M")
        add(repeat, "StopAtDurationEnd", "false")
        add(
            trigger,
            "StartBoundary",
            config.schedule.next_after(datetime.now(timezone.utc)).isoformat(),
        )
        add(trigger, "Enabled", "true")
        principal = ET.SubElement(add(root, "Principals"), "Principal", id="Collector")
        add(principal, "UserId", config.run_as)
        add(principal, "LogonType", "Password")
        add(principal, "RunLevel", "LeastPrivilege")
        settings = add(root, "Settings")
        for key, value in {
            "MultipleInstancesPolicy": "IgnoreNew",
            "DisallowStartIfOnBatteries": "false",
            "StopIfGoingOnBatteries": "false",
            "StartWhenAvailable": "false",
            "RunOnlyIfNetworkAvailable": "false",
            "WakeToRun": "false",
            "Enabled": str(config.enabled).lower(),
            "ExecutionTimeLimit": "PT0S",
        }.items():
            add(settings, key, value)
        actions = ET.SubElement(root, "Actions", Context="Collector")
        execute = add(actions, "Exec")
        add(execute, "Command", self.command[0])
        add(
            execute,
            "Arguments",
            subprocess.list2cmdline(
                [*self.command[1:], "--config", self.config_path, "run", "--scheduled"]
            ),
        )
        return ET.tostring(root, encoding="unicode")

    def _powershell(self, script, payload):
        result = self.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
        )
        return result

    def apply(self, config):
        xml = self.render(config)
        password = self.prompt(config.run_as)
        script = """$ErrorActionPreference='Stop'; try {
$p=ConvertFrom-Json ([Console]::In.ReadToEnd());
$s=New-Object -ComObject 'Schedule.Service'; $s.Connect();
$null=$s.GetFolder('\\').RegisterTask($p.name,$p.xml,6,$p.user,$p.password,1,$null);
exit 0 } catch { exit 1 }"""
        try:
            result = self._powershell(
                script,
                {
                    "name": self.name(config),
                    "xml": xml,
                    "user": config.run_as,
                    "password": password,
                },
            )
        finally:
            password = None
        if result.returncode:
            raise RuntimeError("Nie udało się zarejestrować zadania Windows")

    def status(self, config):
        script = """$ErrorActionPreference='Stop'; try {
$p=ConvertFrom-Json ([Console]::In.ReadToEnd()); $s=New-Object -ComObject 'Schedule.Service'; $s.Connect();
try { $t=$s.GetFolder('\\').GetTask($p.name) } catch { exit 3 }
@{ installed=$true; enabled=[bool]$t.Enabled; revision_matches=$t.Xml.Contains($p.revision) } | ConvertTo-Json -Compress;
exit 0 } catch { exit 1 }"""
        result = self._powershell(
            script, {"name": self.name(config), "revision": config.revision}
        )
        if result.returncode == 3:
            return {"installed": False, "enabled": False, "revision_matches": False}
        if result.returncode:
            raise RuntimeError("Nie można odczytać zadania Windows")
        return json.loads(result.stdout)
