from __future__ import annotations

import inspect
import os
import pickle
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import update_wrapper
from pathlib import Path
from typing import Callable, get_type_hints, Optional, TYPE_CHECKING, Iterator, Mapping

import expyro._hook as hook

type ExperimentFn[I, O] = Callable[[I], O]
type Postprocessor[I, O] = Callable[[Run[I, O]], None]
type ExperimentWrapper[I, O] = Callable[[Experiment[I, O]], Experiment[I, O]]

if TYPE_CHECKING:
    from expyro._artifacts import ArtifactProcedure

registry: dict[str, Experiment] = {}


@dataclass(frozen=True)
class Signature[I, O]:
    type_config: type[I]
    type_result: type[O]
    name_config: str

    @classmethod
    def from_fn(cls, fn: ExperimentFn[I, O]) -> Signature[I, O]:
        signature = inspect.signature(fn)
        type_hints = get_type_hints(fn)

        if "return" not in type_hints:
            raise TypeError(f"Experiment `{fn.__name__}` must define return annotation.")

        type_result = type_hints.pop("return")

        if len(type_hints) != 1:
            raise TypeError(f"Experiment `{fn.__name__}` must have exactly 1 type-annotated parameter, got signature "
                            f"{signature}.")

        name_config, type_config = type_hints.popitem()

        return Signature(
            type_config=type_config,
            type_result=type_result,
            name_config=name_config,
        )


@dataclass
class Run[I, O]:
    config: I
    result: O
    path: Path

    @property
    def root_dir(self) -> Path:
        return self.path.parent

    @classmethod
    def is_run(cls, path: Path) -> bool:
        return (
                (path / "result.pickle").is_file()
                and (path / "config.pickle").is_file()
        )

    @classmethod
    def load(cls, path: Path) -> Run[I, O]:
        if not cls.is_run(path):
            raise KeyError(f"Directory `{path}` is not a valid run.")

        with open(path / "config.pickle", "rb") as f:
            config = pickle.load(f)

        with open(path / "result.pickle", "rb") as f:
            result = pickle.load(f)

        return Run(config=config, result=result, path=path)

    def dump(self):
        if self.is_run(self.path):
            raise IsADirectoryError(f"Run at {self.path} already exists.")

        self.path.mkdir(parents=True, exist_ok=True)

        with open(self.path / "result.pickle", "wb") as f:
            pickle.dump(self.result, f)

        with open(self.path / "config.pickle", "wb") as f:
            pickle.dump(self.config, f)

    def rename(self, name: str, soft: bool = False):
        new_path = self.root_dir / name

        if not soft and self.is_run(new_path):
            raise IsADirectoryError(f"Run at {new_path} already exists.")

        if soft:
            i = 1

            while new_path.exists():
                new_path = self.root_dir / f"{name} ({i})"
                i += 1

        self.path = self.path.rename(new_path)

    def move(self, path: Path, soft: bool = False):
        path = path.absolute()

        if soft:
            i = 1
            name = path.name
            while path.exists():
                path = path.parent / f"{name} ({i})"
                i += 1

        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = self.path.rename(path)

    def make_new_subdir(self, name: str) -> Path:
        subdir = self.path / name

        i = 1
        while subdir.exists():
            subdir = self.path / f"{name} ({i})"
            i += 1

        subdir.mkdir(parents=True, exist_ok=False)

        return subdir


class Artifact[I, O]:
    procedure: ArtifactProcedure[I, O]
    directory_name: str

    def __init__(self, procedure: ArtifactProcedure[I, O], directory_name: str):
        self.procedure = procedure
        self.directory_name = directory_name

    def __call__(self, run: Run[I, O]) -> None:
        path = self.path(run)
        path.mkdir(parents=True, exist_ok=False)
        self.procedure(path, run.config, run.result)

    def path(self, run: Run) -> Path:
        return run.path / "artifacts" / self.directory_name


