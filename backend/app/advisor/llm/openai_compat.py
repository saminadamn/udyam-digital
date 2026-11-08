import json
import logging

import httpx

from app.i18n import LANG_NAMES

log = logging.getLogger("app.llm")

SYSTEM = (
    "You help small Indian business owners choose Accel Business telecom services. "
    "Speak simply, like a helpful shopkeeper, in the language you are told. Never use product codes such as P01. "
    "Never mention a product, price or offer that is not given to you."
)


class OpenAICompatProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: int):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.key, self.model, self.timeout = api_key, model, timeout_s

    def _chat(self, user: str, json_mode: bool = False) -> str | None:
        body = {"model": self.model, "temperature": 0.3, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            r = httpx.post(self.url, headers={"Authorization": f"Bearer {self.key}", "api-subscription-key": self.key}, json=body, timeout=self.timeout)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.warning("LLM call failed: %s", type(e).__name__)
            return None

    def phrase_question(self, field, lang, profile, default):
        out = self._chat(f"Rephrase this question naturally in {LANG_NAMES[lang]}, keep it to one short sentence, "
                         f"same meaning, no extra questions:\n{default}")
        return out or default

    def extract(self, field, content, lang, profile):
        spec = {
            "type": '{"type": one of "micro" (shop or small service), "prof" (clinic, office, professional), "multi" (several branches), "mfg" (factory)}',
            "team": '{"employees": integer, "sites": integer}',
            "city": '{"city": string, "city_tier": 1 for big metro or 2 otherwise}',
        }.get(field)
        if not spec:
            return None
        out = self._chat(f"The owner answered: {content!r}. Extract {spec}. Reply with JSON only, or {{}} if it is not clear.", json_mode=True)
        try:
            data = json.loads(out or "{}")
            return data or None
        except json.JSONDecodeError:
            return None

    def choose(self, profile, eligible, suggested):
        out = self._chat(
            "Business profile: " + json.dumps(profile, ensure_ascii=False) + "\nProducts this business is allowed to buy: " +
            json.dumps(eligible, ensure_ascii=False) + "\nSuggested bundle: " + json.dumps(suggested) +
            '\nAdjust the suggestion only if it clearly fits the stated needs better. Use only ids from the allowed list. '
            'Reply as JSON {"core": [ids], "addons": [ids]}.', json_mode=True)
        try:
            data = json.loads(out or "{}")
            return data if isinstance(data.get("core"), list) else None
        except (json.JSONDecodeError, AttributeError):
            return None

    def explain(self, context, lang, default):
        out = self._chat(
            f"Write 2 or 3 short, plain sentences in {LANG_NAMES[lang]} telling the owner why this plan fits them. "
            f"Use only these products and this total. Mention the monthly total exactly as Rs {context['total']}.\n"
            + json.dumps(context, ensure_ascii=False))
        return out or default
