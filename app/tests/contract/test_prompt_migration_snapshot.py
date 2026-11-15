"""Historical migration seed data must not depend on current service prompts."""

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, String, Table, create_engine, select


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


def test_agent_query_migration_updates_only_the_matching_system_template():
    from aperag.service.prompt_template_service import DEFAULT_AGENT_QUERY_PROMPT

    versions = Path(__file__).resolve().parents[2] / 'aperag/migration/versions'
    path = versions / '20261114163000-50eeb342a7c9.py'
    spec = importlib.util.spec_from_file_location('repair_agent_query_prompt', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    metadata = MetaData()
    prompts = Table(
        'prompt_template', metadata, Column('id', String, primary_key=True),
        Column('prompt_type', String), Column('scope', String), Column('user_id', String),
        Column('gmt_deleted', String), Column('gmt_updated', String), Column('content', String),
    )
    old_content = 'Keep this first line\n' + migration.OLD_IMAGE_CHECK + 'Keep this last line'
    repaired_content = 'Keep this first line\nKeep this last line'
    assert migration.OLD_IMAGE_CHECK not in DEFAULT_AGENT_QUERY_PROMPT
    with create_engine('sqlite://').begin() as conn:
        metadata.create_all(conn)
        base = dict(prompt_type='agent_query', scope='system', user_id=None, gmt_deleted=None, content=old_content)
        conn.execute(prompts.insert(), [
            dict(base, id='pt_sys_agent_query'),
            dict(base, id='user-template', scope='user', user_id='user'),
            dict(base, id='other-system-template'),
        ])
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            migration.upgrade()
        assert dict(conn.execute(select(prompts.c.id, prompts.c.content)).tuples().all()) == {
            'pt_sys_agent_query': repaired_content,
            'user-template': old_content,
            'other-system-template': old_content,
        }

        # A fresh install seeds an earlier template without the faulty block.
        conn.execute(prompts.update().where(prompts.c.id == 'pt_sys_agent_query').values(content='Earlier template'))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        assert conn.scalar(select(prompts.c.content).where(prompts.c.id == 'pt_sys_agent_query')) == 'Earlier template'
