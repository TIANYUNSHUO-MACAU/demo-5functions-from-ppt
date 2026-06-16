# 简历优化路由
# 支持文本输入或上传文件（PDF/Word）提取文本后优化
# 核心特性：
#   - result: 完整 Markdown 输出（含 AI 建议与优化后的简历），用于页面展示
#   - optimized_resume: 仅包含简历内容，用于导出 Word/PDF
#   - input_text: 原始输入文本（截断）

import os
import re
from flask import Blueprint, request, jsonify
from services.ai_service import ai_service
from services.doc_parser import extract_text_from_upload

resume_bp = Blueprint("resume", __name__)

# 让 AI 明确输出两部分：问题与建议 + 优化后的简历
# 优化后的简历必须用清晰的标记包住，便于后处理时精准提取
RESUME_OPTIMIZE_PROMPT = """你是一位资深HR和职业规划专家。用户会给你一份简历内容。

请严格按以下两部分结构输出（必须用中文回答）：

## 一、问题与建议

1. 识别简历存在的具体问题（结构、内容、表达、技能描述等）
2. 给出针对性的优化建议，每条要具体、可操作

## 二、优化后的简历

请在"===== 简历开始 ===== 和"===== 简历结束 ===== 之间输出优化后的完整简历。要求：

- 保留原简历的信息结构和布局（原有的姓名、联系方式、教育经历、工作经历、项目经历、技能等章节均需完整保留并优化表达）
- 用Markdown 标题分层（姓名用 #，章节用 ##）
- 工作/项目要点用 - 列出，量化成果
- 使用 **加粗** 突出关键亮点
- 语言精练、专业，符合互联网/科技行业 HR 阅读习惯
- 如果原简历内容是纯文本，请将其重新整理为标准简历结构
- 输出仅限简历内容，不要在"===== 简历结束 =====之后不要再添加任何额外说明

示例：
===== 简历开始 =====
# 张三
高级工程师 · 上海 · zhangsan@example.com · 13800138000

## 个人简介
资深软件工程师，具备扎实的工程经验...

## 工作经历
### 某某科技有限公司  高级工程师  2021.06 – 至今
- 负责XX项目，将XX指标提升XX%
- ...

## 项目经历
- ...
===== 简历结束 =====
"""

RESUME_ANALYZE_PROMPT = """你是一位资深HR。请对用户的简历进行专业分析：
1. 评估简历的整体质量（满分100分）
2. 列出3-5个最突出的优点
3. 列出3-5个最需要改进的地方
4. 给出适合的岗位建议
5. 用Markdown格式输出

请用中文回答。"""


