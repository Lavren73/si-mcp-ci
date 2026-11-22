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


CLAIM_LIST = None   # файл заявленных «своих» прогонов, если задан
CHECK_NESTED_HOLD = True   # заглядывать ли внутрь папки перед rmtree (#481)

# Сколько записей дерева максимум просматриваем в поисках записки «не удалять».
NESTED_HOLD_BUDGET = 20000

# Разрешение удалять папку, дерево которой не обошли до конца: список путей
# (файл построчно) или 'runs/<папка> [-разрешение]'. Точное разрешение на
# конкретный путь, а не общий флаг «не досматриваем нигде»: находка #481.
WHOLE_RUN_ALLOWLIST = None


def claims():
    """Свои прогоны: строки вида runs/<число>[-<attempt>] или просто <число>."""
    if not CLAIM_LIST:
        return frozenset()
    try:
        text = pathlib.Path(CLAIM_LIST).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return frozenset()
    out = set()
    for line in text.splitlines():
        line = line.split('#', 1)[0].strip().rstrip('/')   # хвостовые пояснения допустимы
        if not line:
            continue
        tail = line.split('/')[-1]
        if re.fullmatch(r'\d+(?:-\d+)?', tail):
            out.add(tail)
    return frozenset(out)


def claimed(path):
    """Заявлено ли это своим прогоном - по авторству прогона, а не по диску."""
    return pathlib.Path(path).name in claims()


def allowlist_paths():
    """Пути, для которых разрешено whole-run удаление при недообследованном дереве."""
    if not WHOLE_RUN_ALLOWLIST:
        return frozenset()
    try:
        text = pathlib.Path(WHOLE_RUN_ALLOWLIST).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return frozenset()
    out = set()
    for line in text.splitlines():
        line = line.split('#', 1)[0].strip().rstrip('/')
        if not line:
            continue
        # только полный путь или путь относительно корня прогонов; basename из
        # чужого дерева НЕ извлекаем (находка координатора 18:07): строка
        # /unrelated/runs/12345-1 не должна авторизовать реальный runs/12345-1
        out.add(line)
        try:
            rel = str(pathlib.PurePath(line).relative_to(
                pathlib.Path(RUN_ROOT).resolve()))
            if rel and rel != line:
                out.add(rel)
        except (ValueError, OSError):
            pass
    return frozenset(out)


def allowed_whole_run(path, root=None):
    """Есть ли точное разрешение на эту папку (по имени или по относительному пути)."""
    paths = allowlist_paths()
    if not paths:
        return False
    cand = pathlib.Path(path)
    try:
        resolved = cand.resolve()
        rel = str(resolved.relative_to(pathlib.Path(root or RUN_ROOT).resolve()))
    except (OSError, ValueError):
        rel = ''
    # совпадение либо по относительному пути («runs/<id>»), либо по полному
    # абсолютному пути строкой; одиночный basename больше не ключ
    return bool(rel) and (rel in paths or str(resolved) in paths or str(cand) in paths)


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


def nested_hold(directory, budget=None):
    """(записка, обошли_ли_дерево_до_конца) - запрет «не удалять» ВНУТРИ папки.

    Записка в runs/<id>/retained/DO-NOT-CLEAN.md означает, что внутри лежат
    чужие или постоянные данные, а удаление всей папки - это rmtree. Обход
    ограничен бюджетом записей и не идёт за симлинками.

    Второе поле - ответ на находку #481 (независимое подтверждение): «не нашли»
    и «не досмотрели» - разные факты, и смешивать их нельзя. Прежний вариант
    «досрочно остановились -> просто предупреждаем и удаляем» позволял снести
    real DO-NOT-CLEAN.md, лежащий за лимитом. Теперь это scan-incomplete: по
    умолчанию KEEP, а удаление такого дерева возможно только по точному
    разрешению на конкретный путь (см. allowed_whole_run).
    """
    # задерживаем чтение бюджета до вызова: тесты (и домик) подменяют
    # guard.NESTED_HOLD_BUDGET уже после определения функции
    budget = NESTED_HOLD_BUDGET if budget is None else budget
    try:
        it = os.walk(str(directory), followlinks=False)
        seen = 0
        for dirpath, dirnames, filenames in it:
            for fn in filenames:
                seen += 1
                if seen > budget:
                    sys.stderr.write('warning: nested-hold scan of %s stopped after '
                                     '%d files, no hold found (scan-incomplete)\n'
                                     % (directory, budget))
                    return None, False
                if HELD.search(fn):
                    return fn, True
            for fn in sorted(filenames):
                if not fn.lower().endswith(('.txt', '.md')):
                    continue
                try:
                    fp = pathlib.Path(dirpath) / fn
                    if fp.stat().st_size > 4096:
                        continue
                    if HELD.search(fp.read_text(encoding='utf-8', errors='replace')):
                        return fn, True
                except OSError:
                    continue
    except OSError:
        # дерево не прочитать вообще - это тоже «не проверено», а не «чисто»
        return None, False
    return None, True


