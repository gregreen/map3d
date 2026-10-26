"""Small helpers shared by the views."""

from __future__ import annotations

import numpy as np


def array_like(x) -> bool:
    return hasattr(x, "__len__") and not isinstance(x, (str, bytes))


def filter_dict(d: dict, decimals: int = 5) -> dict:
    """Round floats in a dict of arrays/scalars, converting to plain Python types."""
    out = {}
    for key, value in d.items():
        if isinstance(value, np.ndarray):
            if value.dtype.kind in "iu":
                out[key] = value.tolist()
            else:
                out[key] = np.around(value.tolist(), decimals=decimals).tolist()
        elif isinstance(value, (float, np.floating)):
            out[key] = round(float(value), decimals)
        elif isinstance(value, (int, np.integer)):
            out[key] = int(value)
        elif isinstance(value, (bool, np.bool_)):
            out[key] = bool(value)
        else:
            out[key] = value
    return out


def filter_NaN(obj, replace=None):
    """Recursively replace NaNs with ``replace`` inside nested containers."""
    if isinstance(obj, list):
        return [filter_NaN(o, replace) for o in obj]
    elif isinstance(obj, tuple):
        return tuple(filter_NaN(o, replace) for o in obj)
    elif isinstance(obj, dict):
        return {k: filter_NaN(v, replace) for k, v in obj.items()}
    elif isinstance(obj, (float, np.floating)) and np.isnan(obj):
        return replace
    elif isinstance(obj, np.ndarray):
        return filter_NaN(obj.tolist(), replace)
    return obj


def scalar(value):
    """Convert a 0-d array / numpy scalar to a plain Python value."""
    if isinstance(value, np.ndarray):
        if value.ndim == 0:
            value = value[()]
        elif value.size == 1:
            value = value.reshape(-1)[0]
        else:
            return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value