def _extract_resume_section(text: str) -> str:
    """从AI的完整输出中提取"优化后的简历"部分。

    优先匹配 ===== 简历开始 ===== / ===== 简历结束 ===== 标记。
    如果找不到标记，退回到"## 优化后的简历"或"二、优化后的简历"之后的内容。
    如果都没有，返回去除明显的"建议/分析"章节后的内容。
    """
    if not text:
        return ""

    cleaned = text.strip()

    # 方式1: 精确匹配标记行
    start_markers = [
        r"={3,}\s*简历开始\s*={3,}",
        r"={3,}\s*RESUME START\s*={3,}",
        r"={3,}\s*RESUME\s*={3,}",
        r"===== 简历开始 =====",
    ]
    end_markers = [
        r"={3,}\s*简历结束\s*={3,}",
        r"={3,}\s*RESUME END\s*={3,}",
        r"===== 简历结束 =====",
    ]

    start_idx = -1
    for pat in start_markers:
        m = re.search(pat, cleaned, re.IGNORECASE)
        if m:
            start_idx = m.end()
            break

    if start_idx >= 0:
        remainder = cleaned[start_idx:]
        # 找结束标记
        end_idx = len(remainder)
        for pat in end_markers:
            m2 = re.search(pat, remainder, re.IGNORECASE)
            if m2:
                end_idx = m2.start()
                break
        extracted = remainder[:end_idx].strip()
        if extracted:
            return extracted

    # 方式2: 找"优化后的简历"标题之后的内容
    # 匹配：## 优化后的简历 / ## 优化后简历 / 二、优化后的简历
    pattern = re.compile(
        r"(?:^|\n)\s*#{1,4}\s*(?:优化后的简历|优化后简历|优化简历|简历|RESUME)[^\n]*\n",
        re.IGNORECASE | re.MULTILINE
    )
    m = pattern.search(cleaned)
    if m:
        after = cleaned[m.end():].strip()
        # 去掉直到下一个"## "标题（如果存在"建议/分析/总结"等章节）
        next_h2 = re.search(r"\n\s*#{1,2}\s*(?:问题|建议|分析|总结|总结与|结论|改进|推荐|岗位|总结与建议)", after, re.IGNORECASE)
        if next_h2:
            after = after[:next_h2.start()].strip()
        return after

    # 方式3: 去除明显的建议章节 + 找真正的简历内容（从"# 姓名" 或 "## 工作经历" 这种章节开始）
    resume_start = re.search(r"(?:^|\n)\s*#\s+[\u4e00-\u9fa5A-Za-z]", cleaned)
    if resume_start:
        candidate = cleaned[resume_start.start():].strip()
        # 再次去掉结尾的建议/分析内容
        if len(candidate) > 100:
            return candidate

    # 方式4: 实在没有任何标记，尝试去掉开头的建议/问题章节
    lines = cleaned.split("\n")
    keep = []
    in_suggestion = False
    for line in lines:
        low = line.strip().lower()
        if any(k in low for k in ["问题", "建议", "## 问题", "## 建议", "一、", "1."]):
            in_suggestion = True
            continue
        if in_suggestion and re.match(r"^\s*#{1,4}\s", line):
            # 新章节开始，停止建议部分
            in_suggestion = False
        if not in_suggestion:
            keep.append(line)
    fallback = "\n".join(keep).strip()
    return fallback if len(fallback) > 100 else cleaned


@resume_bp.route("/optimize", methods=["POST"])
def optimize_resume():
    text = ""

    if request.content_type and "multipart/form-data" in request.content_type:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "请上传简历文件"}), 400
        file = request.files["file"]
        if not file.filename:
            return jsonify({"success": False, "error": "文件名为空"}), 400
        try:
            text = extract_text_from_upload(file)
        except Exception as e:
            return jsonify({"success": False, "error": f"解析文件失败：{str(e)}"}), 400
    else:
        data = request.get_json() or {}
        text = (data.get("text") or "").strip()

    if not text or len(text) < 20:
        return jsonify({"success": False, "error": "简历内容过短（至少20字）"}), 400

    result = ai_service.chat(
        system_prompt=RESUME_OPTIMIZE_PROMPT,
        user_prompt=f"以下是用户的原始简历内容：\n\n{text[:6000]}",
        temperature=0.5,
    )

    optimized = _extract_resume_section(result)
    # 如果提取失败或太短，使用原文（去除开头到第一个建议/问题章节之前的部分，或全文）
    if not optimized or len(optimized) < 100:
        optimized = result

    return jsonify({
        "success": True,
        "result": result,
        "optimized_resume": optimized,
        "input_text": text[:500],
    })


@resume_bp.route("/analyze", methods=["POST"])
def analyze_resume():
    text = ""

    if request.content_type and "multipart/form-data" in request.content_type:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "请上传简历文件"}), 400
        file = request.files["file"]
        try:
            text = extract_text_from_upload(file)
        except Exception as e:
            return jsonify({"success": False, "error": f"解析文件失败：{str(e)}"}), 400
    else:
        data = request.get_json() or {}
        text = (data.get("text") or "").strip()

    if not text or len(text) < 20:
        return jsonify({"success": False, "error": "简历内容过短（至少20字）"}), 400

    result = ai_service.chat(
        system_prompt=RESUME_ANALYZE_PROMPT,
        user_prompt=f"请分析以下简历：\n\n{text[:6000]}",
        temperature=0.3,
    )

    return jsonify({
        "success": True,
        "result": result,
        "input_text": text[:500],
    })
