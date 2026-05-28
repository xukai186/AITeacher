"""merge p2 and p3 heads

Revision ID: 15c768af9282
Revises: 3caa35db2988, ea55f158215b
Create Date: 2026-05-28 14:13:08.933989

"""
from alembic import op
import sqlalchemy as sa


revision = '15c768af9282'
down_revision = ('3caa35db2988', 'ea55f158215b')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
