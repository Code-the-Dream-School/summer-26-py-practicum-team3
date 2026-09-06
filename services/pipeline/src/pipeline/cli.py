from __future__ import annotations

from urllib.parse import urlparse

import rich_click as click

from pipeline.common.config import settings
from pipeline.common.db import get_connection, normalize_dsn
from pipeline.orchestration import run_pipeline_job
from pipeline.run_tracking import list_pipeline_runs

DB_TABLES = (
    "cities",
    "pipeline_runs",
    "raw_geocoding_responses",
    "raw_air_pollution_responses",
    "air_pollution_gold",
)


@click.group()
def main() -> None:
    """Pipeline command-line tools."""


@main.command()
def run() -> None:
    """Run the pipeline through the shared runner."""
    try:
        result = run_pipeline_job()

        click.secho("✓ Pipeline completed successfully.", fg="green")
        click.echo(f"Run ID: {result.run_id}")

    except Exception as exc:
        click.secho(
            f"✗ Pipeline failed: {exc}",
            fg="red",
            err=True,
        )
        raise click.ClickException(str(exc)) from exc


@main.command()
@click.option(
    "--limit",
    default=10,
    show_default=True,
    type=int,
)
def runs(limit: int) -> None:
    """Display recent pipeline runs."""
    try:
        records = list_pipeline_runs(limit=limit)

        if not records:
            click.echo("No pipeline runs found.")
            return

        click.secho("Pipeline Runs", fg="cyan", bold=True)
        click.echo()

        for record in records:
            status_color = {
                "succeeded": "green",
                "failed": "red",
                "running": "yellow",
            }.get(record.status, "white")

            click.secho(
                f"{record.run_id}  {record.status}",
                fg=status_color,
                bold=True,
            )

            click.echo(
                f"  Pipeline Run ID: {record.pipeline_run_id}\n"
                f"  Source:          {record.source}\n"
                f"  Cities:          {record.city_count}\n"
                f"  Raw records:     {record.raw_response_count}\n"
                f"  Gold rows:       {record.gold_row_count}"
            )

            if record.error_message:
                click.secho(
                    f"  Error:           {record.error_message}",
                    fg="red",
                )

            click.echo()
            
    except Exception as exc:
        raise click.ClickException(
            f"Unable to retrieve pipeline runs: {exc}"
        ) from exc

@main.command()
def db() -> None:
    """Display basic database information."""
    db_url = settings.database_url.get_secret_value()
    if not db_url:
        click.echo("DATABASE_URL is not configured; pipeline runs write Parquet only.")
        return

    try:
        conn = get_connection()
    except Exception as exc:
        click.secho(f"✗ Could not connect: {exc}", fg="red", err=True)
        raise click.ClickException(str(exc)) from exc

    try:
        parsed = urlparse(normalize_dsn(db_url))
        click.secho("Connected to PostgreSQL", fg="green", bold=True)
        click.echo(f"Host:     {parsed.hostname}")
        click.echo(f"Database: {parsed.path.lstrip('/')}")
        click.echo()

        with conn.cursor() as cur:
            for table in DB_TABLES:
                cur.execute(f"SELECT COUNT(*) FROM {table};")
                (count,) = cur.fetchone()
                click.echo(f"  {table}: {count}")
    finally:
        conn.close()