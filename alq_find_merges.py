#!/usr/bin/env python

""" Creates the sequence merge table

    Include merges that don't reach 25.  
"""

import argparse
import logging
from pathlib import Path
from datetime import datetime
from sql import SQL
from aliquot_statistics import AliquotStatistics
import aliquot_util

logger = logging.getLogger(__name__)

class FindMerge:
    def __init__(self, sql):
        self.statistics = AliquotStatistics(sql)

    def get_last_two_lines(self, file):
        lines = file.readlines()
        lines = lines[-2:]
        return lines

    def find_merges(self):
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('min', type=int, help='Minimum value of the range')
        parser.add_argument('max', type=int, help='Maximum value of the range')
        parser.add_argument('--clean', action='store_true', help='remove unnecessary merge')
        argv = parser.parse_args()
        max_seq = argv.max
        min_seq = max(argv.min, 2)
        clean = argv.clean
        for seq in range(min_seq, max_seq+1):
            if seq % 10000 == 0:
                now = datetime.now()
                print(f'{seq} at {now}')
            if clean:
                #remove old. Will get readded correctly after if it should be there.
                self.statistics.delete_merge(seq)
            subd = seq // 1000000
            elf_name = f'elf_{subd}/alq_{seq}.elf'
            elg_name = f'elg_{subd}/alq_{seq}.elg'
            if Path(elf_name).is_file():
                # No merge
                continue
            if Path(elg_name).is_file():
                with open(elg_name, 'r', encoding='ascii') as elg_file:
                    lines = self.get_last_two_lines(elg_file)
                    if len(lines) == 2:
                        pre_data = aliquot_util.parse_elf_line(lines[0])
                        post_data = aliquot_util.parse_to_line(lines[1])
                        merge_data = {}
                        merge_data['merge_from_sequence'] = seq
                        merge_data['merge_from_index'] = pre_data['index']
                        merge_data['num_before_merge'] = pre_data['num']
                        merge_data['merge_to_sequence'] = post_data['base']
                        merge_data['merge_to_index'] = post_data['index']
                        merge_data['num_after_merge'] = pre_data['aliquot_sum']
                        merge_data['processed'] = False
                        self.statistics.add_merge(merge_data)
            else:
                self.statistics.renew_merge_from_local_data(seq)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_find_merges.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    merge = FindMerge(pg)
    merge.find_merges()
    logger.info('finished')