def stand_owner(root=None):
    """Чей этот стенд по метке корня (``$RUN_ROOT/OWNER.txt``).

    Стенд на si1c провизил один агент, и метка корня - единственная письменная
    подсказка, чей вообще этот ``runs/``. Нужна она для папок без собственной
    метки: «ничьё» на общем раннере остаётся «не моё», если только папка не
    лежит внутри стенда, который принадлежит просящему, и не создана тем же
    пользователем на диске.
    """
    try:
        text = (pathlib.Path(root or RUN_ROOT) / 'OWNER.txt').read_text(
            encoding='utf-8', errors='replace')
    except OSError:
        return None
    found = AGENT_NAME.search(text)
    return 'agent-%s' % int(found.group(1)) if found else None


def marker_owners(directory):
    """Все владельцы, заявленные метками в этой папке: {'agent-11', 'agent-16'}.

    Обход НЕ прерывается на первом совпадении: «первое по сортировке имя»
    превращало две разные метки в разрешение удалить чужое (находка координатора
    #481, воспроизведена на main 50004ea / blob 21ffe450). Прочитать нужно все.
    """
    owners = set()
    try:
        names = sorted(p.name for p in directory.iterdir() if p.is_file())
    except OSError:
        return owners
    for name in names:
        match = MARKER.match(name)
        if not match:
            continue
        if match.group(1):
            owners.add('agent-%s' % int(match.group(1)))
            continue
        try:
            text = (directory / name).read_text(encoding='utf-8', errors='replace')
        except OSError:
            owners.add('unreadable-marker')
            continue
        found = AGENT_NAME.search(text)
        if found:
            owners.add('agent-%s' % int(found.group(1)))
    return owners


def marker_owner(directory):
    """Чья папка по метке: 'agent-16', 'agent-11' (по OWNER.txt-тексту) или None."""
    owners = marker_owners(directory)
    if len(owners) != 1:
        return None          # ни одной - или конфликт: решает decide(), а не сортировка имён
    return next(iter(owners))


def inside_run_root(path, root=None):
    """Разрешено удалять только непосредственно папки прогонов: runs/<число>[-<число>].

    Корень берётся из вызова: ``--root`` на раннере и ``root=`` в тестах обязан
    влиять и на это решение, иначе сверка с дефолтным RUN_ROOT отвергала бы
    всё подряд на машине, где домашний каталог называется иначе.
    """
    root = pathlib.Path(root or RUN_ROOT).resolve()
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


