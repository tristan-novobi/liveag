# Copyright © 2024 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Check if display_name column exists before renaming
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'slide_type'
        AND column_name = 'display_name'
    """)

    if cr.fetchone():
        _logger.info("Renaming slide_type.display_name column to label")
        cr.execute("""
            ALTER TABLE slide_type
            RENAME COLUMN display_name TO label
        """)
    else:
        _logger.info("Column slide_type.display_name already renamed, skipping")
