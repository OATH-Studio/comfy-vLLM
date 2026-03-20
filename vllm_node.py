import random
import re
import requests

# ── Wildcard expansion ────────────────────────────────────────────────────────

def expand_wildcards(prompt: str) -> str:
    pattern = re.compile(r"\{([^{}]+)\}")
    def replace(match):
        options = match.group(1).split("|")
        return random.choice(options)
    while pattern.search(prompt):
        prompt = pattern.sub(replace, prompt, count=1)
    return prompt

# ── vLLM helpers ──────────────────────────────────────────────────────────────

def get_model_name(host: str, port: int) -> str:
    response = requests.get(f"http://{host}:{port}/v1/models", timeout=5)
    response.raise_for_status()
    return response.json()["data"][0]["id"]

def build_completion_prompt(user_prompt: str) -> str:
    return (
        "### Stable Diffusion prompt tags (comma separated, no sentences):\n"
        f"Input: {user_prompt}\n"
        "Output:"
    )

def call_vllm(prompt: str, host: str, port: int, max_tokens: int, temperature: float, retries: int = 3) -> str:
    url   = f"http://{host}:{port}/v1/completions"
    model = get_model_name(host, port)

    payload = {
        "model":       model,
        "prompt":      build_completion_prompt(prompt),
        "max_tokens":  max_tokens,
        "temperature": temperature,
        "stop":        ["\n", "###", "Input:"],
    }

    for attempt in range(retries):
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            text = response.json()["choices"][0]["text"].strip()
            if text:
                return text
            print(f"[vLLM] empty response on attempt {attempt + 1}, retrying...")
        except requests.exceptions.Timeout:
            print(f"[vLLM] timeout on attempt {attempt + 1}, retrying...")
        except requests.exceptions.RequestException as e:
            print(f"[vLLM] request error on attempt {attempt + 1}: {e}, retrying...")

    raise RuntimeError(f"[vLLM] failed after {retries} attempts")

# ── ComfyUI Node ──────────────────────────────────────────────────────────────

class VLLMPromptNode:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt":      ("STRING", {"multiline": True, "default": "A {red|blue|green} dragon, wild dynamic pose, {breathing fire and launching into the sky|coiled around a mountain peak in a storm|diving into a glowing ocean abyss|rearing up against a blood moon}"}),
                "prefix":      ("STRING", {"multiline": True, "default": "masterpiece, best quality, highres"}),
                "host":        ("STRING", {"default": "localhost"}),
                "port":        ("INT",    {"default": 8765, "min": 1,   "max": 65535}),
                "max_tokens":  ("INT",    {"default": 128,  "min": 1,   "max": 4096}),
                "temperature": ("FLOAT",  {"default": 0.7,  "min": 0.0, "max": 2.0, "step": 0.05}),
                "retries":     ("INT",    {"default": 3,    "min": 1,   "max": 10}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("combined_prompt",)

    FUNCTION    = "generate"
    CATEGORY    = "utils/llm"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def generate(self, prompt, prefix, host, port, max_tokens, temperature, retries):
        expanded  = expand_wildcards(prompt)
        generated = call_vllm(expanded, host, port, max_tokens, temperature, retries)

        combined = f"{prefix.strip()}, {generated}" if prefix.strip() else generated

        preview = (
            f"[prefix]\n{prefix.strip() or '(none)'}\n\n"
            f"[generated]\n{generated}\n\n"
            f"[combined]\n{combined}"
        )

        return {
            "ui":     {"text": [preview]},
            "result": (combined,),
        }

# ── ComfyUI registration ──────────────────────────────────────────────────────

NODE_CLASS_MAPPINGS        = {"VLLMPromptNode": VLLMPromptNode}
NODE_DISPLAY_NAME_MAPPINGS = {"VLLMPromptNode": "vLLM Prompt"}

# ── Local test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    node = VLLMPromptNode()
    result = node.generate(
        prompt      = "A {red|blue|green} dragon, wild dynamic pose, {breathing fire and launching into the sky|coiled around a mountain peak in a storm}",
        prefix      = "masterpiece, best quality, highres",
        host        = "localhost",
        port        = 8765,
        max_tokens  = 128,
        temperature = 0.7,
        retries     = 3,
    )
    print(result["result"][0])