class Experiment[I, O]:
    fn: ExperimentFn[I, O]
    signature: Signature[I, O]
    root_dir: Path
    name: str
    __artifacts: dict[str, Artifact[I, O]]
    __postprocessors: list[Postprocessor[I, O]]
    __default_configs: dict[str, I]

    @property
    def artifact_names(self) -> set[str]:
        return set(self.__artifacts.keys())

    @property
    def default_configs(self) -> dict[str, I]:
        return dict(self.__default_configs)

    def __init__(self, fn: ExperimentFn[I, O], dir_runs: Path, name: str):
        if not inspect.isfunction(fn):
            raise TypeError(f"Expected function, got {type(fn)}.")

        if name in registry:
            raise KeyError(f"Experiment `{name}` already exists.")

        registry[name] = self

        self.fn = fn
        self.signature = Signature.from_fn(fn)
        self.root_dir = dir_runs.absolute() / name
        self.name = name
        self.__artifacts = {}
        self.__postprocessors = []
        self.__default_configs = {}

        self.root_dir.mkdir(parents=True, exist_ok=True)

        update_wrapper(self, fn)

    def register_artifact(
            self, procedure: ArtifactProcedure[I, O], name: Optional[str] = None, directory_name: Optional[str] = None
    ):
        if name is None:
            name = procedure.__name__

        if directory_name is None:
            directory_name = name

        if name in self.__artifacts:
            raise KeyError(f"Experiment `{self.name}` already has artifact named `{name}`.")

        self.__artifacts[name] = Artifact(procedure, directory_name)

    def register_postprocessor(self, processor: Postprocessor[I, O]):
        self.__postprocessors.append(processor)

    def register_default_config(self, name: str, config: I):
        if name in self.__default_configs:
            raise KeyError(f"Experiment `{self.name}` already has default config named `{name}`.")

        self.__default_configs[name] = config

    def redo_artifact(self, name: str, run: Run[I, O] | str | Path):
        if not isinstance(run, Run):
            run = self[run]

        if name not in self.__artifacts:
            raise KeyError(f"Experiment `{self.name}` has no artifact named `{name}`.")

        artifact = self.__artifacts[name]
        path = artifact.path(run)

        if path.exists():
            shutil.rmtree(path)

        artifact(run)

    def reproduce(self, run: Run[I, O] | str | Path) -> Run[I, O]:
        if not isinstance(run, Run):
            run = self[run]

        return self(run.config)

    def run_default(self, name: str) -> Run[I, O]:
        if name not in self.__default_configs:
            raise KeyError(f"Experiment `{self.name}` has no default config named `{name}`.")

        config = self.__default_configs[name]

        return self(config)

    def __call__(self, config: I) -> Run[I, O]:
        now = datetime.now()
        run_name = f"{now.strftime("%H:%M:%S.%f")[:-3]} {uuid.uuid4().hex[:8]}"
        dir_run = self.root_dir / now.strftime("%Y-%m-%d") / run_name

        context_token = hook.context.set(dir_run)

        try:
            result = self.fn(config)
        finally:
            hook.context.reset(context_token)

        run = Run(config, result, dir_run)
        run.dump()

        for artifact in self.__artifacts.values():
            artifact(run)

        for processor in self.__postprocessors:
            processor(run)

        return run

    def __iter__(self) -> Iterator[Run[I, O]]:
        for path_str, _, _ in os.walk(self.root_dir):
            path = Path(path_str)

            if Run.is_run(path):
                yield Run.load(path)

    def __getitem__(self, item: str | Path) -> Run[I, O]:
        if isinstance(item, str):
            item = self.root_dir / item

        return Run.load(item)


def experiment[I, O](root: Path, name: Optional[str] = None) -> Callable[[Callable[[I], O]], Experiment[I, O]]:
    def wrapper(fn: Callable[[I], O]) -> Experiment[I, O]:
        nonlocal name

        if name is None:
            name = fn.__name__

        return Experiment(fn, dir_runs=root, name=name)

    return wrapper


def default[I, O](name: str, config: I) -> ExperimentWrapper[I, O]:
    return defaults({name: config})


def defaults[I, O](configs: Mapping[str, I]) -> ExperimentWrapper[I, O]:
    def wrapper(exp: Experiment[I, O]) -> Experiment[I, O]:
        for name, config in configs.items():
            exp.register_default_config(name, config)

        return exp

    return wrapper
