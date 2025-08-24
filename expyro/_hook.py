from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Optional, overload, ContextManager, BinaryIO, Literal, TextIO

context: ContextVar[Optional[Path]] = ContextVar("dump_context", default=None)

type BinaryMode = Literal[
    "rb", "br", "wb", "bw", "ab", "ba", "xb", "bx", "rb+", "br+", "wb+", "bw+", "ab+", "ba+", "xb+", "bx+"
]


@overload
def hook(name: str, mode: BinaryMode, *, encoding: None = ..., **kwargs) -> ContextManager[BinaryIO]: ...


@overload
def hook(name: str, mode: str = "r", *, encoding: str | None = ..., **kwargs) -> ContextManager[TextIO]: ...


@contextmanager
def hook(name: str, mode: str = "r", *, encoding: str | None = None, **kwargs):
    path = context.get()

    if path is None:
        raise ValueError("Context for current run was empty.")

    dump_dir = path / "data"
    dump_dir.mkdir(parents=True, exist_ok=True)

    with open(dump_dir / name, mode, encoding=encoding, **kwargs) as f:
        yield f
