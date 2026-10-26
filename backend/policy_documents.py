from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

POLICY_REFERENCE_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "policies" / "policy_references.json"
)
POLICY_REFERENCE_PDF = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "policies"
    / "武汉市国土空间总体规划_2021-2035.pdf"
)


def load_policy_references() -> list[dict[str, Any]]:
    if not POLICY_REFERENCE_FILE.exists():
        return []
    try:
        payload = json.loads(POLICY_REFERENCE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    documents: list[dict[str, Any]] = []
    for item in payload.get("documents", []):
        text = str(item.get("text") or "")
        documents.append(
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or "政策参考文档"),
                "size": len(text.encode("utf-8")),
                "uploaded_at": str(payload.get("generated_at") or ""),
                "text_length": len(text),
                "excerpt": str(item.get("excerpt") or text[:140]),
                "warning": None,
                "text": text,
                "source_format": str(item.get("source_format") or ""),
                "stored_format": str(item.get("stored_format") or "plain_text"),
                "builtin": True,
            }
        )
    return documents


def extract_policy_text(path: Path) -> tuple[str, str | None]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".docx":
            return _extract_docx(path), None
        if suffix == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore"), None
        if suffix == ".doc":
            if path.read_bytes()[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                return "", "DOC为旧版二进制Word格式；请另存为DOCX后上传"
            text = _extract_legacy_doc(path)
            warning = None if len(text) > 80 else "DOC文本提取有限，建议转换为DOCX"
            return text, warning
    except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        return "", f"政策文件解析失败：{exc}"
    return "", "当前支持DOCX、DOC或TXT政策文件"


def _extract_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        line = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def _extract_legacy_doc(path: Path) -> str:
    data = path.read_bytes()
    best_chunks: list[str] = []
    for encoding in ("utf-16le", "gb18030", "utf-8"):
        text = data.decode(encoding, errors="ignore")
        chunks = re.findall(
            r"[\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9，。；：、（）《》“”‘’\s\-]{3,}",
            text,
        )
        cleaned_chunks: list[str] = []
        for chunk in chunks:
            cleaned = re.sub(r"\s+", " ", chunk).strip()
            cjk_count = sum(1 for char in cleaned if "\u4e00" <= char <= "\u9fff")
            if cjk_count >= 4 and cjk_count / max(len(cleaned), 1) >= 0.35:
                cleaned_chunks.append(cleaned)
        if sum(map(len, cleaned_chunks)) > sum(map(len, best_chunks)):
            best_chunks = cleaned_chunks
    return "\n".join(dict.fromkeys(best_chunks))
