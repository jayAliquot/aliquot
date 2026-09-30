#!/usr/bin/env python

""" Rank open series based on a threshold.

    For threshold N we check N to N/2 for merge to open series and also value for
    elements over N within open series.
"""

import argparse
import sys
import os
import logging
from pathlib import Path
from operator import itemgetter
from datetime import datetime
from sql import SQL
from aliquot_data import AliquotData
import aliquot_util

logger = logging.getLogger(__name__)

class Ranking:
    def __init__(self, sql):
        self.aliquot_data = AliquotData(sql)
        self.max_inverse = 1000000000000
        self.sequences = {}

    def init_open_seq(self, max_seq, min_seq):
        self.sequences['all'] = {}
        self.sequences['seq'] = {}
        data = self.aliquot_data.get_incomplete()
        for pair in data:
            seq = pair[0]
            if seq < max_seq:
                self.sequences['all'][seq] = pair[1]
                if seq < min_seq:
                    self.sequences['seq'][seq] = {}
                    self.sequences['seq'][seq]['nums'] = {}
                    self.sequences['seq'][seq]['next_nums'] = {}

    def is_open(self, seq):
        if seq in self.sequences['all']:
            return True
        return False


    def load_progress_file(self, file_name):
        with open(file_name, 'r', encoding='ascii') as file:
            lines = file.readlines()
            lines_length = len(lines)
            current = int(lines[0])
            for line_num in range(1,lines_length,3):
                seq = int(lines[line_num])
                if not seq in self.sequences['seq']:
                    continue
                nums = lines[line_num + 1].strip()
                if len(nums) > 0:
                    num_list = nums.split(';')
                    for num in num_list:
                        self.sequences['seq'][seq]['nums'][int(num)] = True
                next_nums = lines[line_num + 2].strip()
                if len(next_nums) > 0:
                    next_num_list = next_nums.split(';')
                    for pair_string in next_num_list:
                        pair = pair_string.split(':')
                        next_num = int(pair[0])
                        self.sequences['seq'][seq]['next_nums'][next_num] = float(pair[1])
        return current

    def save_progress_file(self, current, file_name):
        file_name_bak = f'{file_name}.bak'
        if Path(file_name).is_file():
            os.rename(file_name, file_name_bak)
        with open(file_name, 'w+', encoding='ascii') as file:
            file.write(f'{current}\n')
            for seq in self.sequences['seq']:
                file.write(f'{seq}\n')
                num_string = ''
                for num in self.sequences['seq'][seq]['nums']:
                    if num_string == '':
                        num_string = f'{num}'
                    else:
                        num_string += f';{num}'
                file.write(f'{num_string}\n')
                next_num_string = ''
                for next_num in self.sequences['seq'][seq]['next_nums']:
                    sum_value = self.sequences['seq'][seq]['next_nums'][next_num]
                    if next_num_string == '':
                        next_num_string = f'{next_num}:{sum_value}'
                    else:
                        next_num_string += f';{next_num}:{sum_value}'
                file.write(f'{next_num_string}\n')

    def find_rank(self):
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('max', type=int, help='The threshold N')
        argv = parser.parse_args()
        max_arg = argv.max
        if max_arg % 2 == 1:
            max_arg += 1
        min_arg = max_arg // 2
        self.init_open_seq(max_arg, min_arg)
        subd = max_arg // 1000000
        rem = max_arg % 1000000
        if rem == 0:
            file_name = f'rank_{subd}M.txt'
        else:
            file_name = f'rank_{subd}M_{rem}.txt'
        current = max_arg
        if Path(file_name).is_file():
            current = self.load_progress_file(file_name)
        if current > 0:
            self.find_nrange(current, max_arg, min_arg, file_name)
            self.save_progress_file(0, file_name)
        downdriver_limit = max_arg * 3 // 4
        range_totals = {}
        over_n_totals = {}
        overall_totals = {}
        range_sum = 0
        over_n_sum = 0
        for seq in self.sequences['seq']:
            sums = []
            for _ in range(8):
                sums.append(0)
            num_list= self.sequences['seq'][seq]['nums']
            num_count = len(num_list)
            for num in num_list:
                self.add_range_type(num, downdriver_limit, sums)
            weight = [0, 32, 215, 0, 15, 143, 104, 0]
            total = 0
            sums_string = None
            for iq in range(8):
                total += weight[iq] * sums[iq]
                if sums_string:
                    sums_string += f', {sums[iq]}'
                else:
                    sums_string = f'({sums[iq]}'
            sums_string += ')'
            range_totals[seq] = total
            range_sum += total
            over_n = 0
            next_num_list = self.sequences['seq'][seq]['next_nums']
            next_num_count = len(next_num_list)
            for next_num in next_num_list:
                over_n += next_num_list[next_num]
            over_n_totals[seq] = over_n
            over_n_sum += over_n
            print(f'-----------------------------\n{seq}:')
            print(f'Total from Range: {total} {sums_string}')
            print(f'Count from Range: {num_count}')
            print(f'Sum for over N: {over_n:.3f}')
            print(f'Count for over N: {next_num_count}')
            weight_over_n = 1
            weight_range = 1
        seq_0_100k = {}
        seq_100k_1m = {}
        seq_1m_5m = {}
        seq_5m_10m = {}
        seq_10m_20m = {}
        for seq in self.sequences['seq']:
            # range_total/range_sum and over_n_total/over_n_sum allow us to normalize the weights.
            #
            # The weight_over_n and weight_range come from similar numbers of merges before and
            # after 40 million when run on 20 million sequences.
            # I think these weights may be good for the current code, but running
            # alq_analyze_merge.py for 0 to  min_arg could be used to check.
            #
            # Multiplying by min_arg is to make the values above 1 is an arbitrary scaling to lessen
            # use of fractions.
            overall_totals[seq] = (min_arg * range_totals[seq] * weight_range / range_sum +
                                   min_arg * over_n_totals[seq] * weight_over_n/ over_n_sum)
            if seq < 100000:
                seq_0_100k[seq] = overall_totals[seq]
            elif seq < 1000000:
                seq_100k_1m[seq] = overall_totals[seq]
            elif seq < 5000000:
                seq_1m_5m[seq] = overall_totals[seq]
            elif seq < 10000000:
                seq_5m_10m[seq] = overall_totals[seq]
            else:
                seq_10m_20m[seq] = overall_totals[seq]

        range_sorted = sorted(range_totals.items(),key=itemgetter(1),reverse=True)
        over_n_sorted = sorted(over_n_totals.items(),key=itemgetter(1),reverse=True)
        overall_sorted = sorted(overall_totals.items(),key=itemgetter(1),reverse=True)
        sorted_0_100k = sorted(seq_0_100k.items(),key=itemgetter(1),reverse=True)
        sorted_100k_1m = sorted(seq_100k_1m.items(),key=itemgetter(1),reverse=True)
        sorted_1m_5m = sorted(seq_1m_5m.items(),key=itemgetter(1),reverse=True)
        sorted_5m_10m = sorted(seq_5m_10m.items(),key=itemgetter(1),reverse=True)
        sorted_10m_20m = sorted(seq_10m_20m.items(),key=itemgetter(1),reverse=True)

        print('-----------------------------')
        print('Sorted by Overall')
        for item in overall_sorted:
            print(f'ff{item[0]}:{item[1]}')
        print('-----------------------------')
        print('Sorted by Range')
        for item in range_sorted:
            print(f'{item[0]}:{item[1]}')
        print('-----------------------------')
        print('Sorted by Over N')
        for item in over_n_sorted:
            print(f'{item[0]}:{item[1]}')
        print('-----------------------------')
        print('Sorted for 0 to 100k')
        for item in sorted_0_100k:
            print(f'aa{item[0]}:{item[1]}')
        print('------------------------------')
        print('Sorted for 100k to 1M')
        for item in sorted_100k_1m:
            print(f'bb{item[0]}:{item[1]}')
        print('------------------------------')
        print('Sorted for 1M to 5M')
        for item in sorted_1m_5m:
            print(f'cc{item[0]}:{item[1]}')
        print('------------------------------')
        print('Sorted for 5M to 10M')
        for item in sorted_5m_10m:
            print(f'dd{item[0]}:{item[1]}')
        print('------------------------------')
        print('Sorted for 10M to 20M')
        for item in sorted_10m_20m:
            print(f'ee{item[0]}:{item[1]}')

    def find_nrange(self, current, max_arg, min_arg, file_name):
        overbound = max_arg // 4
        try:
            for num in range(current, overbound, -2):
                if num % 1000 == 0:
                    print(num)
                if num % 100000 == 0 and num != max_arg:
                    now = datetime.now()
                    print(f'===Saving file {file_name}==={now}')
                    self.save_progress_file(num,file_name)
                    print('save done')
                data = self.aliquot_data.select_data(num, True)
                if not data:
                    print(f'Missing Entry for {num}')
                    self.save_progress_file(current, file_name)
                    sys.exit(1)
                next_num = data['aliquot_sum']
                if num >= min_arg or next_num > max_arg:
                    seq = self.check_open_merge(num, max_arg, min_arg)
                    if 0 < seq < min_arg:
                        if num >= min_arg:
                            self.sequences['seq'][seq]['nums'][num] = True
                        if next_num > max_arg:
                            self.sequences['seq'][seq]['next_nums'][next_num] = 0
                            self.add_series(next_num, seq, max_arg)
        except KeyboardInterrupt:
            print('Saving...')
            self.save_progress_file(num, file_name)
            sys.exit(0)

    def add_range_type(self, num, downdriver_limit, sums):
        below_dd = num <= downdriver_limit
        rem = num % 12
        if below_dd:
            rtype = 0
        else:
            rtype = 4
        if rem == 0:
            rtype += 0
        elif rem in (4, 8):
            rtype += 1
        elif rem in (2, 10):
            rtype += 2
        elif rem == 6:
            rtype += 3
        else:
            print('value should be even')
            return
        sums[rtype] += 1

    def get_pre_merge_data(self, elg_name):
        data = None
        with open(elg_name, 'r', encoding='ascii') as file:
            lines = file.readlines()
            if len(lines) < 2:
                print(f'Broken/short elg file: {elg_name}')
                return None
            pre_merge_line = lines[-2]
            data = aliquot_util.parse_elf_line(pre_merge_line)
        return data

    def check_open_merge(self, num, max_arg, min_arg):
        data = self.aliquot_data.select_data(num, True)
        curr = num
        base = data['base']
        done = False
        values = {}
        seq = 0
        if num < min_arg and data['aliquot_sum'] < max_arg:
            return seq
        while not done:
            if self.is_open(base):
                seq = base
                done = True
            else:
                subd = curr // 1000000
                elg_name = f'elg_{subd}/alq_{base}.elg'
                if Path(elg_name).is_file():
                    #skip elg entries.
                    elg_data = self.get_pre_merge_data(elg_name)
                    if elg_data:
                        curr = elg_data['aliquot_sum']
                        data = self.aliquot_data.select_data(curr, True)
                        if not data:
                            print(f'Unexpected missing data for {num},{curr}')
                            return 0

                        if base == data['base']:
                            print(f'cycle for {num} in {base}')
                            done = True
                        base = data['base']
                    else:
                        values[curr] = True
                        curr = data['aliquot_sum']
                        data = self.aliquot_data.select_data(curr, True)
                        if not data:
                            print(f'Unexpected missing data for {num},{curr}')
                            return 0
                        base = data['base']
                else:
                    aliquot_sum = data['aliquot_sum']
                    if curr == 1 or curr in values or aliquot_sum == 1:
                        done = True
                    else:
                        values[curr] = True
                        curr = data['aliquot_sum']
                        data = self.aliquot_data.select_data(curr, True)
                        if not data:
                            print(f'Unexpected missing data for {num},{curr}')
                            return 0
                        base = data['base']
        return seq

    def add_series(self, num, seq, max_arg):
        curr = num
        done = False
        values = {}
        while not done:
            if max_arg < curr < self.max_inverse:
                self.sequences['seq'][seq]['next_nums'][num] += 1000000 / curr
            data = self.aliquot_data.select_data(curr, True)
            if curr in values:
                done = True
            if not data:
                done = True
            else:
                values[curr] = True
                curr = data['aliquot_sum']
                if curr <= max_arg:
                    done = True

if __name__ == "__main__":
    logging.basicConfig(filename='alq_rank.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    ranking = Ranking(pg)
    ranking.find_rank()
    logger.info('finished')
