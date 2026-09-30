#!/usr/bin/env python

""" Extends local data and elf files with data from the factordb

Takes an ext file that has been downloaded from the factordb and extends the local data using that
file and then also update the elf file to match.  If a merge occurs we handle it and will
end up with an elg file.

The ext file is meant to start where the local data ends, though there is some ability to adjust
if they don't match exactly.
"""

import argparse
import logging
from pathlib import Path
from sql import SQL
import aliquot_util
from aliquot_main import AliquotMain
from aliquot_verify import AliquotVerify


logger = logging.getLogger(__name__)

def extend_series(sql_connection:SQL, min_seq:int, max_seq:int) -> None:
    """Extend local data over a range

    Parses a maximum and minimum range to look for ext files.  In practice, this is called
    for a single sequence with max and minimum being equal.

    Args:
        sql_connection: postgres sql connection
        min_seq: Minimum of the range to check for ext files.
        max_seq: Maximum of the range to check for ext files.
    """

    logger.info('Extend range %s to %s', min_seq, max_seq)
    
    verify_service = AliquotVerify(sql_connection)
    main_service = AliquotMain(sql_connection)
    for seq in range(min_seq, max_seq+1):
        if seq % 100000 == 0:
            print(seq)

        subd = seq // aliquot_util.INTERVAL
        ext_name = f'elf_{subd}/alq_{seq}.ext'
        if Path(ext_name).is_file():
            main_service.extend_elf(seq)
            verify_service.verify(seq, None)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_extend.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    argv = parser.parse_args()

    pg = SQL()

    extend_series(pg, argv.min, argv.max)

    logger.info('finished')
