import peewee as pw
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    validation = pw.TextField(null=True)  

    run_migrations(
        migrator.add_column('research', 'validation', validation),
        migrator.add_column('portfolioresearch', 'validation', validation),
    )

def downgrade(migrator: SchemaMigrator):
    run_migrations(
        migrator.drop_column('research', 'validation'),
        migrator.drop_column('portfolioresearch', 'validation'),
    )