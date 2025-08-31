from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Literal, Mapping, Optional

from expyro._experiment import Experiment, ExperimentWrapper

if TYPE_CHECKING:
    import matplotlib.pyplot as plt
    import pandas as pd

type Artifact[I, O] = Callable[[Path, I, O], None]


def artifact[I, O](
        processor: Artifact[I, O], name: Optional[str] = None, directory_name: Optional[str] = None
) -> Callable[[Experiment[I, O]], Experiment[I, O]]:
    def wrapper(experiment: Experiment[I, O]) -> Experiment[I, O]:
        experiment.register_artifact(processor, name, directory_name)
        return experiment

    return wrapper


type Nested[T] = T | Mapping[str, T]
type Artist[I, O, T] = Callable[[I, O], Nested[T]]
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


def _handle_artists[I, O, T](
        config: I, result: O, artists: Iterable[Artist[I, O, T]], handle: Callable[[Path | str, T], None]
):
    for artist in artists:
        outcome = artist(config, result)

        if isinstance(outcome, Mapping):
            flat_result = _flatten_nested(outcome, parent_key=artist.__name__)

            for sub_path, figure in flat_result.items():
                handle(sub_path, figure)
        else:
            handle(artist.__name__, outcome)


def plot[I, O](
        *artists: Callable[[I, O], NestedPlot],
        file_format: Literal["png", "pdf"] = "png",
        dpi: int = 500,
        **kwargs
) -> ExperimentWrapper[I, O]:
    try:
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise ImportError("Install with `pip install expyro[matplotlib]` to use with matplotlib.") from e

    def processor(dir_plots: Path, config: I, result: O) -> None:
        def save(sub_path: Path | str, figure: plt.Figure):
            path = dir_plots / sub_path
            path.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(f"{path}.{file_format}", dpi=dpi, **kwargs)

        _handle_artists(config, result, artists, save)

    return artifact(processor, name="plots", directory_name="plots")


def table[I, O](*artists: Callable[[I, O], NestedTable]) -> ExperimentWrapper[I, O]:
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError("Install with `pip install expyro[pandas]` to use with pandas.") from e

    def processor(dir_tables: Path, config: I, result: O) -> None:
        def save(sub_path: Path | str, df: pd.DataFrame):
            path = dir_tables / sub_path
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(f"{path}.csv", index=False)

        _handle_artists(config, result, artists, save)

    return artifact(processor, name="tables", directory_name="tables")
