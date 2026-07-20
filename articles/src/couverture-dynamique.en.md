---
tldr: delta hedging works well in theory, but transaction costs, stochastic volatility and rebalancing constraints make it far more complex in practice. Here is what I learned during my capstone project with EY.
---

## Introduction

As part of my final-year project at ECE Paris, carried out in collaboration with EY, I worked on the **modelling and steering of dynamic hedging strategies** applied to insurance and banking portfolios.

The goal: compare theoretical hedging models (Black-Scholes, local volatility models) against real operational constraints — transaction costs, rebalancing frequency, and basis risk management.

## The theoretical framework

Delta hedging rests on a simple idea: at every instant, you adjust the quantity of the underlying asset held so as to neutralise the portfolio's sensitivity to price movements.

::formula
Δ = ∂V/∂S = N(d₁)   where   d₁ = [ln(S/K) + (r + σ²/2)T] / (σ√T)
::

In theory, with continuous rebalancing and no transaction costs, the P&L of the hedging strategy converges to zero. In practice, it is another story.

### The model's key assumptions

- **Constant volatility** (rarely the case in reality)
- **Continuous rebalancing** (impossible in practice)
- **No transaction costs** (significant on real markets)
- **Perfect liquidity** (not always available)

## Experimental results

We simulated several rebalancing strategies (daily, weekly, delta-threshold based) on both historical and synthetic data. The main observations:

### 1. The impact of rebalancing frequency

Daily rebalancing cuts hedging error by roughly **60%** compared with weekly rebalancing, but raises transaction costs by **400%**. The sweet spot depends heavily on the volatility profile and the bid-ask spread.

### 2. Stochastic vs implied volatility

Using implied rather than historical volatility to compute the delta significantly reduces tracking error. During periods of market stress, however, no approach performs well — hence the interest in stochastic volatility models (Heston, SABR).

### 3. The delta-threshold approach

"Smart" rebalancing — triggered by a threshold on delta variation rather than a fixed frequency — offers the best cost/efficiency trade-off. We found a threshold of **Δ ± 0.05** to be optimal in our simulations.

```
# Simplified threshold-based rebalancing
def should_rebalance(current_delta, target_delta, threshold=0.05):
    return abs(current_delta - target_delta) > threshold

# Hedging loop
for t in range(1, T):
    new_delta = bs_delta(S[t], K, sigma, T-t, r)
    if should_rebalance(portfolio_delta, new_delta):
        trade_quantity = new_delta - portfolio_delta
        execute_trade(trade_quantity)
        portfolio_delta = new_delta
        transaction_costs += abs(trade_quantity) * spread
```

## Lessons learned

> The perfect model does not exist: a quant's real skill is understanding where and how their model will break.

This project taught me that moving from theory to practice in quantitative finance is not a matter of implementing a formula. You have to understand the operational constraints, the hidden costs, and above all be able to quantify the uncertainty of your own models.

If this topic interests you, feel free to reach out — I am always up for a conversation about it.
