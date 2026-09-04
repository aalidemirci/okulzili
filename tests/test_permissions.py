from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "okul_zili" / "app.py"


def _method(tree: ast.Module, class_name: str, method_name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    raise AssertionError(f"{class_name}.{method_name} bulunamadı.")


def _calls_permission(function: ast.FunctionDef, action: str) -> bool:
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_require_permission"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == action
        ):
            return True
    return False


class PermissionGuardTests(unittest.TestCase):
    """D7: yetki denetimi düğme durumuna bırakılmaz; metotlar rolü doğrular.

    ``OkulZiliApp`` Tk olmadan örneklenemediği için denetim kaynak ağacı
    üzerinden yapılır: listelenen her metot ilgili eylem için
    ``_require_permission`` çağırmalıdır.
    """

    def setUp(self) -> None:
        self.tree = ast.parse(APP.read_text(encoding="utf-8"), filename=str(APP))

    def test_guarded_methods_check_the_expected_action(self) -> None:
        expectations = {
            "_stop_audio": "gunluk_eylem",
            "_manual_play": "gunluk_eylem",
            "_manual_sequence": "gunluk_eylem",
            "_toggle_scheduler": "gunluk_eylem",
            "_defer_next": "gunluk_eylem",
            "_toggle_mute_today": "gunluk_eylem",
            "_clear_critical_alerts": "gunluk_eylem",
            "_open_management_center": "yapilandir",
            "_open_profile_manager": "yapilandir",
            "_open_settings": "yapilandir",
            "_backup_menu": "yapilandir",
            "_regenerate_schedule": "yapilandir",
            "_reset_schedule": "yapilandir",
            "_delete_rule": "yapilandir",
            "_request_exit": "kapat",
        }
        for method_name, action in expectations.items():
            with self.subTest(method=method_name):
                function = _method(self.tree, "OkulZiliApp", method_name)
                self.assertTrue(_calls_permission(function, action))

    def test_tray_stop_audio_is_dispatched_to_the_main_thread(self) -> None:
        # Yetki iletisi bir Tk penceresidir; tepsi iş parçacığından doğrudan
        # çağrılamaz. Tüm tepsi geri çağrıları root.after ile aktarılır.
        init = _method(self.tree, "OkulZiliApp", "__init__")
        for node in ast.walk(init):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "TrayController":
                for keyword in node.keywords:
                    with self.subTest(callback=keyword.arg):
                        self.assertIsInstance(keyword.value, ast.Lambda)
                        body = keyword.value.body
                        self.assertIsInstance(body, ast.Call)
                        self.assertEqual("after", body.func.attr)  # type: ignore[union-attr]
                return
        self.fail("TrayController kurulumu bulunamadı.")

    def test_lock_button_demotes_to_view_only(self) -> None:
        lock = _method(self.tree, "OkulZiliApp", "_lock_session")
        calls = [
            node.args[0].value
            for node in ast.walk(lock)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "set_role"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ]
        self.assertEqual(["goruntuleme"], calls)


if __name__ == "__main__":
    unittest.main()
