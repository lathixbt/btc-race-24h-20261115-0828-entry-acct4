"""BTC race bot — thrust momentum (long only, one setup).

The idea: BTC trends in bursts. This bot sits in cash and waits for a
genuine uptrend to confirm itself on several independent readings at once,
then buys the momentum at full size and rides it with a trailing stop. It
never buys a dip, never buys a falling knife, and never chases a vertical
spike. The signal is deliberately fast — a strong, rising MACD histogram, not
a slow moving-average alignment — because on 1-minute bars a trend that
waits for the slow averages to line up is already over. And it is
deliberately strong: a bare MACD cross whipsaws through every basing
range, so the histogram must be big and rising and the bar itself a
thrust. No setup means no trade.

Entry (all of these at bar i):
  1. MACD momentum is ACTIVE and STRONG: the histogram is positive,
     rising on the previous bar, and at least 3 bps of the close in
     size. A bare cross is not enough — on 1-minute bars the MACD
     whipsaws through basing ranges, and only a strong, rising
     histogram marks a real thrust.
  2. RSI(14) in the strong momentum zone: 60 <= RSI <= 80.
  3. Thrust bar: this close is up at least 25 bps on the previous
     close and above the previous bar's high.
  4. No vertical spike: the close rose less than 200 bps over the last
     5 bars (a parabolic 5-bar jump is chased by nobody here).
  5. The 60-bar trend is up: the close is at least 25 bps above where
     it was 60 bars ago. Buying momentum into a falling 1-hour trend is
     buying a bounce inside a downtrend, and that loses; the thrust
     must come with the hour already rising.
  6. Reward-to-risk: the stop sits at the 20-bar swing low, clamped to
     50-100 bps under the entry (risk 0.5-1% of equity on a full-size
     buy); the room back to the 240-bar high is at least twice the risk,
     OR the entry is a new 240-bar high (a breakout has no overhead
     resistance, so the room is open-ended).

Exit: a hard stop under the swing low, a trailing stop that arms at
+60 bps and trails the peak close by 40 bps, a MACD bearish cross,
RSI(14) falling under 50, or a 240-bar maximum hold — whichever comes
first.

Guards: at most 2 entries per window (2 trades a day), stop after 2
consecutive losses, never enter under 98% of starting equity, no
entries after bar 1320, and a 60-bar cooldown after any exit.

Backtest (faithful harness fill model: 4 bps fee, 2 bps slip, exact
depth on the kit window): this round's dev window (14 Nov 08:29 ->
15 Nov 08:28 UTC) +$12.24 (+1.224%), maxDD 0.43%, 1 buy — clears the
dev gate. Held-out 1-11 Nov (Binance, approx depth) +$0.34 over 11
windows, 1 profitable, 8 windows with no trade. Round-3 live window
(14-15 Nov, Binance, approx depth) +$13.41, maxDD 0.37%, 2 buys.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
BPS = 10_000

# --- entry thresholds (basis points unless noted) -------------------------
RSI_LOW = 60             # RSI must be at least this (strong momentum zone)
RSI_HIGH = 80            # RSI must be at most this (not extremely overbought)
SPIKE_5BARS = 200        # max rise over 5 bars (no chasing a spike)
THRUST_BPS = 25          # this bar must close up at least this many bps
HIST_MIN_BPS = 3         # MACD histogram must be at least this many bps of the close
MIN_RR = 2               # reward must be >= 2x the risk
SWING_BARS = 20          # stop sits at the low of this many bars
TREND_BARS = 60          # the 1-hour trend lookback
TREND_MIN_BPS = 25       # the 60-bar change must be at least this
ROOM_BARS = 240          # reward room measured to the high of this many bars

# --- exits ----------------------------------------------------------------
STOP_FLOOR_BPS = 50      # stop never closer than this under the entry
STOP_CEIL_BPS = 100      # stop never further than this under the entry
TRAIL_ARM_BPS = 60       # trailing stop arms once price is this far above entry
TRAIL_GAP_BPS = 40       # trailing stop trails the peak close by this much
MAX_HOLD = 240           # bars
RSI_EXIT = 50            # exit when RSI falls under this

# --- guards ---------------------------------------------------------------
MAX_ENTRIES = 2
MAX_LOSERS = 2
EQUITY_FLOOR_BPS = 9_800  # 98% of starting equity
LAST_ENTRY_BAR = 1_320
COOLDOWN = 60
SLIP_BPS = 500           # max slippage on any order (fills are ~1 bar away)
RSI_LEN = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9


def _ema(prev, price, span):
    """One EMA step. prev is None on the first bar (seed with the price)."""
    if prev is None:
        return float(price)
    alpha = 2.0 / (span + 1)
    return price * alpha + prev * (1.0 - alpha)


def _rsi(closes, period, upto):
    """Wilder's RSI(period) of closes[0..upto]. None when not enough data."""
    if upto < period:
        return None
    gain = 0.0
    loss = 0.0
    for k in range(1, period + 1):
        move = closes[k] - closes[k - 1]
        if move > 0:
            gain += move
        else:
            loss -= move
    avg_gain = gain / period
    avg_loss = loss / period
    for k in range(period + 1, upto + 1):
        move = closes[k] - closes[k - 1]
        up = move if move > 0 else 0
        down = -move if move < 0 else 0
        avg_gain = (avg_gain * (period - 1) + up) / period
        avg_loss = (avg_loss * (period - 1) + down) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


