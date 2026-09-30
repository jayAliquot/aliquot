#!/usr/bin/env python

""" Initialize the status table


"""

import argparse
import logging
from pathlib import Path
from sql import SQL
from aliquot_data import AliquotData
from aliquot_status import AliquotStatus

logger = logging.getLogger(__name__)

def main(sql):
    """Init any missing status between min and max values."""
    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    argv = parser.parse_args()
    max_seq = argv.max
    min_seq = argv.min
    aliquot_data = AliquotData(sql)
    status_data = AliquotStatus(sql)
    inc = aliquot_data.get_incomplete()
    incomplete = {}
    for pair in inc:
        seq = pair[0]
        if seq < min_seq or seq > max_seq:
            continue
        incomplete[seq] = len(str(pair[1]))
    for seq in range(min_seq, max_seq+1):
        if seq % 10000 == 0:
            print(seq)
        if not status_data.get_status(seq):
            complete = True
            factordb = 'NA'
            if seq in incomplete:
                complete = False
                factordb = 'unchecked'
            status_data.set_defaults(seq, complete, factordb)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_init_status.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    main(pg)
    logger.info('finished')
