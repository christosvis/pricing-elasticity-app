"""Load pymc-marketing without executing its package ``__init__``.

``pymc_marketing/__init__.py`` eagerly imports ``mmm``, which defines
``AdstockTransformation`` with ``@validate_call`` on ``priors: dict[str, SupportedPrior]``.
On Streamlit Cloud that annotation builds an invalid pydantic ``isinstance`` schema
(``SchemaError: 'cls' must be valid as the first argument to 'isinstance'``), even
with pymc-marketing 0.19.2 and pydantic 2.10.

pypricing only needs ``ModelBuilder`` from ``pymc_marketing.model_builder``, which
does not depend on MMM. Registering a package stub with ``__path__`` lets that
submodule load without running the package init.
"""

from __future__ import annotations

import importlib.util
import sys
import types


def skip_pymc_marketing_mmm_import() -> None:
    name = "pymc_marketing"
    existing = sys.modules.get(name)
    if existing is not None and getattr(existing, "__file__", None):
        return
    spec = importlib.util.find_spec(name)
    if spec is None or not spec.submodule_search_locations:
        return
    module = types.ModuleType(name)
    module.__file__ = spec.origin
    module.__path__ = list(spec.submodule_search_locations)
    module.__package__ = name
    module.__spec__ = spec
    sys.modules[name] = module
    from pymc_marketing.version import __version__

    module.__version__ = __version__
    module.__all__ = ["__version__"]
