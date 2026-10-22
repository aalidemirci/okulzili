"""Oturum açılışında otomatik başlatmanın denetimi ve onarımı.

Windows'ta Görev Zamanlayıcı'daki "Okul Zili" görevi, Linux'ta paketin
``/etc/xdg/autostart`` girdisi denetlenir. Görevi kurucu da aynı kodla yazar
(``OkulZili.exe --otomatik-baslatmayi-kur``); kurucu ile uygulama içindeki
"Otomatik başlatmayı onar" düğmesi tek bir uygulamayı paylaşır.

0.8.0'da görev, yetkisiz bağlamda "her kullanıcının oturum açılışı"
tetikleyicisiyle yazılmaya çalışılıyordu; Windows bunu "Erişim engellendi"
ile reddediyor, kurucu da hatayı yutuyordu. Tetikleyici artık görevi yazan
hesaba bağlanır; bu biçim yönetici yetkisi istemez.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ElementTree

TASK_NAME = "Okul Zili"
_TASK_NAMESPACE = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"
LINUX_AUTOSTART_ENTRY = Path("/etc/xdg/autostart/okul-zili.desktop")


@dataclass(frozen=True, slots=True)
class AutostartStatus:
    ok: bool
    detail: str
    repairable: bool = False


def _no_window_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def windows_task_script(executable: str) -> str:
    """Görevi yazan PowerShell betiği; tetikleyici çalışan hesaba bağlıdır."""
    quoted = executable.replace("'", "''")
    return "\n".join(
        (
            '$ErrorActionPreference = "Stop"',
            # İlerleme kayıtları stderr'e CLIXML olarak düşer ve hata metnini örter.
            "$ProgressPreference = 'SilentlyContinue'",
            '$user = "$env:USERDOMAIN\\$env:USERNAME"',
            f"$action = New-ScheduledTaskAction -Execute '{quoted}'",
            # -User zorunlu: kullanıcısız AtLogOn yönetici yetkisi ister.
            "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user",
            "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries"
            " -DontStopIfGoingOnBatteries -StartWhenAvailable"
            " -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5"
            " -RestartInterval (New-TimeSpan -Minutes 1)",
            "$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited",
            f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger"
            " -Settings $settings -Principal $principal -Force | Out-Null",
        )
    )


def parse_task_xml(text: str, executable: str) -> AutostartStatus:
    """schtasks /XML çıktısını beklenen ayarlarla karşılaştırır."""
    # Bildirim UTF-16 der ama metin zaten çözülmüştür; ElementTree bildirimi
    # str girdide reddettiği için atılır.
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text)
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return AutostartStatus(False, "Otomatik başlatma görevi okunamadı.", True)

    def find(path: str) -> ElementTree.Element | None:
        return root.find(_qualified(path))

    enabled = find("Settings/Enabled")
    if enabled is not None and (enabled.text or "").strip().lower() == "false":
        return AutostartStatus(False, "Otomatik başlatma görevi devre dışı bırakılmış.", True)
    logon = find("Triggers/LogonTrigger")
    if logon is None:
        return AutostartStatus(False, "Görevde oturum açılışı tetikleyicisi yok.", True)
    trigger_enabled = logon.find(_TASK_NAMESPACE + "Enabled")
    if trigger_enabled is not None and (trigger_enabled.text or "").strip().lower() == "false":
        return AutostartStatus(False, "Oturum açılışı tetikleyicisi devre dışı.", True)
    batteries = find("Settings/DisallowStartIfOnBatteries")
    if batteries is not None and (batteries.text or "").strip().lower() == "true":
        return AutostartStatus(False, "Görev yalnız prizdeyken başlayacak biçimde ayarlı.", True)
    command = find("Actions/Exec/Command")
    target = (command.text or "").strip().strip('"') if command is not None else ""
    if os.path.normcase(os.path.normpath(target)) != os.path.normcase(os.path.normpath(executable)):
        return AutostartStatus(
            False,
            f"Otomatik başlatma görevi başka bir dosyayı açıyor: {target or 'boş'}.",
            True,
        )
    return AutostartStatus(True, "Oturum açılınca Görev Zamanlayıcı ile başlatılır.")


def _qualified(path: str) -> str:
    return "/".join(_TASK_NAMESPACE + part for part in path.split("/"))


def windows_status(executable: str | None = None) -> AutostartStatus:
    executable = executable or sys.executable
    try:
        completed = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME, "/XML"],
            capture_output=True,
            timeout=15,
            check=False,
            creationflags=_no_window_flags(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return AutostartStatus(False, f"Görev Zamanlayıcı sorgulanamadı: {exc}", False)
    if completed.returncode != 0:
        return AutostartStatus(
            False,
            "Otomatik başlatma görevi yok; bilgisayar yeniden başlatıldığında Okul Zili kendiliğinden açılmaz.",
            True,
        )
    # schtasks çıktısı konsolun OEM kod sayfasıyladır (Türkçe Windows'ta cp857).
    text = completed.stdout.decode("oem" if sys.platform == "win32" else "utf-8", errors="replace")
    return parse_task_xml(text, executable)


def install_windows_task(executable: str | None = None) -> tuple[bool, str]:
    """Görevi çalışan hesap için (yeniden) yazar; yönetici yetkisi gerekmez."""
    script = windows_task_script(executable or sys.executable)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            capture_output=True,
            timeout=60,
            check=False,
            creationflags=_no_window_flags(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"PowerShell çalıştırılamadı: {exc}"
    if completed.returncode != 0:
        detail = completed.stderr.decode("oem" if sys.platform == "win32" else "utf-8", errors="replace")
        lines = [line.strip() for line in detail.splitlines() if line.strip() and not line.lstrip().startswith(("#< CLIXML", "<Objs"))]
        return False, lines[0] if lines else f"Çıkış kodu {completed.returncode}"
    return True, "Otomatik başlatma görevi oluşturuldu."


def _linux_user_override() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return config_home / "autostart" / "okul-zili.desktop"


def linux_status(entry: Path = LINUX_AUTOSTART_ENTRY, override: Path | None = None) -> AutostartStatus:
    override = override or _linux_user_override()
    if override.is_file():
        text = override.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\s*(Hidden\s*=\s*true|X-GNOME-Autostart-enabled\s*=\s*false)\s*$", text, re.IGNORECASE | re.MULTILINE):
            return AutostartStatus(
                False,
                f"Otomatik başlatma bu kullanıcı için kapatılmış ({override}).",
                True,
            )
    if not entry.is_file():
        return AutostartStatus(False, f"Otomatik başlatma girdisi yok: {entry}. Paketi yeniden kurun.", False)
    return AutostartStatus(True, "Oturum açılınca masaüstü otomatik başlatmasıyla açılır.")


def repair_linux(override: Path | None = None) -> tuple[bool, str]:
    override = override or _linux_user_override()
    try:
        override.unlink(missing_ok=True)
    except OSError as exc:
        return False, f"Kullanıcı girdisi kaldırılamadı: {exc}"
    return True, "Kullanıcıya özel kapatma kaldırıldı; sistem girdisi yeniden etkin."


def applicable() -> bool:
    """Yalnız kurulu dağıtımda denetlenir; kaynak koddan çalışırken atlanır."""
    if sys.platform == "win32":
        return bool(getattr(sys, "frozen", False))
    return Path(__file__).resolve().as_posix().startswith("/usr/")


def current_status() -> AutostartStatus | None:
    if not applicable():
        return None
    if sys.platform == "win32":
        return windows_status()
    return linux_status()


def repair() -> tuple[bool, str]:
    if sys.platform == "win32":
        return install_windows_task()
    return repair_linux()
