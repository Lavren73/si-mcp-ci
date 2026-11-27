"""Тесты клиентского сторожа красных (red_names_guard).

Проверяют ровно то, на чём он однажды ошибся:
- ложный РЕГРЕСС из-за префиксов (клиент/ против tests/) — канон();
- ложный РЕГРЕСС из-за окруженческих ERROR (фикстуры `test_installer.py`,
  которым нужен собранный si-agent-setup.zip) — секция `# Исключение:`;
- что исключение НЕ может спрятать FAILED, иначе сторож перестанет ловить регресс;
- что неполный/оборванный прогон не даёт «всё хорошо».
"""
from __future__ import annotations

import pathlib
import tempfile
import unittest

import red_names_guard as g

ЛОГ_ЧИСТЫЙ = """\
.........FF
FAILED client/tests/test_panel_unknown_outcome.py::PanelUnknownOutcome::test_lost_write_response_does_not_trigger_rollback
FAILED client/tests/test_terminal_offline.py::OfflineTests::test_no_rollback_on_malformed_diagnostics_after_write
ERROR client/tests/test_installer.py::TestLaunchOpensWindow::test_окно_по_умолчанию_чат_по_флагу
ERROR client/tests/test_installer.py::TestLaunchOpensWindow::test_подсказка_говорит_про_браузер
2 failed, 1401 passed, 21 skipped, 2 errors, 213 subtests passed in 152.39s
"""

ЭТАЛОН = """\
# Total: 1399  (failed+passed)
# Исключение: tests/test_installer.py::TestLaunchOpensWindow::test_окно_по_умолчанию_чат_по_флагу
# Исключение: tests/test_installer.py::TestLaunchOpensWindow::test_подсказка_говорит_про_браузер
tests/test_panel_unknown_outcome.py::PanelUnknownOutcome::test_lost_write_response_does_not_trigger_rollback
tests/test_terminal_offline.py::OfflineTests::test_no_rollback_on_malformed_diagnostics_after_write
"""


def _run(лог: str, эталон: str) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as d:
        p1 = pathlib.Path(d) / "pytest.log"
        p2 = pathlib.Path(d) / "etalon.txt"
        p1.write_text(лог, encoding="utf-8")
        p2.write_text(эталон, encoding="utf-8")
        code = g.main(["red_names_guard.py", str(p1), str(p2)])
        return code, ""


def _call(лог: str, эталон: str) -> int:
    with tempfile.TemporaryDirectory() as d:
        p1 = pathlib.Path(d) / "pytest.log"
        p2 = pathlib.Path(d) / "etalon.txt"
        p1.write_text(лог, encoding="utf-8")
        p2.write_text(эталон, encoding="utf-8")
        out = []
        import builtins
        real = builtins.print

        def spy(*a, **k):
            real(*a, **k)
            out.append(" ".join(str(x) for x in a))

        builtins.print = spy
        try:
            code = g.main(["red_names_guard.py", str(p1), str(p2)])
        finally:
            builtins.print = real
        _call.last = out  # type: ignore[attr-defined]
        return code


class GuardTest(unittest.TestCase):
    def test_environment_errors_are_skipped_but_listed(self):
        code = _call(ЛОГ_ЧИСТЫЙ, ЭТАЛОН)
        текст = " | ".join(_call.last)  # type: ignore[attr-defined]
        self.assertEqual(code, 0, текст)
        self.assertIn("СТОРОЖ_ВЕРДИКТ=CLEAN", текст)
        self.assertIn("СТОРОЖ_ИСКЛЮЧЕНО=2", текст)
        self.assertIn("ИСКЛЮЧЁН: tests/test_installer.py::TestLaunchOpensWindow", текст)

    def test_without_exclusion_same_log_is_regression(self):
        эталон = ЭТАЛОН.replace("# Исключение:", "# (нет) Исключение:")
        code = _call(ЛОГ_ЧИСТЫЙ, эталон)
        self.assertEqual(code, 1)
        self.assertIn("СТОРОЖ_НОВЫЕ=2", " | ".join(_call.last))  # type: ignore[attr-defined]

    def test_failed_cannot_be_excluded(self):
        лог = ЛОГ_ЧИСТЫЙ + "FAILED client/tests/test_new_break.py::C::m\n"
        эталон = ЭТАЛОН + "# Исключение: tests/\n"
        code = _call(лог, эталон)
        self.assertEqual(code, 1)
        self.assertIn("НОВЫЙ: tests/test_new_break.py::C::m", " | ".join(_call.last))  # type: ignore[attr-defined]

    def test_unlisted_error_still_blocks(self):
        лог = ЛОГ_ЧИСТЫЙ + "ERROR client/tests/test_other.py::C::m\n"
        code = _call(лог, ЭТАЛОН)
        self.assertEqual(code, 1)

    def test_prefix_difference_does_not_matter(self):
        лог = ЛОГ_ЧИСТЫЙ.replace("client/tests/", "tests/")
        self.assertEqual(_call(лог, ЭТАЛОН), 0)

    def test_truncated_run_has_no_verdict(self):
        лог = ЛОГ_ЧИСТЫЙ.replace("2 failed, 1401 passed", "2 failed, 300 passed")
        code = _call(лог, ЭТАЛОН)
        self.assertEqual(code, 1)
        self.assertIn("INCOMPLETE", " | ".join(_call.last))  # type: ignore[attr-defined]

    def test_names_flag_omitted_has_no_verdict(self):
        лог = "2 failed, 1401 passed, 21 skipped in 152.39s\n"
        self.assertEqual(_call(лог, ЭТАЛОН), 1)

    def test_fewer_reds_is_stale_not_clean(self):
        лог = ".........\n2 skipped in 152.39s\n"
        code = _call(лог.replace("2 skipped", "1401 passed, 21 skipped"), ЭТАЛОН)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
