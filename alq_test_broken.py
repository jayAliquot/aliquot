#!/usr/bin/env python

""" Finds sequences that do not return correctly from the online factor database.

    Attempts to find the final entry in the factor database.  If this fails it looks to see
    if an entry doesn't return correctly and reports it.
"""

from pathlib import Path
import logging

from sql import SQL
import aliquot_util
from aliquot_factordb import AliquotFactorDB
from aliquot_data import AliquotData

logger = logging.getLogger(__name__)

class ReportBrokenDB:
    """ Class to list broken sequences"""

    def __init__(self, sql):
        """Initializes subclasses used.

        Attributes:
            aliquot: Used to parse elf line.
            factordb: Used to handle calls into the factordb.
        """
        self.factordb = AliquotFactorDB(sql)
        self.aliquot_data = AliquotData(sql)
        self.known_broken_data = []
        self.get_broken_list()

    def get_lines(self, file_name):
        """Gets lines from the file"""
        with open(file_name, 'r', encoding = 'ascii') as file:
            lines = file.readlines()
        return lines

    def get_broken_list(self):
        """Gets known broken sequences"""

        broken_list_file_name = 'fdb_error.txt'
        lines = self.get_lines(broken_list_file_name)
        for line in lines:
            if len(line) > 0:
                data = self.get_broken_data(line)
                if data:
                    self.known_broken_data.append(data)

    def get_broken_data(self, line):
        """Parses sentences about known broken sequences"""

        words = line.split(' ')
        if len(words) == 9:
            data = {}
            data['base'] = int(words[2])
            data['index'] = int(words[5][:-1])
            data['num'] = int(words[6])
            return data
        print(f'{line} is not expected format')
        return None

    def report(self):
        """Updates report for a given range
        
        Parses min and max inputs and for all sequences within range that
        have an elf or elg file, it tests if it can get the sequence from the remote db.
        """
        not_fixed = []
        fixed = []
        still_broken_list = []
        print('Not retested')
        for broken in self.known_broken_data:
            seq = broken['base']
            index = broken['index']
            num = broken['num']
            digits = len(str(num))
            subd = seq // 1000000
            elf_name = f'elf_{subd}/alq_{seq}.elf'
            if Path(elf_name).is_file():
                past_break = aliquot_util.get_line_count(elf_name) - index - 1
            local_data = self.aliquot_data.select_data(num, True)
            is_complete = True
            if not local_data:
                is_complete = False
                local_data = self.aliquot_data.select_data(num, False)
                if not local_data:
                    print(f'For {seq}:{index} - Error occcured')
            still_broken = True
            #if self.factordb.check_factors(num, seq):
            #    still_broken = False
            data = {
                'seq': seq,
                'index': index,
                'digits': digits,
                'num': num,
                'after': past_break,
                'complete': is_complete,
                'final_digits': len(str(aliquot_util.get_final_num(elf_name)))
            }
            if still_broken:
                still_broken_list.append(num)
                not_fixed.append(data)
            else:
                fixed.append(data)
        for item in fixed:
            seq = item['seq']
            index = item['index']
            after = item['after']
            complete = item['complete']
            digits = item['digits']
            print(f'Fixed {seq}:{index} - digits: {digits}, known after: {after}, '
            f'is_complete: {complete}')

        print('')
        not_fixed.sort(key=lambda x: x['seq'])
        for item in not_fixed:
            seq = item['seq']
            index = item['index']
            after = item['after']
            complete = item['complete']
            digits = item['digits']
            final = item['final_digits']
            print(f'Not Fixed {seq}:{index} - digits: {digits}, known after: {after}, '
                  f'final: {final}')
        for item in not_fixed:
            num = item['num']
            data = self.aliquot_data.select_data(num, True)
            if not data:
                data = self.aliquot_data.select_data(num, False)
            if data:
                seq = data['base']
                index = data['index']
                factor_string = data['factor_string'].replace('*', ' * ')
                print('')
                print(f'From alq_{seq}.elf:')
                print(f'{index} . {num} = {factor_string}')
                num = data['aliquot_sum']
                if num > 0:
                    data = self.aliquot_data.select_data(num, True)
                    if not data:
                        data = self.aliquot_data.select_data(num, False)
                    if data:
                        seq = data['base']
                        index = data['index']
                        factor_string = data['factor_string'].replace('*', ' * ')
                        print(f'{index} . {num} = {factor_string}')
            else:
                seq = item['seq']
                print(f'Did not find data for {seq}')
        with open('fdb_error_num.txt', 'w', encoding = 'ascii') as file:
            for item in not_fixed:
                num = item['num']
                data = self.aliquot_data.select_data(num, True)
                if not data:
                    data = self.aliquot_data.select_data(num, False)
                if data:
                    seq = data['base']
                    index = data['index']
                    factor_string = data['factor_string'].replace('*', ' * ')
                seq = item['seq']
                after = item['after'] + 1
                subd = seq // aliquot_util.INTERVAL
                file.write(f'From alq_{seq}.elf:\n')
                file.write(f'{index} . {num} = {factor_string}\n\n')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_report_broken.log', level=logging.INFO)
    logger.info('Started')
    pq = SQL()
    report_broken = ReportBrokenDB(pq)
    report_broken.report()
    logger.info('finished')
