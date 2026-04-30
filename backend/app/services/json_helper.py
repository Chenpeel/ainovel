"""JSON 处理工具类"""
import json
import re
from typing import Any, Dict, List, Union

from app.logger import get_logger

try:
    import json5

    HAS_JSON5 = True
except ImportError:
    HAS_JSON5 = False

logger = get_logger(__name__)


# 中文引号/括号到 ASCII 的映射
_QUOTE_MAP = {
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u300e": '"',
    "\u300f": '"',
    "\u300c": '"',
    "\u300d": '"',
}


def _fix_json_string_values(text: str) -> str:
    """
    修复 JSON 字符串值中的常见问题：
    1. 裸换行符/制表符 -> 转义
    2. 字符串值内的中文引号 -> 转义为 ASCII 引号，避免破坏 JSON 结构
    3. 结构位置的中文引号 -> 直接替换为 ASCII 引号
    """
    if not text or '"' not in text:
        return text

    result: List[str] = []
    i = 0
    in_string = False
    fixed_count = 0

    while i < len(text):
        c = text[i]

        if c == '"' and not in_string:
            in_string = True
            result.append(c)
            i += 1
            continue

        if in_string:
            if c == "\\":
                if i + 1 < len(text):
                    next_c = text[i + 1]
                    if next_c in ('"', "\\", "/", "b", "f", "n", "r", "t"):
                        result.append(c)
                        result.append(next_c)
                        i += 2
                        continue
                    if next_c == "u":
                        if i + 5 < len(text) and all(
                            text[i + 2 + k] in "0123456789abcdefABCDEF" for k in range(4)
                        ):
                            result.append(text[i : i + 6])
                            i += 6
                            continue

                        result.append(next_c)
                        fixed_count += 1
                        i += 2
                        continue

                    result.append(next_c)
                    fixed_count += 1
                    i += 2
                    continue

                fixed_count += 1
                i += 1
                continue

            if c == '"':
                in_string = False
                result.append(c)
                i += 1
                continue

            if c == "\n":
                result.append("\\")
                result.append("n")
                fixed_count += 1
                i += 1
                continue

            if c == "\r":
                result.append("\\")
                result.append("n")
                fixed_count += 1
                if i + 1 < len(text) and text[i + 1] == "\n":
                    i += 2
                else:
                    i += 1
                continue

            if c == "\t":
                result.append("\\")
                result.append("t")
                fixed_count += 1
                i += 1
                continue

            if c in _QUOTE_MAP:
                result.append("\\")
                result.append(_QUOTE_MAP[c])
                fixed_count += 1
                i += 1
                continue

        if not in_string and c in _QUOTE_MAP:
            result.append(_QUOTE_MAP[c])
            fixed_count += 1
            i += 1
            continue

        result.append(c)
        i += 1

    if fixed_count > 0:
        logger.debug(f"✅ 修复了{fixed_count}个 JSON 问题（裸控制字符/中文引号）")

    return "".join(result)


