#!/usr/bin/env python

"""combines all known factors for the last entry of an open sequence

        Finds the smallest prime powers manually.
        Also checks the elf file for primes that might have come from the
        factordb.
        It also fixes errors if somehow we have a prime not in the prime
        factorization of num.  This might rarely occur if we get a partial number
        from the factordb.
"""

import argparse
import logging
from sql import SQL
from aliquot_elf import AliquotElf
from aliquot_data import AliquotData

logger = logging.getLogger(__name__)

def factor_check(sql):
    """Checks final partial factorization and makes consistent for elf and  local data."""

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    argv = parser.parse_args()
    max_seq = argv.max
    min_seq = argv.min
    aliquot_elf = AliquotElf(sql)
    aliquot_data = AliquotData(sql)
    data = aliquot_data.get_incomplete()
    count = 0
    for pair in data:
        num = pair[1]
        seq = pair[0]
        if max_seq >= seq >= min_seq:
            if count % 10000 == 0:
                print(f'{count}: {seq}')
            aliquot_elf.factor_check(seq, num)
            count += 1

if __name__ == "__main__":
    logging.basicConfig(filename='alq_factor_check.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    factor_check(pg)
    logger.info('finished')
