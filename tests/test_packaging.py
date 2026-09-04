from __future__ import annotations

import ast
from importlib import metadata
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
        # deb üreticileri sürümü koddan okur; belge sürümle birlikte güncellenir.
        from tools.build_deb import VERSION as deb_builder_version

        self.assertEqual(__version__, deb_builder_version)
        build_script = (ROOT / "packaging" / "linux" / "build-deb.sh").read_text(encoding="utf-8")
        self.assertIn("okul_zili.__version__", build_script)
        self.assertIn("okul-zili_${VERSION}_all.deb", build_script)
        setup_guide = (ROOT / "KURULUM.md").read_text(encoding="utf-8")
        self.assertIn(f"okul-zili_{__version__}_all.deb", setup_guide)
        self.assertIn(f"OkulZili-Kurulum-{__version__}.exe", setup_guide)
        # uv.lock de sürümü taşır; bayat kalmasın.
        self.assertIn(f'name = "okul-zili"\nversion = "{__version__}"', (ROOT / "uv.lock").read_text(encoding="utf-8"))
        release_notes = (ROOT / "SURUM-NOTLARI.md").read_text(encoding="utf-8")
        self.assertIn(f"## {__version__}", release_notes)

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
        # D13: görev kaydı kurulumu başlatan hesapta; yükseltmede çalışan uygulama durur.
        self.assertRegex(script, r"install-task\.ps1.*runasoriginaluser")
        self.assertIn("function PrepareToInstall", script)
        self.assertIn("VersionInfoVersion={#MyAppVersion}", script)
        self.assertIn("version=str(version_file)", spec)
        self.assertTrue((ROOT / "packaging" / "windows" / "make_version_info.py").is_file())
        task_script = (ROOT / "packaging" / "windows" / "install-task.ps1").read_text(encoding="utf-8")
        self.assertIn("USERDOMAIN", task_script)
        build_script = (ROOT / "packaging" / "windows" / "build.ps1").read_text(encoding="utf-8")
        # D12: derleme yorumlayıcısı PATH'ten değil, sürüm ve modül denetimiyle seçilir.
        self.assertIn("(3, 12)", build_script)
        self.assertIn("make_version_info.py", build_script)
        self.assertNotIn('$python = "python"', build_script)

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
        # 7.10: zaman aşımına düşen öz-test başarılı sayılmaz.
        self.assertIn("zaman aşımı", verifier)
        entrypoint = (ROOT / "packaging" / "windows" / "entrypoint.py").read_text(encoding="utf-8")
        self.assertIn("os._exit(3)", entrypoint)

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
        launcher = (ROOT / "packaging" / "linux" / "okul-zili").read_text(encoding="utf-8")
        for name in ("customtkinter", "darkdetect", "packaging"):
            self.assertIn(f'vendor/{name}"', build_script)
            self.assertTrue((ROOT / "vendor" / name / "__init__.py").is_file())
        self.assertIn(
            "import okul_zili, tkinter, PIL, pystray, six, customtkinter, darkdetect, packaging",
            verifier,
        )
        # D10: gömülü kütüphaneler sistemin dist-packages dizinine yazılmaz;
        # başlatıcı ve doğrulama betiği aynı vendor yolunu kullanır.
        self.assertIn("/usr/lib/okul-zili/vendor", build_script)
        self.assertNotIn('vendor/packaging" "$BUILD_ROOT/usr/lib/python3/dist-packages', build_script)
        self.assertIn("/usr/lib/okul-zili/vendor", launcher)
        self.assertIn("PYTHONPATH", launcher)
        self.assertIn("PYTHONPATH=/usr/lib/okul-zili/vendor", verifier)
        self.assertIn("md5sums", build_script)
        self.assertIn("Installed-Size", build_script)

    def test_timezone_data_is_an_explicit_dependency(self) -> None:
        # D11: tzdata derleme makinesinde tesadüfen kurulu olduğu için çalışıyordu.
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        spec = (ROOT / "packaging" / "windows" / "okul-zili.spec").read_text(encoding="utf-8")
        control = (ROOT / "packaging" / "linux" / "control").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "testler.yml").read_text(encoding="utf-8")
        self.assertRegex(project, r'"tzdata>=')
        self.assertIn('collect_data_files("tzdata")', spec)
        self.assertIn("tzdata", control)
        # CI bağımlılıkları pyproject'ten kurar; ayrı bir liste ayrışamaz.
        self.assertIn("pip install -e .", workflow)

    def test_ci_matrix_covers_target_python_versions(self) -> None:
        # 8.5: Pardus 23 = 3.11, Ubuntu 22.04 = 3.10, Windows paketi = 3.12.
        workflow = (ROOT / ".github" / "workflows" / "testler.yml").read_text(encoding="utf-8")
        for version in ("3.10", "3.11", "3.12"):
            self.assertIn(f'"{version}"', workflow)
        self.assertIn("windows-latest", workflow)

    def test_vendored_customtkinter_matches_pinned_and_installed_version(self) -> None:
        # 8.3: Windows paketi pip kopyasını, Linux paketi vendor kopyasını taşır;
        # ikisi ayrışırsa arayüz iki platformda farklı davranır.
        vendored = re.search(r'__version__ = "([^"]+)"', (ROOT / "vendor" / "customtkinter" / "__init__.py").read_text(encoding="utf-8"))
        self.assertIsNotNone(vendored)
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'"customtkinter=={vendored.group(1)}"', project)  # type: ignore[union-attr]
        try:
            installed = metadata.version("customtkinter")
        except metadata.PackageNotFoundError:
            self.skipTest("customtkinter kurulu değil")
        self.assertEqual(vendored.group(1), installed)  # type: ignore[union-attr]

    def test_third_party_license_texts_cover_bundled_components(self) -> None:
        # 8.7: Windows paketine cffi ve tzdata, her iki pakete Roboto yazı tipi giriyor.
        licenses = {item.name for item in (ROOT / "THIRD_PARTY_LICENSES").iterdir()}
        for expected in ("tzdata-LICENSE.txt", "cffi-LICENSE.txt", "Roboto-LICENSE.txt", "packaging-LICENSE.txt"):
            self.assertIn(expected, licenses)

    def test_runtime_has_no_network_client_dependency(self) -> None:
        # Bilinçli iki istisna dışında hiçbir modül ağ istemcisi içeremez:
        # sound_catalog yalnız yönetici onayıyla MEB indirmesi yapar,
        # time_check yalnız isteğe bağlı SNTP saat karşılaştırması yapar.
        allowed_sources = {"sound_catalog.py", "time_check.py"}
        forbidden = {"requests", "httpx", "socket", "urllib", "http.client", "ftplib", "smtplib", "xmlrpc", "asyncio"}
        # 8.6: import düğümü dışındaki kaçış yolları — alt süreçle indirme aracı,
        # dinamik içe aktarma, WinINet. (webbrowser bilinçli istisna: yalnız
        # kullanıcı tıklamasıyla dış bağlantı açar, bkz. MIMARI.md.)
        forbidden_text = re.compile(
            r"\b(curl|wget|Invoke-WebRequest|WinHttp|WinINet|urlmon|import_module\(\s*['\"](urllib|socket|http))\b"
        )

        def is_forbidden(name: str) -> bool:
            return any(name == item or name.startswith(item + ".") for item in forbidden)

        violations: list[str] = []
        for source in (ROOT / "src" / "okul_zili").glob("*.py"):
            if source.name in allowed_sources:
                continue
            text = source.read_text(encoding="utf-8")
            for match in forbidden_text.finditer(text):
                violations.append(f"{source.name}: metin '{match.group(0)}'")
            tree = ast.parse(text, filename=str(source))
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
        for filename in ("app.py", "dialogs.py", "tray.py"):
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
