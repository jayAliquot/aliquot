#!/usr/bin/env python

""" Print out one sequence to indicate how factors persist.


"""

import argparse
import logging
from sql import SQL
from aliquot_misc import AliquotMisc

logger = logging.getLogger(__name__)

def calc_factors(sql):
    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('seq', type=int, help='Sequence to check')
    parser.add_argument('-l', type=int, default=10, help='limit on pesistence')
    argv = parser.parse_args()
    seq = argv.seq
    limit = argv.l
    aliquot_misc = AliquotMisc(sql)
    aliquot_misc.calc_seq_persistence(seq, limit)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_factors.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    calc_factors(pg)
    logger.info('finished')
