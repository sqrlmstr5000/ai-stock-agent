import peewee as pw
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    step = pw.CharField(max_length=32, null=True)
    run_migrations(
        migrator.add_column('apirequestusage', 'step', step),
    )

def downgrade(migrator: SchemaMigrator):
    run_migrations(
        migrator.drop_column('apirequestusage', 'step'),
    )
