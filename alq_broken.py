#!/usr/bin/env python

""" Analyzes broken sequence numbers in the fdb

    Takes a file with the list of broken seqs from data using alq_report_broken.py
    Looks at the numbers and tries to find smaller broken and/or working terms.
"""
import re
import argparse
import logging
from sql import SQL
from aliquot_data import AliquotData
from aliquot_factordb import AliquotFactorDB
import aliquot_util

logger = logging.getLogger(__name__)

class ReportBrokenDB:
    """ Class to list broken sequences"""

    def __init__(self, sql):
        """Initializes subclasses used.

        Args:
            sql: postgres sql connection

        Attributes:
            aliquot: Used to parse elf line.
            factordb: Used to handle calls into the factordb.
        """
        self.aliquot_data = AliquotData(sql)
        self.factordb = AliquotFactorDB(sql)
        self.broken_numbers = []
        self.broken_sequences = []

    def update(self):
        """Updates report for a given range
        
        Parses min and max inputs and for all sequences within range that
        have an elf or elg file, it tests if it can get the sequence from the remote db.
        """
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('broken_file', help='file with broken sequences listed')
        argv = parser.parse_args()
        broken_file_name = argv.broken_file
        with open(broken_file_name, 'r+', encoding = 'ascii') as broken_file:
            lines = broken_file.readlines()
            for line in lines:
                if len(line) > 0:
                    num_type = r'^\d+$'
                    if not re.search(num_type, line):
                        print('Not a valid number')
                        return
                    num = int(line)
                    curr_data = self.aliquot_data.select_data(num, True)
                    if not curr_data:
                        curr_data = self.aliquot_data.select_data(num, False)
                    if not curr_data:
                        print(f'No data known for {num}')
                        continue
                    self.process_num(curr_data)
        self.broken_numbers.sort()
        for broken in self.broken_numbers:
            print(broken)

    def process_num(self, curr_data):
        """Print whether known factors are broken"""

        num = curr_data['num']
        seq = curr_data['base']
        index = curr_data['index']
        factor_string = curr_data['factor_string']
        if self.report_on_num(num, seq):
            print('---------------------')
            print(f'For sequence: {seq} at index {index}:')
            print(f'    Known factors: {factor_string}')
            print(f'broken: {num}')
            if factor_string != '':
                factors = aliquot_util.to_factors(factor_string)
                if factors:
                    for prime in factors:
                        curr_num = num
                        max_power = factors[prime]
                        for _ in range(0, int(max_power)):
                            curr_num = curr_num // int(prime)
                            if self.report_on_num(curr_num, seq):
                                print(f'broken: {curr_num}')
                            else:
                                print(f'ok    : {curr_num}')
        print('')

    def report_on_num(self, num, seq):
        """ Report on broken state for a single number"""
        if not self.factordb.check_factors(num, seq):
            self.broken_numbers.append(num)
            return True
        return False

def main_report():
    """Call report broken"""

if __name__ == "__main__":
    logging.basicConfig(filename='alq_broken.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    report_broken = ReportBrokenDB(pg)
    report_broken.update()
    logger.info('finished')
