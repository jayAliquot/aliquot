#!/usr/bin/env python

""" Creation of generalized elf files that indicate when a sequence joins another.

    It will leave elf files for open sequences and use elg files for merges.
"""

import sys
import logging
import argparse
from sql import SQL
from aliquot_elg import AliquotElg

logger = logging.getLogger(__name__)

def main(sql):
    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    argv = parser.parse_args()
    max_seq = argv.max
    min_seq = argv.min
    aliquot_elg = AliquotElg(sql)
    for num in range(min_seq, max_seq+1):
        if num % 1000 == 0:
            print(num, file=sys.stderr)
        aliquot_elg.make_elg(num)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_elg.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    main(pg)
    logger.info('finished')
