"""Guard the advertised public surface of the package.

``f1show.__all__`` is a published promise: every name listed there must resolve
from the package root, because that is exactly what ``from f1show import <name>``
and ``from f1show import *`` consume. This check walks the real ``__all__``
rather than a hardcoded list, so a name added to the list is covered
automatically, and it refuses a trivially-passing empty or duplicated list.

Scope, stated on purpose: this asserts only the forward direction
(``__all__ -> module``) for **every** listed name. It deliberately does **not**
assert the inverse direction (an importable name that is missing from
``__all__``): ``__all__`` does not restrict a plain ``import``, it only narrows
``import *``, and a reverse check would need a hand-maintained exception list
(such as module attributes that are not meant to be public). That is the very
maintenance this package-wide sweep exists to avoid on a surface that grows. A
closed, hardcoded set can afford both directions; a growing one cannot, so the
limit is declared here instead of left for a reader to over-infer. Resolution
mirrors what ``from f1show import <name>`` really does: the attribute, or the
submodule fallback the import system applies when the attribute is absent.
"""

from __future__ import annotations

import importlib

import f1show


def test_every_advertised_name_is_importable_from_the_package_root() -> None:
    """Each ``__all__`` entry must resolve, and the list must be a real promise."""
    names = list(f1show.__all__)
    assert names, "__all__ must not be empty, or this guard proves nothing"
    assert len(names) == len(set(names)), f"duplicate names in __all__: {names}"
    for name in names:
        try:
            getattr(f1show, name)
        except AttributeError:
            # Match what ``from f1show import <name>`` actually does. When the
            # attribute is missing, the import system falls back to importing a
            # submodule of that name; resolving with ``getattr`` alone would be
            # STRICTER than the language and could fail a name that imports fine.
            try:
                importlib.import_module(f"{f1show.__name__}.{name}")
            except ImportError as exc:
                # Mirror the failure the real import would raise, so a name
                # advertised but never provided is reported as the defect it is.
                raise ImportError(
                    f"cannot import name {name!r} from 'f1show' ({f1show.__file__})"
                ) from exc
