"""
Local AQOS playground.

Run:
    python scripts/play_local_dashboard.py

This builds sample AQOS market, signal, portfolio, status, and combined
dashboard payloads locally and exports a frontend-ready JSON file.
"""

from __future__ import annotations

import json
from pathlib import Path

from aqos.dashboard import (
    aggregate_dashboard_payloads,
    build_broker_provider_status_payload,
    build_broker_provider_status_snapshot,
    build_integration_status_item,
    build_market_overview_payload,
    build_market_overview_snapshot,
    build_portfolio_position_item,
    build_portfolio_risk_payload,
    build_portfolio_risk_snapshot,
    build_signal_dashboard_item,
    build_signal_strategy_payload,
    build_strategy_dashboard_snapshot,
    frontend_response_from_payload,
)


def main() -> None:
    # 1. Market dashboard
    market_snapshot = build_market_overview_snapshot(
        symbol="XAUUSD",
        timeframe="H1",
        latest_price=2020.0,
        previous_price=2000.0,
        provider_id="local-demo-provider",
        session_status="open",
    )

    market_payload = build_market_overview_payload(
        snapshots=[market_snapshot],
    )

    # 2. Signal / Strategy dashboard
    signal = build_signal_dashboard_item(
        signal_id="signal-demo-001",
        symbol="XAUUSD",
        direction="buy",
        confidence=0.82,
        strategy_name="Liquidity Sweep",
        timeframe="H1",
        entry_price=2020.0,
        stop_loss=2005.0,
        take_profit=2050.0,
        risk_reward=2.0,
        generated_at="2026-01-01T00:00:00+00:00",
        reason="Bullish liquidity sweep with positive momentum confirmation.",
    )

    strategy_snapshot = build_strategy_dashboard_snapshot(
        strategy_id="strategy-demo-001",
        strategy_name="Liquidity Sweep Strategy",
        state="active",
        signals=[signal],
        metrics={
            "win_rate": 62.5,
            "profit_factor": 1.8,
            "sharpe_ratio": 1.2,
            "max_drawdown_pct": 8.5,
        },
    )

    signal_payload = build_signal_strategy_payload(
        snapshots=[strategy_snapshot],
    )

    # 3. Portfolio / Risk dashboard
    position = build_portfolio_position_item(
        position_id="position-demo-001",
        symbol="XAUUSD",
        side="long",
        quantity=2,
        average_price=2000.0,
        market_price=2020.0,
        unrealized_pnl=40.0,
        realized_pnl=10.0,
        allocation_pct=25.0,
    )

    portfolio_snapshot = build_portfolio_risk_snapshot(
        portfolio_id="portfolio-demo-001",
        account_id="account-demo-001",
        currency="USD",
        cash_balance=96000.0,
        equity=100000.0,
        buying_power=90000.0,
        realized_pnl=500.0,
        unrealized_pnl=250.0,
        max_drawdown_pct=6.0,
        daily_var=2.0,
        positions=[position],
        pnl_history=[
            {"x": "2026-01-01", "y": 500},
            {"x": "2026-01-02", "y": 750},
        ],
    )

    portfolio_payload = build_portfolio_risk_payload(
        snapshots=[portfolio_snapshot],
    )

    # 4. Broker / Provider status dashboard
    status_snapshot = build_broker_provider_status_snapshot(
        broker_items=[
            build_integration_status_item(
                status_id="paper-broker-demo",
                name="Paper Broker Demo",
                kind="broker",
                health="online",
                connected=True,
                active=True,
                capabilities=["paper_trading", "market_orders"],
                latency_ms=12.5,
                message="Paper broker is online.",
            )
        ],
        provider_items=[
            build_integration_status_item(
                status_id="market-provider-demo",
                name="Market Provider Demo",
                kind="provider",
                health="online",
                connected=True,
                active=True,
                capabilities=["historical_ohlcv", "live_quotes"],
                latency_ms=5.5,
                message="Market provider is online.",
            )
        ],
    )

    status_payload = build_broker_provider_status_payload(
        snapshot=status_snapshot,
    )

    # 5. Aggregate full AQOS dashboard
    full_dashboard_payload = aggregate_dashboard_payloads(
        payloads={
            "market": market_payload,
            "signals": signal_payload,
            "portfolio": portfolio_payload,
            "status": status_payload,
        },
        section_kinds={
            "market": "market",
            "signals": "signals",
            "portfolio": "portfolio",
            "status": "status",
        },
        snapshot_id="aqos-local-dashboard",
        title="AQOS Local Dashboard",
        mode="full",
    )

    frontend_response = frontend_response_from_payload(full_dashboard_payload)

    output_dir = Path("tmp")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "aqos_local_dashboard.json"
    output_file.write_text(
        json.dumps(frontend_response, indent=2),
        encoding="utf-8",
    )

    print("AQOS local playground completed.")
    print(f"Dashboard status: {frontend_response['payload']['status']}")
    print(f"Components: {frontend_response['payload']['component_count']}")
    print(f"Metrics: {frontend_response['payload']['metric_count']}")
    print(f"Issues: {frontend_response['payload']['issue_count']}")
    print(f"Output file: {output_file}")


if __name__ == "__main__":
    main()