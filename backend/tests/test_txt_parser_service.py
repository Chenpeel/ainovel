from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.txt_parser_service import TxtParserService


def test_split_chapters_ignores_end_markers_and_meta_lines() -> None:
    text = """
第1章 第一章

这是第一章正文。

(本章完)

完结感言

这里是感言，不应该被当成正文标题。

第2章 第二章

这是第二章正文。
""".strip()

    parser = TxtParserService()
    chapters = parser.split_chapters(text)

    assert [chapter["title"] for chapter in chapters] == ["第1章 第一章", "第2章 第二章"]
    assert chapters[0]["content"] == "这是第一章正文。"


def test_split_chapters_supports_special_appendix_heading() -> None:
    text = """
第1章 第一章

这是第一章正文。

番外：清旺来

这是番外正文。
""".strip()

    parser = TxtParserService()
    chapters = parser.split_chapters(text)

    assert [chapter["title"] for chapter in chapters] == ["第1章 第一章", "番外：清旺来"]


def test_split_chapters_skips_volume_meta_heading() -> None:
    text = """
第1卷（完）

第1章 第一章

这是第一章正文。
""".strip()

    parser = TxtParserService()
    chapters = parser.split_chapters(text)

    assert [chapter["title"] for chapter in chapters] == ["第1章 第一章"]
