"""Create the normalized Stickfix persistence schema."""

import sqlalchemy as sa

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), primary_key=True),
        sa.Column("private_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("shuffle", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "stickers",
        sa.Column("id", sa.String(), primary_key=True),
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )
    op.create_table(
        "user_sticker_tags",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("sticker_id", sa.String(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sticker_id"], ["stickers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "sticker_id", "tag_id"),
    )
    op.create_table(
        "public_sticker_tags",
        sa.Column("sticker_id", sa.String(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["sticker_id"], ["stickers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("sticker_id", "tag_id"),
    )
    op.create_table(
        "user_cached_stickers",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column("sticker_id", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "tag_id", "sticker_id"),
    )
    op.create_table(
        "public_cached_stickers",
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column("sticker_id", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tag_id", "sticker_id"),
    )
    op.create_index("ix_user_sticker_tags_user_tag", "user_sticker_tags", ["user_id", "tag_id"])
    op.create_index("ix_public_sticker_tags_tag", "public_sticker_tags", ["tag_id"])
    op.create_index(
        "ix_user_cached_stickers_user_tag", "user_cached_stickers", ["user_id", "tag_id"]
    )
    op.create_index("ix_public_cached_stickers_tag", "public_cached_stickers", ["tag_id"])


def downgrade() -> None:
    op.drop_index("ix_public_cached_stickers_tag", table_name="public_cached_stickers")
    op.drop_index("ix_user_cached_stickers_user_tag", table_name="user_cached_stickers")
    op.drop_index("ix_public_sticker_tags_tag", table_name="public_sticker_tags")
    op.drop_index("ix_user_sticker_tags_user_tag", table_name="user_sticker_tags")
    op.drop_table("public_cached_stickers")
    op.drop_table("user_cached_stickers")
    op.drop_table("public_sticker_tags")
    op.drop_table("user_sticker_tags")
    op.drop_table("tags")
    op.drop_table("stickers")
    op.drop_table("users")
