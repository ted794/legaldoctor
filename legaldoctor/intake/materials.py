"""창업자가 낸 자료를 모델에 넘길 수 있는 단위(Material)로 바꾼다.

- 텍스트: 그대로
- 문서: PDF·PPTX·DOCX·HWPX·TXT·MD에서 글을 뽑는다. PDF는 도식이 많으므로 앞쪽 몇 쪽을 그림으로도 만든다.
- 그림: 업로드 사진이나 화면에서 그린 그림. 긴 변을 줄여서 넘긴다.

모든 Material에는 출처 이름이 붙는다. 이후 BM 프로필의 각 항목은 이 이름으로 출처를 밝힌다.
"""

from __future__ import annotations

import base64
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from PIL import Image

MaterialKind = Literal["text", "document", "image", "interview"]

MAX_IMAGE_SIDE = 1280
MAX_PDF_PAGE_IMAGES = 6
MAX_PDF_PAGE_IMAGES_NO_TEXT = 10
MAX_TEXT_PER_MATERIAL = 6000
# 조작된 파일로 서버 메모리·시간을 소진시키는 것을 막는 상한
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 300
MAX_SLIDES = 300
MAX_IMAGE_PIXELS = 40_000_000  # 약 6300x6300
MAX_ZIP_BYTES = 200 * 1024 * 1024  # 압축을 푼 크기 합(docx·pptx·hwpx는 zip 구조)
MAX_ZIP_ENTRIES = 5000

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
DOC_EXT = {".pdf", ".pptx", ".docx", ".hwpx", ".txt", ".md"}


class UnsupportedFile(ValueError):
    pass


@dataclass
class Material:
    kind: MaterialKind
    name: str  # 출처 이름. 예: "직접 입력", "소개서.pdf 3쪽", "그림 1", "질문 4"
    text: str = ""
    image_b64: str | None = None  # PNG/JPEG base64
    mime: str | None = None

    @property
    def is_image(self) -> bool:
        return self.image_b64 is not None


# 이미지 ---------------------------------------------------------------
def image_to_b64(img: Image.Image) -> tuple[str, str]:
    img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"


def from_image_bytes(data: bytes, name: str) -> Material:
    try:
        img = Image.open(io.BytesIO(data))
        if img.size[0] * img.size[1] > MAX_IMAGE_PIXELS:
            raise UnsupportedFile(f"그림이 너무 큼: {name}")
        img.load()
    except UnsupportedFile:
        raise
    except Exception as e:  # noqa: BLE001
        raise UnsupportedFile(f"그림을 열 수 없음: {name}") from e
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = bg
    b64, mime = image_to_b64(img)
    return Material(kind="image", name=name, image_b64=b64, mime=mime)


def from_data_url(data_url: str, name: str) -> Material:
    """웹 화면 그리기판에서 온 data:image/png;base64,... 문자열."""
    m = re.match(r"data:image/[\w.+-]+;base64,(.+)", data_url, re.S)
    if not m:
        raise UnsupportedFile("그림 데이터 형식이 아님")
    return from_image_bytes(base64.b64decode(m.group(1)), name)


# 문서 ----------------------------------------------------------------
def _clip(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:MAX_TEXT_PER_MATERIAL]


def _pdf(data: bytes, fname: str) -> list[Material]:
    import pypdf
    import pypdfium2 as pdfium

    out: list[Material] = []
    reader = pypdf.PdfReader(io.BytesIO(data))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise UnsupportedFile(f"{fname}: {MAX_PDF_PAGES}쪽이 넘는 PDF는 필요한 부분만 나눠서 올려 주세요")
    for i, page in enumerate(reader.pages, 1):
        text = _clip(page.extract_text() or "")
        if text:
            out.append(Material(kind="document", name=f"{fname} {i}쪽", text=text))
    pdf = pdfium.PdfDocument(data)
    # 글이 거의 없는 PDF(그림으로 만든 IR 자료 등)는 쪽 화면을 더 많이 본다
    few_text = sum(len(m.text or "") for m in out) < 300
    for i in range(min(len(pdf), MAX_PDF_PAGE_IMAGES_NO_TEXT if few_text else MAX_PDF_PAGE_IMAGES)):
        img = pdf[i].render(scale=1.4).to_pil()
        b64, mime = image_to_b64(img)
        out.append(Material(kind="image", name=f"{fname} {i + 1}쪽 화면", image_b64=b64, mime=mime))
    return out


