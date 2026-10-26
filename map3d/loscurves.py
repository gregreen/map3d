"""ASCII line-of-sight reddening tables offered by the interactive page."""

from __future__ import annotations

from urllib.parse import quote

import numpy as np


def encode_ascii(txt: str) -> str:
    data = txt.encode("US-ASCII", errors="replace")
    return f"data:text/plain;charset=US-ASCII,{quote(data)}"


def los_ascii_summary(
    coords,
    samples,
    best,
    flags=None,
    distmod=np.linspace(4.0, 19.0, 31),
    colwidth: int = 6,
    encode: bool = True,
    units: str = "E(g−r)",
    best_label: str = "BestFit",
):
    """Build a readable table of reddening vs distance modulus.

    `units` names the quantity in the table and `best_label` the row that holds
    the single curve (a best fit where the map has one, otherwise its mean), so
    that the header is right for every map.
    """
    frame = coords.frame.name
    if frame == "galactic":
        coord_txt = (
            "# Galactic coordinates (in degrees):\n"
            f"#     l = {coords.l.deg:.4f}\n"
            f"#     b = {coords.b.deg:.4f}\n"
        )
    else:
        coord_txt = (
            f"# Equatorial (J2000, {str(frame.upper()):s}) coordinates (in degrees):\n"
            f"#     ra = {coords.ra.deg:.4f}\n"
            f"#     dec = {coords.dec.deg:.4f}\n"
        )

    if flags is not None:
        reliable_txt = (
            "# Reliable distance moduli:\n"
            "#     min: {min_reliable_distmod:.2f}\n"
            "#     max: {max_reliable_distmod:.2f}\n"
            "# Fit converged: {converged:}\n"
        ).format(
            min_reliable_distmod=flags["min_reliable_distmod"],
            max_reliable_distmod=flags["max_reliable_distmod"],
            converged=flags["converged"],
        )
    else:
        reliable_txt = (
            "# Reliable distance moduli:\n"
            "#     min: (not reported by this map)\n"
            "#     max: (not reported by this map)\n"
            "# Fit converged: (not reported by this map)\n"
        )

    header = (
        "#\n"
        "# Line-of-Sight Reddening Results\n"
        "# ===============================\n"
        "#\n"
        f"# {coord_txt:s}"
        "#\n"
        f"{reliable_txt:s}"
    )

    first_row = {"BestFit": "best fit", "Mean": "mean"}.get(best_label, best_label.lower())

    explanation = (
        "#\n"
        f"# The table contains {units:s} in magnitudes out to the specified distance moduli.\n"
        "# Each column corresponds to a different distance modulus, and each row\n"
        f"# corresponds to a different sample. The first row is the {first_row:s},\n"
        "# and the rows below it are drawn from the posterior distribution of\n"
        "# distance-reddening profiles.\n"
        "#\n"
        "# See the papers for each map (https://argonaut.skymaps.info/papers) for\n"
        "# how the line-of-sight reddening is computed. To convert to extinction in\n"
        "# other bands, use the coefficients in Table 6 of Schlafly & Finkbeiner\n"
        "# (2011), or the extinction curve published with the map.\n"
        "#\n"
    )

    table = "SampleNo".center(10) + "| DistanceModulus\n"
    table += "".center(10) + "|"
    table += "".join([f"{dm:.2f}".rjust(colwidth) for dm in distmod])
    table += "\n" + "-" * (11 + len(distmod) * colwidth) + "\n"

    table += best_label.center(10) + "|"
    table += "".join([f"{E:.3f}".rjust(colwidth) for E in np.atleast_1d(best)])
    table += "\n"

    if samples is not None:
        for k, samp in enumerate(np.atleast_2d(samples)):
            table += f"{k:^10d}" + "|"
            table += "".join([f"{E: >6.3f}" for E in samp])
            table += "\n"

    text = header + explanation + table
    return encode_ascii(text) if encode else text
