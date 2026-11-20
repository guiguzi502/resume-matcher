# -*- coding: utf-8 -*-
"""resume-matcher 单元测试。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matcher.extract import UnsupportedFormatError, extract_text  # noqa: E402
from matcher.scorer import RuleScorer, score_resume  # noqa: E402


# ---------------- extract ----------------
class TestExtract:
    def test_txt(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("姓名：张三\n技能：Python", encoding="utf-8")
        assert "Python" in extract_text(f)

    def test_unsupported(self, tmp_path):
        f = tmp_path / "a.xyz"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(UnsupportedFormatError):
            extract_text(f)

    def test_md(self, tmp_path):
        f = tmp_path / "b.md"
        f.write_text("# 简历\n- pandas", encoding="utf-8")
        assert "pandas" in extract_text(f)

    def test_docx(self, tmp_path):
        import docx
        d = docx.Document()
        d.add_paragraph("教育：湖南大学")
        p = tmp_path / "c.docx"
        d.save(str(p))
        assert "湖南大学" in extract_text(p)


# ---------------- scorer ----------------
class TestScorer:
    def test_rule_match(self):
        jd = "要求：Python、数据分析、爬虫、Docker、大模型"
        r = "会用 Python 做数据分析与爬虫，pandas 可视化。"
        res = score_resume(r, jd, use_llm=False)
        assert res["engine"] == "rule"
        assert "Python" in res["matched_skills"]
        assert "Docker" in res["missing_skills"]
        assert 0 <= res["score"] <= 100

    def test_rule_full_match_high_score(self):
        jd = "要求：Python、数据分析"
        r = "Python 数据分析 项目"
        res = score_resume(r, jd, use_llm=False)
        assert res["score"] >= 85
        assert not res["missing_skills"]

    def test_rule_no_overlap_low_score(self):
        jd = "要求：Docker、C++、嵌入式"
        r = "Python 爬虫 可视化"
        res = score_resume(r, jd, use_llm=False)
        assert res["score"] < 60
        assert "Docker" in res["missing_skills"]

    def test_sanitize_real(self):
        # 模拟 LLM 返回越界分数
        from matcher.scorer import _sanitize
        assert _sanitize({"score": 500})["score"] == 100
        assert _sanitize({"score": -3})["score"] == 0
        assert _sanitize({})["matched_skills"] == []