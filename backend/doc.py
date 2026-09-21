"""營運SOP文件的轉換、文字擷取與資料庫同步。
舊版*.doc優先使用 LibreOffice 無介面轉成快取*.docx；
若本機沒有LibreOffice，才在 Windows使用 Microsoft Word COM。原始文件永遠不會被修改。
支援 Word、Excel 與 PDF 文件。
"""

from __future__ import annotations

import argparse
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
# 目的是「精簡＋方便未來擴充關鍵字」，用資料驅動的寫法會更乾淨、更易維護
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "財務行政": ("會計", "財務", "出納", "帳務", "稅務"),
    "商務營運": ("業務", "合約", "客戶", "銷售", "專案", "營運"),
    "工安健康": ("安全", "健康", "醫療", "衛生", "消防", "急救", "礦場"),
    "生產製造": ("工藝", "鍛造", "裁縫", "製程", "品質", "設備", "倉儲"),
    "人事行政": ("人事", "招募", "福利", "考勤"),
}


class DocumentImportError(RuntimeError):
    """營運SOP文件無法轉換、擷取或同步時使用的安全例外。"""


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
        raise DocumentImportError(f"無法讀取營運SOP文件：{path.name}") from exc

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
            raise DocumentImportError(f"無法存取營運SOP文件：{source.name}") from exc
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
            print(f"已同步 {sync_operations_manuals()} 份營運SOP文件。")
        else:
            documents = read_operations_manuals()
            sections = sum(len(item["sections"]) for item in documents)
            print(f"已讀取 {len(documents)} 份文件，共 {sections} 個段落區塊。")
    except DocumentImportError as exc:
        raise SystemExit(f"營運SOP文件處理失敗：{exc}") from exc


if __name__ == "__main__":
    main()
