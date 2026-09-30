#!/usr/bin/env python

""" Finds the aliquot seqence starting from an input number and adds it to the database.

    If an elf or elg file exists for a starting number, all entries will be checked with new entries
    being added as needed.  Otherwise it will stop when it finds a db entry already exists.
"""

import argparse
import logging
from sql import SQL
from aliquot_main import AliquotMain

logger = logging.getLogger(__name__)

def main(sql_connection: SQL, min_seq: int, max_seq: int) -> None:
    """Adds sequence to the local postgres database.
    
    Initially, it manually calculates a new sequence up to 25 digits using numpy.
    However, the much more common usage is to find the associated elf file and add
    any missing entries into the postgres database.  
    It can also find low factors for a final open sequence term.
    If a merge is detected the elg file is created for the merge.

    Args:
        sql_connection: Postgres sql connection.
        min_seq: The minimum sequence to process.
        max_seq: The maximum sequence to process.
    """

    min_seq = max(min_seq, 1)

    logger.info('Main range %s to %s', min_seq, max_seq)

    aliquot_main = AliquotMain(sql_connection)

    for seq in range(min_seq, max_seq+1):
        aliquot_main.calc_sequence(seq)

if __name__ == "__main__":
    logging.basicConfig(filename='main.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    argv = parser.parse_args()

    pg = SQL()

    main(pg, argv.min, argv.max)

    logger.info('finished')