def clean_json_response(text: str) -> str:
    """清洗 AI 返回的 JSON（改进版 - 流式安全）"""
    try:
        if not text:
            logger.warning("⚠️ clean_json_response: 输入为空")
            return text

        original_length = len(text)
        logger.debug(f"🔍 开始清洗JSON，原始长度: {original_length}")

        # AI 偶尔会在结构位置输出中文逗号/冒号，统一转换。
        text = text.replace("\uff0c", ",")
        text = text.replace("\uff1a", ":")

        text = _fix_json_string_values(text)

        text = re.sub(r"^```json\s*\n?", "", text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r"^```\s*\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
        text = text.strip()

        if len(text) != original_length:
            logger.debug(f"   移除markdown后长度: {len(text)}")

        try:
            json.loads(text)
            logger.debug("✅ 直接解析成功，无需清洗")
            return text
        except Exception:
            pass

        start = -1
        for i, c in enumerate(text):
            if c in ("{", "["):
                start = i
                break

        if start == -1:
            logger.warning("⚠️ 未找到JSON起始符号 { 或 [")
            logger.debug(f"   文本预览: {text[:200]}")
            return text

        if start > 0:
            logger.debug(f"   跳过前{start}个字符")
            text = text[start:]

        stack: List[str] = []
        i = 0
        end = -1
        in_string = False

        while i < len(text):
            c = text[i]

            if c == '"':
                if not in_string:
                    in_string = True
                else:
                    num_backslashes = 0
                    j = i - 1
                    while j >= 0 and text[j] == "\\":
                        num_backslashes += 1
                        j -= 1

                    if num_backslashes % 2 == 0:
                        in_string = False

                i += 1
                continue

            if in_string:
                i += 1
                continue

            if c == "{" or c == "[":
                stack.append(c)
            elif c == "}":
                if stack and stack[-1] == "{":
                    stack.pop()
                    if not stack:
                        end = i + 1
                        logger.debug(f"✅ 找到JSON结束位置: {end}")
                        break
                elif stack:
                    logger.warning(f"⚠️ 括号不匹配：遇到 }} 但栈顶是 {stack[-1]}")
                else:
                    logger.warning("⚠️ 遇到多余的 }，忽略")
            elif c == "]":
                if stack and stack[-1] == "[":
                    stack.pop()
                    if not stack:
                        end = i + 1
                        logger.debug(f"✅ 找到JSON结束位置: {end}")
                        break
                elif stack:
                    logger.warning(f"⚠️ 括号不匹配：遇到 ] 但栈顶是 {stack[-1]}")
                else:
                    logger.warning("⚠️ 遇到多余的 ]，忽略")

            i += 1

        if in_string:
            logger.warning("⚠️ 字符串未闭合，JSON可能不完整")

        if end > 0:
            result = text[:end]
            logger.debug(f"✅ JSON清洗完成，结果长度: {len(result)}")
        else:
            result = text
            logger.warning(f"⚠️ 未找到JSON结束位置，返回全部内容（长度: {len(result)}）")
            logger.debug(f"   栈状态: {stack}")

        try:
            json.loads(result)
            logger.debug("✅ 清洗后JSON验证成功")
        except json.JSONDecodeError as e:
            logger.error(f"❌ 清洗后JSON仍然无效: {e}")
            logger.debug(f"   结果预览: {result[:500]}")
            logger.debug(f"   结果结尾: ...{result[-200:]}")

        return result

    except Exception as e:
        logger.error(f"❌ clean_json_response 出错: {e}")
        logger.error(f"   文本长度: {len(text) if text else 0}")
        logger.error(f"   文本预览: {text[:200] if text else 'None'}")
        raise


def parse_json(text: str) -> Union[Dict, List]:
    """解析 JSON，优先标准 json，失败后再尝试 json5 容错解析。"""
    cleaned = clean_json_response(text)

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, Exception):
        pass

    if HAS_JSON5:
        try:
            logger.info("🔄 标准JSON解析失败，使用json5容错解析")
            result = json5.loads(cleaned)
            logger.info("✅ json5容错解析成功")
            return result
        except Exception as e5:
            logger.error(f"❌ json5容错解析也失败: {e5}")

    logger.error("❌ parse_json 完全失败")
    logger.error(f"   原始文本长度: {len(text) if text else 0}")
    logger.error(f"   清洗后文本长度: {len(cleaned) if cleaned else 0}")
    logger.debug(f"   清洗后文本预览: {cleaned[:500] if cleaned else 'None'}")
    raise json.JSONDecodeError("JSON解析失败（标准和json5均失败）", cleaned, 0)


def loads_json(text: str) -> Any:
    """`json.loads` 的容错替代品。"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, Exception):
        pass

    if HAS_JSON5:
        try:
            logger.info("🔄 json.loads失败，使用json5容错解析")
            result = json5.loads(text)
            logger.info("✅ json5容错解析成功")
            return result
        except Exception as e5:
            logger.error(f"❌ json5容错解析也失败: {e5}")

    raise json.JSONDecodeError("JSON解析失败（标准和json5均失败）", text, 0)
