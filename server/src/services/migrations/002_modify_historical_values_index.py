"""
Modify HistoricalValues index: Remove unique constraint from stock_id, report_date compound index
"""
from peewee import *
from playhouse.migrate import *

def upgrade(migrator):
    # Drop the existing index if it exists
    migrator.drop_index('historical_values', ('stock_id', 'report_date'))
    
    # Create a new non-unique index
    migrator.add_index('historical_values', ('stock_id', 'report_date'), False)

def downgrade(migrator):
    # Drop the non-unique index
    migrator.drop_index('historical_values', ('stock_id', 'report_date'))
    
    # Recreate the unique index
    migrator.add_index('historical_values', ('stock_id', 'report_date'), True)
