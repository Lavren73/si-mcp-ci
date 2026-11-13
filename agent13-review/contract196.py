#!/usr/bin/env python3
"""Synthetic #197 wire shapes -> exact #196 client. No live server or writes."""
import sys,pathlib,copy
sys.path.insert(0,str(pathlib.Path.cwd()/'client'))
from siagent.mcp import normalize_tool_result
from siagent.rollback import rollback_after_write, Snapshot
base={'complete':True,'reasons':[],'uncomputedMarkers':0,'capped':False,'returnedCount':0,'totalMatching':0,'partialModelCoverage':False,'excludedProviders':[],'noSessionChanges':False,'unresolvedObjects':[]}
def trial(comp, mode='text'):
    wire={'content':[{'type':'text','text':'# Nothing Found\n\n**Scope:** project\n**Found:** 0'}]}
    if comp is not None: wire['structuredContent']={'completeness':comp}
    if mode=='no_completeness':wire['structuredContent']={}
    if mode=='resource': wire['content']=[{'type':'resource','resource':{'uri':'mcp://diagnostics','mimeType':'text/markdown','text':'# Nothing Found\n\n**Scope:** project\n**Found:** 0'}}]
    normalized=normalize_tool_result(wire)
    events=[]
    def call(name,args):
        events.append(name)
        return normalized if name=='get_project_errors' else {'text':'ok','is_error':False}
    out=rollback_after_write(call,'P','M.bsl','new',before=Snapshot('M.bsl','old'))
    return out.written,events.count('write_module_source'),out.note
cases={
 'CLEAN_TEXT':(base, 'text',True),
 'CLEAN_RESOURCE':(base, 'resource',True),
 'CAPPED':({**base,'capped':True},'text',False),
 'UNCOMPUTED_CONTRADICTION':({**base,'uncomputedMarkers':1},'text',False),
 'UNRESOLVED_CONTRADICTION':({**base,'unresolvedObjects':['synthetic-object']},'text',False),
 'EXCLUDED_CONTRADICTION':({**base,'excludedProviders':['synthetic-provider']},'text',False),
 'BOOL_IN_INT':({**base,'uncomputedMarkers':True},'text',False),
 'STRUCTURED_MISSING_COMPLETENESS':(base,'no_completeness',False),
 'INCOMPLETE_WITH_REASON':({**base,'complete':False,'reasons':['request_failed']},'text',False),
}
for name,(comp,mode,expected_write) in cases.items():
 written,count,note=trial(comp,mode)
 print(f'{name}=' + ('PASS' if written == expected_write and count == int(expected_write) else 'FAIL') + f' WRITE={count}')
print('FAKE_ONLY=1')
