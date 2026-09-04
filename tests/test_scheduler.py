from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
import tempfile
import threading
import unittest

import json
from unittest import mock

from okul_zili.audio import PlaybackManager
from okul_zili.calendar_engine import CalendarEngine
from okul_zili.defaults import default_config
from okul_zili.domain import DateRule, EventSpec, EventType, ExceptionKind
from okul_zili.scheduler import STATE_IDENTITY_VERSION, BellScheduler, FakeClock, RunState
from tests.helpers import MockAudioBackend, write_wave


class SchedulerTests(unittest.TestCase):
    def test_run_state_serializes_concurrent_updates_safely(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calisma-durumu.json"
            state = RunState(path)
            workers = [threading.Thread(target=state.mark, args=(f"olay-{index}",)) for index in range(30)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=2)
            restored = RunState(path)
            self.assertEqual({f"olay-{index}" for index in range(30)}, set(restored.completed))

    def _scheduler(self, directory: str, current: datetime, grace: int = 90):
        root = Path(directory)
        config = replace(default_config(), grace_seconds=grace)
        for relative in config.sounds.values():
            write_wave(root / relative)
        backend = MockAudioBackend()
        clock = FakeClock(current)
        state = RunState()
        scheduler = BellScheduler(config, CalendarEngine(config), PlaybackManager(backend), root, state, clock)
        return scheduler, clock, backend, state

    def test_due_event_plays_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, _, backend, _ = self._scheduler(directory, datetime(2026, 9, 7, 8, 18))
            first = scheduler.tick()
            second = scheduler.tick()
            self.assertEqual(1, len(first))
            self.assertEqual([], second)
            self.assertEqual(1, sum(call[0] == "file" for call in backend.calls))

    def test_low_priority_audio_is_stopped_before_due_bell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = default_config()
            for relative in config.sounds.values():
                write_wave(root / relative)
            order: list[str] = []
            backend = MockAudioBackend()
            original_play = backend.play_file

            def play(path: Path, device: str) -> None:
                order.append("zil")
                original_play(path, device)

            backend.play_file = play  # type: ignore[method-assign]
            scheduler = BellScheduler(
                config,
                CalendarEngine(config),
                PlaybackManager(backend),
                root,
                RunState(),
                FakeClock(datetime(2026, 9, 7, 8, 18)),
                before_play=lambda: order.append("muzigi-durdur"),
            )
            scheduler.tick()
            self.assertEqual(["muzigi-durdur", "zil"], order)

    def test_busy_playback_defers_event_until_lock_is_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, _, backend, state = self._scheduler(directory, datetime(2026, 9, 7, 8, 18))
            playback = scheduler.playback
            # Manuel bir ses çalıyormuş gibi kilidi dışarıdan tut.
            self.assertTrue(playback._lock.acquire(blocking=False))
            try:
                first = scheduler.tick()
            finally:
                playback._lock.release()
            self.assertEqual(1, len(first))
            self.assertEqual("uyarı", first[0].level)
            self.assertIn("bekletildi", first[0].message)
            # Pilot günlüğü sözleşmesi: bekletilen olay çalma sonucu taşımaz.
            self.assertIsNone(first[0].result)
            # Olay tamamlanmış sayılmadı; kilit boşalınca zil gerçekten çalar.
            self.assertEqual(0, sum(call[0] == "file" for call in backend.calls))
            second = scheduler.tick()
            self.assertEqual(1, len(second))
            self.assertTrue(second[0].result is not None and second[0].result.success)
            self.assertEqual(1, sum(call[0] == "file" for call in backend.calls))
            # Aynı olay için ikinci kez "bekletildi" uyarısı üretilmez.
            self.assertEqual([], scheduler.tick())

    def test_missed_events_are_logged_not_burst_played(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, _, backend, _ = self._scheduler(directory, datetime(2026, 9, 7, 12, 0))
            notices = scheduler.tick()
            self.assertTrue(any("topluca çalınmadı" in item.message for item in notices))
            self.assertEqual(0, sum(call[0] == "file" for call in backend.calls))

    def test_event_inside_grace_window_plays(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, _, backend, _ = self._scheduler(directory, datetime(2026, 9, 7, 8, 21), grace=90)
            scheduler.tick()
            self.assertEqual(1, sum(call[0] == "file" for call in backend.calls))

    def test_event_type_specific_grace_overrides_global_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = replace(
                default_config(),
                grace_seconds=30,
                grace_seconds_by_type={EventType.LESSON_START.value: 120},
            )
            for relative in config.sounds.values():
                write_wave(root / relative)
            backend = MockAudioBackend()
            scheduler = BellScheduler(
                config,
                CalendarEngine(config),
                PlaybackManager(backend),
                root,
                RunState(),
                FakeClock(datetime(2026, 9, 7, 8, 21)),
            )
            scheduler.tick()
            self.assertEqual(1, sum(kind == "file" for kind, _ in backend.calls))

    def test_backward_clock_jump_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, clock, _, _ = self._scheduler(directory, datetime(2026, 9, 7, 7, 0))
            scheduler.tick()
            clock.set(clock.now() - timedelta(minutes=10))
            notices = scheduler.tick()
            self.assertTrue(any("sıçrama" in item.message and item.level == "kritik" for item in notices))

    def test_small_clock_jump_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, clock, _, _ = self._scheduler(directory, datetime(2026, 9, 7, 7, 0))
            scheduler.tick()
            clock.set(clock.now() + timedelta(seconds=10))
            notices = scheduler.tick()
            self.assertTrue(any("sıçrama" in item.message and item.level == "kritik" for item in notices))

    def test_wakeup_without_suspend_aware_monotonic_is_warning_not_critical(self) -> None:
        # O4: Linux'ta CLOCK_MONOTONIC askıyı saymaz; uyanma duvar saatinde
        # büyük pozitif kayma gibi görünür. Bu kritik sıçrama değil uyarıdır.
        with tempfile.TemporaryDirectory() as directory:
            scheduler, clock, _, _ = self._scheduler(directory, datetime(2026, 9, 7, 7, 0))
            scheduler.tick()
            clock.set(clock.now() + timedelta(hours=2))
            notices = scheduler.tick()
            self.assertTrue(any("ileri alınması" in item.message and item.level == "uyarı" for item in notices))
            self.assertFalse(any("sıçrama" in item.message for item in notices))

    def test_sleep_is_distinguished_from_wall_clock_jump(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, clock, _, _ = self._scheduler(
                directory, datetime(2026, 9, 7, 7, 0)
            )
            scheduler.tick()
            clock.advance(timedelta(minutes=10))
            notices = scheduler.tick()
            self.assertTrue(any("Uyku" in item.message for item in notices))
            self.assertFalse(any("sıçrama" in item.message for item in notices))

    def test_midnight_transition_uses_new_date_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, clock, _, _ = self._scheduler(directory, datetime(2026, 9, 6, 23, 59, 59))
            before = scheduler.next_event()
            clock.advance(timedelta(seconds=2))
            after = scheduler.next_event()
            self.assertEqual(date(2026, 9, 7), before.scheduled_at.date())
            self.assertEqual(before.event_id, after.event_id)

    def test_same_time_events_play_in_sequence_and_validate_device_each_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = EventSpec(time(8, 20), EventType.CEREMONY, "Saygı duruşu", "bir", sequence=0)
            second = EventSpec(time(8, 20), EventType.ANNOUNCEMENT, "İstiklâl Marşı", "iki", sequence=1)
            config = replace(
                default_config(),
                sounds={"bir": "sesler/bir.wav", "iki": "sesler/iki.wav"},
                weekly_schedule={0: (first, second)},
            )
            write_wave(root / "sesler" / "bir.wav")
            write_wave(root / "sesler" / "iki.wav")
            backend = MockAudioBackend()
            scheduler = BellScheduler(
                config,
                CalendarEngine(config),
                PlaybackManager(backend),
                root,
                RunState(),
                FakeClock(datetime(2026, 9, 7, 8, 20)),
            )
            scheduler.tick()
            files = [value for kind, value in backend.calls if kind == "file"]
            checks = [value for kind, value in backend.calls if kind == "device"]
            self.assertEqual(["bir.wav", "iki.wav"], files)
            self.assertEqual(["varsayilan", "varsayilan"], checks)

    def test_announcement_uses_separate_configured_device(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event = EventSpec(time(8, 20), EventType.ANNOUNCEMENT, "Anons", "anons")
            config = replace(
                default_config(),
                announcement_device="anons-karti",
                weekly_schedule={0: (event,)},
            )
            write_wave(root / config.sounds["anons"])
            backend = MockAudioBackend(available_devices={"varsayilan", "anons-karti"})
            scheduler = BellScheduler(
                config,
                CalendarEngine(config),
                PlaybackManager(backend),
                root,
                RunState(),
                FakeClock(datetime(2026, 9, 7, 8, 20)),
            )
            scheduler.tick()
            self.assertIn(("device", "anons-karti"), backend.calls)

    def test_deferred_event_does_not_play_at_original_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, clock, backend, _ = self._scheduler(
                directory, datetime(2026, 9, 7, 8, 17)
            )
            deferred = scheduler.defer_next(5)
            self.assertEqual(datetime(2026, 9, 7, 8, 23), deferred.scheduled_at)
            clock.advance(timedelta(minutes=1))
            self.assertEqual([], scheduler.tick())
            clock.advance(timedelta(minutes=5))
            scheduler.tick()
            self.assertEqual(1, sum(kind == "file" for kind, value in backend.calls))

    def test_mute_marks_due_event_without_playing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, clock, backend, _ = self._scheduler(
                directory, datetime(2026, 9, 7, 8, 20)
            )
            scheduler.mute_until(datetime(2026, 9, 7, 23, 59, 59))
            notices = scheduler.tick()
            self.assertTrue(any("Sessize alma" in item.message for item in notices))
            self.assertEqual(0, sum(kind == "file" for kind, value in backend.calls))

    def test_defer_and_mute_state_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "durum.json"
            first = RunState(path)
            deferred_at = datetime(2026, 9, 7, 8, 25)
            muted_until = datetime(2026, 9, 7, 23, 59, 59)
            first.defer("olay", deferred_at)
            first.set_muted_until(muted_until)
            restored = RunState(path)
            self.assertEqual(deferred_at, restored.deferred["olay"])
            self.assertEqual(muted_until, restored.muted_until)

    # --- D1: kimlik kural adından bağımsız -------------------------------

    def _add_today_ceremony(self, scheduler: BellScheduler, day: date) -> None:
        rule = DateRule(
            "Bayrak töreni", ExceptionKind.CEREMONY, day, day,
            (EventSpec(time(10, 0), EventType.CEREMONY, "Bayrak töreni", "anons"),),
        )
        config = replace(scheduler.config, date_rules=[rule])
        scheduler.update_config(config, CalendarEngine(config))

    def test_adding_a_rule_mid_day_does_not_replay_bells_within_grace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, clock, backend, _ = self._scheduler(directory, datetime(2026, 9, 7, 8, 20))
            scheduler.tick()
            self.assertEqual(1, sum(kind == "file" for kind, _ in backend.calls))
            self._add_today_ceremony(scheduler, date(2026, 9, 7))
            clock.advance(timedelta(seconds=30))
            notices = scheduler.tick()
            self.assertEqual(1, sum(kind == "file" for kind, _ in backend.calls))
            self.assertFalse(any("Kaçırılan" in item.message for item in notices))

    def test_deferral_survives_mid_day_rule_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, clock, backend, _ = self._scheduler(directory, datetime(2026, 9, 7, 8, 17))
            deferred = scheduler.defer_next(5)
            self.assertEqual(datetime(2026, 9, 7, 8, 23), deferred.scheduled_at)
            self._add_today_ceremony(scheduler, date(2026, 9, 7))
            clock.advance(timedelta(minutes=2))  # 08:19: özgün saat geçti
            scheduler.tick()
            self.assertEqual(0, sum(kind == "file" for kind, _ in backend.calls))
            clock.advance(timedelta(minutes=4))  # 08:23: ertelenen saat
            scheduler.tick()
            self.assertEqual(1, sum(kind == "file" for kind, _ in backend.calls))

    # --- D3: durum dosyası dayanıklılığı -----------------------------------

    def test_state_save_failure_keeps_ticking_and_reports_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = default_config()
            for relative in config.sounds.values():
                write_wave(root / relative)
            backend = MockAudioBackend()
            state = RunState(root / "durum.json")
            state.needs_resync = False
            state.recovery_note = None
            scheduler = BellScheduler(
                config, CalendarEngine(config), PlaybackManager(backend), root, state,
                FakeClock(datetime(2026, 9, 7, 8, 20)),
            )
            with mock.patch("okul_zili.scheduler.os.replace", side_effect=OSError("disk dolu")):
                notices = scheduler.tick()
                # 08:18 öğrenci zili toleransı aştı (uyarı), 08:20 çaldı; ikisi
                # de işlendi, yazma hatası tek kritik uyarı olarak eklendi.
                self.assertEqual(1, sum(kind == "file" for kind, _ in backend.calls))
                self.assertTrue(any("Kaçırılan" in item.message for item in notices))
                critical = [item for item in notices if item.level == "kritik"]
                self.assertEqual(1, len(critical))
                self.assertIn("yazılamadı", critical[0].message)
                self.assertEqual([], scheduler.tick())
            # Yazma yeniden mümkün olunca sonraki işaretleme diske ulaşır.
            state.mark("sonra")
            self.assertIsNone(state.save_error)
            self.assertIn("sonra", json.loads((root / "durum.json").read_text(encoding="utf-8"))["completed"])

    def test_completed_entries_expire_by_age_not_lexicographically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "durum.json"
            state = RunState(path)
            now = datetime.now()
            state.mark("aaa-eski", now - timedelta(days=10))
            state.mark("zzz-yeni", now)
            state.mark("mmm-dun", now - timedelta(days=1))
            restored = RunState(path)
            self.assertEqual({"zzz-yeni", "mmm-dun"}, set(restored.completed))
            self.assertEqual(STATE_IDENTITY_VERSION, json.loads(path.read_text(encoding="utf-8"))["identity_version"])

    def _resync_scheduler(self, directory: str, state: RunState):
        root = Path(directory)
        config = default_config()
        for relative in config.sounds.values():
            write_wave(root / relative)
        backend = MockAudioBackend()
        scheduler = BellScheduler(
            config, CalendarEngine(config), PlaybackManager(backend), root, state,
            FakeClock(datetime(2026, 9, 7, 12, 0)),
        )
        return scheduler, backend

    def test_legacy_state_file_resyncs_without_replaying_or_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "durum.json"
            path.write_text(json.dumps({"completed": ["eski-kimlik"], "deferred": {}, "muted_until": None}), encoding="utf-8")
            state = RunState(path)
            self.assertTrue(state.needs_resync)
            scheduler, backend = self._resync_scheduler(directory, state)
            notices = scheduler.tick()
            self.assertEqual(0, sum(kind == "file" for kind, _ in backend.calls))
            self.assertFalse(any("Kaçırılan" in item.message for item in notices))
            self.assertTrue(any("eşitlendi" in item.message for item in notices))
            self.assertEqual([], scheduler.tick())
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(STATE_IDENTITY_VERSION, raw["identity_version"])
            self.assertIn("eski-kimlik", raw["completed"])

    def test_unreadable_state_file_is_quarantined_and_resynced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "durum.json"
            path.write_text("{bozuk", encoding="utf-8")
            state = RunState(path)
            self.assertTrue(state.needs_resync)
            self.assertIn("okunamadı", state.recovery_note or "")
            self.assertTrue(any("bozuk-" in item.name for item in path.parent.iterdir()))
            scheduler, backend = self._resync_scheduler(directory, state)
            notices = scheduler.tick()
            self.assertEqual(0, sum(kind == "file" for kind, _ in backend.calls))
            self.assertTrue(any(item.level == "uyarı" and "okunamadı" in item.message for item in notices))
            self.assertFalse(any("Kaçırılan" in item.message for item in notices))

    def test_fresh_state_file_resyncs_past_events_silently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = RunState(Path(directory) / "durum.json")
            scheduler, backend = self._resync_scheduler(directory, state)
            notices = scheduler.tick()
            self.assertFalse(any("Kaçırılan" in item.message for item in notices))
            self.assertFalse(any(item.level in ("uyarı", "kritik") for item in notices))
            self.assertEqual(0, sum(kind == "file" for kind, _ in backend.calls))

    def test_identical_events_play_once_per_tick(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = EventSpec(time(9, 45), EventType.ANNOUNCEMENT, "Anons", "anons")
            config = replace(default_config(), weekly_schedule={}, extra_events={0: (spec, spec)})
            write_wave(root / config.sounds["anons"])
            backend = MockAudioBackend()
            scheduler = BellScheduler(
                config, CalendarEngine(config), PlaybackManager(backend), root, RunState(),
                FakeClock(datetime(2026, 9, 7, 9, 45)),
            )
            notices = scheduler.tick()
            self.assertEqual(1, sum(kind == "file" for kind, _ in backend.calls))
            self.assertEqual(1, len([item for item in notices if item.result is not None]))

    # --- D4: meşgul penceresi ---------------------------------------------

    def test_bell_due_during_long_scheduled_playback_plays_afterwards(self) -> None:
        class LongPlaybackBackend(MockAudioBackend):
            def __init__(self, clock: FakeClock, seconds: int) -> None:
                super().__init__()
                self.clock = clock
                self.seconds = seconds

            def play_file(self, path: Path, device_id: str) -> None:
                super().play_file(path, device_id)
                # Uzun tören kaydı: çalma boyunca duvar saati ilerler.
                self.clock.advance(timedelta(seconds=self.seconds))
                self.seconds = 0

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ceremony = EventSpec(time(9, 5), EventType.CEREMONY, "10 Kasım", "on_kasim_butun")
            announcement = EventSpec(time(9, 6), EventType.ANNOUNCEMENT, "Anons", "anons")
            config = replace(default_config(), weekly_schedule={}, extra_events={0: (ceremony, announcement)})
            for relative in config.sounds.values():
                write_wave(root / relative)
            clock = FakeClock(datetime(2026, 9, 7, 9, 5))
            backend = LongPlaybackBackend(clock, 182)
            scheduler = BellScheduler(config, CalendarEngine(config), PlaybackManager(backend), root, RunState(), clock)
            scheduler.tick()
            self.assertEqual(datetime(2026, 9, 7, 9, 8, 2), clock.now())
            notices = scheduler.tick()
            self.assertEqual(2, sum(kind == "file" for kind, _ in backend.calls))
            self.assertFalse(any("Kaçırılan" in item.message for item in notices))

    def test_bell_due_during_manual_playback_plays_after_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = EventSpec(time(9, 0), EventType.ANNOUNCEMENT, "Anons", "anons")
            config = replace(default_config(), weekly_schedule={}, extra_events={0: (spec,)})
            write_wave(root / config.sounds["anons"])
            backend = MockAudioBackend()
            clock = FakeClock(datetime(2026, 9, 7, 8, 59))
            scheduler = BellScheduler(config, CalendarEngine(config), PlaybackManager(backend), root, RunState(), clock)
            scheduler.tick()
            playback = scheduler.playback
            self.assertTrue(playback._lock.acquire(blocking=False))
            try:
                clock.advance(timedelta(minutes=1))  # 09:00: elle yayın sürüyor
                first = scheduler.tick()
                self.assertTrue(any("bekletildi" in item.message for item in first))
                clock.advance(timedelta(minutes=3))  # 09:03: hâlâ sürüyor
                scheduler.tick()
            finally:
                playback._lock.release()
            clock.advance(timedelta(seconds=1))
            notices = scheduler.tick()
            self.assertEqual(1, sum(kind == "file" for kind, _ in backend.calls))
            self.assertFalse(any("Kaçırılan" in item.message for item in notices))

    # --- 6.5: duraklatma --------------------------------------------------

    def test_paused_scheduler_marks_due_events_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, clock, backend, _ = self._scheduler(directory, datetime(2026, 9, 7, 8, 20))
            notices = scheduler.tick(paused=True)
            self.assertEqual(0, sum(kind == "file" for kind, _ in backend.calls))
            self.assertTrue(any("duraklatıldığı için" in item.message and item.level == "uyarı" for item in notices))
            self.assertTrue(all(item.result is None for item in notices))
            clock.advance(timedelta(seconds=10))
            # Sürdürünce eski ziller topluca çalmaz, sahte uyku uyarısı üretilmez.
            resumed = scheduler.tick()
            self.assertEqual(0, sum(kind == "file" for kind, _ in backend.calls))
            self.assertFalse(any("Uyku" in item.message for item in resumed))


if __name__ == "__main__":
    unittest.main()
