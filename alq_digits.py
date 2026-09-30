#!/usr/bin/env python

"""Computes driver information for a given number of digits.

"""

import argparse
import logging
from sql import SQL
from aliquot_data import AliquotData
import aliquot_util

logger = logging.getLogger(__name__)

class AliquotRuns():
    """Chance of escape from a driver.

    Gives all drivers for a given number of digits.
    """
    def __init__(self, sql):
        """ Initializes main modules used by the class

        Variables:
           aliquot_data: Gets the sequence series from the data base.
           statistics: Called to set the run data from the series.
        """
        self.aliquot_data = AliquotData(sql)

    def calc_statistics(self):
        """ Main public function to calculate escape percentage at a given size

        Args:
           digits: The size to check percentage chance of escape.
        """
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('digits', type=int, help='digits to check')
        argv = parser.parse_args()
        digits = argv.digits
        seq_steps = self.aliquot_data.get_all_digit_table(digits)
        chance_table = {}
        count = 0
        print('Count: ', end='')
        for step in seq_steps:
            count += 1
            if count % 100000 == 0:
                print('.',end='', flush=True)
            num = step[1]
            aliquot_sum = step[2]
            driver_uid = aliquot_util.calc_driver_uid(num)
            next_driver = aliquot_util.calc_driver_uid(aliquot_sum)
            if not driver_uid in chance_table:
                chance_table[driver_uid] = {'match': 0, 'escape':0}
            if driver_uid == next_driver:
                chance_table[driver_uid]['match'] += 1
            else:
                chance_table[driver_uid]['escape'] += 1
        print('')
        for driver in sorted(chance_table.keys()):
            match = chance_table[driver]['match']
            escape = chance_table[driver]['escape']
            total = match + escape
            if escape > 0:
                one_in = total/escape
            else:
                one_in = 'N/A'
            print(f'Driver: {driver}, Escape: {escape}, Match: {match}, One in: {one_in}')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_digits.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    aliquot_runs = AliquotRuns(pg)
    aliquot_runs.calc_statistics()
    logger.info('finished')
