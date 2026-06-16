# 文案生成路由
# 接收场景描述，生成多种风格的文案

from flask import Blueprint, request, jsonify
from services.ai_service import ai_service

copywriting_bp = Blueprint('copywriting', __name__)

# 系统提示词
SYSTEM_PROMPT = """你是一位资深文案策划师。用户会给你一个场景或产品描述，你需要：
1. 生成至少3种不同风格的文案方案
2. 每种方案标注适用场景（如社交媒体、官网、广告等）
3. 文案要有创意、有吸引力、有记忆点
4. 用Markdown格式输出，结构清晰
5. 每种方案控制在50-200字之间

请用中文回答。"""


@copywriting_bp.route('/generate', methods=['POST'])
def generate_copy():
    """
    文案生成接口
    请求体：{ "scene": "场景描述", "style": "风格(可选)", "count": 数量(可选,默认3) }
    返回：{ "success": true, "result": "生成的文案(Markdown)" }
    """
    data = request.get_json()

    if not data or 'scene' not in data:
        return jsonify({
            "success": False,
            "error": "请提供场景描述，字段名：scene"
        }), 400

    scene = data['scene'].strip()
    style = data.get('style', '')
    count = data.get('count', 3)

    if len(scene) < 5:
        return jsonify({
            "success": False,
            "error": "场景描述过短，请提供更详细的信息"
        }), 400

    # 构建用户提示词
    user_prompt = f"请为以下场景生成{count}种风格的文案：\n\n场景：{scene}"
    if style:
        user_prompt += f"\n偏好风格：{style}"

    # 调用AI服务
    result = ai_service.chat(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.8  # 较高温度，增加创意性
    )

    return jsonify({
        "success": True,
        "result": result
    })


@copywriting_bp.route('/rewrite', methods=['POST'])
def rewrite_copy():
    """
    文案改写接口
    请求体：{ "text": "原始文案", "style": "目标风格" }
    返回：{ "success": true, "result": "改写后的文案" }
    """
    data = request.get_json()

    if not data or 'text' not in data:
        return jsonify({"success": False, "error": "请提供原始文案"}), 400

    original = data['text'].strip()
    style = data.get('style', '更简洁有力')

    rewrite_prompt = f"""你是一位资深文案策划师。请将以下文案改写为「{style}」的风格：

原始文案：
{original}

要求：
1. 保持核心信息不变
2. 按照目标风格调整语气和表达
3. 提供改写后的完整文案
4. 简要说明改写思路"""

    result = ai_service.chat(
        system_prompt="你是资深文案策划师，擅长多种风格的文案创作。",
        user_prompt=rewrite_prompt,
        temperature=0.7
    )

    return jsonify({
        "success": True,
        "result": result
    })
