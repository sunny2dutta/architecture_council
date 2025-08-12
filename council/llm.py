import os, json, urllib.request, urllib.error, socket, time
from typing import Any, Dict, List, Optional

class DeepSeekClient:
    """
    Minimal DeepSeek-compatible chat client with robust timeouts & retries.

    Env:
      DEEPSEEK_API_BASE   e.g. https://api.deepseek.com
      DEEPSEEK_API_KEY
      DEEPSEEK_MODEL      e.g. deepseek-chat
      DEEPSEEK_DEBUG      set to "1" to print request/response debug
    """
    def __init__(self, api_base: str=None, api_key: str=None, model: str=None,
                 timeout: int=60, read_timeout: int=100, retries: int=3, backoff: float=1.5,
                 debug: Optional[bool]=None):
        self.api_base = (api_base or os.getenv("DEEPSEEK_API_BASE", "")).rstrip("/")
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.timeout = timeout          # connect timeout
        self.read_timeout = read_timeout
        self.retries = retries
        self.backoff = backoff
        self.debug = bool(int(os.getenv("DEEPSEEK_DEBUG", "0"))) if debug is None else debug
        if not self.api_base or not self.api_key:
            raise ValueError("DeepSeekClient: set DEEPSEEK_API_BASE and DEEPSEEK_API_KEY")

    def _extract_content(self, out: Dict[str, Any]) -> str:
        """
        Try the common places content might live.
        """
        # OpenAI-style
        try:
            c = out.get("choices", [{}])[0].get("message", {}).get("content")
            if c: return c
        except Exception:
            pass
        # Some providers also expose plain 'text'
        try:
            c = out.get("choices", [{}])[0].get("text")
            if c: return c
        except Exception:
            pass
        # DeepSeek may expose a separate reasoning field; we still prefer 'content'
        return ""

    def chat(self, messages: List[Dict[str, str]], temperature: float=0.2,
             max_tokens: int=7000, extra: Optional[Dict]=None) -> Dict[str, Any]:
        """
        Calls /v1/chat/completions (OpenAI-like). Forces non-streaming by default.
        Retries on transient network/timeout errors.
        """
        url = f"{self.api_base}/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,  # IMPORTANT: avoid chunked/streaming responses
        }
        if extra:
            payload.update(extra)

        data = json.dumps(payload).encode("utf-8")
        last_err = None

        for attempt in range(1, self.retries + 1):
            req = urllib.request.Request(url, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            req.add_header("Connection", "close")  # avoid stuck keep-alives

            try:
                if self.debug:
                    print("\n=== DeepSeek REQUEST =====================")
                    print("URL:", url)
                    print("Payload:", json.dumps(payload)[:2000])
                    print("=========================================\n")

                socket.setdefaulttimeout(self.read_timeout)  # read timeout
                with urllib.request.urlopen(req, data=data, timeout=self.timeout) as resp:
                    body_bytes = resp.read()  # non-streamed body
                    body_text = body_bytes.decode("utf-8", errors="replace")

                    if self.debug:
                        print("\n=== DeepSeek RAW RESPONSE ===============")
                        print(body_text[:5000])
                        print("=========================================\n")

                    out = json.loads(body_text)
                    content = self._extract_content(out)
                    reasoning = out.get("choices", [{}])[0].get("message", {}).get("reasoning", "")
                    usage = out.get("usage", {})

                    # If content is empty, surface why
                    if not content and self.debug:
                        print("⚠️ No 'content' found in response. Parsed keys:", list(out.keys()))

                    return {"content": content, "reasoning": reasoning, "usage": usage, "raw": out}

            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
                if self.debug:
                    print("\n=== DeepSeek HTTPError ==================")
                    print("Status:", e.code)
                    print("Body:", err_body[:5000])
                    print("=========================================\n")
                # 4xx (like invalid model) are not retried
                raise RuntimeError(f"DeepSeek HTTP {e.code}: {err_body}") from e

            except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
                last_err = e
                if self.debug:
                    print(f"⚠️ Network/timeout on attempt {attempt}/{self.retries}: {e}")
                if attempt < self.retries:
                    time.sleep(self.backoff ** (attempt - 1))
                    continue
                raise RuntimeError(f"DeepSeek network/timeout error after {self.retries} attempts: {e}") from e

            finally:
                # Reset default timeout so we don't affect the rest of the app
                socket.setdefaulttimeout(None)
