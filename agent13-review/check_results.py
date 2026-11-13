import pathlib,sys,xml.etree.ElementTree as E
mode=sys.argv[1]; exitcode=int(sys.argv[2]); found={}
for file in pathlib.Path('project/server').glob('**/target/surefire-reports/TEST-*.xml'):
 try:
  r=E.parse(file).getroot(); name=r.get('name','').rsplit('.',1)[-1]
  if name not in ('DiagnosticsCompletenessTest','Agent13Pr197IsolationSentinelTest'): continue
  if name in found: raise RuntimeError('duplicate report')
  found[name]=r
 except Exception:
  print('REPORT_PARSE_ERROR=1');sys.exit(2)
for n in ('DiagnosticsCompletenessTest','Agent13Pr197IsolationSentinelTest'):
 r=found.get(n)
 print(n+'='+str(None if r is None else tuple(int(r.get(k,'0')) for k in ('tests','failures','errors','skipped'))))
if len(found)!=2:
 print('EXPECTED_XML_MISSING=1');sys.exit(2)
def failed(cls,name):
 cases=[t for t in found[cls].findall('testcase') if t.get('name')==name]
 if len(cases)!=1:raise RuntimeError('expected exact test missing/duplicate')
 return cases[0].find('failure') is not None or cases[0].find('error') is not None
sent='Agent13Pr197IsolationSentinelTest';diag='DiagnosticsCompletenessTest'
try:
 if mode in ('baseline','setup_failure'):
  ok=exitcode==0 and all(int(r.get(k,'0'))==0 for r in found.values() for k in ('failures','errors','skipped')) and not failed(sent,'preservesIdentityAndAliasAfterSetupOrInjectedFailure')
 elif mode=='registry_negative':
  ok=exitcode!=0 and failed(sent,'preservesIdentityAndAliasAfterSetupOrInjectedFailure')
 elif mode in ('marker_negative','count_negative'):
  ok=exitcode!=0 and failed(diag,'eclipseMarkerStoreCoreExceptionFailsClosedAcrossAllModes')
 elif mode=='coverage_negative':
  ok=exitcode!=0 and failed(diag,'coverageProviderFailureMarksCompletenessIncompleteFailClosed')
 else:ok=False
except RuntimeError as e:
 print('MISSING_EXPECTED_TEST=1');sys.exit(2)
print('MAVEN_EXIT='+str(exitcode));print('EXPECTED_RESULT='+('PASS' if ok else 'FAIL'));print('ARTIFACTS_UPLOADED=0');sys.exit(0 if ok else 1)
