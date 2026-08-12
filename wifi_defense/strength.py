"""Offline password-strength assessment without password retention."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re


@dataclass(frozen=True)
class PasswordAssessment:
    """A non-sensitive summary of a locally assessed password."""

    score: int
    label: str
    estimated_guesses_log10: float
    feedback: tuple[str, ...]
    length: int


def assess_password(password: str) -> PasswordAssessment:
    """Assess a password locally and return guidance without storing the input."""
    if not isinstance(password, str):
        raise TypeError("密码必须是字符串")

    length = len(password)
    categories = sum(
        [
            bool(re.search(r"[a-z]", password)),
            bool(re.search(r"[A-Z]", password)),
            bool(re.search(r"\d", password)),
            bool(re.search(r"[^A-Za-z0-9]", password)),
        ]
    )
    charset_size = [0, 26, 52, 62, 94][categories]
    entropy_bits = math.log2(charset_size**length) if length and charset_size else 0.0
    guesses_log10 = max(0.0, entropy_bits * math.log10(2))

    feedback: list[str] = []
    if length < 14:
        feedback.append("建议使用至少 14 个字符的随机长口令。")
    if categories < 3:
        feedback.append("建议组合大小写字母、数字和符号，并避免可预测替换。")
    if re.search(r"(.)\1\1", password):
        feedback.append("避免连续重复字符，例如 aaa 或 111。")
    if _contains_sequence(password):
        feedback.append("避免常见顺序或键盘模式，例如 1234、abcd、qwerty。")
    common_pattern = _looks_like_common_pattern(password)
    if common_pattern:
        feedback.append("避免常见单词、品牌名、姓名或日期组合；优先使用密码管理器生成的随机口令。")

    if length >= 16 and categories >= 3 and not feedback:
        score, label = 4, "强"
    elif length >= 14 and categories >= 3:
        score, label = 3, "良好"
    elif length >= 10 and categories >= 2:
        score, label = 2, "一般"
    elif length >= 8:
        score, label = 1, "弱"
    else:
        score, label = 0, "很弱"

    if common_pattern:
        score = min(score, 1)
        label = "弱" if score == 1 else "很弱"

    if not feedback:
        feedback.append("该口令通过了本地启发式检查；仍建议为不同网络使用独立随机口令。")

    return PasswordAssessment(
        score=score,
        label=label,
        estimated_guesses_log10=round(guesses_log10, 1),
        feedback=tuple(feedback),
        length=length,
    )


def _contains_sequence(value: str) -> bool:
    lowered = value.lower()
    patterns = ("0123456789", "abcdefghijklmnopqrstuvwxyz", "qwertyuiop", "asdfghjkl", "zxcvbnm")
    for pattern in patterns:
        for index in range(len(pattern) - 3):
            segment = pattern[index : index + 4]
            if segment in lowered or segment[::-1] in lowered:
                return True
    return False


def _looks_like_common_pattern(value: str) -> bool:
    lowered = value.lower()
    common_fragments = ("password", "wifi", "admin", "welcome", "letmein", "iloveyou", "123456")
    return any(fragment in lowered for fragment in common_fragments)
