# PDF摘要路由
# 上传PDF文件，提取文本并生成摘要

import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from services.ai_service import ai_service

pdf_summary_bp = Blueprint('pdf_summary', __name__)

# PDF摘要系统提示词
PDF_SUMMARY_PROMPT = """你是一位专业的文档分析师。用户会给你一段从PDF中提取的文本，你需要：
1. 概述文档的整体主题和类型
2. 提取3-5个关键要点
3. 总结重要结论或建议
4. 用Markdown格式输出，结构清晰
5. 如果文本不完整，说明哪些部分可能缺失

请用中文回答，摘要控制在500字以内。"""


@pdf_summary_bp.route('/upload', methods=['POST'])
def upload_and_summarize():
    """
    PDF上传并生成摘要
    请求：multipart/form-data，包含 file 字段
    返回：{ "success": true, "result": "摘要(Markdown)", "pages": 页数 }
    """
    if 'file' not in request.files:
        return jsonify({
            "success": False,
            "error": "请上传PDF文件"
        }), 400

    file = request.files['file']

    if not file.filename:
        return jsonify({"success": False, "error": "文件名为空"}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"success": False, "error": "仅支持PDF格式文件"}), 400

    try:
        # 保存文件
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 提取PDF文本
        extracted_text = _extract_pdf_text(filepath)

        if not extracted_text.strip():
            return jsonify({
                "success": False,
                "error": "未能从PDF中提取到文本内容，可能是扫描件或加密文件"
            }), 400

        # 调用AI生成摘要
        result = ai_service.chat(
            system_prompt=PDF_SUMMARY_PROMPT,
            user_prompt=f"请对以下PDF文档内容生成摘要：\n\n{extracted_text[:8000]}",
            temperature=0.3
        )

        # 清理上传文件
        try:
            os.remove(filepath)
        except:
            pass

        return jsonify({
            "success": True,
            "result": result,
            "text_length": len(extracted_text),
            "filename": file.filename
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"处理PDF时出错：{str(e)}"
        }), 500


@pdf_summary_bp.route('/summarize', methods=['POST'])
def summarize_text():
    """
    直接对文本生成摘要（无需上传文件）
    请求体：{ "text": "文档文本" }
    返回：{ "success": true, "result": "摘要" }
    """
    data = request.get_json()

    if not data or 'text' not in data:
        return jsonify({"success": False, "error": "请提供文档文本"}), 400

    text = data['text'].strip()

    if len(text) < 20:
        return jsonify({"success": False, "error": "文本内容过短"}), 400

    result = ai_service.chat(
        system_prompt=PDF_SUMMARY_PROMPT,
        user_prompt=f"请对以下文档内容生成摘要：\n\n{text[:8000]}",
        temperature=0.3
    )

    return jsonify({
        "success": True,
        "result": result
    })


def _extract_pdf_text(filepath: str) -> str:
    """
    从PDF文件中提取文本
    优先使用 pdfplumber，备选 PyPDF2
    """
    text = ""

    # 方案1：pdfplumber（推荐，提取效果更好）
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except ImportError:
        pass
    except Exception:
        pass

    # 方案2：PyPDF2（备选）
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except ImportError:
        return "[错误] 未安装PDF解析库。请运行：pip install pdfplumber"
    except Exception as e:
        return f"[错误] PDF解析失败：{str(e)}"
