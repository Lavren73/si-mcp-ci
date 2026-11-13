#!/usr/bin/env python3
"""Independent synthetic checks for PR #196 @ 3a0dff; no real EDT/IB or writes."""
from pathlib import Path
import json, sys
sys.path.insert(0, str(Path.cwd() / 'client'))
from siagent.mcp import normalize_tool_result
from siagent.rollback import Snapshot, rollback_after_write

def check(name, ok):
    print(name + '=' + ('PASS' if ok else 'FAIL'))
    return bool(ok)

# A foreign edit appears between the attempted write and the post-write diagnostic.
state={'source':'old','writes':0,'diagnostics':0}
def competing_call(name,args):
    if name=='write_module_source':
        state['writes']+=1; state['source']=args['source']
        return {'text':'ok','is_error':False}
    if name=='get_project_errors':
        state['diagnostics']+=1
        if state['diagnostics']==1:return {'text':'0 problems','is_error':False}
        state['source']='external editor change'
        return {'text':'Ошибка: synthetic post-write diagnostic','is_error':False}
    raise AssertionError('unexpected fake tool')
out=rollback_after_write(competing_call,'P','M.bsl','new source',before=Snapshot('M.bsl','old'))
competing_ok=(state['source']=='external editor change' and state['writes']==1
              and out.written is True and out.rolled_back is False
              and bool(out.new_errors) and 'вручную' in out.note.lower()
              and 'проверка чистая' not in out.note.lower())
checks=[check('COMPETING_EDIT_PRESERVED_ONE_WRITE_AND_HONEST_MESSAGE',competing_ok)]

# A post-write diagnostic exception is reported as unverified, without a second write.
state2={'writes':0,'diagnostics':0}
def failing_diagnostic_call(name,args):
    if name=='write_module_source':
        state2['writes']+=1; return {'text':'ok','is_error':False}
    if name=='get_project_errors':
        state2['diagnostics']+=1
        if state2['diagnostics']==1:return {'text':'0 problems','is_error':False}
        raise ValueError('synthetic decode failure')
    raise AssertionError('unexpected fake tool')
out2=rollback_after_write(failing_diagnostic_call,'P','M.bsl','new source',before=Snapshot('M.bsl','old'))
post_failure_ok=(state2['writes']==1 and out2.written is True and out2.rolled_back is False
                 and 'ПРОВЕРКА НЕ ВЫПОЛНЕНА' in out2.note and 'проверка чистая' not in out2.note.lower())
checks.append(check('POST_WRITE_DIAGNOSTIC_FAILURE_NO_RESTORE',post_failure_ok))

# A lost reply from the initial write is explicitly unknown, not a claim that nothing was written.
state3={'writes':0}
def timeout_call(name,args):
    if name=='get_project_errors':return {'text':'0 problems','is_error':False}
    if name=='write_module_source':
        state3['writes']+=1; raise TimeoutError('synthetic lost reply')
    raise AssertionError('unexpected fake tool')
out3=rollback_after_write(timeout_call,'P','M.bsl','new source',before=Snapshot('M.bsl','old'))
timeout_ok=(state3['writes']==1 and out3.rolled_back is False
            and 'СОСТОЯНИЕ ЗАПИСИ НЕИЗВЕСТНО' in out3.note
            and 'не записано' not in out3.note.lower())
checks.append(check('WRITE_TIMEOUT_REPORTED_AS_UNKNOWN',timeout_ok))

# Track the known open issue; do not treat it as fixed by the no-restore change.
unknown=normalize_tool_result({'content':[{'type':'text','text':'future unrecognized diagnostic format'}]})
state4={'writes':0,'diagnostics':0}
def unknown_call(name,args):
    if name=='get_project_errors':state4['diagnostics']+=1;return unknown
    if name=='write_module_source':state4['writes']+=1;return {'text':'ok','is_error':False}
    raise AssertionError('unexpected fake tool')
out4=rollback_after_write(unknown_call,'P','M.bsl','new source',before=Snapshot('M.bsl','old'))
known_gap=(state4['writes']==1 and out4.note=='проверка чистая')
print('KNOWN_GAP_UNKNOWN_LEGACY_FORMAT_STILL_ACCEPTED='+('CONFIRMED' if known_gap else 'NOT_REPRODUCED'))
print('FAKE_ONLY=1')
print('LIVE_EDT_IB=0')
print('FILESYSTEM_WRITES=0')
print('REQUIRED_CASES='+str(sum(checks))+'/'+str(len(checks)))
sys.exit(0 if all(checks) else 1)
