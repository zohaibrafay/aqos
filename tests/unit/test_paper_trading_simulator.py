"""Unit tests for the paper execution simulator."""

from __future__ import annotations

from datetime import datetime

import pytest

from aqos.paper_trading.contracts import (
    PaperAction,
    PaperPosition,
    PaperPositionStatus,
    PaperSide,
    PaperTradingError,
)
from aqos.paper_trading.simulator import (
    IntrabarExitPolicy,
    PaperExitReason,
    PaperMarketBar,
    PaperSimulatorConfig,
    calculate_fill_price,
    calculate_gross_pnl,
    is_buy_fill,
    is_stop_loss_hit,
    is_take_profit_hit,
    resolve_position_exit,
    resolve_reference_price,
)


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_bar(
    open_price: float = 100.0,
    high: float = 105.0,
    low: float = 95.0,
    close: float = 102.0,
    symbol: str = "XAUUSD",
) -> PaperMarketBar:
    return PaperMarketBar(
        symbol=symbol,
        timestamp_utc=FIXED_NOW,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1_000.0,
    )


def build_position(
    side: PaperSide = PaperSide.LONG,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    status: PaperPositionStatus = PaperPositionStatus.OPEN,
    symbol: str = "XAUUSD",
) -> PaperPosition:
    return PaperPosition(
        position_id="pos_1",
        account_id="acc_1",
        symbol=symbol,
        side=side,
        quantity=2.0,
        entry_price=100.0,
        opened_at_utc=FIXED_NOW,
        status=status,
        stop_loss=stop_loss,
        take_profit=take_profit,
        closed_at_utc=(
            FIXED_NOW if status == PaperPositionStatus.CLOSED else None
        ),
        closed_quantity=(
            2.0 if status == PaperPositionStatus.CLOSED else 0.0
        ),
    )


class TestPaperMarketBar:
    def test_a_valid_bar_round_trips(self) -> None:
        bar = build_bar()

        payload = bar.to_dict()

        assert payload["symbol"] == "XAUUSD"
        assert payload["high"] == 105.0
        assert payload["timestamp_utc"] == FIXED_NOW.isoformat()

    def test_an_empty_symbol_is_rejected(self) -> None:
        with pytest.raises(PaperTradingError, match="symbol cannot be empty"):
            build_bar(symbol="   ")

    @pytest.mark.parametrize("field", ["open", "high", "low", "close"])
    def test_a_non_positive_price_is_rejected(self, field: str) -> None:
        prices = {"open_price": 100.0, "high": 105.0, "low": 95.0, "close": 102.0}
        prices["open_price" if field == "open" else field] = 0.0

        with pytest.raises(PaperTradingError, match="must be positive"):
            build_bar(**prices)

    def test_a_high_below_the_body_is_rejected(self) -> None:
        with pytest.raises(PaperTradingError, match="high must cover"):
            build_bar(open_price=100.0, high=99.0, low=95.0, close=98.0)

    def test_a_low_above_the_body_is_rejected(self) -> None:
        with pytest.raises(PaperTradingError, match="low must cover"):
            build_bar(open_price=100.0, high=105.0, low=101.0, close=102.0)

    def test_negative_volume_is_rejected(self) -> None:
        with pytest.raises(PaperTradingError, match="volume cannot be negative"):
            PaperMarketBar(
                symbol="XAUUSD",
                timestamp_utc=FIXED_NOW,
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
                volume=-1.0,
            )


class TestPaperSimulatorConfig:
    def test_defaults_apply_no_costs(self) -> None:
        config = PaperSimulatorConfig()

        assert config.cost_per_side == 0.0
        assert config.intrabar_exit_policy == IntrabarExitPolicy.STOP_LOSS_FIRST

    def test_cost_per_side_scales_with_point_size(self) -> None:
        config = PaperSimulatorConfig(
            spread_points=2.0,
            slippage_points=1.0,
            point_size=0.1,
        )

        assert config.cost_per_side == pytest.approx(0.3)

    @pytest.mark.parametrize(
        "kwargs, message",
        [
            ({"spread_points": -1.0}, "spread_points"),
            ({"slippage_points": -1.0}, "slippage_points"),
            ({"commission_per_fill": -1.0}, "commission_per_fill"),
            ({"point_size": 0.0}, "point_size"),
            ({"contract_size": 0.0}, "contract_size"),
        ],
    )
    def test_invalid_settings_are_rejected(
        self,
        kwargs: dict[str, float],
        message: str,
    ) -> None:
        with pytest.raises(PaperTradingError, match=message):
            PaperSimulatorConfig(**kwargs)

    def test_to_dict_reports_every_setting(self) -> None:
        payload = PaperSimulatorConfig(spread_points=1.0).to_dict()

        assert payload["spread_points"] == 1.0
        assert payload["intrabar_exit_policy"] == "stop_loss_first"
        assert payload["fill_on_bar_open"] is True


