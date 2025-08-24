from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal, Mapping, Optional, Iterable

from expyro._experiment import ExperimentWrapper, Experiment, Run

try:
    from matplotlib import pyplot as plt
except ImportError as e:
    raise ImportError("Install with `pip install expyro[matplotlib]` to use with matplotlib.") from e

try:
    import pandas as pd
except ImportError as e:
    raise ImportError("Install with `pip install expyro[pandas]` to use with pandas.") from e

type Nested[T] = T | Mapping[str, T]
type NestedPlot = Nested[plt.Figure]
type NestedTable = Nested[pd.DataFrame]


def _flatten_nested[T](
        result: Mapping[str, Nested[T]], parent_key: Optional[Path | str] = None
) -> dict[Path, T]:
    items = {}

    if parent_key is None:
        parent_key = Path()

    if isinstance(parent_key, str):
        parent_key = Path(parent_key)

    for key, value in result.items():
        new_key = parent_key / key

        if isinstance(value, dict):
            items.update(_flatten_nested(value, new_key))
        else:
            items[new_key] = value

    return items


type Artist[I, O, T] = Callable[[I, O], Nested[T]]


def _handle_artists[I, O, T](
        run: Run[I, O], artists: Iterable[Artist[I, O, T]], handle: Callable[[Path | str, T], None]
):
    for artist in artists:
        result = artist(run.config, run.result)

        if isinstance(result, Mapping):
            flat_result = _flatten_nested(result, parent_key=artist.__name__)

            for sub_path, figure in flat_result.items():
                handle(sub_path, figure)
        else:
            handle(artist.__name__, result)


def plot[I, O](
        *artists: Callable[[I, O], Nested],
        file_format: Literal["png", "pdf"] = "png",
        dpi: int = 500,
        **kwargs
) -> ExperimentWrapper[I, O]:
    def postprocessor(run: Run[I, O]):
        dir_plots = run.make_new_subdir("plots")

        def save(sub_path: Path | str, figure: plt.Figure):
            path = dir_plots / sub_path
            path.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(f"{path}.{file_format}", dpi=dpi, **kwargs)

        _handle_artists(run, artists, save)

    def wrapper(experiment: Experiment[I, O]) -> Experiment[I, O]:
        experiment.plots.append(postprocessor)
        return experiment

    return wrapper


def table[I, O](*artists: Callable[[I, O], NestedTable]) -> ExperimentWrapper[I, O]:
    def postprocessor(run: Run[I, O]) -> None:
        dir_tables = run.make_new_subdir("tables")

        def save(sub_path: Path | str, df: pd.DataFrame):
            path = dir_tables / sub_path
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(f"{path}.csv", index=False)

        _handle_artists(run, artists, save)

    def wrapper(experiment: Experiment[I, O]) -> Experiment[I, O]:
        experiment.tables.append(postprocessor)
        return experiment

    return wrapper
