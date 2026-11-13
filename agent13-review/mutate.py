#!/usr/bin/env python3
import pathlib,sys
mode=sys.argv[1]
root=pathlib.Path('project')
fixture=root/'server/tests/si.edt.mcp.server.tests/src/si/edt/mcp/server/wire/DiagnosticsCompletenessWireTest.java'
reader=root/'server/bundles/si.edt.mcp.server/src/si/edt/mcp/server/toolkit/ops/ProjectProblemsReader.java'
coverage=root/'server/bundles/si.edt.mcp.server/src/si/edt/mcp/server/support/modules/ModuleSources.java'
def edit(path, old, new):
 s=path.read_text()
 if s.count(old)!=1: raise SystemExit('mutation match count != 1')
 path.write_text(s.replace(old,new,1))
if mode=='setup_failure':
 edit(fixture,'            registry.clear();\n            router = new McpRequestRouter();','            registry.clear();\n            if (Boolean.getBoolean("agent13.setupFailure")) throw new IllegalStateException("agent13 setup failure");\n            router = new McpRequestRouter();')
elif mode=='registry_negative':
 edit(fixture,'                    for (IMcpTool own : savedOwnTools)\n                    {\n                        registry.register(own);\n                    }','                    for (IMcpTool own : savedOwnTools)\n                    {\n                        // deliberately omit restore in this disposable negative control\n                    }')
elif mode=='marker_negative':
 edit(reader,'                throw new MarkerStoreException("Could not read Eclipse markers of project \'" //$NON-NLS-1$\n                    + project.getName() + "\': " + failureText(e), e); //$NON-NLS-1$','                continue; // negative control: swallowed marker store failure')
elif mode=='count_negative':
 edit(reader,'                throw new MarkerStoreException("Could not read Eclipse markers of project \'" //$NON-NLS-1$\n                    + project.getName() + "\': " + failureText(cannotRead), cannotRead); //$NON-NLS-1$','                continue; // negative control: swallowed count failure')
elif mode=='coverage_negative':
 edit(coverage,'                out.add(new CoverageEntry(kind,\n                    "Model coverage check failed for provider " + kind //$NON-NLS-1$\n                        + " (coverage outside the BSL index could not be verified).", //$NON-NLS-1$\n                    true));','                // negative control: drop failed coverage entry')
elif mode!='baseline': raise SystemExit('unknown mode')
print('MODE='+mode)