class ThrustMomentum:
    """One window of state: the bar tape, the indicators, the open trade."""

    def __init__(self):
        self.closes = []
        self.highs = []
        self.lows = []
        self.macd_fast = None
        self.macd_slow = None
        self.macd_signal = None
        self.hist = []           # MACD histogram per bar (macd - signal)
        self.start_equity = None
        self.entries = 0
        self.losers = 0
        self.cool_until = -1
        # open-trade bookkeeping (decision-bar reference prices)
        self.entry_ref = None
        self.entry_bar = None
        self.stop = None
        self.trail = None
        self.armed = False
        self.peak = None

    def _update_indicators(self, bar):
        """Fold one bar into the MACD. Runs before any
        decision on that bar, so every reading below is current."""
        close = int(bar["c"])
        self.macd_fast = _ema(self.macd_fast, close, MACD_FAST)
        self.macd_slow = _ema(self.macd_slow, close, MACD_SLOW)
        macd = self.macd_fast - self.macd_slow
        self.macd_signal = _ema(self.macd_signal, macd, MACD_SIGNAL)
        self.hist.append(macd - self.macd_signal)

    def _setup(self, i):
        """True when bar i is a confirmed-momentum entry."""
        if i < ROOM_BARS:
            return False
        # 1) MACD momentum active and strong: histogram positive,
        #    rising, and at least HIST_MIN_BPS of the close
        if self.hist[i] <= 0 or self.hist[i] <= self.hist[i - 1]:
            return False
        if self.hist[i] * BPS // self.closes[i] < HIST_MIN_BPS:
            return False
        # 2) RSI in the strong momentum zone
        rsi = _rsi(self.closes, RSI_LEN, i)
        if rsi is None or rsi < RSI_LOW or rsi > RSI_HIGH:
            return False
        # 3) thrust bar: up at least THRUST_BPS on the previous close
        #    and above the previous bar's high
        prev = i - 1
        if self.closes[i] < self.closes[prev] * (BPS + THRUST_BPS) // BPS:
            return False
        if self.closes[i] <= self.highs[prev]:
            return False
        # 4) no vertical spike: less than 200 bps up over 5 bars
        if i >= 5:
            rise = (self.closes[i] - self.closes[i - 5]) * BPS // self.closes[i - 5]
            if rise >= SPIKE_5BARS:
                return False
        # 5) the 60-bar trend is up at least TREND_MIN_BPS
        if i >= TREND_BARS:
            trend = (self.closes[i] - self.closes[i - TREND_BARS]) * BPS // self.closes[i - TREND_BARS]
            if trend < TREND_MIN_BPS:
                return False
        # 6) reward-to-risk: room to the 240-bar high >= 2x the risk,
        #    or a new 240-bar high (breakout: no overhead resistance)
        swing_low = min(self.lows[i - SWING_BARS + 1: i + 1])
        ref = self.closes[i]
        stop_lowest = ref * (BPS - STOP_CEIL_BPS) // BPS
        stop_highest = ref * (BPS - STOP_FLOOR_BPS) // BPS
        stop = swing_low
        if stop < stop_lowest:
            stop = stop_lowest
        if stop > stop_highest:
            stop = stop_highest
        risk = ref - stop
        if risk <= 0:
            return False
        high240 = max(self.highs[i - ROOM_BARS + 1: i + 1])
        high240_prev = max(self.highs[max(0, i - ROOM_BARS): i])
        breakout = ref >= high240_prev
        if not breakout and high240 - ref < MIN_RR * risk:
            return False
        self._pending_stop = stop
        return True

    def on_batch(self, state, batch):
        bar = state.latest.get(SYMBOL)
        if bar is None:
            return []
        self.closes.append(int(bar["c"]))
        self.highs.append(int(bar["h"]))
        self.lows.append(int(bar["l"]))
        self._update_indicators(bar)
        i = state.seq
        if self.start_equity is None:
            self.start_equity = state.equity
        if state.warming_up:
            return []

        holding = state.positions.get(SYMBOL)
        if holding is not None:
            return self._manage(state, i, holding)
        return self._maybe_enter(state, i)

    def _manage(self, state, i, holding):
        """We hold a position: trail the stop, or get out."""
        close = self.closes[i]
        if self.peak is None or close > self.peak:
            self.peak = close
        # arm the trailing stop once price is far enough above the entry
        if not self.armed and self.entry_ref is not None:
            if close >= self.entry_ref * (BPS + TRAIL_ARM_BPS) // BPS:
                self.armed = True
        if self.armed:
            trail = self.peak * (BPS - TRAIL_GAP_BPS) // BPS
            if self.trail is None or trail > self.trail:
                self.trail = trail
        # exit: stop hit, trailing stop hit, momentum died, or held too long
        stop_hit = self.stop is not None and close < self.stop
        trail_hit = self.armed and self.trail is not None and close < self.trail
        macd_dead = (
            len(self.hist) >= 2
            and self.hist[-2] >= 0 > self.hist[-1]
        )
        rsi = _rsi(self.closes, RSI_LEN, i)
        rsi_dead = rsi is not None and rsi < RSI_EXIT
        too_long = self.entry_bar is not None and i - self.entry_bar >= MAX_HOLD
        if stop_hit or trail_hit or macd_dead or rsi_dead or too_long:
            if self.entry_ref is not None and close < self.entry_ref:
                self.losers += 1
            else:
                self.losers = 0
            self.cool_until = i + COOLDOWN
            self.entry_ref = None
            self.entry_bar = None
            self.stop = None
            self.trail = None
            self.armed = False
            self.peak = None
            return [{
                "side": "sell",
                "symbol": SYMBOL,
                "qty": holding.qty,
                "max_slippage_bps": SLIP_BPS,
            }]
        return []

    def _maybe_enter(self, state, i):
        """Flat: enter only when the setup and every guard agree."""
        if self.entries >= MAX_ENTRIES:
            return []
        if self.losers >= MAX_LOSERS:
            return []
        if i > LAST_ENTRY_BAR:
            return []
        if i < self.cool_until:
            return []
        if self.start_equity and state.equity * BPS // self.start_equity < EQUITY_FLOOR_BPS:
            return []
        if state.cash < 1_000_000:
            return []
        self._pending_stop = None
        if not self._setup(i):
            return []
        self.entries += 1
        self.entry_ref = self.closes[i]
        self.entry_bar = i
        self.stop = self._pending_stop
        self.trail = None
        self.armed = False
        self.peak = self.closes[i]
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": state.cash,
            "max_slippage_bps": SLIP_BPS,
        }]


_BOT = ThrustMomentum()


def on_batch(state, batch):
    return _BOT.on_batch(state, batch)


if __name__ == "__main__":
    makefun_bars.run(on_batch)
