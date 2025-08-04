import peewee as pw
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    economic_analysis = pw.TextField(null=True)  
    run_migrations(
        migrator.add_column('portfolioresearch', 'economic_analysis', economic_analysis),
    )

def downgrade(migrator: SchemaMigrator):
    run_migrations(
        migrator.drop_column('portfolioresearch', 'economic_analysis'),
    )
