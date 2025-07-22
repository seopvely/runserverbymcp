"""Initial servers table

Revision ID: 001
Revises: 
Create Date: 2024-01-22 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create servers table"""
    op.create_table(
        'servers',
        sa.Column('id', sa.Integer(), nullable=False, comment='서버 ID'),
        sa.Column('title', sa.String(255), nullable=False, comment='서버 제목'),
        sa.Column('host', sa.String(255), nullable=False, comment='서버 IP/호스트명'),
        sa.Column('port', sa.Integer(), nullable=False, server_default='22', comment='SSH 포트'),
        sa.Column('username', sa.String(100), nullable=False, server_default='root', comment='SSH 사용자명'),
        sa.Column('description', sa.Text(), nullable=True, comment='서버 설명'),
        sa.Column('created_at', mysql.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='생성일시'),
        sa.Column('updated_at', mysql.TIMESTAMP(), nullable=False, 
                 server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), comment='수정일시'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('host', 'port', 'username', name='unique_server'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci'
    )


def downgrade() -> None:
    """Drop servers table"""
    op.drop_table('servers') 
