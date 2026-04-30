from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import json_helper


def test_parse_json_repairs_chinese_quotes_and_bare_newline() -> None:
    text = """```json
{
  "title"："他说：“你好”",
  "summary":"第一行
第二行"
}
```"""

    parsed = json_helper.parse_json(text)

    assert parsed["title"] == '他说:"你好"'
    assert parsed["summary"] == "第一行\n第二行"


def test_parse_json_strips_invalid_escape_character() -> None:
    text = '{"value":"abc\\qdef"}'

    parsed = json_helper.parse_json(text)

    assert parsed["value"] == "abcqdef"


def test_loads_json_falls_back_to_json5_when_available() -> None:
    if not json_helper.HAS_JSON5:
        return

    parsed = json_helper.loads_json("{'name': 'mumu',}")

    assert parsed == {"name": "mumu"}
