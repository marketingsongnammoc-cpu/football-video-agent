"""
fetcher/__init__.py — Factory + registry cho tất cả nguồn báo.
"""

from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse

from .base import BaseAdapter, FetchConfig, Article

# Import từng adapter — đã có sẵn sẽ enable, chưa có sẽ skip
ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {}


def _try_register(key: str, module: str, classname: str) -> None:
    """Import lazy: nếu file adapter tồn tại thì register."""
    try:
        mod = __import__(module, fromlist=[classname])
        cls = getattr(mod, classname)
        ADAPTER_REGISTRY[key] = cls
    except (ImportError, AttributeError):
        pass


# VN sources
_try_register("bongda", "scripts.fetcher.vn.bongda", "BongdaAdapter")
_try_register("vnexpress", "scripts.fetcher.vn.vnexpress", "VnExpressAdapter")
_try_register("tuoitre", "scripts.fetcher.vn.tuoitre", "TuoiTreAdapter")
_try_register("thanhnien", "scripts.fetcher.vn.thanhnien", "ThanhNienAdapter")
_try_register("bongdaplus", "scripts.fetcher.vn.bongdaplus", "BongDaPlusAdapter")
# International sources
_try_register("goal", "scripts.fetcher.goal", "GoalAdapter")
# Tabloid sources
_try_register("thesun", "scripts.fetcher.tabloid.thesun", "TheSunAdapter")
_try_register("dailymail", "scripts.fetcher.tabloid.dailymail", "DailyMailAdapter")
_try_register("mirror", "scripts.fetcher.tabloid.mirror", "MirrorAdapter")
_try_register("marca", "scripts.fetcher.tabloid.marca", "MarcaAdapter")
_try_register("donbalon", "scripts.fetcher.tabloid.donbalon", "DonBalonAdapter")
_try_register("aljazeera", "scripts.fetcher.tabloid.aljazeera", "AlJazeeraAdapter")


def load_sources_config(config_path: Path) -> dict[str, FetchConfig]:
    """Load config từ sources.json."""
    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    configs = {}
    for key, cfg in raw.items():
        if not cfg.get("enabled", True):
            continue
        configs[key] = FetchConfig(
            name=key,
            branch=cfg["branch"],
            homepage=cfg["homepage"],
            language=cfg.get("language", "vi"),
            tabloid=cfg.get("tabloid", False),
            image_cdn_whitelist=cfg.get("image_cdn_whitelist", []),
            priority=cfg.get("priority", 99),
        )
    return configs


def get_adapter(source_key: str, configs: dict[str, FetchConfig]) -> BaseAdapter:
    """Tạo adapter instance theo key."""
    if source_key not in ADAPTER_REGISTRY:
        raise ValueError(
            f"Chưa implement adapter cho '{source_key}'. "
            f"Đã có: {list(ADAPTER_REGISTRY.keys())}"
        )
    if source_key not in configs:
        raise ValueError(f"Không có config cho '{source_key}' trong sources.json")
    cls = ADAPTER_REGISTRY[source_key]
    return cls(configs[source_key])


def detect_adapter_from_url(url: str, configs: dict[str, FetchConfig]) -> str:
    """Detect adapter key từ URL (so domain với homepage của từng adapter)."""
    domain = urlparse(url).netloc.lower().replace("www.", "")
    for key, cfg in configs.items():
        cfg_domain = urlparse(cfg.homepage).netloc.lower().replace("www.", "")
        if domain == cfg_domain or domain.endswith("." + cfg_domain):
            return key
    raise ValueError(f"Không nhận diện được nguồn từ URL: {url}")


def list_all_sources(configs: dict[str, FetchConfig], branch: str | None = None) -> list[str]:
    """List source keys theo priority. branch='vn'|'tabloid'|None (all)."""
    items = [(k, c) for k, c in configs.items() if branch is None or c.branch == branch]
    items.sort(key=lambda x: x[1].priority)
    return [k for k, _ in items if k in ADAPTER_REGISTRY]
