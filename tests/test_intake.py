import base64
import io
import zipfile

from PIL import Image

from legaldoctor.intake import BMProfile, Interview, from_data_url, from_file
from legaldoctor.intake.profile import merge_slots


def test_docx_and_pptx():
    from docx import Document
    from pptx import Presentation
    from pptx.util import Inches

    d = Document()
    d.add_paragraph("배달로봇 서비스 소개")
    buf = io.BytesIO()
    d.save(buf)
    ms = from_file(buf.getvalue(), "소개서.docx")
    assert ms[0].name == "소개서.docx" and "배달로봇" in ms[0].text

    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text_frame.text = "수익모델: 배달비"
    buf = io.BytesIO()
    prs.save(buf)
    ms = from_file(buf.getvalue(), "IR.pptx")
    assert ms[0].name == "IR.pptx 1번 슬라이드" and "배달비" in ms[0].text


def test_hwpx():
    xml = (
        '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
        'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
        "<hp:p><hp:run><hp:t>아파트 단지 배달</hp:t></hp:run></hp:p></hs:sec>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Contents/section0.xml", xml)
    ms = from_file(buf.getvalue(), "계획서.hwpx")
    assert "아파트 단지 배달" in ms[0].text


def test_pdf_text_and_page_image():
    img = Image.new("RGB", (200, 100), "white")
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    ms = from_file(buf.getvalue(), "a.pdf")
    assert any(m.is_image and m.name == "a.pdf 1쪽 화면" for m in ms)


def test_drawing_data_url_and_resize():
    img = Image.new("RGBA", (3000, 1000), (255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    m = from_data_url("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), "그림 1")
    out = Image.open(io.BytesIO(base64.b64decode(m.image_b64)))
    assert max(out.size) <= 1280 and m.mime == "image/jpeg"


def test_hwp_rejected_with_guidance():
    import pytest

    from legaldoctor.intake import UnsupportedFile

    with pytest.raises(UnsupportedFile, match="PDF"):
        from_file(b"x", "old.hwp")


def test_merge_requires_known_source():
    p = BMProfile()
    rejected = merge_slots(
        p,
        {
            "service": {"값": "로봇 배달", "출처": ["직접 입력"]},
            "data": {"값": "영상", "출처": ["지어낸 출처"]},
            "goods": {"값": "모름", "출처": ["직접 입력"]},
            "bogus": {"값": "x", "출처": ["직접 입력"]},
        },
        {"직접 입력"},
    )
    assert list(p.slots) == ["service"]
    assert len(rejected) == 1


class FakeModel:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat_json(self, messages, **kw):
        self.calls.append(messages)
        return self.replies.pop(0)


def test_interview_flow():
    m = FakeModel(
        [
            {"반영": {}, "완료": False, "다음질문": {"질문": "로봇이 다니는 길은 어디인가요?", "보기": ["단지 안", "일반 도로"], "항목": "place"}},
            {"반영": {"place": {"값": "단지 안 도로", "출처": ["질문 1"]}}, "완료": True},
        ]
    )
    iv = Interview(model=m)
    q = iv.step()
    assert q.no == 1 and q.choices[-1] == "잘 모르겠어요" and q.slot == "place"
    assert iv.step("단지 안") is None
    assert iv.profile.slots["place"].sources == ["질문 1"]
    assert iv.done


def test_interview_ignores_dont_know_source():
    m = FakeModel(
        [
            {"다음질문": {"질문": "결제는요?", "보기": ["앱"]}},
            {"반영": {"money_flow": {"값": "앱 결제", "출처": ["질문 1"]}}, "다음질문": {"질문": "다음"}},
        ]
    )
    iv = Interview(model=m)
    iv.step()
    iv.step("잘 모르겠어요")
    assert "money_flow" not in iv.profile.slots
