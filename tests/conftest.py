import os
import tempfile
import pytest
from db.migrations.initial_schema import run_migration

@pytest.fixture
def temp_db():
    """
    Fixture creating a temporary SQLite database initialized with schema.sql.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    run_migration(path)
    yield path
    import gc
    gc.collect()
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
