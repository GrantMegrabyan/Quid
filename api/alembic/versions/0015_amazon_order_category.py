"""amazon orders category_id

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("amazon_orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("category_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_amazon_orders_category_id",
            "categories",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("amazon_orders", schema=None) as batch_op:
        batch_op.drop_constraint("fk_amazon_orders_category_id", type_="foreignkey")
        batch_op.drop_column("category_id")
