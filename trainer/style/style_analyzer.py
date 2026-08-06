"""SoulSync - 语言风格：用户语言特征分析"""
import re
from collections import Counter
from ..trainer_types import LanguageProfile


PARTICLES = ["吧", "呢", "呀", "嘛", "哈", "嗯", "哦", "嘞"]
NET_SPEECH = ["hhh", "绝绝子", "蚌埠住了", "yyds", "笑死", "麻了"]


class StyleAnalyzer:
    def analyze_increment(self, message: str, profile: LanguageProfile = None) -> dict:
        if profile is None:
            profile = LanguageProfile()
        profile.total_turns += 1
        length = len(message)
        profile.avg_length = (profile.avg_length * (profile.total_turns - 1) + length) / profile.total_turns

        particle_count = sum(1 for p in PARTICLES if p in message)
        net_count = sum(1 for n in NET_SPEECH if n in message)
        eng_count = len(re.findall(r'[a-zA-Z]+', message))
        total_chars = len(re.sub(r'\s', '', message))
        profile.english_mix_rate = (eng_count / max(1, total_chars)) if total_chars > 0 else 0

        return {"length": length, "particles": particle_count, "net_speech": net_count}