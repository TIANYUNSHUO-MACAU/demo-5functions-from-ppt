# 翻译路由
# 支持文本输入或上传文件（PDF/Word/TXT）提取文本后翻译

import os
from flask import Blueprint, request, jsonify
from services.ai_service import ai_service
from services.doc_parser import extract_text_from_upload

translate_bp = Blueprint("translate", __name__)

TRANSLATE_PROMPT = """你是一位专业翻译。请将用户提供的文本翻译成{target_lang}。
要求：
1. 准确传达原意，语言自然流畅
2. 保留专业术语的准确性
3. 严格保留原文的结构、段落划分、列表、标题层级和排版
4. 直接输出翻译结果，不要加任何解释、说明、问候或前缀
5. 如果原文包含 Markdown 格式（# 标题、** 加粗、- 列表等），必须完整保留
6. 不要输出 "以下是翻译内容"、"翻译如下" 等包裹性文字

直接输出翻译结果即可。"""


@translate_bp.route("/translate", methods=["POST"])
def translate_text():
    """
    翻译文本或文件
    请求体：{ "text": "...", "target_lang": "English" } 或 multipart/form-data
    返回：{ "success": true, "result": "翻译结果", "source": "原文" }
    """
    text = ""
    target_lang = "English"

    if request.content_type and "multipart/form-data" in request.content_type:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "请上传文件"}), 400
        file = request.files["file"]
        target_lang = request.form.get("target_lang", "English")
        try:
            text = extract_text_from_upload(file)
        except Exception as e:
            return jsonify({"success": False, "error": f"解析文件失败：{str(e)}"}), 400
    else:
        data = request.get_json() or {}
        text = (data.get("text") or "").strip()
        target_lang = (data.get("target_lang") or "English").strip()

    if not text or len(text) < 5:
        return jsonify({"success": False, "error": "文本内容过短（至少5字）"}), 400

    result = ai_service.chat(
        system_prompt=TRANSLATE_PROMPT.format(target_lang=target_lang),
        user_prompt=text[:6000],
        temperature=0.3,
    )

    return jsonify({
        "success": True,
        "result": result,
        "optimized_text": result,
        "source": text[:1000],
        "target_lang": target_lang,
    })


@translate_bp.route("/polish", methods=["POST"])
def polish_text():
    """
    润色文本
    请求体：{ "text": "..." }
    """
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text or len(text) < 5:
        return jsonify({"success": False, "error": "文本内容过短（至少5字）"}), 400

    result = ai_service.chat(
        system_prompt="""你是一位专业文字编辑。请对用户提供的文本进行润色，要求：
1. 保持原意
2. 让语言更流畅自然
3. 修复语法错误
4. 保留 Markdown 格式
5. 用中文回复并直接给出润色后的结果，不要加解释""",
        user_prompt=text[:4000],
        temperature=0.4,
    )

    return jsonify({
        "success": True,
        "result": result,
        "optimized_text": result,
        "source": text[:1000],
    })


@translate_bp.route("/languages", methods=["GET"])
def list_languages():
    """支持的目标语言列表"""
    return jsonify({
        "success": True,
        "languages": [
            {"code": "English", "name": "英语"},
            {"code": "中文", "name": "中文（简体）"},
            {"code": "日本語", "name": "日语"},
            {"code": "한국어", "name": "韩语"},
            {"code": "Français", "name": "法语"},
            {"code": "Deutsch", "name": "德语"},
            {"code": "Español", "name": "西班牙语"},
            {"code": "Русский", "name": "俄语"},
        ]
    })
