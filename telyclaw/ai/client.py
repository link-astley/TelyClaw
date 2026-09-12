"""DeepSeek 调用封装 + 错误规范化

按决策：写死 DeepSeek，不做离线兜底内容。
失败时只返回"人话提示 + 是否可重试"，绝不用预写内容冒充 AI 输出。
"""

import json
import re

import requests

from config import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT


class AIError(Exception):
    """AI 调用失败。code 用于前端判断，message 是直接给用户看的人话"""

    CODES = {
        "no_key": "还没填 AI 密钥，去设置页填一下就能用",
        "network": "连不上 AI 服务，检查一下网络",
        "timeout": "AI 这次响应超时了，可以重试",
        "auth": "AI 密钥不对或已失效，去设置页检查",
        "quota": "AI 账户额度不足，去 DeepSeek 后台看看",
        "server": "AI 服务那边出了点问题，稍后重试",
        "parse": "AI 这次返回的内容没看懂，建议重试",
        "empty": "AI 这次没返回内容，建议重试",
        "unknown": "AI 调用失败了，可以重试",
    }

    def __init__(self, code: str, detail: str = ""):
        self.code = code if code in self.CODES else "unknown"
        self.detail = detail or ""
        super().__init__(self.message)

    @property
    def message(self) -> str:
        return self.CODES.get(self.code, self.CODES["unknown"])

    @property
    def retryable(self) -> bool:
        return self.code in {"network", "timeout", "server", "parse", "empty", "unknown"}

    def to_dict(self):
        return {
            "ok": False,
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "retryable": self.retryable,
        }


def chat(messages: list, api_key: str, temperature: float = 0.7,
         max_tokens: int = 2000, response_format_json: bool = False) -> str:
    """调用 DeepSeek，返回模型输出的字符串内容"""
    if not (api_key or "").strip():
        raise AIError("no_key")

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if response_format_json:
        payload["response_format"] = {"type": "json_object"}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=DEEPSEEK_TIMEOUT)
    except requests.exceptions.Timeout:
        raise AIError("timeout")
    except requests.exceptions.RequestException as e:
        raise AIError("network", str(e))

    if resp.status_code == 401 or resp.status_code == 403:
        raise AIError("auth", f"HTTP {resp.status_code}")
    if resp.status_code == 402:
        raise AIError("quota", f"HTTP {resp.status_code}")
    if resp.status_code >= 500:
        raise AIError("server", f"HTTP {resp.status_code}")
    if resp.status_code != 200:
        raise AIError("unknown", f"HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        raise AIError("parse", str(e))

    if not content or not str(content).strip():
        raise AIError("empty")
    return str(content)


# ------------------------------------------------------------------ JSON 解析
def parse_json_safely(content: str):
    """模型偶尔会裹上 ```json 代码块，这里统一剥掉再解析"""
    text = (content or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    # 退而求其次：截取第一个 { 到最后一个 }
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    raise AIError("parse", "返回内容不是合法 JSON")
