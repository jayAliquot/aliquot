#!/usr/bin/env python

""" Finds sequences that merge into another sequence

    It will leave elf files for open sequences and use elg files for merges.
"""

import argparse
import logging
from sql import SQL
from aliquot_data_statistics import AliquotDataStatistics

logger = logging.getLogger(__name__)

def main(sql):
    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('num', type=int, help='Number to check merges into')
    argv = parser.parse_args()
    num = argv.num
    aliquot_data_statistics = AliquotDataStatistics(sql)
    merge_list = []
    merge_list.append(num)
    count = 0
    while len(merge_list) > 0:
        seq = merge_list.pop()
        merges = aliquot_data_statistics.get_all_merging_into(seq)
        for merge in merges:
            count += 1
            from_seq = merge['merge_from_sequence']
            merge_list.append(from_seq)
            from_index = merge['merge_from_index']
            to_seq = merge['merge_to_sequence']
            to_index = merge['merge_to_index']
            print(f'{count}. Merge {from_seq}:{from_index}.>{to_seq}:{to_index}')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_into.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    main(pg)
    logger.info('finished')
