# -*- coding: utf-8 -*-
import json
import pathlib

data = {
    "name": "resume-matcher",
    "description": "简历 vs JD 匹配分析器:上传简历+粘贴岗位描述,输出可解释匹配报告(分数/命中缺失技能/改进建议/扣分理由)",
    "homepage": "https://github.com/guiguzi502/resume-matcher",
    "private": False,
    "has_issues": True,
    "has_wiki": False,
}
out = pathlib.Path(r"C:\Users\111\Documents\deepseek-harness\default-workspace\resume-matcher\create_repo.json")
out.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
print("written", len(json.dumps(data, ensure_ascii=True)), "bytes to", out)