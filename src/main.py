"""
WorkFlow — unified CLI for LaTeX projects, exercises, lectures, and knowledge graph.
"""

import click

from workflow.tikz.cli import tikz
from workflow.validation.cli import validate
from workflow.exercise.cli import exercise
from workflow.lecture.cli import lectures
from workflow.graph.cli import graph


@click.group("workflow")
def cli():
    """WorkFlow: manage LaTeX projects, exercises, lectures, and knowledge graph."""


cli.add_command(tikz)
cli.add_command(validate)
cli.add_command(exercise)
cli.add_command(lectures)
cli.add_command(graph)


if __name__ == "__main__":
    cli()
