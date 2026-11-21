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
