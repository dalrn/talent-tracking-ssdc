# core package
#
# Make dashboard/ importable as a plain module path (config.py, schema.py
# style) regardless of how the entry point was launched: streamlit run
# app.py (script mode, core has no parent package), a page under pages/,
# or a plain "import dashboard.core.loader" from the repo root.
#
# Streamlit always runs app.py as a top level script, so relative imports
# inside core/ (from .. import config) fail with "attempted relative
# import beyond top-level package" in that mode. Adding dashboard/ to
# sys.path once here lets every core module use plain absolute imports
# (import config, import schema) that work the same in every mode.

import os
import sys

_core_dir = os.path.dirname(os.path.abspath(__file__))
_dashboard_dir = os.path.dirname(_core_dir)
# config.py lives at dashboard/, schema.py lives at dashboard/core/.
# Both directories must be on sys.path for the plain "import config" and
# "import schema" statements used across core/ to resolve.
for _p in (_dashboard_dir, _core_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)
