"""
WorkFlow — unified CLI for LaTeX projects, exercises, lectures, and knowledge graph.
"""

import click

from workflow.db.cli import db
from workflow.tikz.cli import tikz
from workflow.validation.cli import validate
from workflow.exercise.cli import exercise
from workflow.lecture.cli import lectures
from workflow.graph.cli import graph
from workflow.notes.cli import notes
from workflow.evaluation.cli import evaluations, item, course
from workflow.prisma.cli import prisma
from workflow.project.cli import project
from workflow.vault.cli import vault


@click.group("workflow")
def cli():
    """WorkFlow: manage LaTeX projects, exercises, lectures, and knowledge graph."""


cli.add_command(db)
cli.add_command(tikz)
cli.add_command(validate)
cli.add_command(exercise)
cli.add_command(lectures)
cli.add_command(graph)
cli.add_command(notes)
cli.add_command(evaluations)
cli.add_command(item)
cli.add_command(course)
cli.add_command(prisma)
cli.add_command(project)
cli.add_command(vault)


if __name__ == "__main__":
    cli()