class TestFillDirection:
    def test_buy_and_sell_are_direct(self) -> None:
        assert is_buy_fill(PaperAction.BUY) is True
        assert is_buy_fill(PaperAction.SELL) is False

    def test_closing_a_long_sells(self) -> None:
        assert is_buy_fill(PaperAction.CLOSE, PaperSide.LONG) is False

    def test_closing_a_short_buys(self) -> None:
        assert is_buy_fill(PaperAction.CLOSE, PaperSide.SHORT) is True

    def test_closing_without_a_side_is_rejected(self) -> None:
        with pytest.raises(PaperTradingError, match="requires the side"):
            is_buy_fill(PaperAction.CLOSE)


class TestFillPrice:
    def test_costs_always_move_against_the_trader(self) -> None:
        config = PaperSimulatorConfig(spread_points=1.0, slippage_points=0.5)

        assert calculate_fill_price(100.0, True, config) == pytest.approx(101.5)
        assert calculate_fill_price(100.0, False, config) == pytest.approx(98.5)

    def test_a_costless_config_fills_at_the_reference(self) -> None:
        config = PaperSimulatorConfig()

        assert calculate_fill_price(100.0, True, config) == 100.0
        assert calculate_fill_price(100.0, False, config) == 100.0

    def test_a_non_positive_reference_is_rejected(self) -> None:
        with pytest.raises(PaperTradingError, match="reference_price"):
            calculate_fill_price(0.0, True, PaperSimulatorConfig())

    def test_costs_that_wipe_out_the_price_are_rejected(self) -> None:
        config = PaperSimulatorConfig(spread_points=100.0)

        with pytest.raises(PaperTradingError, match="zero or below"):
            calculate_fill_price(50.0, False, config)

    def test_the_reference_follows_the_configured_bar_side(self) -> None:
        bar = build_bar()

        assert resolve_reference_price(bar, PaperSimulatorConfig()) == 100.0
        assert resolve_reference_price(
            bar,
            PaperSimulatorConfig(fill_on_bar_open=False),
        ) == 102.0


class TestLevelHits:
    def test_a_long_stop_triggers_on_the_low(self) -> None:
        position = build_position(stop_loss=96.0)

        assert is_stop_loss_hit(position, build_bar(low=95.0)) is True
        assert is_stop_loss_hit(position, build_bar(low=97.0, close=98.0)) is False

    def test_a_short_stop_triggers_on_the_high(self) -> None:
        position = build_position(side=PaperSide.SHORT, stop_loss=104.0)

        assert is_stop_loss_hit(position, build_bar(high=105.0)) is True
        assert is_stop_loss_hit(
            position,
            build_bar(high=103.0, close=102.0),
        ) is False

    def test_a_long_target_triggers_on_the_high(self) -> None:
        position = build_position(take_profit=104.0)

        assert is_take_profit_hit(position, build_bar(high=105.0)) is True

    def test_a_short_target_triggers_on_the_low(self) -> None:
        position = build_position(side=PaperSide.SHORT, take_profit=96.0)

        assert is_take_profit_hit(position, build_bar(low=95.0)) is True

    def test_a_position_without_levels_never_triggers(self) -> None:
        position = build_position()

        assert is_stop_loss_hit(position, build_bar()) is False
        assert is_take_profit_hit(position, build_bar()) is False


