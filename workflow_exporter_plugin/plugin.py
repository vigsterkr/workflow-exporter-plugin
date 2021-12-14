from uuid import uuid4

import click
from lazy_object_proxy import Proxy


from renku.cli.utils.plugins import supported_formats
from renku.cli.utils.callback import ClickCallback
from renku.core.management.command_builder import inject
from renku.core.management.command_builder.command import Command
from renku.core.management.interface.activity_gateway import IActivityGateway
from renku.core.management.interface.client_dispatcher import IClientDispatcher
from renku.core.management.workflow.activity import sort_activities
from renku.core.commands.update import _get_downstream_activities
from renku.core.models.workflow.composite_plan import CompositePlan
from renku.core.utils.metadata import filter_overridden_activities
from renku.core.utils.os import get_relative_paths


@inject.autoparams()
def _export(
    client_dispatcher: IClientDispatcher,
    activity_gateway: IActivityGateway,
    paths,
    format,
    output,
):
    from renku.core.plugins.workflow import workflow_converter

    client = client_dispatcher.current_client

    paths = get_relative_paths(base=client.path, paths=paths)
    all_activities = activity_gateway.get_all_activities()
    relevant_activities = filter_overridden_activities(all_activities)
    activities = _get_downstream_activities(
        relevant_activities, activity_gateway, paths
    )
    activities = sort_activities(activities, remove_overridden_parents=False)
    plans = [a.plan_with_values for a in activities]

    workflow = CompositePlan(
        id=CompositePlan.generate_id(),
        plans=plans,
        name=f"plan-collection-{uuid4().hex}",
    )

    converter = workflow_converter(format)
    return converter(
        workflow=workflow, basedir=client.path, output=output, output_format=format
    )


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option(
    "--format",
    default="cwl",
    type=click.Choice(Proxy(supported_formats), case_sensitive=False),
    show_default=True,
    help="Workflow language format.",
)
@click.option(
    "-o",
    "--output",
    metavar="<path>",
    type=click.Path(exists=False),
    default=None,
    help="Save to <path> instead of printing to terminal",
)
def export(paths, format, output):
    """Export a workflow for given files."""

    communicator = ClickCallback()

    result = (
        Command()
        .command(_export)
        .with_communicator(communicator)
        .with_database()
        .build()
        .execute(paths=paths, format=format, output=output)
    )

    if not output:
        click.echo(result.output)
