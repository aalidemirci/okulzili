from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from okul_zili.instance import SingleInstanceLock


class SingleInstanceTests(unittest.TestCase):
    def test_second_instance_is_rejected_until_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "uygulama.lock"
            first = SingleInstanceLock(path)
            second = SingleInstanceLock(path)
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()

    def test_activation_request_is_consumed_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = SingleInstanceLock(Path(directory) / "uygulama.lock")
            self.assertFalse(lock.consume_activation_request())
            lock.request_activation()
            self.assertTrue(lock.activation_path.is_file())
            self.assertTrue(lock.consume_activation_request())
            self.assertFalse(lock.consume_activation_request())


if __name__ == "__main__":
    unittest.main()
