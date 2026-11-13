import pathlib,sys,xml.etree.ElementTree as E
mode=sys.argv[1]; exitcode=int(sys.argv[2]); found={}
expected={'DiagnosticsCompletenessTest':13,'Agent13Pr197IsolationSentinelTest':1,'TheEmptyFirstReadIsRetriedTest':4,'Agent13InterruptedBaselineTest':3}
for f in pathlib.Path('project/server').glob('**/target/surefire-reports/TEST-*.xml'):
 r=E.parse(f).getroot();name=r.get('name','').rsplit('.',1)[-1]
 if name in expected:
  if name in found:raise RuntimeError('duplicate XML')
  found[name]=r
for n in expected:
 r=found.get(n);print(n+'='+str(None if r is None else tuple(int(r.get(k,'0')) for k in ('tests','failures','errors','skipped'))))
if set(found)!=set(expected):print('REPORT_MISSING=1');sys.exit(2)
def fail(cls,name):
 x=[t for t in found[cls].findall('testcase') if t.get('name')==name]
 if len(x)!=1: raise RuntimeError('method missing or duplicate')
 return x[0].find('failure') is not None or x[0].find('error') is not None
if mode in ('baseline','setup_failure'):
 ok=exitcode==0 and all(int(found[n].get('tests','0'))==v and all(int(found[n].get(k,'0'))==0 for k in ('failures','errors','skipped')) for n,v in expected.items())
elif mode=='interrupt_negative':
 ok=(exitcode!=0 and fail('Agent13InterruptedBaselineTest','baselineRefusesInterruptedEmptyRetryWithoutPretendingSnapshot') and fail('Agent13InterruptedBaselineTest','laterInterruptAfterFirstRetryAlsoFailsClosed') and not fail('Agent13InterruptedBaselineTest','baselineHealthyControlReturnsSnapshot') and fail('TheEmptyFirstReadIsRetriedTest','anInterruptedRetryFailsClosedInsteadOfReportingClean'))
else:ok=False
print('MAVEN_EXIT='+str(exitcode));print('EXPECTED_RESULT='+('PASS' if ok else 'FAIL'));print('ARTIFACTS_UPLOADED=0');sys.exit(0 if ok else 1)
