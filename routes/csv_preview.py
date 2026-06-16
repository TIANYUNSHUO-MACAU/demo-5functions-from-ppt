# CSV预览路由
# 上传CSV文件，解析数据并生成分析报告

import os
import uuid
import io
from flask import Blueprint, request, jsonify, current_app
from services.ai_service import ai_service

csv_preview_bp = Blueprint('csv_preview', __name__)

# CSV分析系统提示词
CSV_ANALYSIS_PROMPT = """你是一位数据分析专家。用户会给你一个CSV文件的结构信息和前几行数据，你需要：
1. 概述数据集的整体特征
2. 分析各列的数据类型和含义
3. 指出数据质量问题（缺失值、异常值、重复数据等）
4. 给出基本统计摘要
5. 提供数据分析建议
6. 用Markdown格式输出，包含表格

请用中文回答。"""


@csv_preview_bp.route('/upload', methods=['POST'])
def upload_and_analyze():
    """
    CSV上传并分析
    请求：multipart/form-data，包含 file 字段
    返回：{ "success": true, "preview": {...}, "analysis": "分析报告" }
    """
    if 'file' not in request.files:
        return jsonify({
            "success": False,
            "error": "请上传CSV文件"
        }), 400

    file = request.files['file']

    if not file.filename:
        return jsonify({"success": False, "error": "文件名为空"}), 400

    if not file.filename.lower().endswith(('.csv', '.tsv', '.txt')):
        return jsonify({"success": False, "error": "仅支持CSV/TSV格式文件"}), 400

    try:
        # 保存文件
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 解析CSV
        preview_data, analysis_input = _parse_csv(filepath)

        if preview_data is None:
            return jsonify({
                "success": False,
                "error": "CSV解析失败，请检查文件格式"
            }), 400

        # 调用AI生成分析报告
        analysis = ai_service.chat(
            system_prompt=CSV_ANALYSIS_PROMPT,
            user_prompt=f"请分析以下CSV数据：\n\n{analysis_input}",
            temperature=0.3
        )

        # 清理上传文件
        try:
            os.remove(filepath)
        except:
            pass

        return jsonify({
            "success": True,
            "preview": preview_data,
            "analysis": analysis,
            "filename": file.filename
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"处理CSV时出错：{str(e)}"
        }), 500


@csv_preview_bp.route('/analyze', methods=['POST'])
def analyze_csv_text():
    """
    直接分析CSV文本数据（无需上传文件）
    请求体：{ "data": "CSV格式文本" }
    返回：{ "success": true, "preview": {...}, "stats": {...}, "analysis": "分析报告" }
    """
    data = request.get_json()

    if not data or 'data' not in data:
        return jsonify({"success": False, "error": "请提供CSV数据"}), 400

    csv_text = data['data'].strip()

    if len(csv_text) < 20:
        return jsonify({"success": False, "error": "数据内容过短"}), 400

    try:
        import pandas as pd
        from io import StringIO
        
        df = pd.read_csv(StringIO(csv_text))
        
        preview = {
            "columns": list(df.columns),
            "row_count": len(df),
            "col_count": len(df.columns),
            "head": df.head(10).to_dict(orient='records'),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "null_counts": {col: int(df[col].isnull().sum()) for col in df.columns},
        }
        
        stats = {
            "rows": len(df),
            "columns": len(df.columns),
            "numeric_columns": len(df.select_dtypes(include=['int64', 'float64']).columns),
            "missing_values": int(df.isnull().sum().sum()),
        }
        
        analysis_input = f"""CSV文件信息：
- 列数：{len(df.columns)}
- 行数：{len(df)}
- 列名：{list(df.columns)}
- 数据类型：{dict(df.dtypes)}
- 缺失值统计：{dict(df.isnull().sum())}

前10行数据：
{df.head(10).to_markdown()}"""

        analysis = ai_service.chat(
            system_prompt=CSV_ANALYSIS_PROMPT,
            user_prompt=f"请分析以下CSV数据：\n\n{analysis_input}",
            temperature=0.3
        )

        return jsonify({
            "success": True,
            "preview": preview,
            "stats": stats,
            "analysis": analysis
        })

    except ImportError:
        return jsonify({
            "success": False,
            "error": "未安装pandas。请运行：pip install pandas tabulate"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"CSV解析失败：{str(e)}"
        }), 400


def _parse_csv(filepath: str):
    """
    解析CSV文件，返回预览数据和分析用文本
    """
    try:
        import pandas as pd

        # 尝试多种分隔符
        for sep in [',', '\t', ';']:
            try:
                df = pd.read_csv(filepath, sep=sep, nrows=100)
                if len(df.columns) > 1:
                    break
            except:
                continue
        else:
            df = pd.read_csv(filepath, nrows=100)

        # 预览数据
        preview = {
            "columns": list(df.columns),
            "row_count": len(df),
            "col_count": len(df.columns),
            "head": df.head(10).to_dict(orient='records'),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "null_counts": {col: int(df[col].isnull().sum()) for col in df.columns},
            "memory_usage": f"{df.memory_usage(deep=True).sum() / 1024:.1f} KB"
        }

        # 构建AI分析输入
        analysis_input = f"""CSV文件信息：
- 列数：{len(df.columns)}
- 行数（预览）：{len(df)}
- 列名：{list(df.columns)}
- 数据类型：{dict(df.dtypes)}
- 缺失值统计：{dict(df.isnull().sum())}

前10行数据：
{df.head(10).to_markdown()}"""

        return preview, analysis_input

    except ImportError:
        return None, "[错误] 未安装pandas。请运行：pip install pandas tabulate"
    except Exception as e:
        return None, f"[错误] CSV解析失败：{str(e)}"
