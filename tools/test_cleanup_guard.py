"""Тесты сторожа уборки на общем раннере.

Правило, которое они держат, сформулировал владелец 22.11.2026:
чужого не трогать; моё - только по моему согласию; своё - удалять;
лицензионную 1С не удаляет никто.
"""
import os
import pathlib
import shutil
import tempfile
import time
import unittest
from unittest import mock

import cleanup_guard as guard


class Фундамент(unittest.TestCase):
    """Временный корень вместо настоящего: на раннере тесты ничего не трогают."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        (self.root / 'runs').mkdir()
        (self.root / 'licensed-1cv8').mkdir()
        self._root, self._protected = guard.RUN_ROOT, guard.PROTECTED_ROOTS
        guard.RUN_ROOT = str(self.root)
        guard.PROTECTED_ROOTS = (str(self.root / 'licensed-1cv8'),)
        self.now = time.time()

    def tearDown(self):
        guard.RUN_ROOT, guard.PROTECTED_ROOTS = self._root, self._protected
        self.tmp.cleanup()

    def папка_прогона(self, имя='43084355230-1', метка=None, возраст_минут=600):
        d = self.root / 'runs' / имя
        d.mkdir(parents=True, exist_ok=True)
        if метка:
            (d / метка[0]).write_text(метка[1], encoding='utf-8')
        штамп = self.now - возраст_минут * 60
        os.utime(d, (штамп, штамп))
        return d


class СвоёИЧужое(Фундамент):
    def test_свою_пролитую_папку_удаляем(self):
        d = self.папка_прогона(метка=('OWNER.txt', 'SI-MCP team test stand; provisioned by agent 11'))
        можно, причина = guard.decide(str(d), now=self.now)
        self.assertTrue(можно, причина)
        self.assertEqual('own', причина)

    def test_свежую_не_трогаем_даже_свою(self):
        d = self.папка_прогона(метка=('OWNER.txt', 'provisioned by agent 11'), возраст_минут=3)
        можно, причина = guard.decide(str(d), now=self.now)
        self.assertFalse(можно)
        self.assertEqual('too-fresh', причина)

    def test_чужую_без_согласия_не_удаляем(self):
        d = self.папка_прогона(метка=('OWNER-Agent-16.txt',
                                      'Личная постоянная тестовая папка агента 16. Не удалять автоматически.'))
        можно, причина = guard.decide(str(d), requester='agent-11', now=self.now)
        self.assertFalse(можно)
        self.assertEqual('needs-consent-from-agent-16', причина)

    def test_моё_у_другого_только_по_моему_согласию(self):
        d = self.папка_прогона(метка=('OWNER.txt', 'provisioned by agent 11'))
        можно, причина = guard.decide(str(d), requester='agent-14', now=self.now)
        self.assertFalse(можно)
        self.assertEqual('needs-consent-from-agent-11', причина)
        можно, причина = guard.decide(str(d), requester='agent-14', consent_from='agent-11',
                                      now=self.now)
        self.assertTrue(можно, причина)
        self.assertEqual('consented-by-agent-11', причина)

    def test_согласие_подставить_нельзя_оно_должно_быть_от_владельца(self):
        d = self.папка_прогона(метка=('OWNER.txt', 'provisioned by agent 11'))
        можно, причина = guard.decide(str(d), requester='agent-14', consent_from='agent-14',
                                      now=self.now)
        self.assertFalse(можно)
        self.assertEqual('needs-consent-from-agent-11', причина)

    def test_без_метки_это_не_моё(self):
        d = self.папка_прогона()
        можно, причина = guard.decide(str(d), now=self.now)
        self.assertFalse(можно)
        self.assertEqual('unmarked', причина)


class ЗащитаУстановки(Фундамент):
    def test_лицензионную_1с_не_удаляет_никто_и_ни_под_каким_согласием(self):
        d = self.root / 'licensed-1cv8'
        (d / 'OWNER.txt').write_text('provisioned by agent 11', encoding='utf-8')
        for разрешающий in ({}, {'consent_from': 'agent-11'}):
            можно, причина = guard.decide(str(d), now=self.now, **разрешающий)
            self.assertFalse(можно)
            self.assertEqual('licensed-or-shared', причина)

    def test_чужой_uid_не_наше_имущество(self):
        d = self.папка_прогона(метка=('OWNER.txt', 'provisioned by agent 11'))
        with mock.patch.object(os, 'getuid', lambda: 999999):
            можно, причина = guard.decide(str(d), now=self.now)
        self.assertFalse(можно)
        self.assertEqual('foreign-uid', причина)

    def test_обход_через_символинку_отклонён(self):
        настоящая = self.root / 'чужая-территория'
        настоящая.mkdir()
        ссылка = self.root / 'runs' / '99999999999-1'
        ссылка.symlink_to(настоящая, target_is_directory=True)
        можно, причина = guard.decide(str(ссылка), now=self.now)
        self.assertFalse(можно)
        self.assertIn(причина, {'symlink', 'path-not-canonical', 'not-a-run-directory'})


class ФормаПути(Фундамент):
    def test_внутри_папки_прогона_не_гадим(self):
        d = self.папка_прогона(метка=('OWNER.txt', 'provisioned by agent 11'))
        вложенная = d / 'workspace'
        вложенная.mkdir()
        можно, причина = guard.decide(str(вложенная), now=self.now)
        self.assertFalse(можно)
        self.assertEqual('not-a-run-directory', причина)

    def test_не_папка_прогона_не_папка_прогона(self):
        d = self.root / 'runs' / 'README'
        d.mkdir()
        (d / 'OWNER.txt').write_text('provisioned by agent 11', encoding='utf-8')
        можно, причина = guard.decide(str(d), now=self.now)
        self.assertFalse(можно)
        self.assertEqual('not-a-run-directory', причина)

    def test_за_пределами_корня_отказ(self):
        d = self.root / 'runs-но-не-тот-корень'
        d.mkdir()
        можно, причина = guard.decide(str(d), now=self.now)
        self.assertFalse(можно)
        self.assertEqual('outside-runs', причина)


class Удаление(Фундамент):
    def test_удаляются_только_разрешённые_и_это_записано_в_журнал(self):
        своя = self.папка_прогона('11111111111-1', метка=('OWNER.txt', 'provisioned by agent 11'))
        чужая = self.папка_прогона('22222222222-1', метка=('OWNER-Agent-16.txt', 'агент 16'))
        journal = self.root / 'журнал.json'
        rows = guard.scan()
        удалено, отказ = guard.apply_deletions(rows, str(journal))
        self.assertFalse(своя.exists(), 'свою непролитую папку надо было удалить')
        self.assertTrue(чужая.exists(), 'чужая папка цела')
        self.assertEqual(1, len(удалено))
        self.assertEqual('needs-consent-from-agent-16', отказ[0]['reason'])
        import json
        записано = json.loads(journal.read_text(encoding='utf-8'))
        self.assertEqual([str(своя)], [r['path'] for r in записано['removed']])

    def test_если_диск_изменился_между_сканом_и_удалением_отказ(self):
        d = self.папка_прогона(метка=('OWNER.txt', 'provisioned by agent 11'))
        rows = [{'path': str(d), 'delete': True, 'reason': 'own', 'owner': 'agent-11'}]
        shutil.rmtree(d)   # папка с меткой: rmdir её не возьмёт
        удалено, отказ = guard.apply_deletions(rows, str(self.root / 'журнал.json'))
        self.assertEqual([], удалено)
        self.assertEqual('changed-to-unreadable', отказ[0]['reason'])

    def test_скан_не_предлагает_ничего_под_защитой(self):
        self.папка_прогона(метка=('OWNER.txt', 'provisioned by agent 11'))
        rows = guard.scan()
        self.assertTrue(rows)
        self.assertTrue(all(not guard.protected(r['path']) for r in rows))


if __name__ == '__main__':
    unittest.main()
