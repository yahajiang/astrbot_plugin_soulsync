"""图鉴注册表测试"""

from astrbot_plugin_soulsync_mirror.guides import (
    GUIDE_REGISTRY,
    CATEGORY_ORDER,
    CATEGORY_ICONS,
    match_guide,
    generate_guide_list,
)


class TestGuideRegistry:
    """图鉴注册表数据校验"""

    def test_total_count_157(self):
        """F-12: 图鉴总数 = 157"""
        assert len(GUIDE_REGISTRY) == 157

    def test_category_counts(self):
        """分类数量与文档一致"""
        counts = {}
        for g in GUIDE_REGISTRY.values():
            cat = g["category"]
            counts[cat] = counts.get(cat, 0) + 1
        assert counts.get("科学量表", 0) == 23
        assert counts.get("关系情感", 0) == 52
        assert counts.get("情绪状态", 0) == 28
        assert counts.get("社交与职场", 0) == 12
        assert counts.get("网络玩梗与趣味", 0) == 42

    def test_all_entries_have_required_fields(self):
        """每条图鉴都有必要字段"""
        for key, g in GUIDE_REGISTRY.items():
            assert "name" in g, f"{key} 缺少 name"
            assert "aliases" in g, f"{key} 缺少 aliases"
            assert "category" in g, f"{key} 缺少 category"
            assert "dims" in g, f"{key} 缺少 dims"
            assert "type_refs" in g, f"{key} 缺少 type_refs"
            assert "opening" in g, f"{key} 缺少 opening"
            assert len(g["dims"]) >= 2, f"{key} dims 不足 2 个"
            assert len(g["type_refs"]) >= 2, f"{key} type_refs 不足 2 个"
            assert g["opening"].endswith("？"), f"{key} opening 未以？结尾"

    def test_name_unique(self):
        """图鉴名称全局唯一"""
        names = [g["name"] for g in GUIDE_REGISTRY.values()]
        assert len(names) == len(set(names)), "存在重复名称"

    def test_aliases_unique(self):
        """别名全局唯一（同一图鉴内可多个）"""
        all_aliases = []
        for g in GUIDE_REGISTRY.values():
            all_aliases.extend(g.get("aliases", []))
        assert len(all_aliases) == len(set(all_aliases)), "存在重复别名"

    def test_no_forbidden_content(self):
        """禁止建议/诊断/你是XX型"""
        import re
        forbidden = re.compile(r"你应该|我建议|诊断|你是.{0,5}型")
        for key, g in GUIDE_REGISTRY.items():
            assert not forbidden.search(g["opening"]), f"{key} opening 含禁止词"


class TestMatchGuide:
    """图鉴匹配器测试（F-12: 157个图鉴均可精确匹配）"""

    def test_match_by_name(self):
        """按名称匹配"""
        assert match_guide("MBTI 16型人格") == "mbti_16"
        assert match_guide("九型人格测试") == "enneagram"

    def test_match_by_alias(self):
        """按别名匹配"""
        assert match_guide("mbti") == "mbti_16"
        assert match_guide("攻受") == "semeuke_test"
        assert match_guide("班味") == "banwei"

    def test_case_insensitive(self):
        """不区分大小写"""
        assert match_guide("MBTI") == "mbti_16"
        assert match_guide("Kinsey") == "kinsey_test"

    def test_no_match(self):
        """未找到返回 None"""
        assert match_guide("不存在的图鉴") is None
        assert match_guide("") is None

    def test_match_all_guides(self):
        """157 个图鉴均可通过名称匹配"""
        for key, g in GUIDE_REGISTRY.items():
            result = match_guide(g["name"])
            assert result == key, f"图鉴 {key}({g['name']}) 无法匹配"

    def test_match_all_aliases(self):
        """所有别名均可匹配"""
        for key, g in GUIDE_REGISTRY.items():
            for alias in g.get("aliases", []):
                result = match_guide(alias)
                assert result == key, f"别名 {alias} 无法匹配到 {key}"


class TestGenerateGuideList:
    """列表生成器测试"""

    def test_list_contains_total(self):
        """列表包含总数"""
        output = generate_guide_list()
        assert "157" in output

    def test_list_contains_all_categories(self):
        """列表包含全部分类"""
        output = generate_guide_list()
        for cat in CATEGORY_ORDER:
            assert cat in output

    def test_list_contains_usage_hint(self):
        """列表包含使用提示"""
        output = generate_guide_list()
        assert "/心镜 [名称]" in output

    def test_list_respects_max_aliases(self):
        """别名数量受限"""
        output = generate_guide_list(max_aliases=2)
        # 检查某一行不超过2个别名
        for line in output.split("\n"):
            if "→" in line:
                alias_part = line.split("→")[1].strip()
                alias_count = len(alias_part.split(" / ")) if alias_part else 0
                assert alias_count <= 2, f"别名数量超限: {alias_part}"
