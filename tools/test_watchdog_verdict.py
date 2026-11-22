import unittest
from watchdog_verdict import classify

class WatchdogVerdictTest(unittest.TestCase):
    def test_same(self):
        self.assertTrue(classify(0,'Список красных совпал с эталоном.')[0])
    def test_removed_only(self):
        result = classify(2,'Ушли из списка (1) — починили\n  - A.old | diagnostic\n')
        self.assertTrue(result[0]); self.assertEqual(result[3], ['A.old'])
    def test_new_and_removed_is_failure(self):
        text='НОВЫЕ падения (1) — это регресс:\n  + B.new | secret content\nУшли из списка (1) — починили\n  - A.old | another detail'
        result=classify(1,text);self.assertFalse(result[0]);self.assertEqual(result[2:],(['B.new'], ['A.old']))
    def test_wrong_return_code_never_green(self):
        self.assertFalse(classify(0,'НОВЫЕ падения (1)\n  + B.new\n')[0])
        self.assertFalse(classify(2,'НОВЫЕ падения (1)\n  + B.new\nУшли из списка (1)\n  - A.old')[0])
    def test_missing_and_partial_output_fail(self):
        for code, output in [(0,''),(1,''),(2,''),(2,'Ушли из списка (2)\n  - A.old')]:
            self.assertFalse(classify(code,output)[0])
    def test_malicious_or_ambiguous_identifier_fails(self):
        self.assertFalse(classify(2,'Ушли из списка (1)\n  - A.old secret')[0])
        self.assertFalse(classify(2,'Ушли из списка (1)\nУшли из списка (1)\n  - A.old')[0])
    def test_error_and_unexpected_exit_fail(self):
        for code in [1,3,127,-9]:self.assertFalse(classify(code,'Список красных совпал с эталоном.')[0])
    def test_no_header_and_conflicting_same_fail(self):
        self.assertFalse(classify(2,'  - A.old')[0])
        self.assertFalse(classify(2,'Ушли из списка (1)\n  - A.old\nСписок красных совпал с эталоном.')[0])
if __name__=='__main__':unittest.main()


class RawOutputOnFailure(unittest.TestCase):
    """При не-«same» обёрка обязана показать сырой stdout сторожа (урок #491)."""

    def _run(self, code, out, err=''):
        import subprocess as sp
        real = sp.run
        class P:
            returncode, stdout, stderr = code, out, err
        import watchdog_verdict as wv
        wv.subprocess.run = lambda *a, **k: P()
        try:
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                import sys as _s
                _s.argv = ['watchdog_verdict.py', 'x', 'y', 'z']
                wv.main()
            return buf.getvalue()
        finally:
            wv.subprocess.run = real

    def test_verdict_new_prints_raw_stdout(self):
        out = 'НОВЫЕ падения (1)\n  + A.t | msg detail\n'
        printed = self._run(1, out)
        self.assertIn('--- сторож: сырой stdout ---', printed)
        self.assertIn('+ A.t | msg detail', printed)

    def test_same_verdict_stays_quiet(self):
        out = 'Список красных совпал с эталоном.\n'
        printed = self._run(0, out)
        self.assertNotIn('сырой stdout', printed)
