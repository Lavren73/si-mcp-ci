#!/usr/bin/env python3
"""Сторож красных (клиент): сравнивает ИМЕНА красных pytest-тестов с эталоном.

Зачем. Клиентский прогон SI-MCP всегда красный: на 26.11.2026 в final это два
падения фона (см. эталон). Пока гейт печатал только счётчики «N failed, M passed»,
приёмка сводилась к тому, что рецензент глазами сравнивал числа двух прогонов.
26.11.2026 это дало промах: PR #631 приняли по дельте «2 failed → 2 failed», а
красный тест в голове был другой — счётчик тот же, набор имён нет (тест на порядок
исполнения флакал и краснел 1 разом из 25 полных прогонов файла). Сторож отвечает на
один вопрос: **список имён красных тот же, что в эталоне, или нет**.

Запуск:
    python3 red_names_guard.py /tmp/pytest.log эталон.txt
    python3 red_names_guard.py /tmp/pytest.log --снять > эталон.txt

Лог должен быть снят с короткой сводкой имён: `pytest -q -rfE --tb=no`
(без `-E` теряются ERROR, и сторож их не видит — это не «упавших нет», а «вердикта нет»).

Код возврата:
    0 — имена совпали с эталоном, прогон полный;
    1 — появились НОВЫЕ имена, либо лог/эталон не прочитаны, либо прогон неполный,
        либо сводка не найдена (обрванный прогон — не «всё хорошо»);
    2 — красных стало МЕНЬШЕ: кто-то починил, эталон нужно обновить в том же PR.
       Гейт трактует это как предупреждение с обязательной правкой эталона, а не как
       «чисто»: молча разъезжающийся эталон так же бесполезен, как завышенный.

Порог полноты берётся из строки `# Total: N` в шапке эталона: это сумма
failed+passed замеренного прогона. Прогон с меньшим числом считается неполным —
так обрезанный артефакт не даёт ложное «всё хорошо». Порог — нижняя граница,
он не доказывает, что набирались те же файлы.
"""
from __future__ import annotations

import re
import sys

ИМЯ = re.compile(r"^(?:FAILED|ERROR) (\S+)")
ИТОГО = re.compile(r"(\d+) failed.*?(\d+) passed", re.S)
ПОРОГ = re.compile(r"^#\s*Total:\s*(\d+)", re.M)


def канон(имя: str) -> str:
    """Каноническая форма узла: путь относительно client/.

    Нужна обязательно: hosted-шаг запускает pytest с рабочим каталогом `client/`
    и получает `tests/test_x.py::K::m`, а локальный прогон от корня репозитория —
    `client/tests/test_x.py::K::m`. На прогоне 45884867004 из-за этого сторож
    выдал РЕГРЕСС на совпадающем по составу фоне (2 failed == 2 эталонных записи),
    потому что сравнивались префиксы, а не имена.
    """
    имя = имя.strip()
    for pref in ("client/", "./client/", "./"):
        if имя.startswith(pref):
            имя = имя[len(pref):]
            break
    return имя


def имена_из_лога(текст: str) -> list[str]:
    """Узлы FAILED/ERROR из короткой сводки, в порядке появления, без дублей."""
    seen: list[str] = []
    for line in текст.splitlines():
        m = ИМЯ.match(line)
        if not m:
            continue
        nm = канон(m.group(1))
        if nm not in seen:
            seen.append(nm)
    return seen


def сводка(текст: str) -> tuple[int, int] | None:
    """(failed, passed) из ПОСЛЕДНЕЙ итоговой строки pytest; None — если итога нет.

    Последняя, а не первая: лог может содержать промежуточные сводки (например,
    второй замер того же шага), а вердикт ставится по факту завершённого прогона.
    """
    m = None
    for m in ИТОГО.finditer(текст):
        pass
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def эталонных_имени(текст: str) -> list[str]:
    return [канон(ln) for ln in текст.splitlines() if ln.strip() and not ln.startswith("#")]


def снять(текст: str) -> str:
    им = имена_из_лога(текст)
    св = сводка(текст)
    строки = [
        "# Эталон красных клиентского прогона SI-MCP (домик si-mcp-ci, шаг «Сторож красных»).",
        "# Снят автоматически: red_names_guard.py <лог> --снять. Не редактировать руками —",
        "# только переснимать с полного прогона и править шапку (SHA, окружение, дата).",
    ]
    if св:
        строки.append(f"# Total: {св[0] + св[1]}  (failed+passed; ниже — итоговая строка прогона)")
        m = re.search(r"^\d+ failed.*$", текст, re.M)
        if m:
            строки.append(f"# {m.group(0).strip()}")
    строки.append("# Формат записи: <узел pytest как его печатает -rfE>, по одному на строку.")
    строки += им
    return "\n".join(строки) + "\n"


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a]
    capture = "--снять" in args
    args = [a for a in args if a != "--снять"]
    if not args:
        print("использование: red_names_guard.py <pytest.log> [<эталон.txt>] [--снять]")
        return 1
    try:
        log = open(args[0], encoding="utf-8", errors="replace").read()
    except OSError as e:
        print(f"СТОРОЖ_ВЕРДИКТ=NO-INPUT | лог не читается: {e}")
        return 1
    if capture:
        sys.stdout.write(снять(log))
        return 0
    if len(args) < 2:
        print("СТОРОЖ_ВЕРДИКТ=NO-INPUT | эталон не передан")
        return 1
    try:
        et = open(args[1], encoding="utf-8", errors="replace").read()
    except OSError as e:
        print(f"СТОРОЖ_ВЕРДИКТ=NO-INPUT | эталон не читается: {e}")
        return 1

    св = сводка(log)
    if св is None:
        print("СТОРОЖ_ВЕРДИКТ=NO-SUMMARY | итоговой строки нет — прогон оборван, вердикта нет")
        return 1
    failed, passed = св
    log_имена = имена_из_лога(log)
    if failed and not log_имена:
        print("СТОРОЖ_ВЕРДИКТ=NO-NAMES | есть падения, но имён в логе нет: нужен `-rfE`, вердикта нет")
        return 1

    эт = эталонных_имени(et)
    порог = ПОРОГ.search(et)
    if порог:
        need = int(порог.group(1))
        if failed + passed < need:
            print(f"СТОРОЖ_ВЕРДИКТ=INCOMPLETE | прогон {failed + passed} < порога {need} — вердикта нет")
            return 1
        print(f"СТОРОЖ_ПОЛНОТА=ok ({failed + passed} >= {need})")

    new = [x for x in log_имена if x not in set(эт)]
    gone = [x for x in эт if x not in set(log_имена)]
    print(f"СТОРОЖ_СЧЁТЧИКИ failed={failed} passed={passed} эталон_записей={len(эт)} лог_имён={len(log_имена)}")
    if new:
        print(f"СТОРОЖ_НОВЫЕ={len(new)}")
        for x in new:
            print(f"  НОВЫЙ: {x}")
        print("СТОРОЖ_ВЕРДИКТ=REGRESS")
        return 1
    if gone:
        print(f"СТОРОЖ_УШЛИ={len(gone)}")
        for x in gone:
            print(f"  УШЁЛ: {x}")
        print("СТОРОЖ_ВЕРДИКТ=STALE-ETALON")
        return 2
    print("СТОРОЖ_ВЕРДИКТ=CLEAN")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