def decide(path, requester=SELF, consent_from=None, now=None, min_age=MIN_AGE_MINUTES,
           root=None, claim_list=None, allow_list=None):
    """(можно_ли, причина) для одной папки. Причина - всегда проверяемый факт."""
    global CLAIM_LIST, WHOLE_RUN_ALLOWLIST
    if claim_list is not None:
        CLAIM_LIST = claim_list
    if allow_list is not None:
        WHOLE_RUN_ALLOWLIST = allow_list
    claimed_own = False
    raw = str(path)
    if protected(raw):
        return False, 'licensed-or-shared'
    ok, where = inside_run_root(raw, root=root)
    if not ok:
        return False, where
    directory = pathlib.Path(raw)
    # Разные владельцы в одной папке - это не «победил тот, чьё имя раньше по
    # алфавиту», а признак, что папку используют вдвоём. Такое не удаляет никто,
    # в том числе по согласию: согласие одного из двух не отменяет второго.
    owners = marker_owners(directory)
    if len(owners) > 1:
        return False, 'owner-conflict-' + '+'.join(sorted(owners))
    # Записку «не удалять» читаем раньше всего остального: она отказывает и
    # владельцу, и тому, кто принёс согласие.
    записка = held_by(directory)
    if записка:
        return False, 'held-by-' + записка
    scan_incomplete_allowed = False
    if CHECK_NESTED_HOLD:
        вложенная, обошли = nested_hold(directory)
        if вложенная:
            return False, 'nested-held-by-' + вложенная
        if not обошли:
            # «не проверено» не равно «чисто»: см. docstring nested_hold.
            # Разрешение из --allow-list снимает ЗДЕСЬ только блокировку
            # недообследованного дерева; оно НЕ переносит решение через
            # владельца, согласие, возраст и uid — находка координатора по
            # b3c2b11dd: ранний return True пропускал их все. Флаг доезжает
            # до конца функции, и окончательный вердикт выносится обычным
            # порядком, а к причине дописывается +scan-incomplete-allowed.
            if allowed_whole_run(raw, root=root):
                scan_incomplete_allowed = True
            else:
                return False, 'nested-scan-incomplete'
    try:
        stat = directory.stat()
    except OSError:
        return False, 'unreadable'
    if stat.st_uid != os.getuid():
        return False, 'foreign-uid'
    owner = marker_owner(directory)
    if owner is None:
        # Инвентарь 22.11 показал, почему нельзя было опознавать по диску: на si1c
        # все 83 папки прогона принадлежат одному пользователю runner - uid агентов
        # не различает, и «своя по uid» легко оказывается чужой: в том же runs/
        # лежит общий EDT-стенд runs/43070810460-1, и он тоже без метки. Без метки
        # папка своя только если она заявлена списком своих прогонов (--claim-list),
        # построенным по авторству прогона в GitHub, а не по файловой системе.
        if claimed(raw):
            owner = requester
            claimed_own = True
        else:
            return False, 'unmarked'
    age = ((now or time.time()) - stat.st_mtime) / 60.0
    if age < min_age:
        return False, 'too-fresh'
    if owner == requester:
        reason = 'claimed-own' if claimed_own else 'own'
    # Согласие должен принести владелец папки, а не тот, кто удаляет: иначе
    # «согласование» превращается в формальность, которую подставляет удалающий.
    elif consent_from == owner:
        reason = 'consented-by-%s' % owner
    else:
        return False, 'needs-consent-from-%s' % owner
    if scan_incomplete_allowed:
        # разрешение применено — и это видно в причине, а не спрятано за 'own'
        reason += '+scan-incomplete-allowed'
    return True, reason


def scan(root=None, requester=SELF, consent_from=None, now=None, min_age=MIN_AGE_MINUTES,
         only=None, claim_list=None, allow_list=None):
    """Все пути решаются относительно того же корня, что и передан в --root."""
    """Отчёт по всем папкам прогонов: что удалим, что нет и почему.

    Корень читается в момент вызова, а не в момент определения: тесты (и домик)
    подменяют RUN_ROOT, и скан обязан увидеть подмену.
    """
    base = pathlib.Path(root or RUN_ROOT) / 'runs'
    rows = []
    if only:
        # Точечная уборка: ровно своя папка прогона, ничего вокруг не сканим.
        target = pathlib.Path(only)
        if not target.exists():
            return rows
        allowed, reason = decide(str(target), requester=requester, consent_from=consent_from,
                                 now=now, min_age=min_age, root=root, claim_list=claim_list,
                                 allow_list=allow_list)
        return [{'path': str(target), 'delete': allowed, 'reason': reason,
                 'owner': marker_owner(target) or 'unmarked'}]
    if not base.is_dir():
        return rows
    for entry in sorted(base.iterdir()):
        if not entry.is_dir() or entry.is_symlink():
            continue
        allowed, reason = decide(str(entry), requester=requester, consent_from=consent_from,
                                 now=now, min_age=min_age, root=root, claim_list=claim_list,
                                 allow_list=allow_list)
        rows.append({'path': str(entry), 'delete': allowed, 'reason': reason,
                     'owner': marker_owner(entry) or 'unmarked'})
    return rows


