from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.book_import import BookImportChapter
from app.services.book_import_service import book_import_service


def test_build_fallback_outline_structure_handles_empty_chapter_content() -> None:
    chapter = BookImportChapter(
        title="第1章",
        content="",
        summary=None,
        chapter_number=1,
        outline_title=None,
    )

    outline = book_import_service._build_fallback_outline_structure(chapter)

    assert outline["title"] == "第1章"
    assert outline["summary"] == "本章围绕主要人物与核心冲突推进剧情。"
