# AI 服务层 - 统一管理 AI 调用
# 支持多模型切换：OpenAI / DeepSeek / 智谱AI / 模拟返回
# 支持运行时由前端更新配置（写入 .env）

import os
import re
from openai import OpenAI
from openai import OpenAIError
from services.mock_data import MOCK_RESPONSES


# 预置模型供应商（前端可选用）
MODEL_PROVIDERS = [
    {
        "id": "openai",
        "name": "OpenAI (官方)",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-3.5-turbo",
        "key_prefix": "sk-",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "key_prefix": "sk-",
    },
    {
        "id": "zhipu",
        "name": "智谱AI (GLM)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "model": "glm-4-flash",
        "key_prefix": "",
    },
    {
        "id": "moonshot",
        "name": "Moonshot (Kimi)",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "key_prefix": "sk-",
    },
    {
        "id": "custom",
        "name": "自定义（OpenAI 兼容）",
        "base_url": "",
        "model": "",
        "key_prefix": "",
    },
]


def _parse_env_file(path: str) -> dict:
    """简单解析 .env 文件（key=value，不处理复杂引号场景）"""
    env = {}
    if not os.path.isfile(path):
        return env
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    except Exception:
        pass
    return env


def _write_env_file(path: str, updates: dict, keep_comments: bool = True) -> None:
    """
    写入 .env 文件，保留注释行与原有的其他键值。
    updates: 需要更新的 key-value 字典。
    """
    lines = []
    existing_keys = set()

    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_lines = f.readlines()
        except Exception:
            raw_lines = []

        for raw in raw_lines:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                lines.append(raw)
                continue
            key, sep, value = raw.partition("=")
            if not sep:
                lines.append(raw)
                continue
            k = key.strip()
            if k in updates:
                lines.append(f"{k}={updates[k]}\n")
                existing_keys.add(k)
            else:
                lines.append(raw)

    # 追加新增的 key
    for k, v in updates.items():
        if k not in existing_keys:
            lines.append(f"{k}={v}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _mask_key(key: str) -> str:
    """对 API Key 做脱敏处理，仅显示前 4 后 4 位"""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * max(4, len(key) - 8)}{key[-4:]}"


class AIService:
    """统一的 AI 调用服务（支持运行时更新配置）"""

    def __init__(self):
        # 定位 .env 路径（项目根目录）
        self.env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
        )

        # 内存中的当前配置（会与 .env 同步）
        self.api_key = ""
        self.api_base = "https://api.openai.com/v1"
        self.model = "gpt-3.5-turbo"
        self.use_mock = True
        self.client = None

        # 初始化时从 .env 同步一次
        self.reload_from_env()

    # ---------- 配置加载与更新 ----------
    def reload_from_env(self) -> None:
        """从 .env 文件重新加载配置，更新内存状态"""
        env = _parse_env_file(self.env_path)
        self.api_key = env.get("AI_API_KEY", "") or ""
        self.api_base = env.get("AI_API_BASE", "") or "https://api.openai.com/v1"
        self.model = env.get("AI_MODEL", "") or "gpt-3.5-turbo"

        explicit_mock = env.get("USE_MOCK", "").lower()
        if explicit_mock in ("true", "false"):
            self.use_mock = explicit_mock == "true"
        else:
            # 没有显式设置时：没有 key 强制 mock
            self.use_mock = not bool(self.api_key)

        self._init_client()

    def _init_client(self) -> None:
        """根据当前配置初始化或重置 OpenAI 客户端"""
        self.client = None
        if self.api_key and not self.use_mock and self.api_base:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.api_base)
            except Exception:
                self.client = None

    def update_config(
        self,
        api_key: str = "",
        api_base: str = "",
        model: str = "",
        use_mock: bool = False,
    ) -> dict:
        """
        运行时更新配置，同时写入 .env。
        返回更新后的状态。
        """
        api_key = (api_key or "").strip()
        api_base = (api_base or "").strip()
        model = (model or "").strip()

        # 如果提供了 api_key，且 base_url 或 model 为空 -> 报错
        if api_key and (not api_base or not model):
            return {
                "success": False,
                "error": "已填写 API Key，但 base_url 或 model 为空，请补全或选择预设模型",
            }

        # 决定 use_mock：有 key 强制为 False（除非用户显式要求 mock）
        if api_key:
            effective_use_mock = bool(use_mock)
        else:
            effective_use_mock = True

        # 写入 .env
        _write_env_file(
            self.env_path,
            {
                "AI_API_KEY": api_key,
                "AI_API_BASE": api_base,
                "AI_MODEL": model,
                "USE_MOCK": "true" if effective_use_mock else "false",
            },
        )

        # 更新内存
        self.api_key = api_key
        self.api_base = api_base or "https://api.openai.com/v1"
        self.model = model or "gpt-3.5-turbo"
        self.use_mock = effective_use_mock
        self._init_client()

        # 同步环境变量（便于同一进程其他模块读取）
        os.environ["AI_API_KEY"] = self.api_key
        os.environ["AI_API_BASE"] = self.api_base
        os.environ["AI_MODEL"] = self.model
        os.environ["USE_MOCK"] = "true" if self.use_mock else "false"

        return {"success": True, "status": self.get_status()}

    def get_status(self) -> dict:
        """返回当前 AI 配置状态（API Key 脱敏）"""
        has_key = bool(self.api_key)
        active = has_key and (not self.use_mock) and bool(self.client)
        return {
            "has_key": has_key,
            "masked_key": _mask_key(self.api_key),
            "api_base": self.api_base,
            "model": self.model,
            "use_mock": self.use_mock,
            "active": active,
            "providers": MODEL_PROVIDERS,
        }

    def test_connection(self) -> dict:
        """使用当前配置测试连通性"""
        if not self.api_key or self.use_mock or not self.client:
            return {
                "success": False,
                "error": "当前为模拟模式或未配置 API Key，请先填入 Key 并保存",
            }
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
                temperature=0,
            )
            content = response.choices[0].message.content or ""
            return {
                "success": True,
                "message": "连接成功",
                "reply": content[:80],
                "model": self.model,
            }
        except OpenAIError as e:
            return {"success": False, "error": f"OpenAI 错误：{str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"连接失败：{str(e)}"}

    # ---------- 业务调用 ----------
    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        """
        统一的 AI 对话接口
        :param system_prompt: 系统提示词
        :param user_prompt: 用户输入
        :param temperature: 创造性程度 0-1
        :return: AI 回复文本
        """
        if self.use_mock or not self.client:
            return self._mock_response(system_prompt, user_prompt)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            return (
                f"[AI 调用失败: {str(e)}，已切换到模拟返回]\n\n"
                + self._mock_response(system_prompt, user_prompt)
            )

    def _mock_response(self, system_prompt: str, user_prompt: str) -> str:
        """模拟返回 - 用于开发和演示"""
        for key, value in MOCK_RESPONSES.items():
            if key in system_prompt:
                return value
        return "这是模拟返回的 AI 响应。请在右上角「设置」中填入 API Key 以启用真实 AI 调用。"


# 全局单例
ai_service = AIService()