def _pptx(data: bytes, fname: str) -> list[Material]:
    from pptx import Presentation

    out: list[Material] = []
    prs = Presentation(io.BytesIO(data))
    if len(prs.slides) > MAX_SLIDES:
        raise UnsupportedFile(f"{fname}: 슬라이드가 {MAX_SLIDES}장이 넘으면 필요한 부분만 나눠서 올려 주세요")
    for i, slide in enumerate(prs.slides, 1):
        texts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    texts.append(" | ".join(c.text for c in row.cells))
        text = _clip("\n".join(t for t in texts if t.strip()))
        if text:
            out.append(Material(kind="document", name=f"{fname} {i}번 슬라이드", text=text))
    return out


def _docx(data: bytes, fname: str) -> list[Material]:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text for c in row.cells))
    text = "\n".join(p for p in parts if p.strip())
    return _chunks(text, fname)


def _hwpx(data: bytes, fname: str) -> list[Material]:
    texts: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        sections = sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml", n))
        for n in sections:
            root = ElementTree.fromstring(z.read(n))
            for para in root.iter():
                if para.tag.endswith("}p"):
                    line = "".join(t.text or "" for t in para.iter() if t.tag.endswith("}t"))
                    if line.strip():
                        texts.append(line)
    return _chunks("\n".join(texts), fname)


def _chunks(text: str, fname: str) -> list[Material]:
    text = text.strip()
    if not text:
        return []
    size = MAX_TEXT_PER_MATERIAL
    pieces = [text[i : i + size] for i in range(0, len(text), size)]
    if len(pieces) == 1:
        return [Material(kind="document", name=fname, text=_clip(pieces[0]))]
    return [Material(kind="document", name=f"{fname} {k}부분", text=_clip(p)) for k, p in enumerate(pieces, 1)]


def _check_zip(data: bytes, fname: str) -> None:
    """압축을 풀면 터무니없이 커지는 파일(zip 폭탄)을 풀기 전에 거른다"""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            if len(infos) > MAX_ZIP_ENTRIES or sum(i.file_size for i in infos) > MAX_ZIP_BYTES:
                raise UnsupportedFile(f"{fname}: 파일 안의 내용이 너무 커서 읽지 않음. PDF로 저장해 올려 주세요")
    except zipfile.BadZipFile as e:
        raise UnsupportedFile(f"{fname}: 파일을 열 수 없음(손상됐거나 형식이 다름)") from e


def from_file(data: bytes, filename: str) -> list[Material]:
    fname = Path(filename).name
    ext = Path(fname).suffix.lower()
    if len(data) > MAX_FILE_BYTES:
        raise UnsupportedFile(f"{fname}: 20MB 초과")
    if ext in (".pptx", ".docx", ".hwpx"):
        _check_zip(data, fname)
    if ext in IMAGE_EXT:
        return [from_image_bytes(data, fname)]
    if ext == ".pdf":
        return _pdf(data, fname)
    if ext == ".pptx":
        return _pptx(data, fname)
    if ext == ".docx":
        return _docx(data, fname)
    if ext == ".hwpx":
        return _hwpx(data, fname)
    if ext in (".txt", ".md"):
        return _chunks(data.decode("utf-8", errors="ignore"), fname)
    if ext == ".hwp":
        raise UnsupportedFile("한글(.hwp) 파일은 PDF나 .hwpx로 저장해서 올려 주세요.")
    if ext in (".ppt", ".doc"):
        raise UnsupportedFile("예전 오피스 형식입니다. .pptx/.docx나 PDF로 저장해서 올려 주세요.")
    raise UnsupportedFile(f"지원하지 않는 파일 형식: {ext or fname}")


def from_text(text: str, name: str = "직접 입력") -> Material:
    return Material(kind="text", name=name, text=text.strip())
