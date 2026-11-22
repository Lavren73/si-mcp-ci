#!/usr/bin/env python3
"""Can this directory on the shared runner be deleted, and by whom?

Правило владельца от 22.11.2026, здесь - единственное место, где оно решается:

* чужого на раннере удалять нельзя;
* чтобы удалить моё (agent-11) на этом раннере, другой агент обязан принести
  согласие владельца папки - без него отказ;
* своё удалять можно и нужно: непролитый мусор после прогонов и есть причина,
  по которой кончается место;
* лицензионную 1С (и EDT, и постоянные тестовые базы) не удаляет никто, ни под
  каким согласием.

Решение принимает только по факту на диске: метка владельца в самой папке
(``OWNER.txt`` / ``OWNER-Agent-NN.txt``), uid, возраст, симлинки, положение
относительно корня прогонов. Никаких «на глаз по имени папки».
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import sys
import time

# Кто запущен в домиках №11 (и, соответственно, чьё «своё»).
SELF = 'agent-11'

# Корень стенда на si1c: удалять можно только внутри runs/.
RUN_ROOT = '/home/runner/si1c-team-tests'

# Не удаляется НИКЕМ и НИ ЗА КАКИМ СОГЛАСИЕМ. Лицензионные установки и
# постоянные базы: их удаление - не уборка мусора, а уничтожение стенда.
PROTECTED_ROOTS = (
    '/opt/1cv8',        # платформы 1С:Предприятие (лицензия)
    '/opt/1cedt',       # EDT (лицензия)
    '/home/runner/test-ib',   # постоянные информационные базы
    RUN_ROOT + '/toolcache',  # общий кэш инструментов: чужие прогоны им живут
    RUN_ROOT + '/locks',      # файл-блокировки общего стенда
)

# Кто кем владеет: метка в папке важнее имени.
MARKER = re.compile(r'^OWNER(?:-Agent-(\d+))?\.txt$')
AGENT_NAME = re.compile(r'agent[\s-]*(\d+)')

# Папка свежее этого возраста не удаляется: её мог бы использовать параллельный
# прогон того же агента.
MIN_AGE_MINUTES = 90


def protected(path):
    """True если путь лежит под защищённым корнем (или им является)."""
    for root in PROTECTED_ROOTS:
        if path == root or path.startswith(root.rstrip('/') + '/'):
            return True
    return False


HELD = re.compile(r'do not clean|не удалять|не трогать|do not touch', re.I)


def held_by(directory):
    """Имя записки, которая запрещает чистить эту папку (обычно её вешает тот, кто
    в ней живёт: у агента 16 это 'do not clean or repeat'). Нужна, потому что под
    однимruns-корнем лежат и общие установки (напр. EDT-стенд), и их удаление -
    не уборка мусора, а обрыв чужого прогона."""
    try:
        files = [p for p in directory.iterdir() if p.is_file()]
    except OSError:
        return None
    for entry in sorted(files, key=lambda p: p.name):
        if entry.suffix.lower() not in ('.txt', '.md', ''):
            continue
        if HELD.search(entry.name):
            return entry.name
        try:
            if entry.stat().st_size <= 4096 and HELD.search(entry.read_text(encoding='utf-8',
                                                                              errors='replace')):
                return entry.name
        except OSError:
            continue
    return None


def marker_owner(directory):
    """Чья папка по метке: 'agent-16', 'agent-11' (по OWNER.txt-тексту) или None."""
    try:
        names = sorted(p.name for p in directory.iterdir() if p.is_file())
    except OSError:
        return None
    for name in names:
        match = MARKER.match(name)
        if not match:
            continue
        if match.group(1):
            return 'agent-%s' % int(match.group(1))
        try:
            text = (directory / name).read_text(encoding='utf-8', errors='replace')
        except OSError:
            return None
        found = AGENT_NAME.search(text)
        return 'agent-%s' % int(found.group(1)) if found else None
    return None


def inside_run_root(path):
    """Разрешено удалять только непосредственно папки прогонов: runs/<число>[-<число>]."""
    root = pathlib.Path(RUN_ROOT).resolve()
    candidate = pathlib.Path(path)
    if candidate.is_symlink():
        return False, 'symlink'
    try:
        real = candidate.resolve(strict=True)
    except OSError:
        return False, 'unreadable'
    if str(real) != str(candidate):
        return False, 'path-not-canonical'
    try:
        relative = real.relative_to(root / 'runs')
    except ValueError:
        return False, 'outside-runs'
    parts = relative.parts
    if len(parts) != 1 or not re.fullmatch(r'\d+(?:-\d+)?', parts[0]):
        return False, 'not-a-run-directory'
    return True, 'ok'


def decide(path, requester=SELF, consent_from=None, now=None, min_age=MIN_AGE_MINUTES):
    """(можно_ли, причина) для одной папки. Причина - всегда проверяемый факт."""
    raw = str(path)
    if protected(raw):
        return False, 'licensed-or-shared'
    ok, where = inside_run_root(raw)
    if not ok:
        return False, where
    directory = pathlib.Path(raw)
    owner = marker_owner(directory)
    if owner is None:
        # Без метки непонятно, чужое это или ничьё; а ничьё на общем раннере -
        # не моё. Такую папку оставляем и говорим почему.
        return False, 'unmarked'
    try:
        stat = directory.stat()
    except OSError:
        return False, 'unreadable'
    if stat.st_uid != os.getuid():
        return False, 'foreign-uid'
    записка = held_by(directory)
    if записка:
        return False, 'held-by-' + записка
    age = ((now or time.time()) - stat.st_mtime) / 60.0
    if age < min_age:
        return False, 'too-fresh'
    if owner == requester:
        return True, 'own'
    # Согласие должен принести владелец папки, а не тот, кто удаляет: иначе
    # «согласование» превращается в формальность, которую подставляет удалающий.
    if consent_from == owner:
        return True, 'consented-by-%s' % owner
    return False, 'needs-consent-from-%s' % owner


def scan(root=None, requester=SELF, consent_from=None, now=None, min_age=MIN_AGE_MINUTES):
    """Отчёт по всем папкам прогонов: что удалим, что нет и почему.

    Корень читается в момент вызова, а не в момент определения: тесты (и домик)
    подменяют RUN_ROOT, и скан обязан увидеть подмену.
    """
    base = pathlib.Path(root or RUN_ROOT) / 'runs'
    rows = []
    if not base.is_dir():
        return rows
    for entry in sorted(base.iterdir()):
        if not entry.is_dir() or entry.is_symlink():
            continue
        allowed, reason = decide(str(entry), requester=requester, consent_from=consent_from,
                                 now=now, min_age=min_age)
        rows.append({'path': str(entry), 'delete': allowed, 'reason': reason,
                     'owner': marker_owner(entry) or 'unmarked'})
    return rows


def apply_deletions(rows, journal):
    """Удаляет только то, что разрешил decide; перед unlink - повторная проверка."""
    removed, refused = [], []
    for row in rows:
        path = row['path']
        if not row['delete']:
            refused.append({'path': path, 'reason': row['reason']})
            continue
        allowed, reason = decide(path)      # перепроверка: диск мог измениться между сканом и удалением
        if not allowed:
            refused.append({'path': path, 'reason': 'changed-to-' + reason})
            continue
        shutil.rmtree(path)
        removed.append({'path': path, 'reason': reason})
    pathlib.Path(journal).write_text(json.dumps(
        {'removed': removed, 'refused': refused, 'protected_roots': list(PROTECTED_ROOTS)},
        indent=2), encoding='utf-8')
    return removed, refused


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--root', default=RUN_ROOT)
    parser.add_argument('--requester', default=SELF)
    parser.add_argument('--consent-from', default='',
                        help='от кого получено согласие (имя владельца папки, напр. agent-11)')
    parser.add_argument('--min-age', type=float, default=MIN_AGE_MINUTES)
    parser.add_argument('--apply', action='store_true',
                        help='удалять; без флага - только отчёт')
    parser.add_argument('--journal', default='')
    args = parser.parse_args(argv)
    rows = scan(args.root, requester=args.requester,
                 consent_from=(args.consent_from or None), min_age=args.min_age)
    for row in rows:
        print('%s %s [%s]' % ('DELETE' if row['delete'] else 'KEEP  ',
                              row['path'], row['reason']))
    removed, refused = ([], [])
    if args.apply:
        journal = args.journal or os.path.join(args.root, 'runs', 'cleanup-journal.json')
        removed, refused = apply_deletions(rows, journal)
        print('REMOVED=%d REFUSED=%d JOURNAL=%s' % (len(removed), len(refused), journal))
    print('CANDIDATES=%d ALLOWED=%d' % (len(rows), sum(1 for r in rows if r['delete'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
