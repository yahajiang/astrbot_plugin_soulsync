"""SoulSync - 语言风格：用户语言特征分析（8维）"""
import re
from collections import Counter
from ..trainer_types import LanguageProfile


PARTICLES = ["吧", "呢", "呀", "嘛", "哈", "嗯", "哦", "嘞"]
NET_SPEECH = ["hhh", "绝绝子", "蚌埠住了", "yyds", "笑死", "麻了", "无语子", "集美"]
PUNCT_MARKS = {"~": "~", "……": "……", "！": "!", "？": "?"}


class StyleAnalyzer:
    def analyze_increment(self, message: str, profile: LanguageProfile = None) -> dict:
        if profile is None:
            profile = LanguageProfile()
        profile.total_turns += 1
        length = len(message)
        profile.avg_length = (profile.avg_length * (profile.total_turns - 1) + length) / profile.total_turns

        particle_count = sum(1 for p in PARTICLES if p in message)
        net_count = sum(1 for n in NET_SPEECH if n in message.lower())
        eng_words = len(re.findall(r'[a-zA-Z]+', message))
        total_chars = len(re.sub(r'\s', '', message))
        profile.english_mix_rate = eng_words / max(1, total_chars)

        for mark, key in PUNCT_MARKS.items():
            if mark in message:
                profile.punctuation[key] = profile.punctuation.get(key, 0) + message.count(mark)

        formality = 1.0
        if particle_count > 0:
            formality -= 0.08 * min(particle_count, 5)
        if net_count > 0:
            formality -= 0.12 * min(net_count, 3)
        if "~" in message:
            formality -= 0.05
        profile.formality_score = max(0.05, min(0.95, (profile.formality_score * (profile.total_turns - 1) + formality) / profile.total_turns))

        directness = 0.5
        if "!" in message or "！" in message:
            directness += 0.15
        if "?" in message or "？" in message:
            directness += 0.05
        profile.directness_score = max(0.05, min(0.95, (profile.directness_score * (profile.total_turns - 1) + directness) / profile.total_turns))

        return {
            "length": length,
            "particles": particle_count,
            "net_speech": net_count,
            "formality": profile.formality_score,
            "directness": profile.directness_score,
        }