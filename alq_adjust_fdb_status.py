#!/usr/bin/env python

"""Factordb status should NA if and only if there is no elf or elg file.

Only sequences that reach 25 digits before a merge are added to the factor database.  This
keeps the factor database clear of millions of sequences that merge quickly.  However merges
can make the status for a number change.  Those sequences that reach 25 have an elf file if open or
an elg file if they merge.  Ones that don't do not have either.
For the factordb status, NA is used for the ones that don't have either.  Elg and Elf sequences
will usually have a status of 'needs_update', 'up_to_date', or 'unchecked'
Running this fixes any issues found within  the given range.
The range is given as min_seq, max_seq when called.

"""

import argparse
import logging
from pathlib import Path
from sql import SQL
from aliquot_status import AliquotStatus

logger = logging.getLogger(__name__)

class CompareFactorDB:
    """Walks through sequences within the range and fixes their factordb status."""
    def __init__(self, sql):
        """Initialization

        Args:
            sql: postgres sql connection

        Attributes:
            status: The local db status table to be checked.
        """

        self.status = AliquotStatus(sql)

    @staticmethod
    def mod_error():
        """Not a module warning"""

        print('This program is designed to be run seperately "python3 alq_adjust_status.py"')
        print('refactor to enable module calls')

    def compare(self):
        """Check the local db value.

        If there is an Elg or Elf file for the sequence its factordb status should
        never be NA, otherwise it should always be NA.  We check and fix if needed.
        print statements indicate changes made.
        """

        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('min', type=int, help='Minimum value of the range')
        parser.add_argument('max', type=int, help='Maximum value of the range')
        argv = parser.parse_args()
        max_seq = argv.max
        min_seq = argv.min
        if min_seq == 0:
            min_seq = 1
        count = 0
        for seq in range(min_seq, max_seq+1):
            subd = seq // 1000000
            elf_name = f'elf_{subd}/alq_{seq}.elf'
            elg_name = f'elg_{subd}/alq_{seq}.elg'
            status =self.status.get_status(seq)
            if Path(elf_name).is_file() or Path(elg_name).is_file():
                count += 1
                if count % 1000 == 0:
                    print(f'{count}:{seq}')
                if status['factordb'] == 'NA':
                    print(f'{seq}: Update fdb status for elf/elg')
                    self.status.set_factordb(seq, 'unchecked')
            else:
                if status['factordb'] != 'NA':
                    print(f' {seq}: Update fdb status when no elf/elg')
                    self.status.set_factordb(seq, 'NA')

# Using class rather than globals.
if __name__ == "__main__":
    logging.basicConfig(filename='alq_adjust_fdb_status.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    compare_fdb = CompareFactorDB(pg)
    compare_fdb.compare()
    logger.info('finished')
