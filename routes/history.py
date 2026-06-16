# 历史记录 + 导出路由
# 1) 工具在生成结果后保存到历史（前端 / 前置中间件调用）
# 2) 用户可拉取 / 删除历史
# 3) 用户可请求导出 Markdown -> docx/pdf

import os
import re
from flask import Blueprint, request, jsonify, send_file, current_app
from services.history_store import (
    add_record, list_records, get_record, delete_record, clear_records
)
from services.exporter import export_to_docx, export_to_pdf

history_bp = Blueprint("history", __name__)


# ============== 工具调用 ==============

@history_bp.route("/save", methods=["POST"])
def save_history():
    """
    保存一条历史记录
    请求体：{ "tool": "resume", "title": "...", "input_text": "...", "output_text": "...", "meta": {...} }
    """
    data = request.get_json() or {}
    tool = (data.get("tool") or "").strip()
    if not tool:
        return jsonify({"success": False, "error": "缺少 tool 字段"}), 400
    rid = add_record(
        tool=tool,
        title=data.get("title", ""),
        input_text=data.get("input_text", ""),
        output_text=data.get("output_text", ""),
        meta=data.get("meta", {}),
    )
    return jsonify({"success": True, "id": rid})


@history_bp.route("/list", methods=["GET"])
def list_history():
    """列出历史（按工具筛选）"""
    tool = request.args.get("tool", "").strip() or None
    limit = int(request.args.get("limit", 50))
    rows = list_records(tool=tool, limit=limit)
    return jsonify({"success": True, "records": rows, "count": len(rows)})


@history_bp.route("/<record_id>", methods=["GET"])
def get_one_history(record_id):
    """获取单条历史"""
    rec = get_record(record_id)
    if not rec:
        return jsonify({"success": False, "error": "记录不存在"}), 404
    return jsonify({"success": True, "record": rec})


@history_bp.route("/<record_id>", methods=["DELETE"])
def delete_one_history(record_id):
    """删除单条历史"""
    ok = delete_record(record_id)
    if not ok:
        return jsonify({"success": False, "error": "记录不存在"}), 404
    return jsonify({"success": True})


@history_bp.route("/clear", methods=["POST"])
def clear_all_history():
    """清空历史"""
    tool = (request.args.get("tool") or (request.get_json() or {}).get("tool") or "").strip() or None
    n = clear_records(tool=tool)
    return jsonify({"success": True, "deleted": n})


# ============== 导出 ==============

@history_bp.route("/export", methods=["POST"])
def export_doc():
    """
    导出 Markdown -> docx/pdf
    请求体：{
      "format": "docx" | "pdf",
      "title": "文档标题",
      "content": "Markdown 文本",
      "style": "report" | "clean",   // report 为默认（带标题日期），clean 为仅内容（适合简历/翻译）
      "record_id": "可选，从历史记录中取"
    }
    """
    data = request.get_json() or {}
    fmt = (data.get("format") or "").lower()
    if fmt not in ("docx", "pdf"):
        return jsonify({"success": False, "error": "format 必须为 docx 或 pdf"}), 400

    title = (data.get("title") or "").strip()
    content = data.get("content", "")
    style = (data.get("style") or "report").lower()
    if style not in ("report", "clean"):
        style = "report"

    # 允许从历史记录导出
    rid = data.get("record_id")
    if rid and not content:
        rec = get_record(rid)
        if not rec:
            return jsonify({"success": False, "error": "记录不存在"}), 404
        title = title or rec.get("title") or rec.get("tool")
        content = rec.get("output_text") or ""

    if not content:
        return jsonify({"success": False, "error": "导出内容为空"}), 400

    try:
        if fmt == "docx":
            path = export_to_docx(title=title, markdown_text=content, style=style)
        else:
            path = export_to_pdf(title=title, markdown_text=content, style=style)
    except Exception as e:
        return jsonify({"success": False, "error": f"导出失败：{str(e)}"}), 500

    # 返回相对路径，前端可访问 /static/exports/xxx
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rel = os.path.relpath(path, project_root)
    download_url = "/" + rel.replace(os.sep, "/")
    filename = os.path.basename(path)

    return jsonify({
        "success": True,
        "format": fmt,
        "filename": filename,
        "download_url": download_url,
        "size": os.path.getsize(path),
        "style": style,
    })


@history_bp.route("/download/<path:filename>", methods=["GET"])
def download_file(filename):
    """下载已生成的文件"""
    safe = os.path.basename(filename)
    filepath = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "static", "exports", safe
    )
    if not os.path.isfile(filepath):
        return jsonify({"success": False, "error": "文件不存在"}), 404
    return send_file(filepath, as_attachment=True, download_name=safe)
