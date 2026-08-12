from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
import tempfile
import threading
import unittest

from okul_zili.audio import PlaybackManager
from okul_zili.calendar_engine import CalendarEngine
from okul_zili.defaults import default_config
from okul_zili.domain import EventSpec, EventType
from okul_zili.scheduler import BellScheduler, FakeClock, RunState
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
            self.assertEqual({f"olay-{index}" for index in range(30)}, restored.completed)

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

    def test_clock_jump_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scheduler, clock, _, _ = self._scheduler(directory, datetime(2026, 9, 7, 7, 0))
            scheduler.tick()
            clock.set(clock.now() + timedelta(hours=2))
            notices = scheduler.tick()
            self.assertTrue(any("sıçrama" in item.message for item in notices))

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


if __name__ == "__main__":
    unittest.main()
