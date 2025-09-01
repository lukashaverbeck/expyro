from pathlib import Path
from typing import Callable

from expyro._experiment import Run, ExperimentWrapper, Experiment

type PostProcessor[I, O] = Callable[[Run[I, O]], None]


def postprocess[I, O](processor: PostProcessor[I, O]) -> ExperimentWrapper[I, O]:
    def wrapper(experiment: Experiment[I, O]) -> Experiment[I, O]:
        experiment.register_postprocessor(processor)
        return experiment

    return wrapper


def rename[I, O](rule: Callable[[I, O], str]) -> ExperimentWrapper[I, O]:
    def _rename(run: Run[I, O]) -> None:
        name = rule(run.config, run.result)
        run.rename(name, soft=True)

    return postprocess(_rename)


def move[I, O](rule: Callable[[I, O], Path | str]) -> ExperimentWrapper[I, O]:
    def _move(run: Run[I, O]) -> None:
        path = rule(run.config, run.result)
        path = Path(path)
        run.move(path, soft=True)

    return postprocess(_move)
