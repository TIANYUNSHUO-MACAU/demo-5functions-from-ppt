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
from services.web_search import search_resume_references

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

# 从简历中提取"目标岗位 + 行业"关键词，用于联网检索同类简历范例
ROLE_EXTRACT_PROMPT = """你是简历分析助手。请阅读用户的简历，提取其最匹配的【目标岗位 + 所属行业】关键词。
要求：
- 只输出一行，例如「前端工程师 互联网」或「财务分析师 金融」
- 不要解释、不要标点修饰、不要换行
- 如果难以判断，给出最接近的通用岗位名称"""

# 带"同类简历参考"的改写提示词：在基础改写要求上，加入参考范例与防编造约束
# 沿用与 RESUME_OPTIMIZE_PROMPT 完全一致的 ===== 简历开始/结束 ===== 标记，复用 _extract_resume_section
RESUME_REFERENCE_PROMPT = """你是一位资深HR和职业规划专家。用户会给你一份简历内容，以及若干份"同类岗位的公开简历范例 / 写法参考"。

请你参考这些范例的【结构、章节安排、要点表达方式、量化与关键词用法】，来优化用户的简历。

**重要原则（必须遵守）：**
- 严禁编造用户简历中不存在的经历、公司、项目、数字或技能；参考范例只用于借鉴"怎么写得更好"，不是搬运内容
- 只对用户已有信息做更专业、更突出的表达与重排
- 必须用中文回答

请严格按以下两部分结构输出：

## 一、问题与建议

1. 结合参考范例，指出用户简历在结构/内容/表达/技能描述上的具体差距
2. 给出针对性、可操作的优化建议（可说明"参考了同类简历的哪种写法"）

## 二、优化后的简历

请在"===== 简历开始 ===== 和"===== 简历结束 ===== 之间输出优化后的完整简历。要求：

- 保留原简历的全部真实信息（姓名、联系方式、教育、工作、项目、技能等章节完整保留并优化表达）
- 用 Markdown 标题分层（姓名用 #，章节用 ##），要点用 - 列出并尽量量化
- 使用 **加粗** 突出关键亮点，语言精练专业
- 输出仅限简历内容，"===== 简历结束 ===== 之后不要再添加任何额外说明

示例：
===== 简历开始 =====
# 张三
高级工程师 · 上海 · zhangsan@example.com · 13800138000

## 个人简介
资深软件工程师...
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


def _read_resume_text(req):
    """从请求中读取简历文本（文本或文件上传两种来源）。

    返回 (text, error_response)。其中 error_response 为 None 表示成功；
    否则为 (json, status_code) 的元组，调用方直接 return 即可。
    """
    text = ""
    if req.content_type and "multipart/form-data" in req.content_type:
        if "file" not in req.files:
            return "", (jsonify({"success": False, "error": "请上传简历文件"}), 400)
        file = req.files["file"]
        if not file.filename:
            return "", (jsonify({"success": False, "error": "文件名为空"}), 400)
        try:
            text = extract_text_from_upload(file)
        except Exception as e:
            return "", (jsonify({"success": False, "error": f"解析文件失败：{str(e)}"}), 400)
    else:
        data = req.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()

    if not text or len(text) < 20:
        return "", (jsonify({"success": False, "error": "简历内容过短（至少20字）"}), 400)

    return text, None


@resume_bp.route("/optimize", methods=["POST"])
def optimize_resume():
    text, err = _read_resume_text(request)
    if err is not None:
        return err

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


def _build_reference_block(refs: list) -> str:
    """把检索到的同类简历范例拼成参考文本块（整体截断到约 3000 字）。"""
    parts = []
    for i, r in enumerate(refs, 1):
        snippet = (r.get("content") or "")[:600]
        parts.append(
            f"【参考{i}】{r.get('title', '')}\n来源：{r.get('url', '')}\n{snippet}"
        )
    return "\n\n".join(parts)[:3000]


@resume_bp.route("/optimize_with_reference", methods=["POST"])
def optimize_resume_with_reference():
    """联网参考模式：推断目标岗位 -> 检索同类简历范例 -> 带参考改写。

    无搜索 Key 或检索失败时，自动回退到基础改写（不报错）。
    """
    text, err = _read_resume_text(request)
    if err is not None:
        return err

    # 1. 让模型推断目标岗位 + 行业，作为检索关键词
    try:
        role_query = ai_service.chat(
            system_prompt=ROLE_EXTRACT_PROMPT,
            user_prompt=text[:2000],
            temperature=0,
        )
        role_query = (role_query or "").strip().splitlines()[0][:60] if role_query else ""
    except Exception:
        role_query = ""

    # 2. 联网检索同类简历参考（无 Key/异常时返回 []）
    refs = search_resume_references(role_query) if role_query else []

    if refs:
        # 3a. 带参考改写
        reference_block = _build_reference_block(refs)
        user_prompt = (
            f"目标岗位关键词：{role_query}\n\n"
            f"=== 用户的原始简历 ===\n{text[:6000]}\n\n"
            f"=== 同类岗位公开简历范例 / 写法参考 ===\n{reference_block}"
        )
        result = ai_service.chat(
            system_prompt=RESUME_REFERENCE_PROMPT,
            user_prompt=user_prompt,
            temperature=0.5,
        )
        references = [{"title": r["title"], "url": r["url"]} for r in refs if r.get("url")]
        used_reference = True
    else:
        # 3b. 回退到基础改写
        result = ai_service.chat(
            system_prompt=RESUME_OPTIMIZE_PROMPT,
            user_prompt=f"以下是用户的原始简历内容：\n\n{text[:6000]}",
            temperature=0.5,
        )
        result = "> ⚠️ 未配置联网搜索 Key 或暂无检索结果，已使用基础优化模式。\n\n" + result
        references = []
        used_reference = False

    optimized = _extract_resume_section(result)
    if not optimized or len(optimized) < 100:
        optimized = result

    return jsonify({
        "success": True,
        "result": result,
        "optimized_resume": optimized,
        "input_text": text[:500],
        "references": references,
        "used_reference": used_reference,
        "role_query": role_query,
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
