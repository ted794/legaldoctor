"""연결 점검(doctor): LAW_OC는 선택이라 비어 있어도 실패로 보이지 않아야 한다"""

from types import SimpleNamespace

import legaldoctor.__main__ as cli
import legaldoctor.law.web as web


def _doc(n):
    return SimpleNamespace(articles=[object()] * n, from_cache=False)


def test_doctor_law_check_uses_web_when_oc_empty(monkeypatch, capsys):
    monkeypatch.setattr(web.WebLaw, "load", lambda self, name: _doc(40))
    assert cli._check_law(SimpleNamespace(has_law_oc=False)) is True
    out = capsys.readouterr().out
    assert "[FAIL]" not in out and "[안내] 설정" in out and "조문 40개" in out


def test_doctor_law_check_fails_when_web_also_fails(monkeypatch, capsys):
    monkeypatch.setattr(web.WebLaw, "load", lambda self, name: None)
    assert cli._check_law(SimpleNamespace(has_law_oc=False)) is False
    assert "[FAIL] 국가법령정보(웹 원문)" in capsys.readouterr().out
