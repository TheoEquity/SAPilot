"""Repair the screenshot check in the stored system query prompt."""

import sqlalchemy as sa
from alembic import op

revision = "50eeb342a7c9"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

OLD_IMAGE_CHECK = """{% set has_image_files = false %}
{% if files %}
{% for file in files %}
{% if file.name and (file.name.endswith('.png') or file.name.endswith('.jpg') or file.name.endswith('.jpeg') or file.name.endswith('.webp') or file.name.endswith('.gif')) %}
{% set has_image_files = true %}
{% break %}
{% endif %}
{% endfor %}
{% endif %}
"""


def upgrade() -> None:
    prompts = sa.table(
        "prompt_template",
        sa.column("id", sa.String),
        sa.column("prompt_type", sa.String),
        sa.column("scope", sa.String),
        sa.column("user_id", sa.String),
        sa.column("gmt_deleted", sa.DateTime),
        sa.column("gmt_updated", sa.DateTime),
        sa.column("content", sa.Text),
    )
    op.execute(
        prompts.update()
        .where(
            prompts.c.id == "pt_sys_agent_query",
            prompts.c.prompt_type == "agent_query",
            prompts.c.scope == "system",
            prompts.c.user_id.is_(None),
            prompts.c.gmt_deleted.is_(None),
            prompts.c.content.contains(OLD_IMAGE_CHECK, autoescape=True),
        )
        .values(
            content=sa.func.replace(prompts.c.content, OLD_IMAGE_CHECK, ""),
            gmt_updated=sa.func.now(),
        )
    )


def downgrade() -> None:
    # Keep the repaired template, which older releases can still render.
    pass
