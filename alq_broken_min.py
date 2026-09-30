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
            min_broken = []
            for line in lines:
                if len(line) > 0:
                    num_type = r'^\d+$'
                    if not re.search(num_type, line):
                        print('Not a valid number')
                        return
                    num = int(line)
                    is_min = True
                    for broken in min_broken:
                        if num % broken == 0:
                            is_min = False
                            break
                    if is_min:
                        min_broken.append(num)
                        print(num)


if __name__ == "__main__":
    logging.basicConfig(filename='alq_broken_min.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    report_broken = ReportBrokenDB(pg)
    report_broken.update()
    logger.info('finished')
