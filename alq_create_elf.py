#!/usr/bin/env python

""" Recreate the elf file from local data.  

    Mostly used when local data changes based on remote data updates,
    Moves old elf to bak and also creates bak_longer if the new elf is shorter. This protects
    against accidentally shortening the elf if local data needs updating.
"""

import logging
import argparse
from sql import SQL
from aliquot_elf import AliquotElf

logger = logging.getLogger(__name__)

def create_elf(sql_connection:SQL, seq:int) -> None:
    """Create elf file from local data

    Args:
        sql_connection: postgres sql connection
        seq: The sequence to generate the elf for
    """

    logger.info('Creating elf %s.', seq)

    elf_service = AliquotElf(sql_connection)
    elf_service.create_elf_file(seq)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_create_elf.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('num', type=int, help='number to create elf file for')
    argv = parser.parse_args()

    pg = SQL()

    create_elf(pg, argv.num)

    logger.info('finished')
