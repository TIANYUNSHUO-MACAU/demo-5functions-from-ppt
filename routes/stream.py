# 流式端点（SSE）—— 各工具的流式版本
# 前端逐字显示，界面/布局完全不变，只改 JS 调 _stream 端点
import io
from flask import Blueprint, request, jsonify

from services.ai_service import ai_service
from services.sse_helper import sse_response
from services.doc_parser import extract_text_from_upload

stream_bp = Blueprint('stream', __name__)

# ============== 提示词（与原路由一致） ==============

RESUME_PROMPT = """你是一位资深HR和职业规划专家。用户会给你一份简历内容。
请从以下方面给出修改建议：
1. 整体印象（10字以内）
2. 优点（2-3条）
3. 不足与改进建议（3-5条，每条具体可操作）
4. 优化后的完整简历（Markdown格式）
请用中文回答，使用Markdown格式。"""

COPY_PROMPT = """你是一位资深文案策划师。用户会给你一个场景或产品描述，你需要：
1. 生成3种不同风格的文案方案
2. 每种方案包含标题和正文
3. 风格鲜明，语言生动
4. 用Markdown格式输出，结构清晰
请用中文回答。"""

TRANSLATE_PROMPT = """你是一位专业翻译。请将用户提供的文本翻译成{target_lang}。
要求：
- 保持原文的语气和风格
- 专业术语准确
- 翻译自然流畅，符合目标语言习惯
直接输出翻译结果，不要添加解释。"""

PDF_PROMPT = """你是一位专业的文档分析师。用户会给你一段从PDF中提取的文本，你需要：
1. 概述文档的整体主题和类型
2. 提取3-5个关键要点
3. 总结重要结论或建议
4. 用Markdown格式输出，结构清晰
5. 如果文本不完整，说明哪些部分可能缺失
请用中文回答，摘要控制在500字以内。"""

CSV_PROMPT = """你是一位数据分析专家。用户会给你一个CSV文件的结构信息和前几行数据，你需要：
1. 概述数据集的整体特征
2. 分析各列的数据类型和含义
3. 指出数据质量问题（缺失值、异常值、重复数据等）
4. 给出基本统计摘要
5. 提供数据分析建议
6. 用Markdown格式输出，包含表格
请用中文回答。"""


# ============== 简历优化（流式） ==============

@stream_bp.route('/api/resume/optimize_stream', methods=['POST'])
def resume_optimize_stream():
    text = ""
    if request.content_type and "multipart/form-data" in request.content_type:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "请上传简历文件"}), 400
        try:
            text = extract_text_from_upload(request.files["file"])
        except Exception as e:
            return jsonify({"success": False, "error": f"解析文件失败：{str(e)}"}), 400
    else:
        data = request.get_json() or {}
        text = (data.get("text") or "").strip()

    if not text or len(text) < 20:
        return jsonify({"success": False, "error": "简历内容过短（至少20字）"}), 400

    return sse_response(lambda: ai_service.chat_stream(
        RESUME_PROMPT, f"以下是用户的原始简历内容：\n\n{text[:6000]}", 0.5,
    ))


# ============== 文案生成（流式） ==============

@stream_bp.route('/api/copywriting/generate_stream', methods=['POST'])
def copywriting_stream():
    data = request.get_json()
    if not data or 'scene' not in data:
        return jsonify({"success": False, "error": "请提供场景描述"}), 400
    scene = data['scene'].strip()
    style = data.get('style', '')
    count = data.get('count', 3)
    try:
        count = max(1, min(int(count), 10))
    except (TypeError, ValueError):
        count = 3
    if len(scene) < 5:
        return jsonify({"success": False, "error": "场景描述过短"}), 400

    user_prompt = f"请为以下场景生成{count}种风格的文案：\n\n场景：{scene}"
    if style:
        user_prompt += f"\n偏好风格：{style}"

    return sse_response(lambda: ai_service.chat_stream(COPY_PROMPT, user_prompt, 0.8))


# ============== 翻译（流式） ==============

