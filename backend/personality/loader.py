import json
import os
from typing import Dict

_cache: Dict[str, dict] = {}
_DIR = os.path.dirname(__file__)


def load_strings(language: str = "he") -> dict:
    if language not in _cache:
        path = os.path.join(_DIR, f"{language}.json")
        if not os.path.exists(path):
            path = os.path.join(_DIR, "he.json")
        with open(path, encoding="utf-8") as f:
            _cache[language] = json.load(f)
    return _cache[language]


def get_string(key: str, language: str = "he", **kwargs) -> str:
    text = load_strings(language).get(key, key)
    return text.format(**kwargs) if kwargs else text
