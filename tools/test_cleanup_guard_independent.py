"""Synthetic decision-only checks. Never invokes apply_deletions."""
from pathlib import Path
import pytest
import cleanup_guard as g

@pytest.fixture
def run(tmp_path):
    p = tmp_path / 'runs' / '12345678901-1'
    p.mkdir(parents=True)
    (p / 'OWNER-Agent-11.txt').write_text('synthetic')
    return tmp_path, p

def decision(root, p, **kwargs):
    return g.decide(str(p), root=str(root), requester='agent-11', min_age=0, **kwargs)

def test_conflict_overrides_consent(run):
    root, p = run
    (p / 'OWNER-Agent-16.txt').write_text('synthetic')
    allowed, why = decision(root, p, consent_from='agent-16')
    assert not allowed and why.startswith('owner-conflict')

def test_visible_nested_hold(run):
    root, p = run
    child = p / 'retained'
    child.mkdir()
    (child / 'DO-NOT-CLEAN.md').write_text('do not clean')
    assert not decision(root, p)[0]

def test_unknown_owner_is_kept(run):
    root, p = run
    (p / 'OWNER-Agent-11.txt').unlink()
    assert not decision(root, p)[0]

def test_license_root_is_kept():
    assert not g.decide('/opt/1cv8', requester='agent-11', consent_from='agent-11', min_age=0)[0]

def test_hold_beyond_scan_budget_must_not_allow_whole_run(run, monkeypatch):
    root, p = run
    retained = p / 'retained'
    retained.mkdir()
    (retained / 'DO-NOT-CLEAN.md').write_text('do not clean')
    # Deterministic directory order: exceed budget before visiting the actual retained folder.
    def large_walk(*args, **kwargs):
        yield str(p), ['retained'], ['synthetic-%05d.bin' % i for i in range(20001)]
        yield str(retained), [], ['DO-NOT-CLEAN.md']
    monkeypatch.setattr(g.os, 'walk', large_walk)
    allowed, reason = decision(root, p)
    assert not allowed, 'incomplete hold scan still allows deletion: ' + reason
