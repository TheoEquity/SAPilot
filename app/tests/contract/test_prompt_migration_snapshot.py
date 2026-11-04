"""Historical migration seed data must not depend on current service prompts."""

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def test_prompt_migration_loads_without_service_and_preserves_historical_text(monkeypatch):
    # A dependency on the live service must fail, even if it was imported earlier.
    monkeypatch.setitem(sys.modules, 'aperag.service.prompt_template_service', ModuleType('blocked-service'))
    path = Path(__file__).resolve().parents[2] / 'aperag/migration/versions/20260204171951-8abbaf1aa10d.py'
    spec = importlib.util.spec_from_file_location('historical_prompt_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    # SHA-256 of the original strings in repository revision 18d00cb.
    expected = {
        'APERAG_AGENT_INSTRUCTION': '24dec67f8bbcf8e4d79ebf062ff96c1d4f207ced868e7643f6197d00d0bbe5bc',
        'DEFAULT_AGENT_QUERY_PROMPT': '72904ce8ea5fd4f138f70e66be3e6e4727b4c1e35b7194397fa5a331546164e2',
    }
    for name, digest in expected.items():
        assert hashlib.sha256(getattr(migration, name).encode('utf-8')).hexdigest() == digest
    assert migration.revision == '8abbaf1aa10d'
    assert migration.down_revision == '332faa764121'
