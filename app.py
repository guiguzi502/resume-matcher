# -*- coding: utf-8 -*-
"""简历 vs JD 匹配分析器 · Streamlit 界面。

运行: streamlit run app.py
"""
import os
from pathlib import Path

import streamlit as st

from matcher.extract import SUPPORTED, UnsupportedFormatError, extract_text
from matcher.scorer import score_resume

st.set_page_config(page_title="简历 vs JD 匹配分析器", page_icon="🎯",
                   layout="centered")

st.title("🎯 简历 vs JD 匹配分析器")
st.caption("上传简历（PDF / DOCX / TXT / MD），粘贴岗位描述，"
           "得到可解释的匹配报告。")

with st.expander("⚙️ 模式设置", expanded=False):
    use_llm = st.checkbox(
        "使用 LLM 打分（更准）", value=bool(os.environ.get("OPENAI_API_KEY")),
        help="未配置 OPENAI_API_KEY 时自动用规则引擎")
    if use_llm:
        with st.form("llm_config"):
            api_key = st.text_input("API Key", type="password",
                                    value=os.environ.get("OPENAI_API_KEY", ""))
            base_url = st.text_input("Base URL（OpenAI 兼容，可留空）",
                                     value=os.environ.get("OPENAI_BASE_URL", ""))
            model = st.text_input("模型", value="gpt-4o-mini")
            submitted = st.form_submit_button("保存配置")
            if submitted:
                if api_key:
                    os.environ["OPENAI_API_KEY"] = api_key
                if base_url:
                    os.environ["OPENAI_BASE_URL"] = base_url
                os.environ["OPENAI_MODEL"] = model
                st.success("配置已保存（本次会话生效）")

left, right = st.columns(2)

with left:
    st.subheader("📄 简历")
    upload = st.file_uploader("上传简历文件", type=["pdf", "docx", "txt", "md"])
    resume_text = ""
    if upload is not None:
        suffix = Path(upload.name).suffix.lower()
        if suffix not in SUPPORTED:
            st.error(f"不支持 {suffix}，请用 PDF/DOCX/TXT/MD")
        else:
            tmp = Path("samples") / f"_upload{suffix}"
            tmp.parent.mkdir(exist_ok=True)
            tmp.write_bytes(upload.getvalue())
            try:
                resume_text = extract_text(tmp)
                st.success(f"已提取 {len(resume_text)} 字符")
            except UnsupportedFormatError as exc:
                st.error(str(exc))
    else:
        st.info("也可以直接粘贴文本 ↓")
    paste_resume = st.text_area("或粘贴简历文本", height=200,
                                value=resume_text if not resume_text else "")
    resume_final = resume_text or paste_resume

with right:
    st.subheader("📋 岗位描述 (JD)")
    jd_text = st.text_area("粘贴 JD 内容", height=320,
                           placeholder="例如：\n要求熟练掌握 Python、数据分析、爬虫...")
    sample_btn = st.button("填入示例 JD")

if sample_btn:
    st.session_state["jd"] = ("岗位：数据分析实习生\n"
                              "要求：Python / pandas / 数据可视化 / SQL / 爬虫，"
                              "有 GitHub 项目优先，英语 CET-6。")

if "jd" in st.session_state:
    jd_text = st.session_state["jd"]
    st.rerun()

st.divider()

if st.button("🚀 开始匹配", type="primary", use_container_width=True):
    if not resume_final.strip():
        st.warning("请先上传或粘贴简历")
    elif not jd_text.strip():
        st.warning("请粘贴岗位描述")
    else:
        with st.spinner("分析中…"):
            result = score_resume(resume_final, jd_text, use_llm=use_llm)

        score = result["score"]
        st.markdown("## 📊 匹配结果")
        col1, col2, col3 = st.columns(3)
        col1.metric("匹配分数", f"{score}/100")
        col2.metric("命中技能", f"{len(result['matched_skills'])} 项")
        col3.metric("缺失技能", f"{len(result['missing_skills'])} 项")

        bar_color = "#2E7D32" if score >= 70 else "#F57C00" if score >= 45 else "#C62828"
        st.progress(score / 100, text=f"匹配度 {score}%")

        st.subheader("✅ 命中技能")
        if result["matched_skills"]:
            st.write("、".join(f"`{s}`" for s in result["matched_skills"]))
        else:
            st.caption("无")

        st.subheader("❌ 缺失技能")
        if result["missing_skills"]:
            st.write("、".join(f"`{s}`" for s in result["missing_skills"]))
        else:
            st.caption("无——JD 要求的你都覆盖了！")

        st.subheader("💡 改进建议")
        for s in result["suggestions"]:
            st.markdown(f"- {s}")

        st.subheader("🔍 扣分/加分理由")
        for r in result["reasons"]:
            st.markdown(f"- **{r['skill']}**：{r['why']}")
            st.caption(f"证据：{r['evidence']}")

        st.caption(f"引擎：{'LLM' if result['engine'] == 'llm' else '规则(离线)'}"
                   " · 分数是参考，不是最终结论")