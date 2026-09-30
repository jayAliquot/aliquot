#!/usr/bin/env python

"""Lists the merges for a sequence.

It it ends at an open sequence the open term is listed as well.
"""

import argparse
import logging
from sql import SQL
from aliquot_misc import AliquotMisc

logger = logging.getLogger(__name__)

def list_merges(sql_connection:SQL, seq:int) -> None:
    """List any merges or open values for a sequence

    Args:
        sql_connection: postgres sql connection.
        seq: The sequence to list the merges of.
    """

    logger.info('Creating elf %s.', seq)

    misc_service = AliquotMisc(sql_connection)
    misc_service.get_merge(seq)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_merge.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('num', type=int, help='number to create elf file for')
    argv = parser.parse_args()

    pg = SQL()

    list_merges(pg, argv.num)

    logger.info('finished')
