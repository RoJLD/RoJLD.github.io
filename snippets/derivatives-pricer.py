from math import log, sqrt, exp, erf

def norm_cdf(x):
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))

def black_scholes(S, K, T, r, sigma):
    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    call = S * norm_cdf(d1) - K * exp(-r * T) * norm_cdf(d2)
    put = K * exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
    return {"call": call, "put": put, "delta": norm_cdf(d1)}
