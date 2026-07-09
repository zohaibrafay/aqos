from aqos.news_providers import (
    build_http_news_provider_config,
    load_http_news_provider_result,
)

config = build_http_news_provider_config(
    provider_id="gdelt",
    name="GDELT News",
    base_url="https://api.gdeltproject.org",
    endpoint="/api/v2/doc/doc",
    default_headers={
        "Accept": "application/json",
        "User-Agent": "AQOS/0.26 local test",
    },
    default_query_params={
        "query": "gold",
        "mode": "artlist",
        "format": "json",
        "maxrecords": 2,
        "sort": "hybridrel",
    },
    payload_key="articles",
)

result = load_http_news_provider_result(config)

print("Success:", result.success)
print("Failed:", result.failed)
print("Records:", result.record_count)
print("Message:", result.message)

for record in result.records[:5]:
    print("---")
    print("ID:", record.event_id)
    print("Time:", record.timestamp)
    print("Title:", record.title)
    print("Source:", record.source)
    print("URL:", record.url)
    print("Symbol:", record.symbol)
    print("Impact:", record.impact)
    print("Sentiment:", record.sentiment)