def apply_deletions(rows, journal, requester=SELF, consent_from=None,
                    now=None, min_age=MIN_AGE_MINUTES, root=None, claim_list=None,
                    allow_list=None):
    """Удаляет только то, что разрешил decide; перед unlink - повторная проверка.

    Перепроверка обязана идти с теми же requester и согласием, что и скан:
    иначе прогон от имени agent-14 снесёт чужие папки только потому, что в
    момент удаления их посчитали своими по умолчанию.
    """
    removed, refused = [], []
    for row in rows:
        path = row['path']
        if not row['delete']:
            refused.append({'path': path, 'reason': row['reason']})
            continue
        allowed, reason = decide(path, requester=requester, consent_from=consent_from,
                                  now=now, min_age=min_age, root=root,
                                  claim_list=claim_list,   # диск мог измениться
                                  allow_list=allow_list)
        if not allowed:
            refused.append({'path': path, 'reason': 'changed-to-' + reason})
            continue
        shutil.rmtree(path)
        removed.append({'path': path, 'reason': reason})
    pathlib.Path(journal).write_text(json.dumps(
        {'removed': removed, 'refused': refused, 'protected_roots': list(PROTECTED_ROOTS),
         'consent_claimed_by': consent_from,
         'whole_run_allowlist': WHOLE_RUN_ALLOWLIST,
         'consent_note': 'consent-from is the caller assertion, not an authentication'},
        indent=2), encoding='utf-8')
    return removed, refused


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--root', default=RUN_ROOT)
    parser.add_argument('--requester', default=SELF)
    parser.add_argument('--consent-from', default='',
                        help='от кого получено согласие (имя владельца папки, напр. agent-11). '
                             'Внимание: это утверждение вызывающего, а не аутентификация - '
                             'сторож не умеет проверить, что согласование действительно было')
    parser.add_argument('--min-age', type=float, default=MIN_AGE_MINUTES)
    parser.add_argument('--apply', action='store_true',
                        help='удалять; без флага - только отчёт')
    parser.add_argument('--journal', default='')
    parser.add_argument('--only', default='',
                        help='ровно эта папка прогона (самоуборка своего прогона); '
                             'ничего другого не сканируется и не удаляется')
    parser.add_argument('--claim-list', default='',
                        help='файл со списком своих прогонов: убирает их без метки, '
                             'потому что на si1c у всех один uid; чужое по метке этот '
                             'список своим не делает')
    parser.add_argument('--allow-list', default='',
                        help='файл с точными путями (runs/<папка> или <id>), для которых '
                             'разрешено whole-run удаление, если дерево не обошли до конца; '
                             'без него недообследованная папка - это KEEP scan-incomplete')
    args = parser.parse_args(argv)
    rows = scan(args.root, requester=args.requester,
                 consent_from=(args.consent_from or None), min_age=args.min_age,
                 only=(args.only or None), claim_list=(args.claim_list or None),
                 allow_list=(args.allow_list or None))
    verb = 'DELETE' if args.apply else 'WOULD '
    for row in rows:
        print('%s %s [%s]' % (verb if row['delete'] else 'KEEP   ',
                              row['path'], row['reason']))
    removed, refused = ([], [])
    if args.apply:
        journal = args.journal or os.path.join(args.root, 'runs', 'cleanup-journal.json')
        removed, refused = apply_deletions(rows, journal, requester=args.requester,
                                            consent_from=(args.consent_from or None),
                                            min_age=args.min_age, root=args.root,
                                            claim_list=(args.claim_list or None),
                                            allow_list=(args.allow_list or None))
        print('REMOVED=%d REFUSED=%d JOURNAL=%s' % (len(removed), len(refused), journal))
    print('CANDIDATES=%d ALLOWED=%d' % (len(rows), sum(1 for r in rows if r['delete'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
