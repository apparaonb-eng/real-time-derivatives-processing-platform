# Real-Time Derivatives Processing Platform (Base Project)

A minimal, dependency-free foundation for a streaming derivatives valuation and risk system.

## Architecture
```
SimulatedFeed ──ticks──► asyncio.Queue ──► Engine ──► subscribers (console / API / DB)
                                            │
                          Pricing (Black-Scholes, Greeks, IV, futures)
                          Portfolio (positions, avg price, realized/unrealized P&L)
                          Risk (delta / gamma / vega / loss limits → alerts)
```

| Module | Purpose |
|---|---|
| `dpp/models.py` | Tick, Option, Future, Trade, Position, Valuation |
| `dpp/pricing.py` | Black-Scholes-Merton, Greeks, implied vol, futures, parity check |
| `dpp/market_data.py` | GBM-based async tick simulator |
| `dpp/engine.py` | Tick consumer, revaluation, portfolio Greeks, pub/sub |
| `dpp/risk.py` | Limit checks and alerts |
| `main.py` | Demo with a sample book |

## Run
```bash
python main.py --seconds 10
pytest -q
```

## Extending
- Swap `SimulatedFeed` for Kafka / WebSocket / FIX consumers (just push `Tick` onto the queue).
- Add a per-option volatility surface instead of one vol per underlying.
- Subscribe a FastAPI/WebSocket publisher or a database writer via `engine.subscribe(...)`.
- Add models: binomial trees, Monte Carlo, American options, VaR.
