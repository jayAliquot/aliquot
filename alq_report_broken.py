#!/usr/bin/env python

""" Finds sequences that do not return correctly from the online factor database.

    Attempts to find the final entry in the factor database.  If this fails it looks to see
    if an entry doesn't return correctly and reports it.
"""

import argparse
import time
import logging
import subprocess
from pathlib import Path
from datetime import datetime

from sql import SQL
import aliquot_util
from aliquot_factordb import AliquotFactorDB

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
        self.broken_numbers = []
        self.broken_sequences = []
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
            print(data)
            return data
        print(f'{line} is not expected format')
        return None

    def update(self):
        """Updates report for a given range
        
        Parses min and max inputs and for all sequences within range that
        have an elf or elg file, it tests if it can get the sequence from the remote db.
        """
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('min', type=int, help='Minimum value of the range')
        parser.add_argument('max', type=int, help='Maximum value of the range')
        argv = parser.parse_args()
        max_seq = argv.max
        min_seq = max(argv.min, 1)
        time_string = datetime.now().strftime('%H%M_%m%d%Y')
        get_report_name = f'report_error_{time_string}.txt'
        failed = []
        retest = 0
        with open(get_report_name, 'w+', encoding = 'ascii') as report_file:
            print(f'start: {datetime.now()}')
            for seq in range(min_seq, max_seq+1):
                subd = seq // 1000000
                elg_name = f'elg_{subd}/alq_{seq}.elg'
                elf_name = f'elf_{subd}/alq_{seq}.elf'
                if Path(elg_name).is_file() or Path(elf_name).is_file():
                    if not self.test_sequence_initial(seq):
                        test = (seq, False)
                        failed.append(test)
                if seq % 10000 == 0:
                    print(f'{seq}:{datetime.now()}')
                if seq % 20000 == 0:
                    final = len(failed)
                    while retest + 5 < final:
                        self.test_sequence_repeat(failed, retest, report_file, False)
                        retest += 1
                    print(f'End retest: {datetime.now()}')

            print(f'Final test: {datetime.now()}')
            while retest < len(failed):
                self.test_sequence_repeat(failed, retest, report_file, True)
                retest += 1
            for seq in self.broken_sequences:
                report_file.write(f'Sequence {seq} failed to return correctly.\n')
            numbers = []
            report_file.write('\n')
            for broken_num in self.broken_numbers:
                seq = broken_num['sequence']
                index = broken_num ['index']
                num = broken_num['num']
                numbers.append(num)
                report_file.write(f'For sequence {seq} at index {index}, {num} is broken.\n')
            numbers.sort()
            report_file.write('\nBroken Number list:\n')
            for num in numbers:
                report_file.write(f'{num}\n')
            report_file.flush()

    def test_sequence_initial(self, seq):
        """Tests a single sequence for issues
        
        If the final index of a sequence can be retrieved, then all is fine.
        If it fails, then it tries each line to see which ones fail.
        """
        done = False
        index = self.factordb.find_last_index(seq, 10, False )
        if index:
            return True
        while not done:
            try:
                index = None
                for _ in range(0,5):
                    index = self.factordb.find_last_index(seq, 10, True)
                    time.sleep(5)
                    if index:
                        # Sequence is ok
                        return True
                print(f'Initial: Unable to access final index for sequence {seq}')
                done = True
            except subprocess.TimeoutExpired:
                print(f'Timeout - sleeping 5 min to try again for {seq}')
                time.sleep(300)
        return False

    def is_known_broken(self, seq):
        """Find if seq is in known broken data"""

        for broken in self.known_broken_data:
            if broken['base'] == seq:
                return broken
        return None

    def test_sequence_repeat(self, failed, retest, report_file, is_final):
        """Tests a single sequence for issues
        
        If the final index of a sequence can be retrieved, then all is fine.
        If it fails, then it tries each line to see which ones fail.
        """
        test = failed[retest]
        seq = test[0]
        check_seq = test[1]
        done = False
        data = self.is_known_broken(seq)
        if data:
            index  = data['index']
            curr = data['num']
            if not self.factordb.check_factors(curr, seq):
                has_error = True
                print(f'Known broken for {seq}:{index} at {curr}: {datetime.now()}')
                report_file.write(f'Sequence: {seq}, index: {index}, '
                                  f'number: {curr} - query failed.\n')
                report_file.flush()
                broken_num = {}
                broken_num['sequence'] = seq
                broken_num['index'] = index
                broken_num['num'] = curr
                self.broken_numbers.append(broken_num)
                return
        while not done:
            try:
                index = None
                for _ in range(0,10):
                    index = self.factordb.find_last_index(seq, 10, True)
                    time.sleep(10)
                    if index:
                        print(f'Sequence {seq} worked on the repeat test')
                        # Sequence is ok
                        return
                print(f'Repeat: Unable to access final index for sequence {seq}')
                report_file.write(f'Attempt to find last index failed for {seq}\n')
                report_file.flush()
                done = True
            except subprocess.TimeoutExpired:
                print(f'Timeout - sleeping 10 min to try again for {seq}')
                time.sleep(600)
        has_error = False
        if not check_seq:
            has_error = self.check_full_sequence(seq, report_file)
        if not has_error:
            if is_final:
                self.broken_sequences.append(seq)
            else:
                test = (seq, True)
                failed.append(test)

    def check_full_sequence(self, seq, report_file):
        """Check each entry of sequence for error"""

        subd = seq // 1000000
        elg_name = f'elg_{subd}/alq_{seq}.elg'
        elf_name = f'elf_{subd}/alq_{seq}.elf'
        if Path(elf_name).is_file():
            lines = self.get_lines(elf_name)
            curr_file = elf_name
        else:
            lines = self.get_lines(elg_name)
            curr_file = elg_name
            lines = lines[:-1]

        if not lines or len(lines) == 0:
            print(f'empty file {curr_file}')
        has_error = False
        for line in lines:
            data = aliquot_util.parse_elf_line(line)
            index  = data['index']
            curr = data['num']
            if not self.factordb.check_factors(curr, seq):
                has_error = True
                print(f'Not able to reach db for {seq}:{index} at {curr}: {datetime.now()}')
                report_file.write(f'Sequence: {seq}, index: {index}, '
                                  f'number: {curr} - query failed.\n')
                report_file.flush()
                broken_num = {}
                broken_num['sequence'] = seq
                broken_num['index'] = index
                broken_num['num'] = curr
                self.broken_numbers.append(broken_num)
            time.sleep(1)
        return has_error

if __name__ == "__main__":
    logging.basicConfig(filename='alq_report_broken.log', level=logging.INFO)
    logger.info('Started')
    pq = SQL()
    report_broken = ReportBrokenDB(pq)
    report_broken.update()
    logger.info('finished')
