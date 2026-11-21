import contextlib,io,pathlib,tempfile,unittest
import maven_log_flags as m
class LogFlags(unittest.TestCase):
 def test_fixed_booleans_no_raw_log(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'private.log';p.write_text('SECRET_PRIVATE_VALUE UnknownHostException\nBUILD FAILURE')
   out=io.StringIO()
   with contextlib.redirect_stdout(out):self.assertEqual(m.main(p),0)
   s=out.getvalue();self.assertIn('MAVEN_FLAG_NETWORK_NAME=true',s);self.assertIn('MAVEN_FLAG_MAVEN_REACTOR_FAILURE=true',s)
   self.assertNotIn('SECRET_PRIVATE_VALUE',s);self.assertNotIn('UnknownHostException',s);self.assertNotIn(str(p),s)
 def test_missing_file(self):
  with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()) as o:
   self.assertEqual(m.main(pathlib.Path(d)/'missing'),1);self.assertEqual(o.getvalue(),'MAVEN_LOG_READABLE=false\n')
if __name__=='__main__':unittest.main()
