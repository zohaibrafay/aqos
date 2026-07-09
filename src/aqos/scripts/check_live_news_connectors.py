"""
Run AQOS live news connector checks.

This script is safe for local testing:
- Hacker News works without API key.
- GDELT may rate-limit sometimes.
- API-key providers are only tested if env vars are present.
"""

from __future__ import annotations

import os

from aqos.news_providers import (
    NewsProviderCredentials,
    build_news_connector_selection_request,
    run_live_news_ingestion,
)


def credentials_from_env() -> dict[str, NewsProviderCredentials]:
    """Build connector credentials from environment variables."""
    mapping: dict[str, NewsProviderCredentials] = {}

    env_to_connector = {
        "AQOS_NEWSAPI_KEY": "news_api",
        "AQOS_MARKETAUX_KEY": "marketaux",
        "AQOS_FINNHUB_KEY": "finnhub",
        "AQOS_TRADING_ECONOMICS_KEY": "trading_economics",
        "AQOS_CRYPTOPANIC_KEY": "cryptopanic",
    }

    for env_name, connector_id in env_to_connector.items():
        value = os.getenv(env_name, "").strip()

        if value:
            mapping[connector_id] = NewsProviderCredentials(
                auth_type="api_key",
                api_key=value,
            )

    return mapping


def main() -> None:
    """Run local connector check."""
    credentials = credentials_from_env()

    connector_ids = ["hacker_news", "gdelt"]

    for connector_id in ["news_api", "marketaux", "finnhub", "trading_economics", "cryptopanic"]:
        if connector_id in credentials:
            connector_ids.append(connector_id)

    batch = run_live_news_ingestion(
        selection_request=build_news_connector_selection_request(
            connector_ids=connector_ids,
        ),
        credentials_by_connector_id=credentials,
    )

    print("Status:", batch.status.value)
    print("Connectors:", batch.connector_count)
    print("Success:", batch.success_count)
    print("Failed:", batch.failed_count)
    print("Records:", batch.total_record_count)
    print("Message:", batch.message)

    for result in batch.results:
        print("---")
        print("Connector:", result.connector_id)
        print("Success:", result.success)
        print("Records:", result.record_count)
        print("Message:", result.message)

        for record in result.provider_result.records[:3]:
            print("  -", record.title, "|", record.source, "|", record.url)


if __name__ == "__main__":
    main()