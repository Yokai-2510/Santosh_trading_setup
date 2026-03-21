"""report — backtesting performance reporting and analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from orders.position_manager import ClosedTrade


@dataclass
class BacktestResult:
    """Complete backtesting result with trade list and performance metrics."""
    trades: List[ClosedTrade] = field(default_factory=list)
    total_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    max_drawdown: float = 0.0
    max_profit: float = 0.0
    win_rate: float = 0.0
    avg_pnl_per_trade: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    profit_factor: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0


def generate_report(trades: List[ClosedTrade]) -> BacktestResult:
    """Compute performance metrics from a list of closed trades."""
    result = BacktestResult(trades=trades)

    if not trades:
        return result

    result.total_trades = len(trades)
    pnls = [t.realised_pnl for t in trades]
    result.total_pnl = sum(pnls)

    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]

    result.winning_trades = len(winners)
    result.losing_trades = len(losers)
    result.win_rate = (result.winning_trades / result.total_trades * 100) if result.total_trades > 0 else 0.0

    result.avg_pnl_per_trade = result.total_pnl / result.total_trades if result.total_trades > 0 else 0.0
    result.avg_winner = sum(winners) / len(winners) if winners else 0.0
    result.avg_loser = sum(losers) / len(losers) if losers else 0.0

    result.largest_win = max(pnls) if pnls else 0.0
    result.largest_loss = min(pnls) if pnls else 0.0

    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))
    result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

    # Max drawdown (peak-to-trough in cumulative P&L)
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    max_pf = 0.0
    for pnl in pnls:
        cumulative += pnl
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd = max(max_dd, dd)
        max_pf = max(max_pf, cumulative)

    result.max_drawdown = max_dd
    result.max_profit = max_pf

    return result


def print_report(result: BacktestResult) -> str:
    """Format a human-readable performance report."""
    lines = [
        "=" * 50,
        "  BACKTEST PERFORMANCE REPORT",
        "=" * 50,
        f"  Total Trades:       {result.total_trades}",
        f"  Total P&L:          {result.total_pnl:,.2f}",
        f"  Win Rate:           {result.win_rate:.1f}%",
        f"  Winning Trades:     {result.winning_trades}",
        f"  Losing Trades:      {result.losing_trades}",
        "-" * 50,
        f"  Avg P&L per Trade:  {result.avg_pnl_per_trade:,.2f}",
        f"  Avg Winner:         {result.avg_winner:,.2f}",
        f"  Avg Loser:          {result.avg_loser:,.2f}",
        f"  Largest Win:        {result.largest_win:,.2f}",
        f"  Largest Loss:       {result.largest_loss:,.2f}",
        "-" * 50,
        f"  Profit Factor:      {result.profit_factor:.2f}",
        f"  Max Drawdown:       {result.max_drawdown:,.2f}",
        f"  Peak Cumulative:    {result.max_profit:,.2f}",
        "=" * 50,
    ]

    # Trade list
    if result.trades:
        lines.append("")
        lines.append("  TRADE LOG")
        lines.append("-" * 80)
        lines.append(f"  {'#':>3}  {'Symbol':<25} {'Entry':>10} {'Exit':>10} {'P&L':>12} {'Reason':<15}")
        lines.append("-" * 80)
        for i, t in enumerate(result.trades, 1):
            lines.append(
                f"  {i:>3}  {t.trading_symbol:<25} {t.entry_price:>10.2f} "
                f"{t.exit_price:>10.2f} {t.realised_pnl:>12.2f} {t.exit_reason:<15}"
            )

    return "\n".join(lines)
