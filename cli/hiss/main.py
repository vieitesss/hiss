"""hiss CLI entry point."""

import typer

from hiss.comments import comments_app
from hiss.issues import issues_app
from hiss.labels import labels_app
from hiss.projects import projects_app

app = typer.Typer(
    add_completion=False,
    help="hiss — issue tracker CLI (Typer + httpx client for the hiss API)",
)


@app.callback()
def callback(
    ctx: typer.Context,
    url: str = typer.Option(
        None,
        "--url",
        help="API base URL (overrides HISS_URL, default http://localhost:8000)",
        envvar="HISS_URL",
        show_default=False,
    ),
) -> None:
    """hiss — manage Projects, Issues, Comments and Labels from the terminal."""
    ctx.ensure_object(dict)
    ctx.obj["url"] = url


app.add_typer(projects_app, name="projects", help="Manage Projects")
app.add_typer(issues_app, name="issues", help="Manage Issues")
app.add_typer(comments_app, name="comments", help="Manage Comments")
app.add_typer(labels_app, name="labels", help="Manage Labels")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
