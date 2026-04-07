import peewee as pw
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    entry_reason = pw.TextField(null=True)
    exit_reason = pw.TextField(null=True)

    run_migrations(
        migrator.alter_column_type('swingtradeplanhistory', 'entry_reason', entry_reason),
        migrator.alter_column_type('swingtradeplanhistory', 'exit_reason', exit_reason),
    )

def downgrade(migrator: SchemaMigrator):
    entry_reason = pw.CharField(null=True)
    exit_reason = pw.CharField(null=True)
    run_migrations(
        migrator.alter_column_type('swingtradeplanhistory', 'entry_reason', entry_reason),
        migrator.alter_column_type('swingtradeplanhistory', 'exit_reason', exit_reason),
    )
