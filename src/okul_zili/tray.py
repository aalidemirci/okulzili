from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any


class TrayController:
    """Pystray varsa gerçek sistem tepsisini, yoksa güvenli geri dönüşü yönetir."""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_lesson_bell: Callable[[], None],
        on_stop_audio: Callable[[], None],
        on_defer: Callable[[], None],
        on_toggle_scheduler: Callable[[], None],
        on_toggle_mute: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.on_show = on_show
        self.on_lesson_bell = on_lesson_bell
        self.on_stop_audio = on_stop_audio
        self.on_defer = on_defer
        self.on_toggle_scheduler = on_toggle_scheduler
        self.on_toggle_mute = on_toggle_mute
        self.on_exit = on_exit
        self.available = False
        self.paused = False
        self.muted = False
        self.critical = False
        self._icon: Any | None = None
        self._last_status: tuple[str, bool, bool, bool] | None = None

    def start(self) -> bool:
        try:
            import pystray

            menu = pystray.Menu(
                pystray.MenuItem("Pencereyi aç", self._show, default=True),
                pystray.MenuItem("Ders zilini çal", self._lesson),
                pystray.MenuItem("Çalan sesi durdur", self._stop_audio),
                pystray.MenuItem("Sonraki zili 5 dk ertele", self._defer),
                pystray.MenuItem(self._toggle_text, self._toggle),
                pystray.MenuItem(self._mute_text, self._toggle_mute),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Uygulamayı kapat", self._exit),
            )
            self._icon = pystray.Icon(
                "okul-zili",
                self._render_icon(),
                "Okul Zili başlatılıyor…",
                menu,
            )
            self._icon.run_detached()
            self.available = True
            return True
        except Exception as exc:
            logging.getLogger("okul_zili").warning(
                "Sistem tepsisi başlatılamadı: %s", exc
            )
            self._icon = None
            self.available = False
            return False

    def update_status(
        self, title: str, *, critical: bool, paused: bool, muted: bool = False
    ) -> None:
        self.critical = critical
        self.paused = paused
        self.muted = muted
        if not self.available or self._icon is None:
            return
        status = (title[:127], critical, paused, muted)
        if status == self._last_status:
            return
        try:
            self._icon.title = status[0]
            self._icon.icon = self._render_icon()
            self._icon.update_menu()
            self._last_status = status
        except Exception:
            logging.getLogger("okul_zili").exception(
                "Sistem tepsisi durumu güncellenemedi."
            )

    def notify(self, message: str, title: str = "Okul Zili") -> None:
        if not self.available or self._icon is None:
            return
        try:
            self._icon.notify(message, title)
        except Exception:
            logging.getLogger("okul_zili").exception(
                "Sistem tepsisi bildirimi gösterilemedi."
            )

    def stop(self) -> None:
        icon, self._icon = self._icon, None
        self.available = False
        self._last_status = None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                logging.getLogger("okul_zili").exception(
                    "Sistem tepsisi kapatılamadı."
                )

    def _toggle_text(self, item: object) -> str:
        return "Zilleri sürdür" if self.paused else "Zilleri duraklat"

    def _mute_text(self, item: object) -> str:
        return "Bugünkü sessize almayı kaldır" if self.muted else "Bugün zil çalma"

    def _show(self, icon: object, item: object) -> None:
        self.on_show()

    def _lesson(self, icon: object, item: object) -> None:
        self.on_lesson_bell()

    def _stop_audio(self, icon: object, item: object) -> None:
        self.on_stop_audio()

    def _defer(self, icon: object, item: object) -> None:
        self.on_defer()

    def _toggle(self, icon: object, item: object) -> None:
        self.on_toggle_scheduler()

    def _toggle_mute(self, icon: object, item: object) -> None:
        self.on_toggle_mute()

    def _exit(self, icon: object, item: object) -> None:
        self.on_exit()

    def _render_icon(self) -> Any:
        from PIL import ImageDraw

        from .branding import load_brand_image

        background = "#b91c1c" if self.critical else ("#64748b" if self.paused else "#0e7490")
        image = load_brand_image(64)
        draw = ImageDraw.Draw(image)
        draw.ellipse((43, 43, 62, 62), fill="#F4FAFA")
        draw.ellipse((46, 46, 59, 59), fill=background)
        if self.critical:
            draw.rectangle((51, 48, 54, 54), fill="#fde047")
            draw.ellipse((51, 56, 54, 59), fill="#fde047")
        return image
