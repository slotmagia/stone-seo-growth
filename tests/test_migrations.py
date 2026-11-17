"""Alembic fresh setup, old-table adoption, safe downgrade and schema drift."""
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy.orm import Session
from app.models import Base, Product, ProductFactRevision

ROOT = Path(__file__).resolve().parents[1]


def cfg(monkeypatch, path):
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{path}')
    config=Config(str(ROOT/'alembic.ini'))
    config.set_main_option('script_location', str(ROOT/'migrations'))
    return config


def test_fresh_db_migration_matches_models_and_empty_rollback(tmp_path, monkeypatch):
    path=tmp_path/'fresh.sqlite'
    config=cfg(monkeypatch,path)
    command.upgrade(config,'head')
    engine=sa.create_engine(f'sqlite:///{path}')
    with engine.connect() as conn:
        names=sa.inspect(conn).get_table_names()
        assert {'products','product_fact_revisions','site_audit_runs','alembic_version'}.issubset(names)
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata)==[]
        assert conn.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one()=='0002_product_facts'
    command.downgrade(config,'0001_baseline')
    with engine.connect() as conn:
        assert not sa.inspect(conn).has_table('product_fact_revisions')
        assert sa.inspect(conn).has_table('products')
    command.upgrade(config,'head')
    engine.dispose()


def test_adopts_old_sqlite_data_and_fails_closed_for_legacy_evidence(tmp_path, monkeypatch):
    path=tmp_path/'legacy.sqlite'
    url=f'sqlite:///{path}'
    engine=sa.create_engine(url)
    tables=[table for table in Base.metadata.sorted_tables if table.name!='product_fact_revisions']
    Base.metadata.create_all(engine,tables=tables)
    with Session(engine) as db:
        db.add(Product(sku='LEGACY-1', title_zh='旧石材', title_en='old stone',
                       stone_type='granite', properties={'thickness_mm':20},
                       evidence={'stone_type':'previous supplier info'},verified_fields=['stone_type']))
        db.commit()
    config=cfg(monkeypatch,path)
    command.upgrade(config,'head')
    with Session(engine) as db:
        saved=db.scalar(sa.select(Product).where(Product.sku=='LEGACY-1'))
        assert saved and saved.evidence['stone_type']=='previous supplier info'
        assert db.scalars(sa.select(ProductFactRevision)).all()==[]
    command.upgrade(config,'head')  # idempotent command
    engine.dispose()


def test_downgrade_refuses_to_destroy_fact_history(tmp_path,monkeypatch):
    path=tmp_path/'with-facts.sqlite'
    config=cfg(monkeypatch,path)
    command.upgrade(config,'head')
    engine=sa.create_engine(f'sqlite:///{path}')
    with Session(engine) as db:
        product=Product(sku='P01',title_zh='测试石材',stone_type='marble',
                        properties={},evidence={},verified_fields=[])
        db.add(product);db.flush()
        db.add(ProductFactRevision(product_id=product.id,field_path='stone_type',revision=1,
                 action='verified',value_snapshot='marble',evidence_reference='supplier p. 2',
                 reviewer='demo reviewer',source_kind='manual_document'))
        db.commit()
    with pytest.raises(RuntimeError,match='delete evidence history'):
        command.downgrade(config,'0001_baseline')
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT COUNT(*) FROM product_fact_revisions')).scalar_one()==1
    engine.dispose()
