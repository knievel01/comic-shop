"""Runtime settings (environment) and business configuration (config/pricing.yaml)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml


def _default_pricing_paths() -> list[Path]:
    paths = [Path(os.environ.get("PRICING_CONFIG", "/app/config/pricing.yaml"))]
    here = Path(__file__).resolve()
    if len(here.parents) > 3:
        paths.append(here.parents[3] / "config" / "pricing.yaml")  # repo checkout
    return paths


@dataclass(frozen=True)
class Settings:
    s3_bucket: str
    aws_region: str = "eu-central-1"
    s3_endpoint_url: str | None = None
    helper_token: str = ""
    review_password: str = ""
    review_base_url: str = ""
    n8n_internal_url: str = "http://n8n:5678"
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "low"
    shopify_shop_domain: str = ""
    shopify_admin_token: str = ""
    shopify_client_id: str = ""
    shopify_client_secret: str = ""
    shopify_webhook_secret: str = ""
    shopify_api_version: str = "2026-07"
    shopify_location_id: str = ""
    shopify_publication_ids: list[str] = field(default_factory=list)
    mail_from: str = ""
    mail_to_daily: str = ""
    mail_to_alerts: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ.get
        return cls(
            s3_bucket=env("S3_BUCKET", ""),
            aws_region=env("AWS_REGION", "eu-central-1"),
            s3_endpoint_url=env("S3_ENDPOINT_URL") or None,
            helper_token=env("HELPER_TOKEN", ""),
            review_password=env("REVIEW_PASSWORD", ""),
            review_base_url=env("REVIEW_BASE_URL", "").rstrip("/"),
            n8n_internal_url=env("N8N_INTERNAL_URL", "http://n8n:5678").rstrip("/"),
            anthropic_model=env("CLAUDE_MODEL", "claude-opus-5-5"),
            anthropic_effort=env("CLAUDE_EFFORT", "low"),
            shopify_shop_domain=env("SHOPIFY_SHOP_DOMAIN", ""),
            shopify_admin_token=env("SHOPIFY_ADMIN_TOKEN", ""),
            shopify_client_id=env("SHOPIFY_CLIENT_ID", ""),
            shopify_client_secret=env("SHOPIFY_CLIENT_SECRET", ""),
            shopify_webhook_secret=env("SHOPIFY_WEBHOOK_SECRET", ""),
            shopify_api_version=env("SHOPIFY_API_VERSION", "2026-07"),
            shopify_location_id=env("SHOPIFY_LOCATION_ID", ""),
            shopify_publication_ids=[p for p in env("SHOPIFY_PUBLICATION_IDS", "").split(",") if p],
            mail_from=env("MAIL_FROM", ""),
            mail_to_daily=env("MAIL_TO_DAILY", ""),
            mail_to_alerts=env("MAIL_TO_ALERTS", ""),
        )


@lru_cache
def settings() -> Settings:
    return Settings.from_env()


def load_pricing(path: Path | None = None) -> dict:
    candidates = [path] if path else _default_pricing_paths()
    for p in candidates:
        if p and p.is_file():
            cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
            cfg["zustaende"] = {int(k): v for k, v in cfg["zustaende"].items()}
            return cfg
    raise FileNotFoundError(f"pricing.yaml not found in {candidates}")


@lru_cache
def pricing_config() -> dict:
    return load_pricing()
