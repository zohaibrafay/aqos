from aqos.news_providers import (
    build_http_news_provider_config,
    load_http_news_provider_result,
)

config = build_http_news_provider_config(
    provider_id="hackernews-json",
    name="Hacker News Algolia JSON",
    base_url="https://hn.algolia.com",
    endpoint="/api/v1/search",
    default_headers={
        "Accept": "application/json",
        "User-Agent": "AQOS/0.26 local test",
    },
    default_query_params={
        "query": "inflation",
        "tags": "story",
        "hitsPerPage": 3,
    },
    payload_key="hits",
)

result = load_http_news_provider_result(config)

print("Success:", result.success)
print("Failed:", result.failed)
print("Records:", result.record_count)
print("Message:", result.message)

for record in result.records[:3]:
    print("---")
    print("ID:", record.event_id)
    print("Time:", record.timestamp)
    print("Title:", record.title)
    print("Source:", record.source)
    print("URL:", record.url)