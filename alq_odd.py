#!/usr/bin/env python

""" Creation of generalized elf files that indicate when a sequence joins another.

    It will leave elf files for open sequences and use elg files for merges.
"""

import argparse
import logging

from sql import SQL
from aliquot_data_statistics import AliquotDataStatistics

logger = logging.getLogger(__name__)

def main(sql):
    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    argv = parser.parse_args()
    max_seq = argv.max
    min_seq = argv.min
    if min_seq % 2 == 0:
        min_seq += 1
    aliquot_data_statistics = AliquotDataStatistics(sql)
    count = 1
    max_digits = 0
    max_odd = 1
    max_stats = {}
    for seq in range(min_seq,max_seq,2):
        if count % 100000 == 1:
            print(f'To {seq}: {max_odd} at {max_digits}')
            #print(max_stats)
        count += 1
        status_data = aliquot_data_statistics.get_stats_data(seq)
        curr_digits = status_data['max_digits']
        if curr_digits > 10:
            print(status_data['stats_string'])
        if curr_digits > max_digits:
            max_odd = seq
            max_digits = curr_digits
            max_stats = status_data
    stats_string = max_stats['stats_string']
    print(f'Final: {max_odd} with max {max_digits} had stats:   "{stats_string}"')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_odd.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    main(pg)
    logger.info('finished')
