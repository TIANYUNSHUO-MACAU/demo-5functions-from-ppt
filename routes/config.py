# 配置管理路由
# 提供 AI 模型与 API Key 的查看/更新/测试接口

from flask import Blueprint, request, jsonify
from services.ai_service import ai_service

config_bp = Blueprint("config", __name__)


@config_bp.route("", methods=["GET"])
def get_config():
    """
    获取当前 AI 配置状态（API Key 脱敏）
    返回示例：
    {
      "success": true,
      "status": {
        "has_key": true,
        "masked_key": "sk-2****7bf5",
        "api_base": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "use_mock": false,
        "active": true,
        "providers": [...]
      }
    }
    """
    return jsonify({"success": True, "status": ai_service.get_status()})


@config_bp.route("", methods=["POST"])
def update_config():
    """
    更新 AI 配置（写入 .env 并实时生效）
    请求体：
    {
      "provider_id": "deepseek",   # 可选
      "api_key": "sk-xxx",         # 必填（若希望启用真实 AI）
      "api_base": "...",            # 可选，未填则按 provider_id 自动补全
      "model": "..."                # 可选，未填则按 provider_id 自动补全
    }
    """
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()
    api_base = (data.get("api_base") or "").strip()
    model = (data.get("model") or "").strip()
    provider_id = (data.get("provider_id") or "").strip()

    # 选择了预设模型，但没填 base/model -> 自动补全
    if provider_id and provider_id != "custom":
        from services.ai_service import MODEL_PROVIDERS

        provider = next((p for p in MODEL_PROVIDERS if p["id"] == provider_id), None)
        if provider:
            if not api_base:
                api_base = provider["base_url"]
            if not model:
                model = provider["model"]

    result = ai_service.update_config(
        api_key=api_key,
        api_base=api_base,
        model=model,
    )
    return jsonify(result)


@config_bp.route("/test", methods=["POST"])
def test_config():
    """
    测试当前 AI 配置是否可用
    返回：
    { "success": true, "message": "连接成功", "model": "...", "reply": "..." }
    或
    { "success": false, "error": "..." }
    """
    return jsonify(ai_service.test_connection())


@config_bp.route("/reset", methods=["POST"])
def reset_config():
    """
    清除已保存的 API Key，恢复模拟模式
    """
    result = ai_service.update_config(
        api_key="",
        api_base="",
        model="",
        use_mock=True,
    )
    return jsonify(result)
