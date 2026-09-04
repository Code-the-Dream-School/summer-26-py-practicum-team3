from __future__ import annotations

import rich_click as click

from pipeline.orchestration import run_pipeline_job
from pipeline.run_tracking import list_pipeline_runs


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

		# TODO: Once PostgreSQL-backed run tracking is wired up, remove the in-memory persistence note below because run history will persist between CLI invocations.
        if not records:
            click.echo("No pipeline runs found.\n\nNote: run history currently uses the in-memory AIR-22 repository and does not persist between CLI invocations.")
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
    # TODO: Use the shared database connection layer once it is available.
    click.echo("Database information is not available yet.")