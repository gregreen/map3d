"""Flask CLI commands for statistics maintenance and data checks."""

from __future__ import annotations

import sys

import click
from flask import current_app


def register_cli(app) -> None:
    @app.cli.command("stats-export")
    @click.option("--days", default=365, show_default=True, help="Look-back window in days.")
    @click.option(
        "--output", "-o", default="-", help="Output file, or '-' for stdout."
    )
    def stats_export(days: int, output: str):
        """Export anonymous usage aggregates as CSV."""
        stats = current_app.extensions["map3d"].stats
        text = stats.export_csv(days=days)
        if output == "-":
            sys.stdout.write(text)
        else:
            with open(output, "w", encoding="utf-8") as fh:
                fh.write(text)
            click.echo(f"wrote {output}")

    @app.cli.command("stats-summary")
    @click.option("--days", default=30, show_default=True)
    def stats_summary(days: int):
        """Print per-map totals for the last N days."""
        stats = current_app.extensions["map3d"].stats
        rows = stats.totals(days=days)
        if not rows:
            click.echo("no data")
            return
        click.echo("{:<20} {:>10} {:>12} {:>12}".format("map", "queries", "coords", "seconds"))
        for row in rows:
            click.echo(
                "{:<20} {:>10} {:>12} {:>12.1f}".format(
                    row["map"], row["n_queries"], row["n_coords"], row["total_seconds"]
                )
            )

    @app.cli.command("stats-purge")
    def stats_purge():
        """Delete aggregates older than the configured retention period."""
        svc = current_app.extensions["map3d"]
        removed = svc.stats.purge()
        click.echo(f"purged {removed} usage rows")

    @app.cli.command("maps")
    def maps_command():
        """List configured maps and whether their data is present."""
        svc = current_app.extensions["map3d"]
        images = set(svc.stamps.available_maps())
        for name in svc.registry.names():
            spec = svc.registry.spec(name)
            click.echo(
                "{:<16} {:<4} stamps={}".format(
                    name, spec.kind, "yes" if name in images else "no"
                )
            )

    @app.cli.command("rate-limit-purge")
    def rate_limit_purge():
        """Drop expired rate-limit counters."""
        removed = current_app.extensions["map3d"].limiter.purge()
        click.echo(f"purged {removed} counters")
