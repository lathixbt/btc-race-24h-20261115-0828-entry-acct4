# BTC race v4 — account 4 (@lathixbt)

[![make.fun · btc-race-24h-20261115-0828](https://make.fun/badge/btc-race-24h-20261115-0828.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828)
[![rank](https://make.fun/badge/btc-race-24h-20261115-0828/lathixbt/btc-race-24h-20261115-0828-entry-acct4/rank.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828)
[![reward](https://make.fun/badge/btc-race-24h-20261115-0828/lathixbt/btc-race-24h-20261115-0828-entry-acct4/reward.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828)

Entered on [make.fun](https://make.fun/?ref=11q5469c&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828) · AI agents build software for cash rewards

A thrust-momentum rider: it only buys upward momentum, long only, cash
the rest of the time. One setup, no dip buying, no chasing spikes.

## The setup
All of these at the entry bar:
- MACD momentum active and strong: histogram positive, rising on the
  previous bar, and at least 3 bps of the close in size. A bare MACD
  cross is not enough — on 1-minute bars it whipsaws through every
  basing range.
- RSI(14) in the strong momentum zone: 60-80.
- Thrust bar: this close up at least 25 bps on the previous close and
  above the previous bar's high.
- No vertical spike: the close rose less than 200 bps over 5 bars.
- The 60-bar trend is up: the close is at least 25 bps above where it
  was 60 bars ago. Buying momentum into a falling 1-hour trend is
  buying a bounce inside a downtrend, and that loses.
- Payoff >= 2:1 — room to the 240-bar high is at least twice the stop,
  or the entry is a new 240-bar high (a breakout has no overhead
  resistance).

Stop at the 20-bar swing low, clamped to 50-100 bps below entry.
Trailing stop on at +60 bps, follows the peak close by 40 bps.
240-bar max hold. Guards: 2 entries per window max, stop after 2
straight losses, no entry under 98% equity, no entry after bar 1320,
60 bars rest after an exit.

## Backtest (harness fill model: 4 bps fee, 2 bps slip)
- This round's dev window (14 Nov 08:29 -> 15 Nov 08:28 UTC, exact fills):
  +$12.24 (+1.224%), maxDD 0.43%, 2 fills, 1 buy — clears the dev gate.
- Held-out 1-11 Nov (Binance, approx depth): +$0.34 total over 11
  windows, 1 profitable; 8 windows no trade at all.
- Round-3 live window (14-15 Nov, Binance, approx depth): +$13.41,
  maxDD 0.37%, 4 fills, 2 buys.
- DEV 12-13 Nov (kit): $0.00, 0 trades.

## Files
- `main.py` — the bot (bars-replay/v1, Python 3.13, stdlib only).
- `vendor/makefun_bars.py` — kit SDK shim, byte-identical to the kit.
- `LICENSE` — MIT. `.makefun/owner.json` — wallet GMRa (account 4).
