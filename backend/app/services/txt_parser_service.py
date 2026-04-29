"""TXT 解析服务：编码识别、文本清洗与章节切分"""
from __future__ import annotations

import re
from typing import Optional

from app.logger import get_logger

logger = get_logger(__name__)


class TxtParserService:
    """TXT 解析服务（规则优先）"""

    STRONG_CHAPTER_PATTERNS = [
        re.compile(r"^第[一二三四五六七八九十百千万零〇两\d]+[章节回集部篇].*$"),
        re.compile(r"^chapter\s*\d+.*$", re.IGNORECASE),
        re.compile(r"^chap\.\s*\d+.*$", re.IGNORECASE),
    ]
    SPECIAL_CHAPTER_PATTERNS = [
        re.compile(r"^(序章|楔子|引子|前言|序|终章|終章|尾声|尾聲)\s*$"),
        re.compile(r"^番外(?:\s*\d+)?(?:\s*[:：].*)?$"),
    ]
    META_SECTION_PATTERNS = [
        re.compile(r"^[（(]\s*本章完\s*[)）]$"),
        re.compile(r"^第[一二三四五六七八九十百千万零〇两\d]+卷.*$"),
        re.compile(r"^(完结感言|完結感言|上架感言|关于番外|關于番外|白金了|单章|單章)$"),
        re.compile(r"^(新书|新書|感谢|感謝|番外更新|更新说明).*$"),
    ]
    SEPARATOR_PATTERN = re.compile(r"^[\-—_=~～·•.。…]{3,}$")
    QUOTED_OR_BRACKETED_PATTERN = re.compile(r'^[“"「『（(《〈【\[].*[”"」』）)》〉】\]]$')

    def decode_bytes(self, content: bytes) -> tuple[str, str]:
        """
        尝试解码 TXT 字节流

        Returns:
            (text, encoding)
        """
        encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "big5"]
        for enc in encodings:
            try:
                return content.decode(enc), enc
            except UnicodeDecodeError:
                continue

        # 最后兜底：不抛错，尽量读出内容
        logger.warning("TXT 编码自动识别失败，使用 utf-8(ignore) 兜底")
        return content.decode("utf-8", errors="ignore"), "utf-8(ignore)"

    def clean_text(self, text: str) -> str:
        """基础清洗：换行归一、去除异常空白、压缩多余空行"""
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
        normalized = normalized.replace("\u3000", "  ")
        normalized = re.sub(r"[ \t]+\n", "\n", normalized)
        normalized = re.sub(r"\n{4,}", "\n\n\n", normalized)
        return normalized.strip()

    def split_chapters(self, text: str) -> list[dict]:
        """
        章节切分（规则优先，失败兜底）

        Returns:
            [{title, content, chapter_number}]
        """
        if not text.strip():
            return []

        lines = text.split("\n")
        heading_indexes: list[int] = []
        meta_section_indexes: list[int] = []

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if self._is_meta_section(stripped):
                meta_section_indexes.append(idx)
                continue
            if self._is_strong_heading(stripped) or self._is_special_heading(stripped):
                heading_indexes.append(idx)

        # 去重并排序
        heading_indexes = sorted(set(heading_indexes))

        # 如果一个标题都识别不到，走固定窗口兜底
        if not heading_indexes:
            return self._fallback_split(text)

        # 如果第一个标题前有较长正文，作为前言章节保留
        chapters: list[dict] = []
        chapter_no = 1

        first_heading = heading_indexes[0]
        if first_heading > 0:
            preface = "\n".join(lines[:first_heading]).strip()
            if len(preface) >= 200:
                chapters.append(
                    {
                        "title": "前言",
                        "content": preface,
                        "chapter_number": chapter_no,
                    }
                )
                chapter_no += 1

        for i, start_idx in enumerate(heading_indexes):
            end_idx = heading_indexes[i + 1] if i + 1 < len(heading_indexes) else len(lines)
            meta_break = next((meta_idx for meta_idx in meta_section_indexes if start_idx < meta_idx < end_idx), None)
            if meta_break is not None:
                end_idx = meta_break
            title = lines[start_idx].strip()[:200] or f"第{chapter_no}章"
            body = self._build_chapter_body(lines[start_idx + 1 : end_idx])
            # 防止空标题/空正文完全丢失
            if not body and i + 1 < len(heading_indexes):
                next_line = lines[start_idx + 1].strip() if start_idx + 1 < len(lines) else ""
                body = next_line

            chapters.append(
                {
                    "title": title,
                    "content": body,
                    "chapter_number": chapter_no,
                }
            )
            chapter_no += 1

        # 过滤掉明显噪音章节
        filtered = [c for c in chapters if c["title"] or c["content"]]
        if filtered:
            return filtered

        return self._fallback_split(text)

    def _is_strong_heading(self, line: str) -> bool:
        return any(pattern.match(line) for pattern in self.STRONG_CHAPTER_PATTERNS)

    def _is_special_heading(self, line: str) -> bool:
        return any(pattern.match(line) for pattern in self.SPECIAL_CHAPTER_PATTERNS)

    def _is_meta_section(self, line: str) -> bool:
        return any(pattern.match(line) for pattern in self.META_SECTION_PATTERNS)

    def _build_chapter_body(self, body_lines: list[str]) -> str:
        filtered_lines = [
            line for line in body_lines
            if not re.match(r"^[（(]\s*本章完\s*[)）]$", line.strip())
        ]
        return "\n".join(filtered_lines).strip()

    def _is_weak_heading(self, lines: list[str], idx: int) -> bool:
        """
        弱模式：短行 + 前后空行 + 明显排除章节结束语/感言/对白/分隔线等误判
        """
        line = lines[idx].strip()
        if not line:
            return False
        if len(line) > 25:
            return False
        if self._is_meta_section(line):
            return False
        if re.search(r"[，。！？；：,.!?;:]", line):
            return False
        if self.SEPARATOR_PATTERN.match(line):
            return False
        if self.QUOTED_OR_BRACKETED_PATTERN.match(line):
            return False
        if re.search(r"[“”\"「」『』（）()《》〈〉【】\[\]]", line):
            return False

        prev_blank = idx == 0 or not lines[idx - 1].strip()
        next_blank = idx == len(lines) - 1 or not lines[idx + 1].strip()
        return prev_blank and next_blank

    def _fallback_split(self, text: str, min_window: int = 3000, max_window: int = 5000) -> list[dict]:
        """
        固定窗口 + 标点边界切分
        """
        chapters: list[dict] = []
        n = len(text)
        start = 0
        chapter_no = 1
        boundary_punctuations = "。！？!?\n"

        while start < n:
            ideal_end = min(start + max_window, n)
            if ideal_end >= n:
                end = n
            else:
                search_from = min(start + min_window, n)
                segment = text[search_from:ideal_end]
                offset = max(segment.rfind(p) for p in boundary_punctuations)
                end = search_from + offset + 1 if offset >= 0 else ideal_end

            chunk = text[start:end].strip()
            if chunk:
                chapters.append(
                    {
                        "title": f"第{chapter_no}章",
                        "content": chunk,
                        "chapter_number": chapter_no,
                    }
                )
                chapter_no += 1

            start = end

        return chapters


txt_parser_service = TxtParserService()
