from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from okul_zili import autostart

EXECUTABLE = r"C:\Program Files\Okul Zili\OkulZili.exe"


def _task_xml(command: str = EXECUTABLE, *, enabled: str = "true", batteries: str = "false", logon: bool = True) -> str:
    trigger = "<LogonTrigger><Enabled>true</Enabled><UserId>OKUL\\ogretmen</UserId></LogonTrigger>" if logon else ""
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\r\r\n'
        '<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
        f"<Triggers>{trigger}</Triggers>"
        f"<Settings><DisallowStartIfOnBatteries>{batteries}</DisallowStartIfOnBatteries><Enabled>{enabled}</Enabled></Settings>"
        f"<Actions><Exec><Command>{command}</Command></Exec></Actions>"
        "</Task>"
    )


class WindowsTaskTests(unittest.TestCase):
    def test_script_binds_trigger_to_current_user(self) -> None:
        # 0.8.0 hatası: kullanıcısız AtLogOn yetkisiz bağlamda "Erişim engellendi".
        script = autostart.windows_task_script(EXECUTABLE)
        self.assertIn("New-ScheduledTaskTrigger -AtLogOn -User $user", script)
        self.assertIn("-AllowStartIfOnBatteries", script)
        self.assertIn("-RunLevel Limited", script)
        self.assertIn(f"-Execute '{EXECUTABLE}'", script)

    def test_script_quotes_apostrophes_in_path(self) -> None:
        script = autostart.windows_task_script(r"C:\Users\O'Brien\OkulZili.exe")
        self.assertIn(r"-Execute 'C:\Users\O''Brien\OkulZili.exe'", script)

    def test_healthy_task(self) -> None:
        status = autostart.parse_task_xml(_task_xml(), EXECUTABLE)
        self.assertTrue(status.ok)

    def test_problems_are_reported_as_repairable(self) -> None:
        cases = {
            "devre dışı": _task_xml(enabled="false"),
            "tetikleyicisi yok": _task_xml(logon=False),
            "prizdeyken": _task_xml(batteries="true"),
            "başka bir dosyayı": _task_xml(command=r"D:\Eski\OkulZili.exe"),
            "okunamadı": "<Task",
        }
        for expected, text in cases.items():
            with self.subTest(expected=expected):
                status = autostart.parse_task_xml(text, EXECUTABLE)
                self.assertFalse(status.ok)
                self.assertTrue(status.repairable)
                self.assertIn(expected, status.detail)

    def test_quoted_command_and_case_are_tolerated(self) -> None:
        status = autostart.parse_task_xml(_task_xml(command=f'"{EXECUTABLE.lower()}"'), EXECUTABLE)
        self.assertEqual(autostart.os.path.normcase(EXECUTABLE.lower()) == autostart.os.path.normcase(EXECUTABLE), status.ok)


class LinuxAutostartTests(unittest.TestCase):
    def test_entry_and_user_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "etc" / "okul-zili.desktop"
            override = root / "home" / "okul-zili.desktop"
            self.assertFalse(autostart.linux_status(entry, override).ok)
            entry.parent.mkdir(parents=True)
            entry.write_text("[Desktop Entry]\n", encoding="utf-8")
            self.assertTrue(autostart.linux_status(entry, override).ok)
            override.parent.mkdir(parents=True)
            override.write_text("[Desktop Entry]\nHidden=true\n", encoding="utf-8")
            status = autostart.linux_status(entry, override)
            self.assertFalse(status.ok)
            self.assertTrue(status.repairable)
            self.assertTrue(autostart.repair_linux(override)[0])
            self.assertTrue(autostart.linux_status(entry, override).ok)


if __name__ == "__main__":
    unittest.main()
