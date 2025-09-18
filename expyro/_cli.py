import ast
import copy
import os
import sys
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, is_dataclass
from importlib import import_module
from pathlib import Path
from typing import Annotated, Union, Iterable

import tyro.extras
from tyro.constructors import UnsupportedTypeAnnotationError

import expyro._experiment
from expyro._experiment import Experiment


@dataclass(frozen=True)
class ExecutableCommand(ABC):
    @abstractmethod
    def __call__(self) -> None:
        raise NotImplementedError


def is_tyro_parseable(t: type) -> bool:
    try:
        tyro.extras.get_parser(t)
    except (AssertionError, UnsupportedTypeAnnotationError) as e:
        return False
    return True


@typing.no_type_check
def make_redo_command[I, O](experiment: Experiment[I, O]):
    artifact_literal = tyro.extras.literal_type_from_choices(sorted(experiment.artifact_names))

    @dataclass(frozen=True)
    class Redo(ExecutableCommand):
        artifact_name: Annotated[artifact_literal, tyro.conf.Positional]  # what to redo
        path: Annotated[str, tyro.conf.Positional]  # path to run

        def __call__(self):
            experiment.redo_artifact(self.artifact_name, self.path)

    return Annotated[Redo, tyro.conf.subcommand(name="redo", description="Recreate artifacts of existing run.")]


def make_reproduce_command[I, O](experiment: Experiment[I, O]):
    @dataclass(frozen=True)
    class Reproduce(ExecutableCommand):
        path: Annotated[str, tyro.conf.Positional]  # path to run

        def __call__(self):
            run = experiment.reproduce(self.path)
            print(f"[expyro] Saved reproduced run to: {run.path.as_uri()}")

    return Annotated[Reproduce, tyro.conf.subcommand(
        name="reproduce", description="Run experiment with config of existing run."
    )]


def make_run_command[I, O](experiment: Experiment[I, O]):
    if not is_tyro_parseable(experiment.signature.type_config):
        @dataclass(frozen=True)
        class RunNotAvailable(ExecutableCommand):
            def __call__(self):
                print(f"[expyro] Cannot run experiment from command line because config "
                      f"`{experiment.signature.type_config}` cannot be parsed.")

        return Annotated[RunNotAvailable, tyro.conf.subcommand(
            name="run", description="Command unavailable. Run without arguments for details."
        )]

    return Annotated[experiment.signature.type_config, tyro.conf.subcommand(
        name="run", description="Run experiment with custom config."
    )]


@typing.no_type_check
def make_default_command[I, O](experiment: Experiment[I, O]):
    if is_tyro_parseable(experiment.signature.type_config):  # overrides possible
        wrapper_classes = set()

        @typing.no_type_check
        def make_option(config) -> type:
            if is_dataclass(experiment.signature.type_config):
                config_cls = experiment.signature.type_config
            else:
                @dataclass(frozen=True)
                class ConfigOption:
                    config: Annotated[experiment.signature.type_config, tyro.conf.Positional] = field(
                        default_factory=lambda: config
                    )

                wrapper_classes.add(ConfigOption)

                config_cls = ConfigOption

            return config_cls

        default_subcommands = [
            Annotated[
                make_option(config),
                tyro.conf.subcommand(name=name, default=config)
            ]
            for name, config in sorted(experiment.default_configs.items())
        ]

        # dummy subcommand ensuring that tyro treats single defaults the same as multiple defaults
        default_subcommands.append(Annotated[None, tyro.conf.Suppress])

        @tyro.conf.configure(tyro.conf.OmitSubcommandPrefixes)
        def parse_default(value: Union[tuple(default_subcommands)]):
            if isinstance(value, experiment.signature.type_config):
                config = value
            elif type(value) in wrapper_classes:
                config = value.config
            else:
                raise ValueError(f"Parsed value `{value}` cannot be converted to config.")

            return copy.deepcopy(config)
    else:  # no overrides possible
        def make_option(config):
            @dataclass(frozen=True)
            class Option:
                def __call__(self):
                    return config

            return Option

        default_subcommands = [
            Annotated[
                make_option(config),
                tyro.conf.subcommand(name=name, default=config)
            ]
            for name, config in sorted(experiment.default_configs.items())
        ]

        # dummy subcommand ensuring that tyro treats single defaults the same as multiple defaults
        default_subcommands.append(Annotated[None, tyro.conf.Suppress])

        @tyro.conf.configure(tyro.conf.OmitSubcommandPrefixes)
        def parse_default(option: Union[tuple(default_subcommands)]):
            return option()

    return Annotated[experiment.signature.type_config, tyro.conf.subcommand(
        name="default",
        description="Run experiment with predefined config.",
        constructor=parse_default,
    )]


@typing.no_type_check
def make_experiment_subcommand(experiment: Experiment):
    args = [
        make_reproduce_command(experiment),
        make_run_command(experiment),
    ]

    if experiment.artifact_names:
        args.append(make_redo_command(experiment))

    if experiment.default_configs:
        args.append(make_default_command(experiment))

    @tyro.conf.configure(tyro.conf.OmitSubcommandPrefixes, tyro.conf.ConsolidateSubcommandArgs)
    def parse_experiment(arg: Union[tuple(args)]):
        if isinstance(arg, ExecutableCommand):
            arg()
        elif isinstance(arg, experiment.signature.type_config):
            run = experiment(arg)
            print(f"[expyro] Saved run to: {run.path.as_uri()}")
        else:
            raise ValueError(f"Cannot handle argument of type {type(arg)}: {arg}.")

    parse_experiment.__doc__ = experiment.__doc__

    return parse_experiment


def cli(*experiments: Experiment):
    prog = "expyro"
    description = "Run experiments and reproduce results. Works on experiments decorated with `@expyro.experiment`."

    tyro.extras.subcommand_cli_from_dict(
        subcommands={
            experiment.name: make_experiment_subcommand(experiment)
            for experiment in experiments
        },
        prog=prog,
        description=description,
    )


SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "site-packages", "expyro"}


def _iter_py_files_pruned(root: Path) -> Iterable[Path]:
    """ Walk cwd, pruning skip dirs early. """

    for dir_path, dir_names, filenames in os.walk(root):
        dir_names[:] = [d for d in dir_names if d not in SKIP_DIRS]

        for filename in filenames:
            if filename.endswith(".py"):
                yield Path(dir_path) / filename


def _mentions_expyro_quick(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False

    return "import expyro" in text or "from expyro" in text


def _file_imports_expyro(path: Path) -> bool:
    """ Confirm via AST that file has an import of expyro. """

    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name == "expyro" or a.name.startswith("expyro.") for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""

            if mod == "expyro" or mod.startswith("expyro."):
                return True

    return False


def import_user_modules() -> None:
    cwd = Path.cwd().resolve()

    if (s := str(cwd)) not in sys.path:
        sys.path.insert(0, s)

    for path in _iter_py_files_pruned(cwd):
        if not _mentions_expyro_quick(path):
            continue
        if not _file_imports_expyro(path):
            continue

        try:
            # relative module path from cwd
            relative_path = path.relative_to(cwd).with_suffix("")
        except ValueError:
            continue

        module = ".".join(relative_path.parts)

        if module in sys.modules:
            continue

        try:
            import_module(module)
        except Exception as e:
            print(f"[expyro] Failed to import {module}: {e}", file=sys.stderr)


def main():
    import_user_modules()

    if not expyro._experiment.registry:
        print(f"[expyro] No experiments found in {Path.cwd()}.", file=sys.stderr)
    else:
        cli(*expyro._experiment.registry.values())