@stream_bp.route('/api/translate/translate_stream', methods=['POST'])
def translate_stream():
    text = ""
    target_lang = "English"
    if request.content_type and "multipart/form-data" in request.content_type:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "请上传文件"}), 400
        target_lang = request.form.get("target_lang", "English")
        try:
            text = extract_text_from_upload(request.files["file"])
        except Exception as e:
            return jsonify({"success": False, "error": f"解析文件失败：{str(e)}"}), 400
    else:
        data = request.get_json() or {}
        text = (data.get("text") or "").strip()
        target_lang = (data.get("target_lang") or "English").strip()

    if not text or len(text) < 5:
        return jsonify({"success": False, "error": "文本内容过短"}), 400

    return sse_response(lambda: ai_service.chat_stream(
        TRANSLATE_PROMPT.format(target_lang=target_lang), text[:6000], 0.3,
    ))


# ============== PDF 摘要（流式 + BytesIO） ==============

@stream_bp.route('/api/pdf/upload_stream', methods=['POST'])
def pdf_stream():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "请上传PDF文件"}), 400
    file = request.files['file']
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        return jsonify({"success": False, "error": "仅支持PDF格式"}), 400

    try:
        file_stream = io.BytesIO(file.read())
        extracted_text = _extract_pdf_from_stream(file_stream)
    except Exception as e:
        return jsonify({"success": False, "error": f"PDF解析失败：{str(e)}"}), 400

    if not extracted_text.strip():
        return jsonify({"success": False, "error": "未能提取文本"}), 400

    # 长文档走 map-reduce 分段摘要；短文档直接流式
    return sse_response(
        lambda: ai_service.chat_long_stream(PDF_PROMPT, extracted_text, 0.3),
        pre_events=[{"text_length": len(extracted_text), "filename": file.filename}],
    )


def _extract_pdf_from_stream(file_stream):
    """BytesIO 内存提取（不写盘）。"""
    import pdfplumber
    with pdfplumber.open(file_stream) as pdf:
        parts = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
        return "\n".join(parts)


# ============== CSV 分析（流式 + BytesIO） ==============

@stream_bp.route('/api/csv/upload_stream', methods=['POST'])
def csv_stream():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "请上传CSV文件"}), 400
    file = request.files['file']
    if not file.filename or not file.filename.lower().endswith(('.csv', '.tsv', '.txt')):
        return jsonify({"success": False, "error": "仅支持CSV/TSV"}), 400

    try:
        file_stream = io.BytesIO(file.read())
        preview, analysis_input = _parse_csv_from_stream(file_stream)
    except Exception as e:
        return jsonify({"success": False, "error": f"CSV解析失败：{str(e)}"}), 400

    if preview is None:
        return jsonify({"success": False, "error": "CSV解析失败"}), 400

    return sse_response(
        lambda: ai_service.chat_stream(
            CSV_PROMPT, f"请分析以下CSV数据：\n\n{analysis_input}", 0.3,
        ),
        pre_events=[{"preview": preview, "filename": file.filename}],
    )


def _parse_csv_from_stream(file_stream):
    """BytesIO 内存解析（不写盘）。"""
    import pandas as pd
    for sep in [',', '\t', ';']:
        try:
            df = pd.read_csv(file_stream, sep=sep, nrows=100)
            if len(df.columns) > 1:
                break
            file_stream.seek(0)
        except Exception:
            file_stream.seek(0)
            continue
    else:
        file_stream.seek(0)
        df = pd.read_csv(file_stream, nrows=100)

    preview = {
        "columns": list(df.columns),
        "row_count": len(df),
        "col_count": len(df.columns),
        "head": df.head(10).to_dict(orient='records'),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "null_counts": {col: int(df[col].isnull().sum()) for col in df.columns},
    }
    analysis_input = f"""CSV文件信息：
- 列数：{len(df.columns)}
- 行数（预览）：{len(df)}
- 列名：{list(df.columns)}
- 数据类型：{dict(df.dtypes)}
- 缺失值统计：{dict(df.isnull().sum())}

前10行数据：
{df.head(10).to_markdown()}"""
    return preview, analysis_input
