import pytest

from legaldoctor.liner.model import LinerModelError, extract_json


def test_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_fenced_with_prose():
    assert extract_json('결과입니다.\n```json\n[1, 2]\n```\n끝') == [1, 2]


def test_embedded():
    assert extract_json('답: {"법령": "산업융합 촉진법"} 이상') == {"법령": "산업융합 촉진법"}


def test_none():
    with pytest.raises(LinerModelError):
        extract_json("JSON 없음")
