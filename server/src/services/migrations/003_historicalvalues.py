import peewee as pw
from playhouse.migrate import migrate as run_migrations, SchemaMigrator

def upgrade(migrator: SchemaMigrator):
    final_recommendation = pw.CharField(null=True)
    final_confidence_score = pw.IntegerField(null=True)

    run_migrations(
        migrator.add_column('historicalvalues', 'final_recommendation', final_recommendation),
        migrator.add_column('historicalvalues', 'final_confidence_score', final_confidence_score),
    )

def downgrade(migrator: SchemaMigrator):
    run_migrations(
        migrator.drop_column('historicalvalues', 'final_recommendation'),
        migrator.drop_column('historicalvalues', 'final_confidence_score')
    )