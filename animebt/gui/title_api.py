"""OpenAI-compatible request and response validation for title display."""

import json
import re
from urllib.parse import urlsplit


def endpoint_for(base):
    if any(character.isspace() for character in base.strip()):
        return ""
    try:
        url = urlsplit(base.strip())
        if not url.hostname or url.username or url.password or url.query or url.fragment:
            return ""
        if url.scheme != "https" and not (
            url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            return ""
        if url.port is not None and not 0 < url.port <= 65535:
            return ""
    except ValueError:
        return ""
    endpoint = url.geturl().rstrip("/")
    return endpoint if endpoint.endswith("/chat/completions") else endpoint + "/chat/completions"


def is_deepseek(endpoint):
    return urlsplit(endpoint).hostname == "api.deepseek.com"


def chat_payload(endpoint, model, messages):
    payload = {"model": model, "messages": messages, "stream": False}
    if is_deepseek(endpoint) or urlsplit(endpoint).hostname == "api.openai.com":
        payload["response_format"] = {"type": "json_object"}
    if is_deepseek(endpoint):
        payload["thinking"] = {"type": "disabled"}
        payload["max_tokens"] = 8192
    return payload


def http_error(code, body):
    try:
        error = json.loads(body).get("error", {})
        detail = str(error).casefold()
    except (ValueError, AttributeError, TypeError):
        detail = ""
    if code == 401:
        reason = "API Key 无效、已过期或缺少认证"
    elif code == 402 or "insufficient_quota" in detail or "insufficient_balance" in detail:
        reason = "账户余额不足或 API 配额已用尽"
    elif code in (400, 404, 422) and "model" in detail and any(
        marker in detail for marker in ("not found", "does not exist", "not exist", "invalid", "不存在", "model_not_found")
    ):
        reason = "模型不存在或不可用，请核对模型名称"
    elif code == 403:
        reason = "API 拒绝访问，请检查模型权限或来源限制"
    elif code == 404:
        reason = "API 路径不存在，请检查 Base URL"
    elif code == 429:
        reason = "API 请求限流，请稍后重试"
    elif 500 <= code < 600:
        reason = "API 服务端错误或暂时过载"
    elif 300 <= code < 400:
        reason = "API 返回重定向，请填写最终的 HTTPS 地址"
    elif code in (400, 422):
        reason = "API 拒绝请求参数，请核对接口与模型配置"
    else:
        reason = "API 请求失败"
    return f"{reason}（HTTP {code}）"


def completion_content(body):
    if len(body) > 1024 * 1024:
        raise ValueError("API 响应过大")
    data = json.loads(body)
    if (not isinstance(data, dict) or not isinstance(data.get("choices"), list)
            or not data["choices"] or not isinstance(data["choices"][0], dict)):
        raise ValueError("响应未包含 Chat Completions choices")
    choice = data["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ValueError("模型输出被截断，请减小批次或更换模型")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("响应未包含 Chat Completions message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("模型未返回有效内容")
    content = content.strip()
    if content.startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if match:
            content = match[1]
    result = json.loads(content)
    if not isinstance(result, dict):
        raise ValueError("模型未返回 JSON 对象")
    return result
