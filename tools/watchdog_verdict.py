#!/usr/bin/env python3
"""Validate a watchdog CLI verdict; reveal identifiers only, never diagnostic text."""
import re
import subprocess
import sys

HEADER_NEW = re.compile(r'^НОВЫЕ падения \((\d+)\)')
HEADER_REMOVED = re.compile(r'^Ушли из списка \((\d+)\)')
IDENT = re.compile(r'^[A-Za-z_$][A-Za-z0-9_.$]*(?:\[[A-Za-z0-9_.$-]+\])?$')


def classify(code, stdout):
    new, removed = [], []
    declared_new, declared_removed = [], []
    for line in stdout.splitlines():
        line = line.strip()
        n, r = HEADER_NEW.match(line), HEADER_REMOVED.match(line)
        if n: declared_new.append(int(n.group(1)))
        if r: declared_removed.append(int(r.group(1)))
        if line.startswith(('+ ', '- ')):
            identifier = line[2:].split(' | ', 1)[0].strip()
            if not IDENT.fullmatch(identifier):
                return False, 'ambiguous-identifier', [], []
            (new if line.startswith('+ ') else removed).append(identifier)
    if len(declared_new) > 1 or len(declared_removed) > 1:
        return False, 'ambiguous-headers', [], []
    if len(new) != (declared_new[0] if declared_new else 0) or len(removed) != (declared_removed[0] if declared_removed else 0):
        return False, 'count-mismatch', [], []
    if declared_new == [0] or declared_removed == [0]:
        return False, 'empty-section', [], []
    if code == 0 and not new and not removed and 'Список красных совпал с эталоном.' in stdout:
        return True, 'same', new, removed
    if code == 2 and not new and removed and 'Список красных совпал с эталоном.' not in stdout:
        return True, 'removed-only', new, removed
    if code == 1:
        return False, 'new-or-no-verdict', new, removed
    return False, 'unexpected-verdict', new, removed


def main():
    if len(sys.argv) != 4:
        print('WATCHDOG=invalid-arguments');return 1
    try:
        proc = subprocess.run([sys.executable, *sys.argv[1:]], text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        print('WATCHDOG=execution-error');return 1
    ok, state, new, removed = classify(proc.returncode, proc.stdout)
    print('WATCHDOG_EXIT='+str(proc.returncode))
    print('WATCHDOG='+state)
    print('WATCHDOG_NEW_COUNT='+str(len(new)))
    for name in new: print('WATCHDOG_NEW='+name)
    print('WATCHDOG_REMOVED_COUNT='+str(len(removed)))
    for name in removed: print('WATCHDOG_REMOVED='+name)
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
