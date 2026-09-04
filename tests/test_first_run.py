from __future__ import annotations

import ast
from pathlib import Path
import tkinter as tk
import unittest

from okul_zili.app import _reveal_main_window


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "src" / "okul_zili"


def _class_node(filename: str, name: str) -> ast.ClassDef:
    tree = ast.parse((SOURCES / filename).read_text(encoding="utf-8"), filename=filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"{name} sınıfı {filename} içinde bulunamadı.")


def _references(filename: str, name: str) -> bool:
    """Kaynakta ``name`` adının içe aktarıldığı ya da kullanıldığı yer var mı?"""
    tree = ast.parse((SOURCES / filename).read_text(encoding="utf-8"), filename=filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
        if isinstance(node, ast.ImportFrom) and any(alias.name == name for alias in node.names):
            return True
        if isinstance(node, ast.Import) and any(
            alias.name.split(".")[-1] == name for alias in node.names
        ):
            return True
    return False


def _assigned_variable_names(node: ast.ClassDef, method: str) -> set[str]:
    """``self.<ad>_var = tk.<...>Var(...)`` biçimindeki atamaların adları."""
    names: set[str] = set()
    for function in node.body:
        if not isinstance(function, ast.FunctionDef) or function.name != method:
            continue
        for statement in ast.walk(function):
            if not isinstance(statement, ast.Assign):
                continue
            call = statement.value
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if not call.func.attr.endswith("Var"):
                continue
            for target in statement.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    names.add(target.attr)
    return names


class InitialSetupScopeTests(unittest.TestCase):
    """İlk kurulum yalnız okul bilgisini sorar; zil düzeni sonra kurulur."""

    def test_initial_setup_only_asks_for_school_identity(self) -> None:
        names = _assigned_variable_names(
            _class_node("dialogs.py", "InitialSetupDialog"), "__init__"
        )
        self.assertEqual({"school_var", "device_var"}, names)

    def test_schedule_reset_dialog_owns_the_lesson_flow_fields(self) -> None:
        node = _class_node("dialogs.py", "ScheduleResetDialog")
        names = _assigned_variable_names(node, "__init__")
        self.assertLessEqual(
            {"mode_var", "scope_var", "student_bell_var", "clear_extras_var"}, names
        )

    def test_pin_windows_no_longer_use_the_legacy_input_boxes(self) -> None:
        # PIN oluşturma artık uygulamanın kart tasarımını kullanan PinDialog
        # ile yapılır; Tk'nin gri simpledialog kutuları hiçbir yerde kalmadı.
        for filename in ("app.py", "dialogs.py"):
            with self.subTest(filename=filename):
                self.assertFalse(_references(filename, "simpledialog"))


class MainWindowRevealTests(unittest.TestCase):
    """Giriş penceresi kapandığında ana pencere görünür kalmalıdır."""

    class FakeRoot:
        def __init__(self, update_error: bool = False) -> None:
            # CustomTkinter'ın Windows açılış bayrakları.
            self._withdraw_called_before_window_exists = True
            self._iconify_called_before_window_exists = True
            self._update_error = update_error
            self.calls: list[str] = []

        def deiconify(self) -> None:
            self.calls.append("deiconify")

        def lift(self) -> None:
            self.calls.append("lift")

        def update(self) -> None:
            self.calls.append("update")
            if self._update_error:
                raise tk.TclError("mock pencere hatası")

    def test_reveal_clears_the_deferred_hide_flags_and_shows_the_window(self) -> None:
        root = self.FakeRoot()

        _reveal_main_window(root)

        self.assertFalse(root._withdraw_called_before_window_exists)
        self.assertFalse(root._iconify_called_before_window_exists)
        self.assertEqual(["deiconify", "lift", "update"], root.calls)

    def test_reveal_survives_a_window_error(self) -> None:
        root = self.FakeRoot(update_error=True)

        _reveal_main_window(root)

        self.assertFalse(root._withdraw_called_before_window_exists)
        self.assertEqual(["deiconify", "lift", "update"], root.calls)


if __name__ == "__main__":
    unittest.main()
