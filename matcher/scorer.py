# -*- coding: utf-8 -*-
"""匹配打分：LLM 结构化输出（主）+ 规则兜底（无 API 时也能用）。

LLM 返回 JSON:
{
  "score": 0-100,
  "matched_skills": ["Python", ...],
  "missing_skills": ["Docker", ...],
  "suggestions": ["补一个 Docker 部署实战", ...],
  "reasons": [{"skill": "Python", "why": "JD 要求 Python，简历有 pandas 项目", "evidence": "原文引用"}]
}

规则兜底：基于关键词在简历/JD 中的命中情况打分，保证离线可用。
"""
import json
import logging
import os
import re

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"

SKILL_KEYWORDS = [
    "Python", "SQL", "pandas", "numpy", "matplotlib", "sqlite", "git",
    "Docker", "Linux", "机器学习", "深度学习", "PyTorch", "TensorFlow",
    "数据分析", "爬虫", "可视化", "GitHub Actions", "API", "REST",
    "C++", "Java", "C", "MATLAB", "信号处理", "自动化", "嵌入式",
    "STM32", "单片机", "通信", "OpenCV", "Streamlit", "Flask",
    "FastAPI", "LangChain", "RAG", "Agent", "大模型", "LLM",
    "英语", "CET-6", "CET-4", "office", "Excel",
]

# 高频技能别名归一化（小写 -> 标准名）
SKILL_ALIAS = {
    "github actions": "GitHub Actions",
    "actions": "GitHub Actions",
    "c++": "C++",
    "c语言": "C",
    "机器学习": "机器学习",
    "ml": "机器学习",
    "深度学习": "深度学习",
    "dl": "深度学习",
    "数据分析": "数据分析",
    "可视化": "数据可视化",
    "爬虫": "爬虫",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _contains(norm_text: str, key: str) -> bool:
    """关键词命中：英文/数字带词边界，中文直接子串。"""
    if re.fullmatch(r"[a-z0-9+#.\-]+", key):
        return re.search(
            rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", norm_text) is not None
    return key in norm_text


def _find_skills(text: str) -> set[str]:
    """在文本中命中技能关键词（别名归一化后）。"""
    norm = _normalize(text)
    found: set[str] = set()
    for skill in SKILL_KEYWORDS:
        key = _normalize(skill)
        if _contains(norm, key):
            found.add(SKILL_ALIAS.get(key, skill))
    return found


class RuleScorer:
    """规则打分：JD 需要的技能在简历里出现多少。"""

    def __init__(self, jd_text: str, resume_text: str):
        self.jd_text = jd_text
        self.resume_text = resume_text

    def score(self) -> dict:
        jd_skills = _find_skills(self.jd_text)
        resume_skills = _find_skills(self.resume_text)
        matched = sorted(jd_skills & resume_skills)
        missing = sorted(jd_skills - resume_skills)
        # 分数：命中率加权，60 为基准（结构与经验项在 LLM 版再补）
        if not jd_skills:
            base = 60
        else:
            rate = len(matched) / len(jd_skills)
            base = round(40 + rate * 55)
        suggestions = []
        for s in missing:
            suggestions.append(f"简历里没看到「{s}」——如果会，补一个相关项目或技能项；不会就诚实标注。")
        if not missing:
            suggestions.append("JD 要求的技能简历都覆盖了，可以强调项目成果数字。")
        reasons = [
            {"skill": s, "why": "JD 要求且简历命中", "evidence": f"JD/简历均出现 {s}"}
            for s in matched
        ]
        return {
            "score": min(base, 99),
            "matched_skills": matched,
            "missing_skills": missing,
            "suggestions": suggestions[:5],
            "reasons": reasons,
            "engine": "rule",
        }


class LLMScorer:
    """LLM 打分：流式/JSON 结构化输出。"""

    def __init__(self, api_key: str | None = None,
                 base_url: str | None = None,
                 model: str = DEFAULT_MODEL):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY", "sk-none"),
            base_url=base_url or os.environ.get("OPENAI_BASE_URL"),
        )
        self.model = model

    _SYSTEM = """你是一个严格的简历筛选助手。根据岗位描述(JD)评估简历匹配度。
必须输出 JSON（不要 markdown 代码块），格式：
{
  "score": 0到100的整数,
  "matched_skills": ["命中技能"],
  "missing_skills": ["JD要求但简历缺失的技能"],
  "suggestions": ["2-5条具体可执行的改进建议"],
  "reasons": [{"skill": "技能名", "why": "为什么扣分或加分", "evidence": "JD或简历原文摘录"}]
}
score 打分考虑：技能命中、项目相关度、经验深度、教育背景、可解释性。
"""

    def score(self, resume_text: str, jd_text: str) -> dict:
        user = f"【岗位描述】\n{jd_text}\n\n【简历】\n{resume_text}"
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": self._SYSTEM},
                      {"role": "user", "content": user}],
            temperature=0.2,
            response_format={"type": "json_object"},
            max_tokens=1200,
        )
        text = resp.choices[0].message.content or "{}"
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("LLM 返回非 JSON，回退规则引擎")
            return RuleScorer(jd_text, resume_text).score()
        data["engine"] = "llm"
        return _sanitize(data)


def _sanitize(data: dict) -> dict:
    """保证返回字段齐全，数值合法。"""
    return {
        "score": max(0, min(100, int(data.get("score", 60)))),
        "matched_skills": list(data.get("matched_skills") or [])[:20],
        "missing_skills": list(data.get("missing_skills") or [])[:20],
        "suggestions": list(data.get("suggestions") or [])[:6],
        "reasons": list(data.get("reasons") or [])[:20],
        "engine": data.get("engine", "llm"),
    }


def score_resume(resume_text: str, jd_text: str,
                 use_llm: bool = True) -> dict:
    """统一入口：优先 LLM，失败/未配置则规则兜底。"""
    if use_llm and os.environ.get("OPENAI_API_KEY"):
        try:
            return LLMScorer().score(resume_text, jd_text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 打分失败（%s），回退规则引擎", exc)
    return RuleScorer(jd_text, resume_text).score()


if __name__ == "__main__":
    # 快速自测
    demo_jd = "要求：Python、数据分析、爬虫、Docker、大模型"
    demo_resume = "会用 Python 做数据分析与爬虫，熟悉 pandas，做过可视化项目。"
    result = score_resume(demo_resume, demo_jd, use_llm=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))