from __future__ import annotations

import inspect
import os
import pickle
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import update_wrapper
from pathlib import Path
from typing import Callable, get_type_hints, Generator, Optional

import expyro._hook as hook

type ExperimentFn[I, O] = Callable[[I], O]
type ExperimentWrapper[I, O] = Callable[..., Experiment[I, O]]
type Postprocessor[I, O] = Callable[[Run[I, O]], None]


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

    def rename(self, name: str):
        new_path = self.root_dir / name

        if self.is_run(new_path):
            raise IsADirectoryError(f"Run at {new_path} already exists.")

        self.path = self.path.rename(new_path)

    def move(self, path: Path):
        self.path = self.path.rename(path)

    def make_new_subdir(self, name: str) -> Path:
        subdir = self.path / name

        i = 1
        while subdir.exists():
            subdir = self.path / f"{name} ({i})"
            i += 1

        subdir.mkdir(parents=True, exist_ok=False)

        return subdir


class Experiment[I, O]:
    fn: ExperimentFn[I, O]
    signature: Signature[I, O]
    root_dir: Path
    name: str
    plots: list[Postprocessor[I, O]]
    tables: list[Postprocessor[I, O]]

    @property
    def postprocessors(self) -> list[Postprocessor[I, O]]:
        return self.plots + self.tables

    def __init__(self, fn: ExperimentFn[I, O], dir_runs: Path, name: str):
        if not inspect.isfunction(fn):
            raise TypeError(f"Expected function, got {type(fn)}.")

        self.fn = fn
        self.signature = Signature.from_fn(fn)
        self.root_dir = dir_runs / name
        self.name = name
        self.plots = []
        self.tables = []

        update_wrapper(self, fn)
        self.root_dir.mkdir(parents=True, exist_ok=True)

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

        for postprocessor in self.postprocessors:
            postprocessor(run)

        return run

    def __iter__(self) -> Generator[Run[I, O], None, None]:
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
