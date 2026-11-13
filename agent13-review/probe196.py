#!/usr/bin/env python3
"""Independent synthetic probe: no real EDT, database, transport, or writes."""
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path.cwd() / 'client'))
from siagent import rollback as rb
from siagent.mcp import normalize_tool_result

WARNING = ('_1 marker(s) carry no computed object data: they match no object or file '
           'filter and are listed as (object data not computed) when nothing narrows '
           'the question. project_admin operation=clean_project rebuilds that data._')
MARKERS = [WARNING, '# Request Failed\n\nfailed', '# More Matches Than Fit',
           '+ (capped at 100)', '[truncated=true: 123]', '# Addresses Not In The Model',
           'hit the aggregation cap of 5000', '**Scan truncated:** yes',
           'Coverage: ordinary form modules outside the BSL index']

def run(replies, concurrent=False):
    replies = iter(replies)
    events = []
    model = {'source': 'old', 'overwrote_other': False}
    def call(name, args):
        events.append((name, dict(args)))
        if name == 'get_project_errors':
            reply = next(replies)
            if concurrent and len([e for e in events if e[0] == 'get_project_errors']) == 2:
                model['source'] = 'other actor changed this'
            return reply if isinstance(reply, dict) else {'text': reply, 'is_error': False}
        if name == 'write_module_source':
            if model['source'] == 'other actor changed this':
                model['overwrote_other'] = True
            model['source'] = args['source']
            return {'text': 'ok', 'is_error': False}
        raise AssertionError('unexpected fake call')
    outcome = rb.rollback_after_write(call, 'P', 'M.bsl', 'new', before=rb.Snapshot('M.bsl', 'old'))
    return outcome, events, model

def nwrite(events):
    return sum(name == 'write_module_source' for name, _ in events)

def scopes(events):
    return [args['scope'] for name, args in events if name == 'get_project_errors']

def malformed_during_diagnostics(phase):
    # Real normalizer, fake transport and fake writes. None inside content is malformed.
    events = []
    step = 0
    def call(name, args):
        nonlocal step
        events.append((name, dict(args)))
        if name == 'write_module_source':
            return {'text': 'ok', 'is_error': False}
        if name != 'get_project_errors':
            raise AssertionError('unexpected fake call')
        step += 1
        if step == phase:
            return normalize_tool_result({'content': [None]})
        text = 'Ошибка: BSL' if phase == 3 and step == 2 else '0 problems'
        return normalize_tool_result({'content': [{'type': 'text', 'text': text}]})
    try:
        outcome = rb.rollback_after_write(call, 'P', 'M.bsl', 'new', before=rb.Snapshot('M.bsl', 'old'))
    except (AttributeError, TypeError):
        return False
    if phase == 2:
        return outcome.written and not outcome.rolled_back and nwrite(events) == 1 and 'ПРОВЕРКА НЕ ВЫПОЛНЕНА' in outcome.note
    return outcome.rolled_back and nwrite(events) == 2 and 'сверка после отката не выполнена' in outcome.note

def evaluate():
    results = {}
    out, e, _ = run(['0 problems', '0 problems'])
    results['CONTROL_CLEAN'] = out.written and out.note == 'проверка чистая' and nwrite(e) == 1
    results['BEFORE_KNOWN_MARKERS'] = all(
        (not out.written and nwrite(e) == 0)
        for out, e, _ in (run([marker]) for marker in MARKERS))
    results['AFTER_KNOWN_MARKERS'] = all(
        (out.written and not out.rolled_back and nwrite(e) == 1 and out.note != 'проверка чистая')
        for out, e, _ in (run(['0 problems', marker]) for marker in MARKERS))
    out, e, _ = run(['0 problems', 'Ошибка: BSL', WARNING])
    results['FINAL_INCOMPLETE'] = out.rolled_back and nwrite(e) == 2 and 'сверка после отката не выполнена' in out.note
    out, e, _ = run(['# No Session Changes', '0 problems', 'Ошибка: BSL', '0 problems'])
    results['PROJECT_FALLBACK_SCOPE'] = out.rolled_back and scopes(e) == ['session', 'project', 'project', 'project']
    # Hypothetical wire responses: no claim these are produced by a live server.
    unknown = {'text': 'A future diagnostic format without a completeness marker', 'is_error': False,
               'raw': {'content': [{'type': 'text', 'text': 'A future diagnostic format without a completeness marker'}]}}
    out, e, _ = run([unknown, unknown])
    results['UNKNOWN_FORMAT_FAIL_CLOSED'] = not out.written and nwrite(e) == 0
    contradictory = {'text': '0 problems', 'is_error': False,
        'raw': {'structuredContent': {'completeness': {'complete': True, 'capped': True}}}}
    out, e, _ = run([contradictory, contradictory])
    results['CONTRADICTORY_METADATA_FAIL_CLOSED'] = not out.written and nwrite(e) == 0
    # Artificial in-memory actor change just before post-write diagnostics.
    out, e, model = run(['0 problems', 'Ошибка: BSL', '0 problems'], concurrent=True)
    results['CONCURRENT_OTHER_EDIT_PRESERVED'] = not model['overwrote_other']
    # JSON fallback generated by the actual transport normalizer, not a made-up client shape.
    structured_only = normalize_tool_result({'structuredContent': {'completeness': {'complete': True}}})
    out, e, _ = run([structured_only, structured_only])
    results['STRUCTURED_WITHOUT_CONTENT_FAIL_CLOSED'] = not out.written and nwrite(e) == 0
    results['MALFORMED_AFTER_EXPLICIT_UNKNOWN'] = malformed_during_diagnostics(2)
    results['MALFORMED_FINAL_EXPLICIT_UNKNOWN'] = malformed_during_diagnostics(3)
    return results

if __name__ == '__main__':
    r = evaluate()
    for name, ok in r.items(): print(name + '=' + ('PASS' if ok else 'FAIL'))
    print('FAKE_ONLY=1')
    print('EXPECTATION_FAILURES=' + str(sum(not ok for ok in r.values())))
    sys.exit(0 if all(r.values()) else 1)
