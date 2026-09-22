"""SOP文件的轉換、文字擷取與資料庫同步。
舊版*.doc優先使用 LibreOffice 無介面轉成快取*.docx；
若本機沒有LibreOffice，才在 Windows使用 Microsoft Word COM。原始文件永遠不會被修改。
支援 Word、Excel 與 PDF 文件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docx import Document

BACKEND_ROOT = Path(__file__).parent.resolve()
PROJECT_ROOT = BACKEND_ROOT.parent
SOURCE_DIR = PROJECT_ROOT / "data" / "exam"
CACHE_DIR = SOURCE_DIR / ".converted"
CONVERSION_TIMEOUT_SECONDS = 300
SECTION_LENGTH = 2600
SYNC_LOCK = threading.Lock()
EXCEL_SUFFIXES = frozenset({".xlsx", ".xlsm", ".xltx", ".xltm", ".xls"})
PDF_SUFFIXES = frozenset({".pdf"})
OCR_LANGUAGES = "chi_tra+eng"
OCR_DPI = 300
MIN_NATIVE_TEXT_LENGTH = 80
QUESTION_START_PATTERN = re.compile(
    r"(?m)^(?:題目\s*)?(?P<number>\d{1,3})\s*[.、)]?\s*"
    r"(?:\((?P<answer>[A-F](?:\s*[A-F])*)\))?\s*(?P<stem>\S.*)$"
)
OPTION_PATTERN = re.compile(
    r"(?m)^\s*(?P<marked>[(（]\s*(?:✅|✓|✔)?\s*[)）])?\s*"
    r"(?P<label>[A-F])\s*[.、．:]\s*(?P<text>.+?)(?=\n\s*(?:[(（]\s*(?:✅|✓|✔)?\s*[)）])?\s*[A-F]\s*[.、．:]|\Z)",
    re.DOTALL,
)
CHAPTER_PATTERN = re.compile(r"(?i)\bCH\s*0?(\d{1,2})\b\s*[:：-]?\s*([^\n]{0,80})")
# 目的是「精簡＋方便未來擴充關鍵字」，用資料驅動的寫法會更乾淨、更易維護
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "財務行政": ("會計", "財務", "出納", "帳務", "稅務"),
    "商務營運": ("業務", "合約", "客戶", "銷售", "專案", "營運"),
    "工安健康": ("安全", "健康", "醫療", "衛生", "消防", "急救", "礦場"),
    "生產製造": ("工藝", "鍛造", "裁縫", "製程", "品質", "設備", "倉儲"),
    "人事行政": ("人事", "招募", "福利", "考勤"),
}


class DocumentImportError(RuntimeError):
    """SOP文件無法轉換、擷取或同步時使用的安全例外。"""


def _source_files(suffix: str) -> list[Path]:
    """以不分大小寫的副檔名取得來源文件。"""
    if not SOURCE_DIR.is_dir():
        return []
    return sorted(
        (
            path
            for path in SOURCE_DIR.iterdir()
            if path.is_file() and path.suffix.casefold() == suffix.casefold()
        ),
        key=lambda path: path.name.casefold(),
    )


def _converted_path(source: Path) -> Path:
    return CACHE_DIR / f"{source.stem}.docx"


def _needs_conversion(source: Path) -> bool:
    converted = _converted_path(source)
    return not converted.is_file() or source.stat().st_mtime > converted.stat().st_mtime


def _run_conversion(command: list[str], environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            env=environment,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=CONVERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise DocumentImportError("Word 文件轉換逾時，請檢查來源文件是否損壞。") from exc
    except OSError as exc:
        raise DocumentImportError("無法啟動 Word 文件轉換程式。") from exc


def _convert_with_libreoffice(executable: str, legacy: list[Path]) -> None:
    with tempfile.TemporaryDirectory(prefix="silver-shield-lo-") as profile:
        command = [
            executable,
            "--headless",
            f"-env:UserInstallation={Path(profile).as_uri()}",
            "--convert-to",
            "docx",
            "--outdir",
            str(CACHE_DIR),
            *(str(path) for path in legacy),
        ]
        result = _run_conversion(command)
    missing = [path.name for path in legacy if not _converted_path(path).is_file()]
    if result.returncode or missing:
        detail = (result.stderr or result.stdout or "LibreOffice 轉換失敗").strip()
        incomplete = f"；未完成：{', '.join(missing[:3])}" if missing else ""
        raise DocumentImportError(f"{detail[-400:]}{incomplete}")


def _convert_with_word(legacy: list[Path]) -> None:
    powershell = shutil.which("powershell")
    if os.name != "nt" or not powershell:
        raise DocumentImportError(
            "找不到 LibreOffice；此環境也無法使用 Microsoft Word COM。"
        )

    script = r"""
    $ErrorActionPreference = 'Stop'
    $source = $env:DOC_CONVERT_SOURCE_DIR
    $targetRoot = $env:DOC_CONVERT_TARGET_DIR
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    try {
        Get-ChildItem -LiteralPath $source -File -Filter '*.doc' | ForEach-Object {
            $target = Join-Path $targetRoot ($_.BaseName + '.docx')
            if (-not (Test-Path -LiteralPath $target) -or $_.LastWriteTimeUtc -gt (Get-Item -LiteralPath $target).LastWriteTimeUtc) {
                $opened = $word.Documents.Open($_.FullName, $false, $true)
                try { $opened.SaveAs2($target, 16) } finally { $opened.Close($false) }
            }
        }
    } finally {
        $word.Quit()
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    }
    """

    environment = os.environ.copy()
    environment["DOC_CONVERT_SOURCE_DIR"] = str(SOURCE_DIR)
    environment["DOC_CONVERT_TARGET_DIR"] = str(CACHE_DIR)
    result = _run_conversion(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
        environment,
    )
    missing = [path.name for path in legacy if not _converted_path(path).is_file()]
    if result.returncode or missing:
        detail = (result.stderr or result.stdout or "Microsoft Word 轉換失敗").strip()
        incomplete = f"；未完成：{', '.join(missing[:3])}" if missing else ""
        raise DocumentImportError(f"{detail[-400:]}{incomplete}")


def _convert_legacy_documents() -> None:
    legacy = [path for path in _source_files(".doc") if _needs_conversion(path)]
    if not legacy:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    executable = shutil.which("soffice") or shutil.which("libreoffice")
    known = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
    if not executable and known.is_file():
        executable = str(known)
    if executable:
        _convert_with_libreoffice(executable, legacy)
    else:
        _convert_with_word(legacy)

# 用來辨識內文的函式
def _category(file_name: str) -> str:
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in file_name for keyword in keywords):
            return category
    return "共同體行政"


def _looks_like_heading(text: str, style_name: str) -> bool:
    style = style_name.casefold()
    if style.startswith("heading") or "標題" in style_name:
        return True
    prefix = r"^(第[一二三四五六七八九十]+|[一二三四五六七八九十]+[、.]|\d+[、.])"
    return len(text) <= 45 and bool(re.match(prefix, text))


def _chunk_section(heading: str, content: str) -> list[dict[str, str]]:
    """將單一文件區塊切成可安全寫入資料庫的長度。"""
    text = content.strip()
    if not text:
        return []
    chunks = [text[index:index + SECTION_LENGTH] for index in range(0, len(text), SECTION_LENGTH)]
    return [
        {
            "heading": (heading if index == 0 else f"{heading}（續）")[:300],
            "content": chunk,
        }
        for index, chunk in enumerate(chunks)
    ]


def _extract_word_sections(path: Path) -> list[dict[str, str]]:
    try:
        document = Document(path)
        blocks: list[tuple[str, str]] = []
        for paragraph in document.paragraphs:
            text = re.sub(r"\s+", " ", paragraph.text).strip()
            if text:
                style_name = paragraph.style.name if paragraph.style else ""
                blocks.append((text, style_name))
        for table in document.tables:
            rows = []
            for row in table.rows:
                values = [re.sub(r"\s+", " ", cell.text).strip() for cell in row.cells]
                if any(values):
                    rows.append(" ｜ ".join(values))
            if rows:
                blocks.append(("\n".join(rows), "表格"))
    except Exception as exc:
        raise DocumentImportError(f"無法讀取SOP文件：{path.name}") from exc

    title = path.stem
    sections: list[dict[str, str]] = []
    heading = "文件內容"
    content: list[str] = []
    size = 0

    def flush() -> None:
        nonlocal content, size
        body = "\n".join(content).strip()
        if body:
            sections.append({"heading": heading[:300], "content": body})
        content = []
        size = 0

    for text, style in blocks:
        if _looks_like_heading(text, style):
            flush()
            heading = text
            continue
        chunks = [text[index:index + SECTION_LENGTH] for index in range(0, len(text), SECTION_LENGTH)]
        for chunk in chunks:
            if content and size + len(chunk) > SECTION_LENGTH:
                flush()
                heading = f"{title}（續）"
            content.append(chunk)
            size += len(chunk)
    flush()
    return sections or [{"heading": "文件內容", "content": "此文件目前沒有可擷取的文字內容。"}]


def _excel_cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    return re.sub(r"\s+", " ", str(value)).strip()


def _extract_modern_excel_sections(path: Path) -> list[dict[str, str]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise DocumentImportError("缺少 openpyxl，無法讀取 Excel 文件。") from exc

    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            sections: list[dict[str, str]] = []
            for worksheet in workbook.worksheets:
                rows = []
                for row in worksheet.iter_rows(values_only=True):
                    values = [_excel_cell_text(value) for value in row]
                    while values and not values[-1]:
                        values.pop()
                    if any(values):
                        rows.append(" ｜ ".join(values))
                sections.extend(_chunk_section(worksheet.title, "\n".join(rows)))
        finally:
            workbook.close()
    except Exception as exc:
        raise DocumentImportError(f"無法讀取 Excel 文件：{path.name}") from exc
    return sections or [{"heading": "試算表內容", "content": "此文件目前沒有可擷取的儲存格內容。"}]


def _extract_legacy_excel_sections(path: Path) -> list[dict[str, str]]:
    try:
        import xlrd
    except ImportError as exc:
        raise DocumentImportError("缺少 xlrd，無法讀取舊版 Excel 文件。") from exc

    try:
        workbook = xlrd.open_workbook(path, on_demand=True)
        try:
            sections: list[dict[str, str]] = []
            for worksheet in workbook.sheets():
                rows = []
                for row_index in range(worksheet.nrows):
                    values = [
                        _excel_cell_text(worksheet.cell_value(row_index, column_index))
                        for column_index in range(worksheet.ncols)
                    ]
                    while values and not values[-1]:
                        values.pop()
                    if any(values):
                        rows.append(" ｜ ".join(values))
                sections.extend(_chunk_section(worksheet.name, "\n".join(rows)))
        finally:
            workbook.release_resources()
    except Exception as exc:
        raise DocumentImportError(f"無法讀取舊版 Excel 文件：{path.name}") from exc
    return sections or [{"heading": "試算表內容", "content": "此文件目前沒有可擷取的儲存格內容。"}]


def _extract_excel_sections(path: Path) -> list[dict[str, str]]:
    if path.suffix.casefold() == ".xls":
        return _extract_legacy_excel_sections(path)
    return _extract_modern_excel_sections(path)


def _extract_pdf_sections(path: Path) -> list[dict[str, str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentImportError("缺少 pypdf，無法讀取 PDF 文件。") from exc

    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise DocumentImportError(f"PDF 文件受密碼保護，無法讀取：{path.name}")
        sections: list[dict[str, str]] = []
        for page_number, page in enumerate(reader.pages, 1):
            lines = [re.sub(r"\s+", " ", line).strip() for line in (page.extract_text() or "").splitlines()]
            sections.extend(_chunk_section(f"第 {page_number} 頁", "\n".join(line for line in lines if line)))
    except DocumentImportError:
        raise
    except Exception as exc:
        raise DocumentImportError(f"無法讀取 PDF 文件：{path.name}") from exc
    return sections or [{"heading": "PDF 內容", "content": "此文件目前沒有可擷取的文字內容。"}]


def _extract_sections(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.casefold()
    if suffix == ".docx":
        return _extract_word_sections(path)
    if suffix in EXCEL_SUFFIXES:
        return _extract_excel_sections(path)
    if suffix in PDF_SUFFIXES:
        return _extract_pdf_sections(path)
    raise DocumentImportError(f"不支援的文件格式：{path.name}")


def read_operations_manuals() -> list[dict[str, Any]]:
    """讀取 ``data/exam`` 的 Word、Excel 與 PDF，回傳可寫入資料庫的結構。"""
    if not SOURCE_DIR.is_dir():
        return []
    _convert_legacy_documents()
    sources: list[tuple[Path, Path]] = []
    for legacy in _source_files(".doc"):
        converted = _converted_path(legacy)
        if not converted.is_file():
            raise DocumentImportError(f"找不到轉換結果：{legacy.name}")
        sources.append((legacy, converted))
    converted_names = {legacy.stem.casefold() for legacy, _ in sources}
    for modern in _source_files(".docx"):
        if modern.stem.casefold() not in converted_names:
            sources.append((modern, modern))
    for suffix in sorted(EXCEL_SUFFIXES | PDF_SUFFIXES):
        sources.extend((path, path) for path in _source_files(suffix))
    sources.sort(key=lambda item: item[0].name.casefold())

    result: list[dict[str, Any]] = []
    for source, readable in sources:
        try:
            stat = source.stat()
            sections = _extract_sections(readable)
        except OSError as exc:
            raise DocumentImportError(f"無法存取SOP文件：{source.name}") from exc
        result.append(
            {
                "file_name": source.name,
                "title": source.stem,
                "category": _category(source.name),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                "sections": sections,
            }
        )
    return result


def _native_text_is_usable(text: str) -> bool:
    """判斷 PDF 文字層是否足以供題目解析，避免把空白或亂碼當成成功。"""
    compact = re.sub(r"\s+", "", text)
    if len(compact) < MIN_NATIVE_TEXT_LENGTH:
        return False
    replacement_ratio = compact.count("�") / max(1, len(compact))
    readable = sum(character.isalnum() or "\u4e00" <= character <= "\u9fff" for character in compact)
    return replacement_ratio < 0.02 and readable / len(compact) >= 0.45


def _tesseract_executable() -> str:
    executable = shutil.which("tesseract")
    known = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if not executable and known.is_file():
        executable = str(known)
    if not executable:
        raise DocumentImportError(
            "找不到 Tesseract OCR；請安裝 Tesseract 並加入 chi_tra、eng 語言資料。"
        )
    return executable


def _ocr_pdf_page(path: Path, page_index: int) -> str:
    """以 300 DPI 與繁中／英文模型 OCR 單一掃描頁面。"""
    try:
        import fitz
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise DocumentImportError(
            "缺少 PyMuPDF、Pillow 或 pytesseract，無法辨識掃描型 PDF。"
        ) from exc

    pytesseract.pytesseract.tesseract_cmd = _tesseract_executable()
    try:
        languages = set(pytesseract.get_languages(config=""))
    except Exception as exc:
        raise DocumentImportError("無法讀取 Tesseract 語言資料。") from exc
    missing_languages = {"chi_tra", "eng"} - languages
    if missing_languages:
        raise DocumentImportError(
            f"Tesseract 缺少語言資料：{', '.join(sorted(missing_languages))}。"
        )
    try:
        with fitz.open(path) as pdf:
            page = pdf.load_page(page_index)
            scale = OCR_DPI / 72
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            return pytesseract.image_to_string(
                image,
                lang=OCR_LANGUAGES,
                config="--oem 1 --psm 3",
            )
    except DocumentImportError:
        raise
    except Exception as exc:
        raise DocumentImportError(f"PDF 第 {page_index + 1} 頁 OCR 失敗：{path.name}") from exc


def _pdf_pages_for_questions(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """逐頁取得 PDF 文字；只有原生文字不足的頁面才啟動 OCR。"""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentImportError("缺少 pypdf，無法讀取 PDF 文件。") from exc

    warnings: list[str] = []
    pages: list[dict[str, Any]] = []
    ocr_unavailable = ""
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise DocumentImportError(f"PDF 文件受密碼保護，無法讀取：{path.name}")
        for page_index, page in enumerate(reader.pages):
            native = page.extract_text() or ""
            method = "native"
            if not _native_text_is_usable(native):
                method = "ocr"
                if ocr_unavailable:
                    native = ""
                else:
                    try:
                        native = _ocr_pdf_page(path, page_index)
                    except DocumentImportError as exc:
                        message = str(exc)
                        warnings.append(f"第 {page_index + 1} 頁：{message}")
                        if message.startswith(("找不到 Tesseract", "缺少 PyMuPDF", "無法讀取 Tesseract", "Tesseract 缺少")):
                            ocr_unavailable = message
                        native = ""
            pages.append({"page": page_index + 1, "text": native, "method": method})
    except DocumentImportError:
        raise
    except Exception as exc:
        raise DocumentImportError(f"無法讀取題庫 PDF：{path.name}") from exc
    return pages, warnings


def _word_pages_for_questions(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    sections = _extract_word_sections(path)
    return [
        {"page": index, "text": f"{section['heading']}\n{section['content']}", "method": "native"}
        for index, section in enumerate(sections, 1)
    ], []


def _question_content_blocks(text: str) -> list[dict[str, str]]:
    """將題幹拆成安全的文字與程式碼區塊，不產生任意 HTML。"""
    lines = [line.rstrip() for line in text.strip().splitlines()]
    blocks: list[dict[str, str]] = []
    current_type = "text"
    current: list[str] = []
    code_pattern = re.compile(
        r"^\s*(?:>>>|\.\.\.|#|(?:async\s+)?def\s+|class\s+|from\s+\S+\s+import\s+|import\s+|"
        r"if\s+|elif\s+|else:|for\s+|while\s+|try:|except\b|finally:|return\b|print\s*\(|"
        r"[A-Za-z_]\w*\s*(?:=|\+=|-=|\*=|/=)).*"
    )

    def flush() -> None:
        nonlocal current
        value = "\n".join(current).strip("\n")
        if value:
            blocks.append({"type": current_type, "content": value})
        current = []

    for line in lines:
        detected = "code" if code_pattern.match(line) else "text"
        if current and detected != current_type:
            flush()
        current_type = detected
        current.append(line)
    flush()
    return blocks or [{"type": "text", "content": text.strip()}]


def _normalize_option_text(value: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", value.strip())[:1000]


def _parse_question_block(
    block: str,
    *,
    number: str,
    answer_marker: str,
    source: Path,
    page_number: int,
    chapter_code: str,
    chapter_name: str,
) -> dict[str, Any] | None:
    first_line, _, remainder = block.partition("\n")
    start = QUESTION_START_PATTERN.match(first_line.strip())
    if not start:
        return None
    stem_head = start.group("stem").strip()
    option_matches = list(OPTION_PATTERN.finditer(remainder))
    first_option_start = option_matches[0].start() if option_matches else len(remainder)
    stem = "\n".join(part for part in (stem_head, remainder[:first_option_start].strip()) if part).strip()
    options = [_normalize_option_text(match.group("text")) for match in option_matches]
    marked_answers = [
        ord(match.group("label")) - ord("A")
        for match in option_matches
        if match.group("marked") and re.search(r"✅|✓|✔", match.group("marked"))
    ]
    explicit_answers = [ord(label) - ord("A") for label in re.findall(r"[A-F]", answer_marker or "")]
    answers = sorted(set(explicit_answers or marked_answers))
    explanation_match = re.search(r"(?is)(?:答案解析|解析|解說)\s*[:：]\s*(.+)$", block)
    explanation = explanation_match.group(1).strip()[:4000] if explanation_match else ""
    warnings: list[str] = []

    is_fill_blank = bool(re.search(r"_{3,}\s*(?:\(\d+\))?\s*_{0,}", stem))
    is_matching = any(keyword in block for keyword in ("移至右側", "配對", "每種資料類型可能"))
    if is_matching:
        question_type = "matching"
    elif is_fill_blank:
        question_type = "fill_blank"
    elif len(answers) > 1:
        question_type = "multiple_choice"
    else:
        question_type = "single_choice"

    if question_type in {"single_choice", "multiple_choice"} and len(options) < 2:
        return None
    if not answers:
        warnings.append("未可靠辨識正確答案")
    if not explanation:
        warnings.append("來源未提供明確解析")
    if question_type == "matching":
        warnings.append("配對項目需由管理員確認")
    if question_type == "fill_blank":
        warnings.append("填空選項需由管理員確認")

    subject = "ITS Python" if "python" in source.name.casefold() else _category(source.name)
    source_key = f"{source.name}:{page_number}:{number}"
    normalized = re.sub(r"\s+", " ", stem).strip().casefold()
    fingerprint = hashlib.sha256(f"{source.name}|{number}|{normalized}".encode("utf-8")).hexdigest()
    confidence = 0.45
    confidence += 0.18 if len(options) >= 2 else 0
    confidence += 0.18 if answers else 0
    confidence += 0.10 if explanation else 0
    confidence += 0.05 if chapter_code else 0
    return {
        "domain": "academic",
        "subject": subject,
        "chapter_code": chapter_code or "UNSORTED",
        "chapter": chapter_name or "待分類",
        "source_document": source.name,
        "source_locator": f"第 {page_number} 頁／題號 {number}",
        "source_question_key": source_key[:200],
        "source_fingerprint": fingerprint,
        "question_type": question_type,
        "stem_blocks": _question_content_blocks(stem),
        "question": stem[:500],
        "options": options,
        "answers": answers,
        "structure": {"blanks": [], "matching_pairs": []},
        "explanation": explanation,
        "parse_confidence": round(min(confidence, 0.99), 2),
        "parse_warnings": warnings,
        "status": "draft",
        "admin_locked": False,
    }


def _parse_questions_from_pages(source: Path, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    chapter_code = ""
    chapter_name = ""
    for page in pages:
        text = re.sub(r"\r\n?", "\n", page["text"] or "")
        chapter = CHAPTER_PATTERN.search(text)
        if chapter:
            chapter_code = f"CH{int(chapter.group(1)):02d}"
            chapter_name = chapter.group(2).strip(" ：:-") or chapter_code
        starts = list(QUESTION_START_PATTERN.finditer(text))
        for index, match in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
            block = text[match.start():end].strip()
            parsed = _parse_question_block(
                block,
                number=match.group("number"),
                answer_marker=match.group("answer") or "",
                source=source,
                page_number=int(page["page"]),
                chapter_code=chapter_code,
                chapter_name=chapter_name,
            )
            if parsed:
                questions.append(parsed)
    return questions


def read_training_question_drafts() -> dict[str, Any]:
    """從題庫來源建立結構化草稿；個別文件失敗不會中斷整批。"""
    drafts: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    sources = [
        path
        for suffix in (".docx", ".pdf")
        for path in _source_files(suffix)
    ]
    for source in sources:
        try:
            if source.suffix.casefold() == ".pdf":
                pages, source_warnings = _pdf_pages_for_questions(source)
            else:
                pages, source_warnings = _word_pages_for_questions(source)
            drafts.extend(_parse_questions_from_pages(source, pages))
            for message in source_warnings:
                detail = {"source": source.name, "message": message}
                if any(marker in message for marker in (
                    "找不到 Tesseract", "缺少 PyMuPDF", "無法讀取 Tesseract", "Tesseract 缺少",
                )):
                    failures.append(detail)
                else:
                    warnings.append(detail)
        except DocumentImportError as exc:
            failures.append({"source": source.name, "message": str(exc)})
    return {
        "questions": drafts,
        "warnings": warnings,
        "failures": failures,
        "sources": len(sources),
    }


def sync_training_sources(*, ensure_schema: bool = True) -> dict[str, Any]:
    """同步 SOP 與題目草稿，回傳可供 MIS 顯示的完整報告。"""
    try:
        from . import data
    except ImportError:
        import data

    with SYNC_LOCK:
        if ensure_schema:
            data.ensure_application_schema()
        documents = read_operations_manuals()
        document_count = data.upsert_operations_manuals(documents)
        parsed = read_training_question_drafts()
        imported = data.import_training_question_drafts(
            parsed["questions"], parsed["warnings"], parsed["failures"],
        )
        return {
            "documents": document_count,
            "sources": parsed["sources"],
            "parsed": len(parsed["questions"]),
            "pending_review": imported["created"] + imported["updated"],
            "warnings": parsed["warnings"],
            "failures": parsed["failures"],
            **imported,
        }


def sync_operations_manuals(*, ensure_schema: bool = True) -> int:
    """將文件同步至網站專用資料表，並避免多個請求同時執行轉檔。"""
    try:
        from . import data
    except ImportError:  # 支援直接執行 backend/doc.py
        import data

    with SYNC_LOCK:
        if ensure_schema:
            data.ensure_application_schema()
        return data.upsert_operations_manuals(read_operations_manuals())


def main() -> None:
    parser = argparse.ArgumentParser(description="匯入銀盾共同體營運SOP Word、Excel 與 PDF 文件")
    parser.add_argument("--sync", action="store_true", help="擷取後寫入 SQL Server")
    args = parser.parse_args()
    try:
        if args.sync:
            print(f"已同步 {sync_operations_manuals()} 份SOP文件。")
        else:
            documents = read_operations_manuals()
            sections = sum(len(item["sections"]) for item in documents)
            print(f"已讀取 {len(documents)} 份文件，共 {sections} 個段落區塊。")
    except DocumentImportError as exc:
        raise SystemExit(f"SOP文件處理失敗：{exc}") from exc


if __name__ == "__main__":
    main()
