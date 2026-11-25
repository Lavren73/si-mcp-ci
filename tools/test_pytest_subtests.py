import pathlib
import tempfile
import unittest

from pytest_subtests import count_subtests, main, verdict


class PytestSubtestsTest(unittest.TestCase):
    def test_reads_final_summary(self):
        text = "old: 212 subtests passed\n1435 passed, 213 subtests passed in 4.2s\n"
        self.assertEqual(count_subtests(text), 213)

    def test_missing_field_is_not_silently_zero(self):
        with self.assertRaises(ValueError):
            count_subtests("1435 passed in 4.2s\n")

    def test_equal_or_greater_is_clean(self):
        self.assertEqual(verdict(213, 213), (True, 0, "CLEAN"))
        self.assertEqual(verdict(214, 213), (True, 1, "CLEAN"))

    def test_minus_one_requires_explanation(self):
        self.assertEqual(
            verdict(212, 213),
            (False, -1, "REQUIRES_EXPLANATION"),
        )

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            log = pathlib.Path(directory) / "pytest.log"
            log.write_text("1435 passed, 213 subtests passed in 4.2s\n")
            self.assertEqual(main([str(log), "--baseline", "213"]), 0)
            self.assertEqual(main([str(log), "--baseline", "214"]), 1)
            log.write_text("pytest crashed before summary\n")
            self.assertEqual(main([str(log), "--baseline", "0"]), 2)


if __name__ == "__main__":
    unittest.main()
