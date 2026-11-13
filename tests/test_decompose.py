from regpang.pipeline.decompose import parse_activities

BIZ = "로봇은 단지 안 보도와 차도를 다니고 공동현관 출입 시스템과 엘리베이터를 연동한다."


def test_keeps_grounded_and_drops_invented():
    data = {
        "activities": [
            {"행위": "로봇이 보도를 주행", "근거구절": "로봇은 단지 안  보도와 차도를 다니고", "검색어": ["실외이동로봇 보도 통행"]},
            {"행위": "드론 배송", "근거구절": "드론으로 배송한다"},
        ],
        "확인필요": ["로봇 무게는?"],
    }
    kept, questions, dropped = parse_activities(data, BIZ)
    assert [a.action for a in kept] == ["로봇이 보도를 주행"]
    assert kept[0].id == "A1"
    assert questions == ["로봇 무게는?"]
    assert len(dropped) == 1


def test_bad_shape():
    assert parse_activities(["x"], BIZ) == ([], [], [])
