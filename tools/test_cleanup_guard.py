"""Тесты сторожа уборки на общем раннере.

Правило, которое они держат, сформулировал владелец 22.11.2026:
чужого не трогать; моё - только по моему согласию; своё - удалять;
лицензионную 1С не удаляет никто.
"""
import json
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
        self._claims = guard.CLAIM_LIST
        guard.RUN_ROOT = str(self.root)
        guard.PROTECTED_ROOTS = (str(self.root / 'licensed-1cv8'),)
        self.now = time.time()

    def tearDown(self):
        guard.RUN_ROOT, guard.PROTECTED_ROOTS = self._root, self._protected
        guard.CLAIM_LIST = self._claims
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
        d = self.папка_прогона(метка=('OWNER-Agent-16.txt', 'Личная тестовая папка агента 16'))
        можно, причина = guard.decide(str(d), requester='agent-11', now=self.now)
        self.assertFalse(можно)
        self.assertEqual('needs-consent-from-agent-16', причина)
        # и с согласием чужое берёт только то, что разрешил владелец чужого
        можно, причина = guard.decide(str(d), requester='agent-11', consent_from='agent-11',
                                      now=self.now)
        self.assertFalse(можно)
        self.assertEqual('needs-consent-from-agent-16', причина)
        можно, причина = guard.decide(str(d), requester='agent-11', consent_from='agent-16',
                                      now=self.now)
        self.assertTrue(можно, причина)

    def test_письменное_не_удалять_сильнее_согласия(self):
        d = self.папка_прогона(метка=('OWNER-Agent-16.txt',
                                      'Личная постоянная тестовая папка агента 16. Не удалять автоматически.'))
        для, причина = guard.decide(str(d), requester='agent-16', consent_from='agent-16',
                                    now=self.now)
        self.assertFalse(для)
        self.assertEqual('held-by-OWNER-Agent-16.txt', причина)

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


    def test_записка_не_удалять_держит_даже_свою_папку(self):
        d = self.папка_прогона(метка=('OWNER.txt', 'provisioned by agent 11'))
        (d / 'do-not-clean.txt').write_text(
            'EDT stand shared with the team; do not clean or repeat\n', encoding='utf-8')
        можно, причина = guard.decide(str(d), now=self.now)
        self.assertFalse(можно)
        self.assertEqual('held-by-do-not-clean.txt', причина)

    def test_записка_в_тексте_метки_тоже_держит(self):
        d = self.папка_прогона(метка=('OWNER-Agent-11.txt',
                                      'постоянный стенд, не удалять'))
        можно, причина = guard.decide(str(d), now=self.now)
        self.assertFalse(можно)
        self.assertEqual('held-by-OWNER-Agent-11.txt', причина)

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
        чужая = self.папка_прогона('22222222222-1', метка=('OWNER-Agent-16.txt', 'папка агента 16'))
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



