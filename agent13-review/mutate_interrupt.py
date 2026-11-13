import pathlib,sys
mode=sys.argv[1]
f=pathlib.Path('project/server/tests/si.edt.mcp.server.tests/src/si/edt/mcp/server/wire/DiagnosticsCompletenessWireTest.java')
p=pathlib.Path('project/server/bundles/si.edt.mcp.server/src/si/edt/mcp/server/toolkit/ops/ProjectProblemsReader.java')
def replace(path,old,new):
 s=path.read_text()
 if s.count(old)!=1:raise SystemExit('mutation match count incorrect')
 path.write_text(s.replace(old,new,1))
if mode=='setup_failure':
 replace(f,'            registry.clear();\n            router = new McpRequestRouter();','            registry.clear();\n            if (Boolean.getBoolean("agent13.setupFailure")) throw new IllegalStateException("agent13 setup failure");\n            router = new McpRequestRouter();')
elif mode=='interrupt_negative':
 replace(p,'                throw new MarkerStoreException(\n                    "Interrupted while waiting for diagnostics markers to refresh.", interrupted); //$NON-NLS-1$','                break; // intentional synthetic negative control')
elif mode!='baseline':raise SystemExit('unknown mode')
print('MODE='+mode)
