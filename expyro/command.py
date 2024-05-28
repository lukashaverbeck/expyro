from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Union, Any

import tyro.extras

from .experiment import Experiment, Run


@dataclass
class Location:
    location: tyro.conf.Positional[str]
    """name of the experiment in the experiment directory or absolute path to where it is located"""

    absolute: bool = False
    """whether the path is an absolute path or a name of the experiment in the experiment directory"""

    def run(self, experiment: Experiment) -> Run:
        path = Path(self.location) if self.absolute else self.location
        return experiment[path]


class PlotLocation(Location):
    pass


class ReproduceLocation(Location):
    pass


def make_experiment_parser(experiment: Experiment):
    if experiment.signature.config_cls is None:
        raise TypeError("Procedure must have a type hint for the configuration class to be used as a CLI argument.")

    @tyro.conf.configure(tyro.conf.OmitSubcommandPrefixes)
    def parse_experiment(command: Union[
        Annotated[PlotLocation, tyro.conf.subcommand(
            name="plot", description="regenerate plots from existing config and result"
        )],
        Annotated[ReproduceLocation, tyro.conf.subcommand(
            name="reproduce", description="rerun experiment from config of a previous run"
        )],
        Annotated[experiment.signature.config_cls, tyro.conf.subcommand(
            name="run", description="run the experiment"
        )]
    ]):
        if isinstance(command, PlotLocation):
            folder = command.run(experiment).plot()
            print(f"Saved to '{folder}'")
        elif isinstance(command, ReproduceLocation):
            run = command.run(experiment).reproduce()
            print(f"Saved to '{run.location}'")
        elif isinstance(command, experiment.signature.config_cls):
            run = experiment(command)
            print(f"Saved to '{run.location}'")
        else:
            raise NotImplementedError("Unknown command")

    return parse_experiment


def cli(experiment: Experiment) -> tuple[Any, list[str]]:
    parser = make_experiment_parser(experiment)
    return tyro.cli(parser)


def multi_cli(*experiments: Experiment):
    subcommands = {}

    if not experiments:
        raise ValueError("At least one experiment must be provided.")

    if len(experiments) == 1:
        return cli(experiments[0])

    for experiment_ in experiments:
        parser = make_experiment_parser(experiment_)
        subcommands[experiment_.name] = parser

    return tyro.extras.subcommand_cli_from_dict(subcommands)
