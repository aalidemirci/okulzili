from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest

from okul_zili import __version__


ROOT = Path(__file__).resolve().parents[1]


class PackagingDefinitionTests(unittest.TestCase):
    def test_release_versions_are_synchronized(self) -> None:
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        installer = (ROOT / "packaging" / "windows" / "okul-zili.iss").read_text(encoding="utf-8")
        linux = (ROOT / "packaging" / "linux" / "control").read_text(encoding="utf-8")
        self.assertIn(f'version = "{__version__}"', project)
        self.assertIn(f'#define MyAppVersion "{__version__}"', installer)
        self.assertIn(f"Version: {__version__}", linux)

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
        self.assertIn('assets/sounds/*.wav', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
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

    def test_linux_package_embeds_gui_dependencies(self) -> None:
        # K1: customtkinter/darkdetect/packaging Pardus depolarında yok;
        # temiz makinede ModuleNotFoundError yaşanmaması için her iki deb
        # üretim yolu da vendor/ kopyalarını gömer, doğrulama betiği
        # importlarını denetler.
        build_script = (ROOT / "packaging" / "linux" / "build-deb.sh").read_text(encoding="utf-8")
        verifier = (ROOT / "tools" / "verify-linux-install.sh").read_text(encoding="utf-8")
        for name in ("customtkinter", "darkdetect", "packaging"):
            self.assertIn(f'vendor/{name}"', build_script)
            self.assertTrue((ROOT / "vendor" / name / "__init__.py").is_file())
        self.assertIn(
            "import okul_zili, tkinter, PIL, pystray, six, customtkinter, darkdetect, packaging",
            verifier,
        )

    def test_runtime_has_no_network_client_dependency(self) -> None:
        # Bilinçli iki istisna dışında hiçbir modül ağ istemcisi içeremez:
        # sound_catalog yalnız yönetici onayıyla MEB indirmesi yapar,
        # time_check yalnız isteğe bağlı SNTP saat karşılaştırması yapar.
        allowed_sources = {"sound_catalog.py", "time_check.py"}
        forbidden = {"requests", "httpx", "socket", "urllib", "http.client"}

        def is_forbidden(name: str) -> bool:
            return any(name == item or name.startswith(item + ".") for item in forbidden)

        violations: list[str] = []
        for source in (ROOT / "src" / "okul_zili").glob("*.py"):
            if source.name in allowed_sources:
                continue
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                else:
                    continue
                violations.extend(
                    f"{source.name}: {name}" for name in names if is_forbidden(name)
                )
        self.assertEqual([], violations)

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