class СвоёПоСпискуПрогонов(Фундамент):
    """Папка без метки - не «моё» по диску: на si1c у всех один uid.

    Инвентарь 22.11.2026: 83 папки, у всех uid=1000(runner), меток нет ни у
    одной; под тем же runs/ лежит общий EDT-стенд runs/43070810460-1. Значит
    «своё» доказывается авторством прогона (список --claim-list), а не диском.
    """

    def claim(self, *имена):
        f = self.root / 'my-runs.txt'
        f.write_text("\n".join('runs/' + i for i in имена) + "\n", encoding='utf-8')
        return str(f)

    def test_без_метки_но_заявлено_своим_прогоном(self):
        d = self.папка_прогона(имя='43090000001-1')
        можно, причина = guard.decide(str(d), now=self.now, claim_list=self.claim('43090000001-1'))
        self.assertTrue(можно, причина)
        self.assertEqual('claimed-own', причина)

    def test_без_метки_и_без_списка_не_трогаем(self):
        d = self.папка_прогона(имя='43090000002-1')
        можно, причина = guard.decide(str(d), now=self.now, claim_list=None)
        self.assertFalse(можно)
        self.assertEqual('unmarked', причина)

    def test_метка_корня_стенда_не_делает_папку_своей(self):
        """Эвристика uid+метка-корня снята именно из-за инвентаря: она присвоила
        бы нам и чужую папку (общий EDT-стенд), потому что uid общий."""
        (self.root / 'OWNER.txt').write_text('provisioned by agent 11', encoding='utf-8')
        d = self.папка_прогона(имя='43070810460-1')
        можно, причина = guard.decide(str(d), now=self.now, claim_list=None)
        self.assertFalse(можно)
        self.assertEqual('unmarked', причина)

    def test_записка_держит_даже_заявленную_папку(self):
        d = self.папка_прогона(имя='43090000004-1',
                               метка=('DO-NOT-CLEAN.md', 'общий EDT-стенд, do not clean'))
        можно, причина = guard.decide(str(d), now=self.now, claim_list=self.claim('43090000004-1'))
        self.assertFalse(можно)
        self.assertTrue(причина.startswith('held-by-'), причина)

    def test_список_не_переписывает_чужую_метку(self):
        d = self.папка_прогона(имя='43090000009-1',
                               метка=('OWNER-Agent-16.txt', 'Личная папка агента 16'))
        можно, причина = guard.decide(str(d), requester='agent-11', now=self.now,
                                      claim_list=self.claim('43090000009-1'))
        self.assertFalse(можно)
        self.assertEqual('needs-consent-from-agent-16', причина)

    def test_список_не_обходит_свежесть(self):
        d = self.папка_прогона(имя='43090000010-1', возраст_минут=4)
        можно, причина = guard.decide(str(d), now=self.now, claim_list=self.claim('43090000010-1'))
        self.assertFalse(можно)
        self.assertEqual('too-fresh', причина)

    def test_список_не_обходит_защиту_лицензии(self):
        можно, причина = guard.decide(str(self.root / 'licensed-1cv8'), now=self.now,
                                      claim_list=self.claim('licensed-1cv8'))
        self.assertFalse(можно)
        self.assertEqual('licensed-or-shared', причина)

    def test_строки_не_по_форме_в_списке_игнорируются(self):
        """Список принимает только имена папок прогонов: «runs/..» туда не пройдёт."""
        f = self.root / 'my-runs.txt'
        f.write_text('# комментарий\nruns/..\nwhatever\n42\n', encoding='utf-8')
        сохранённый = guard.CLAIM_LIST
        try:
            guard.CLAIM_LIST = str(f)
            self.assertEqual(frozenset({'42'}), guard.claims())
            self.assertFalse(guard.claimed(str(self.root)))
        finally:
            guard.CLAIM_LIST = сохранённый

    def test_согласие_не_обязано_молчать_при_перепроверке(self):
        """Чужое с согласием владельца удаляется и после перепроверки тоже."""
        d = self.папка_прогона(имя='43090000005-1',
                               метка=('OWNER-Agent-16.txt', 'папка агента 16'))
        rows = guard.scan(requester='agent-14', consent_from='agent-16', now=self.now, min_age=0)
        self.assertEqual([{'delete': True}], [{'delete': r['delete']} for r in rows])
        removed, refused = guard.apply_deletions(rows, self.root / 'journal.json',
                                                 requester='agent-14', consent_from='agent-16',
                                                 now=self.now, min_age=0)
        self.assertEqual(1, len(removed))
        self.assertFalse(refused)
        self.assertFalse(d.exists())

    def test_точечно_виден_только_свой_прогон(self):
        mine = self.папка_прогона(имя='43090000006-1')
        other = self.папка_прогона(имя='43090000007-1',
                                   метка=('OWNER-Agent-16.txt', 'папка агента 16'))
        rows = guard.scan(only=str(mine), now=self.now, claim_list=self.claim('43090000006-1'))
        self.assertEqual([str(mine)], [r['path'] for r in rows])
        self.assertTrue(rows[0]['delete'])
        self.assertTrue(mine.exists() and other.exists())
        guard.apply_deletions(rows, self.root / 'journal.json', now=self.now,
                              claim_list=self.claim('43090000006-1'))
        self.assertFalse(mine.exists())
        self.assertTrue(other.exists())

    def test_точечно_за_пределами_runs_отказ(self):
        rows = guard.scan(only=str(self.root / 'licensed-1cv8'), now=self.now)
        self.assertEqual(1, len(rows))
        self.assertFalse(rows[0]['delete'])
        self.assertIn(rows[0]['reason'], ('outside-runs', 'licensed-or-shared'))
        self.assertTrue((self.root / 'licensed-1cv8').exists())

    def test_клиент_точечно_удаляет_и_пишет_журнал(self):
        mine = self.папка_прогона(имя='43090000008-1')
        код = guard.main(['--root', str(self.root), '--requester', 'agent-11', '--min-age', '0',
                         '--only', str(mine), '--claim-list', self.claim('43090000008-1'),
                         '--apply', '--journal', str(self.root / 'j.json')])
        self.assertEqual(0, код)
        self.assertFalse(mine.exists())
        журнал = json.loads((self.root / 'j.json').read_text(encoding='utf-8'))
        self.assertEqual([str(mine)], [r['path'] for r in журнал['removed']])

    def test_клиент_точечно_ничего_не_находит_и_не_падает(self):
        код = guard.main(['--root', str(self.root), '--requester', 'agent-11',
                          '--only', str(self.root / 'runs' / '00000000000-1'), '--apply'])
        self.assertEqual(0, код)


class КореньИзАргумента(Фундамент):
    """``--root`` обязан действовать и на решение, и на перепроверку при удалении."""

    def test_чужой_root_не_отвергает_всё_подряд(self):
        # Дефолтный RUN_ROOT уводим в сторону: решение должно браться из --root.
        root, protected = guard.RUN_ROOT, guard.PROTECTED_ROOTS
        try:
            guard.RUN_ROOT = '/home/other-runner/other-stand'
            guard.PROTECTED_ROOTS = (str(self.root / 'licensed-1cv8'),)
            d = self.папка_прогона(имя='43091000001-1',
                                   метка=('OWNER.txt', 'provisioned by agent 11'))
            можно, причина = guard.decide(str(d), now=self.now)
            self.assertFalse(можно)
            self.assertEqual('outside-runs', причина)      # без root - отказ, как и должно
            можно, причина = guard.decide(str(d), now=self.now, root=str(self.root))
            self.assertTrue(можно, причина)
            rows = guard.scan(str(self.root), now=self.now)
            self.assertEqual([True], [r['delete'] for r in rows])
            removed, refused = guard.apply_deletions(rows, self.root / 'j.json', now=self.now,
                                                      root=str(self.root))
            self.assertEqual(1, len(removed))
            self.assertFalse(refused)
        finally:
            guard.RUN_ROOT, guard.PROTECTED_ROOTS = root, protected

if __name__ == '__main__':
    unittest.main()
