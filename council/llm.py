
import os, json, urllib.request, urllib.error

class DeepSeekClient:
    """Minimal DeepSeek-compatible chat client.
    Configure via env:
      DEEPSEEK_API_BASE (e.g., https://api.deepseek.com)  # confirm in your account
      DEEPSEEK_API_KEY
      DEEPSEEK_MODEL   (e.g., deepseek-reasoner or your chosen model)
    """
    def __init__(self, api_base: str=None, api_key: str=None, model: str=None, timeout: int=60):
        self.api_base = api_base or os.getenv("DEEPSEEK_API_BASE", "").rstrip("/")
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")
        self.timeout = timeout
        if not self.api_base or not self.api_key:
            raise ValueError("DeepSeekClient: set DEEPSEEK_API_BASE and DEEPSEEK_API_KEY")

    def chat(self, messages, temperature: float=0.2, max_tokens: int=1200, extra: dict=None):
        url = f"{self.api_base}/v1/chat/completions"  # adjust if your endpoint differs
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if extra:
            payload.update(extra)
        req = urllib.request.Request(url, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        data = json.dumps(payload).encode("utf-8")
        try:
            with urllib.request.urlopen(req, data=data, timeout=self.timeout) as resp:
                out = json.loads(resp.read().decode("utf-8"))
                # Expected OpenAI-like structure:
                # out['choices'][0]['message']['content']
                content = out.get("choices", [{}])[0].get("message", {}).get("content", "")
                # Some providers may include reasoning traces; don't log verbatim.
                reasoning = out.get("choices", [{}])[0].get("message", {}).get("reasoning", "")
                usage = out.get("usage", {})
                return {"content": content, "reasoning": reasoning, "usage": usage, "raw": out}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"DeepSeek HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"DeepSeek URL error: {e}") from e
