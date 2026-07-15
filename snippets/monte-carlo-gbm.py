import numpy as np

def gbm_paths(S0, mu, sigma, T, steps, n):
    dt = T / steps
    Z = np.random.standard_normal((n, steps))
    incr = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z
    return S0 * np.exp(np.cumsum(incr, axis=1))