class TestResolvePositionExit:
    def test_no_exit_when_no_level_is_reached(self) -> None:
        position = build_position(stop_loss=90.0, take_profit=110.0)

        decision = resolve_position_exit(
            position,
            build_bar(),
            PaperSimulatorConfig(),
        )

        assert decision.should_exit is False
        assert decision.exit_reason is None
        assert decision.exit_price is None

    def test_a_stop_exit_uses_the_stop_price(self) -> None:
        position = build_position(stop_loss=96.0, take_profit=110.0)

        decision = resolve_position_exit(
            position,
            build_bar(),
            PaperSimulatorConfig(),
        )

        assert decision.should_exit is True
        assert decision.exit_reason == PaperExitReason.STOP_LOSS
        assert decision.exit_price == 96.0

    def test_a_target_exit_uses_the_target_price(self) -> None:
        position = build_position(stop_loss=90.0, take_profit=104.0)

        decision = resolve_position_exit(
            position,
            build_bar(),
            PaperSimulatorConfig(),
        )

        assert decision.should_exit is True
        assert decision.exit_reason == PaperExitReason.TAKE_PROFIT
        assert decision.exit_price == 104.0

    def test_a_bar_hitting_both_levels_defaults_to_the_stop(self) -> None:
        """The pessimistic side wins unless the caller says otherwise."""

        position = build_position(stop_loss=96.0, take_profit=104.0)

        decision = resolve_position_exit(
            position,
            build_bar(),
            PaperSimulatorConfig(),
        )

        assert decision.exit_reason == PaperExitReason.STOP_LOSS

    def test_the_intrabar_policy_can_prefer_the_target(self) -> None:
        position = build_position(stop_loss=96.0, take_profit=104.0)

        decision = resolve_position_exit(
            position,
            build_bar(),
            PaperSimulatorConfig(
                intrabar_exit_policy=IntrabarExitPolicy.TAKE_PROFIT_FIRST
            ),
        )

        assert decision.exit_reason == PaperExitReason.TAKE_PROFIT
        assert decision.exit_price == 104.0

    def test_a_closed_position_never_exits_again(self) -> None:
        position = build_position(
            stop_loss=96.0,
            status=PaperPositionStatus.CLOSED,
        )

        decision = resolve_position_exit(
            position,
            build_bar(),
            PaperSimulatorConfig(),
        )

        assert decision.should_exit is False

    def test_a_bar_for_another_symbol_is_ignored(self) -> None:
        position = build_position(stop_loss=96.0)

        decision = resolve_position_exit(
            position,
            build_bar(symbol="EURUSD"),
            PaperSimulatorConfig(),
        )

        assert decision.should_exit is False

    def test_decision_to_dict(self) -> None:
        position = build_position(stop_loss=96.0)

        payload = resolve_position_exit(
            position,
            build_bar(),
            PaperSimulatorConfig(),
        ).to_dict()

        assert payload == {
            "should_exit": True,
            "exit_reason": "stop_loss",
            "exit_price": 96.0,
        }


class TestGrossPnl:
    def test_a_winning_long(self) -> None:
        assert calculate_gross_pnl(
            PaperSide.LONG,
            entry_price=100.0,
            exit_price=110.0,
            quantity=2.0,
        ) == pytest.approx(20.0)

    def test_a_losing_long(self) -> None:
        assert calculate_gross_pnl(
            PaperSide.LONG,
            entry_price=100.0,
            exit_price=95.0,
            quantity=2.0,
        ) == pytest.approx(-10.0)

    def test_a_winning_short(self) -> None:
        assert calculate_gross_pnl(
            PaperSide.SHORT,
            entry_price=100.0,
            exit_price=90.0,
            quantity=3.0,
        ) == pytest.approx(30.0)

    def test_a_losing_short(self) -> None:
        assert calculate_gross_pnl(
            PaperSide.SHORT,
            entry_price=100.0,
            exit_price=105.0,
            quantity=1.0,
        ) == pytest.approx(-5.0)

    def test_the_contract_size_scales_the_result(self) -> None:
        assert calculate_gross_pnl(
            PaperSide.LONG,
            entry_price=100.0,
            exit_price=101.0,
            quantity=2.0,
            point_value=100.0,
        ) == pytest.approx(200.0)

    @pytest.mark.parametrize(
        "kwargs, message",
        [
            ({"entry_price": 0.0}, "prices must be positive"),
            ({"exit_price": -1.0}, "prices must be positive"),
            ({"quantity": 0.0}, "quantity must be positive"),
            ({"point_value": 0.0}, "point_value must be positive"),
        ],
    )
    def test_invalid_inputs_are_rejected(
        self,
        kwargs: dict[str, float],
        message: str,
    ) -> None:
        payload = {
            "side": PaperSide.LONG,
            "entry_price": 100.0,
            "exit_price": 110.0,
            "quantity": 1.0,
        }
        payload.update(kwargs)

        with pytest.raises(PaperTradingError, match=message):
            calculate_gross_pnl(**payload)
