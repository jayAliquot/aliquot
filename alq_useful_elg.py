#!/usr/bin/env python

""" Checks if elg file vs reaching 25 digits before merge.

    Note that running on large ranges should be expected to be slow, 500k entries can take an hour.
"""

import argparse
import sys
import logging
from pathlib import Path
from datetime import datetime
from sql import SQL
from aliquot_data_statistics import AliquotDataStatistics

logger = logging.getLogger(__name__)

class CheckElg():
    def __init__(self, sql):
        self.stats = AliquotDataStatistics(sql)
        self.size_count = {}

    def check_all(self):
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('min', type=int, help='Minimum value of the range')
        parser.add_argument('max', type=int, help='Maximum value of the range')
        argv = parser.parse_args()
        max_seq = argv.max
        min_seq = max(argv.min, 1)
        self.check_range(min_seq, max_seq)

    def check_range(self, min_seq, max_seq):
        now = datetime.now()
        time_string=now.strftime('%H%M_%m%d%Y')
        subd = min_seq // 1000000
        alq_file_name = f'merge_elg_{subd}M_{time_string}.sh'
        with open(alq_file_name, 'w+', encoding='ascii') as alq_file:
            for seq in range(min_seq, max_seq+1):
                if seq % 1000 == 0:
                    print(seq, file=sys.stderr)
                self.check_elg(seq, alq_file)
        count = 0
        for key in sorted(self.size_count):
            count += 1
            print(f'{key}: {self.size_count[key]}', end = ' ')
            if count % 5 == 0:
                print('')
        print(f'\n\nFile name is: {alq_file_name}')

    def check_elg(self, seq, alq_file):
        subd = seq // 1000000
        elf_name = f'elf_{subd}/alq_{seq}.elf'
        elg_name = f'elg_{subd}/alq_{seq}.elg'
        merge_name = f'elg_{subd}/alq_{seq}.merge'
        if Path(elf_name).is_file():
            # no elg if the elf file exists.
            return
        #t2 = time.perf_counter()
        has_elg = Path(elg_name).is_file()
        stats_data = self.stats.get_stats_data(seq)
        if not stats_data:
            print(f'For {seq}, there is no stats data.')
            return
        max_digits = stats_data['max_digits']
        if max_digits in self.size_count:
            pair = self.size_count[max_digits]
            if has_elg:
                pair = (pair[0] + 1, pair[1])
            else:
                pair = (pair[0], pair[1] + 1)
            self.size_count[max_digits] = pair
        else:
            if has_elg:
                pair = (1, 0)
            else:
                pair = (0, 1)
            self.size_count[max_digits] = pair
        if max_digits >= 25 and not has_elg:
            print(f'For {seq}, reached {max_digits} digits with no elg.')
            alq_file.write(f'python3 alq_create_elf.py {seq}\n')
            alq_file.write(f'python3 alq_elg.py {seq} {seq}\n')
            alq_file.write(f'python3 alq_adjust_fdb_status.py {seq} {seq}\n')            
        if max_digits < 25 and has_elg:
            print(f'For {seq}, reached {max_digits} digits and then merged, so is not needed.')
            alq_file.write(f'mv {elg_name} {merge_name}\n')
            alq_file.write(f'python3 alq_adjust_fdb_status.py {seq} {seq}\n')
            alq_file.flush()


if __name__ == "__main__":
    logging.basicConfig(filename='alq_useful_elg.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    check_elg = CheckElg(pg)
    check_elg.check_all()
    logger.info('finished')
