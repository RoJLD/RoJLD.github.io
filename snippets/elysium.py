import numpy as np

def sage_layer(H, A, W_self, W_neigh):
    """Une couche GraphSAGE-mean : agrège les voisins puis combine au self."""
    deg = A.sum(axis=1, keepdims=True)
    neigh = (A @ H) / np.clip(deg, 1, None)   # moyenne des voisins
    out = H @ W_self + neigh @ W_neigh         # self + voisinage
    return np.maximum(out, 0.0)                # ReLU
