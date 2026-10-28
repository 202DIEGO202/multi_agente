"""Run integration tests exclusively in fabrica_test, never the project's database."""

import os
import sys
from pathlib import Path

import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402

params = conninfo_to_dict(get_settings().database_url.get_secret_value())
params["dbname"] = "fabrica_test"
os.environ["TEST_DATABASE_URL"] = make_conninfo(**params)
raise SystemExit(pytest.main(sys.argv[1:] or ["-m", "not live", "-q"]))
