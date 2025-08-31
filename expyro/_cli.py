import ast
import os
import sys
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Annotated, Union, Iterable

import tyro.extras

import expyro._experiment
from expyro._experiment import Experiment


@dataclass(frozen=True)
class ExecutableCommand(ABC):
    @abstractmethod
    def __call__(self) -> None:
        raise NotImplementedError


@typing.no_type_check
def make_experiment_subcommand(experiment: Experiment):
    artifact_literal = tyro.extras.literal_type_from_choices(sorted(experiment.artifact_names))
    default_config_literal = tyro.extras.literal_type_from_choices(sorted(experiment.default_config_names))

    @dataclass(frozen=True)
    class Redo(ExecutableCommand):
        artifact_name: Annotated[artifact_literal, tyro.conf.Positional]  # what to redo
        path: Annotated[str, tyro.conf.Positional]  # path to run

        def __call__(self):
            experiment.redo_artifact(self.artifact_name, self.path)

    @dataclass(frozen=True)
    class Reproduce(ExecutableCommand):
        path: Annotated[str, tyro.conf.Positional]  # path to run

        def __call__(self):
            run = experiment.reproduce(self.path)
            print(f"[expyro] Saved reproduced run to: {run.path.as_uri()}")

    @dataclass(frozen=True)
    class Default(ExecutableCommand):
        name: Annotated[default_config_literal, tyro.conf.Positional]  # name of config

        def __call__(self):
            run = experiment.run_default(self.name)
            print(f"[expyro] Saved run to: {run.path.as_uri()}")

    args = [
        Annotated[Reproduce, tyro.conf.subcommand(
            name="reproduce", description="Run experiment with config of existing run."
        )],
        Annotated[experiment.signature.type_config, tyro.conf.subcommand(
            name="run", description="Run experiment with custom config."
        )]
    ]

    if experiment.default_config_names:
        args.append(Annotated[Default, tyro.conf.subcommand(
            name="default", description="Run experiment with predefined config."
        )])
    if experiment.artifact_names:
        args.append(Annotated[Redo, tyro.conf.subcommand(
            name="redo", description="Recreate artifacts of existing run."
        )])

    @tyro.conf.configure(tyro.conf.OmitSubcommandPrefixes)
    def parse_experiment(config: Union[tuple(args)]):
        if isinstance(config, ExecutableCommand):
            config()
        elif isinstance(config, experiment.signature.type_config):
            run = experiment(config)
            print(f"[expyro] Saved run to: {run.path.as_uri()}")
        else:
            raise ValueError(f"Cannot handle argument of type {type(config)}: {config}.")

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
