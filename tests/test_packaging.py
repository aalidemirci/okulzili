from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackagingDefinitionTests(unittest.TestCase):
    def test_windows_installer_is_turkish_and_runs_sound_test_flow(self) -> None:
        script = (ROOT / "packaging" / "windows" / "okul-zili.iss").read_text(
            encoding="utf-8"
        )
        self.assertIn('Name: "turkish"', script)
        self.assertIn("Turkish.isl", script)
        self.assertIn("postinstall", script)
        self.assertIn("install-task.ps1", script)
        self.assertIn("uninstall-stop.ps1", script)
        self.assertIn('RunOnceId: "StopOkulZili"', script)
        spec = (ROOT / "packaging" / "windows" / "okul-zili.spec").read_text(encoding="utf-8")
        self.assertIn('"_cffi_backend"', spec)
        self.assertIn('okul-zili.ico', spec)
        self.assertIn('okul_zili/assets', spec)
        self.assertIn('SetupIconFile=', script)
        self.assertIn('LICENSE', script)
        self.assertIn('NOTICE', script)

    def test_windows_logon_task_allows_battery_operation(self) -> None:
        script = (ROOT / "packaging" / "windows" / "install-task.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("New-ScheduledTaskTrigger -AtLogOn", script)
        self.assertIn("-AllowStartIfOnBatteries", script)
        self.assertIn("-DontStopIfGoingOnBatteries", script)
        self.assertIn("-StartWhenAvailable", script)
        self.assertIn("-RestartCount 5", script)
        self.assertIn("-RestartInterval", script)
        verifier = (ROOT / "tools" / "verify-windows-install.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("DisallowStartIfOnBatteries", verifier)
        self.assertIn("--ses-cihazi-kontrol", verifier)

        stop_script = (
            ROOT / "packaging" / "windows" / "uninstall-stop.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("GetFullPath", stop_script)
        self.assertIn("OrdinalIgnoreCase", stop_script)
        self.assertIn("Stop-Process -Id", stop_script)

    def test_linux_package_has_service_menu_autostart_and_audio_alternatives(self) -> None:
        service = (ROOT / "packaging" / "linux" / "okul-zili.service").read_text(
            encoding="utf-8"
        )
        menu = (ROOT / "packaging" / "linux" / "okul-zili.desktop").read_text(
            encoding="utf-8"
        )
        autostart = (
            ROOT / "packaging" / "linux" / "okul-zili-autostart.desktop"
        ).read_text(encoding="utf-8")
        control = (ROOT / "packaging" / "linux" / "control").read_text(
            encoding="utf-8"
        )
        self.assertIn("WantedBy=default.target", service)
        self.assertIn("Name=Okul Zili", menu)
        self.assertIn("Icon=okul-zili", menu)
        self.assertIn("X-GNOME-Autostart-enabled=true", autostart)
        self.assertIn("pipewire-bin | pulseaudio-utils | alsa-utils", control)
        verifier = (ROOT / "tools" / "verify-linux-install.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("systemctl --user cat okul-zili.service", verifier)
        self.assertIn("--ses-cihazi-kontrol", verifier)

    def test_runtime_has_no_network_client_dependency(self) -> None:
        forbidden = {"requests", "httpx", "socket", "urllib", "http.client"}
        imported: set[str] = set()
        for source in (ROOT / "src" / "okul_zili").glob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
        self.assertEqual(set(), imported & forbidden)

    def test_application_sources_do_not_contain_common_english_ui_commands(self) -> None:
        forbidden = re.compile(
            r"\b(Cancel|Save|Settings|Exit|Error|Warning|Ready|Play|Stop|Next|Open|Close)\b"
        )
        violations: list[str] = []
        for filename in ("app.py", "tray.py"):
            source = ROOT / "src" / "okul_zili" / filename
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value.endswith(".TLabel"):
                        continue
                    if forbidden.search(node.value):
                        violations.append(f"{filename}: {node.value}")
        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
