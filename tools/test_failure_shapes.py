import contextlib
import io
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import failure_shapes as m

class FailureShapes(unittest.TestCase):
    def test_only_whitelisted_method_and_fixed_flags(self):
        method='si.edt.mcp.server.ops.EditFormToolNoEDTTest#executeWithNoParamsReturnsError'
        cls,name=method.split('#')
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'TEST-one.xml'
            path.write_text('<testsuite><testcase classname="'+cls+'" name="'+name+'">'
              '<error type="java.lang.NoClassDefFoundError" message="SECRET_CREDENTIAL_123">'
              'java.lang.NoClassDefFoundError SECRET_CREDENTIAL_123</error></testcase>'
              '<testcase classname="leak.SECRET_CREDENTIAL_123" name="x">'
              '<failure message="SECRET_CREDENTIAL_123">NullPointerException</failure>'
              '</testcase></testsuite>')
            out=io.StringIO()
            with patch.object(sys,'argv',['failure_shapes',str(path)]),contextlib.redirect_stdout(out):
                self.assertEqual(m.main(),0)
            text=out.getvalue()
            self.assertIn('NO_CLASS_DEF',text)
            self.assertIn('OTHER_FAILURE_ELEMENTS=1',text)
            self.assertNotIn('SECRET_CREDENTIAL_123',text)
            self.assertNotIn(str(path),text)
            self.assertNotIn('NullPointerException',text)
    def test_malformed_and_empty_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'TEST-bad.xml';path.write_text('<bad')
            totals,res=m.analyze([str(path)])
            self.assertEqual(totals['parse_errors'],1);self.assertEqual(res,{})
            with patch.object(sys,'argv',['failure_shapes',str(path)]),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(m.main(),1)
            with patch.object(sys,'argv',['failure_shapes',str(path)+'missing']),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(m.main(),1)

if __name__=='__main__':unittest.main()
