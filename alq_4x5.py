#!/usr/bin/env python

""" Finds aliquot sum statistics for numbers between min and max and displays as 4x5 table.

    Uses the local data set so max shouldn't be more than the max sequence number (40 million)
    For each number in the range it calculates the ratio of aliquot sum divided by the number.
    It also calculates the number mod 12.
    There are 4 ratios for the rows: 2x or more(double), 2x to 1x(over), 1x to 3/4x(under),
    3/4x or less (dd which means num is a down driver)
    There are 5 values for the aliquot sum  mod 12; div 2 (even and not div by 3 or 4),
    div 4 (not div by 3), div 6 (not div by 12), div 12, and odd.
    The 20 values in the second table are the counts for the 20 cases.  The first table is
    normalized so the sum of the entries is approximately 1000 and is not exact.
    The normalized table is fairly consistent across most ranges in the millions.
    This was used to set weights for alq_rank.py to estimate merge chances.
"""

import argparse
import logging
from sql import SQL
from aliquot_data import AliquotData

logger = logging.getLogger(__name__)

class AnalyzeSum:
    """ Class does the work for getting the statistics mentioned above"""

    def __init__(self, sql):
        self.aliquot_data = AliquotData(sql)

    @staticmethod
    def mod_error():
        """Not a module warning"""

        print('This program is designed to be run seperately "python3 alq_4x5.py"')
        print('refactor to enable module calls')

    def analyze(self):
        """ Handles the input and calls for each sequence.

        From the sequence range it calls all analyse_seq for each sequence.
        The results are then shown in output_results
        """

        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('min', type=int, help='Minimum value of the range')
        parser.add_argument('max', type=int, help='Maximum value of the range')
        argv = parser.parse_args()
        max_seq = argv.max
        min_seq = argv.min
        # Make max seq even
        max_seq += max_seq % 2
        results = {}
        results['double'] = {}
        results['over'] = {}
        results['under'] = {}
        results['dd'] = {}
        for _, row in results.items():
            row['2'] = 0
            row['4'] = 0
            row['6'] = 0
            row['12'] = 0
            row['1'] = 0

        for seq in range(min_seq, max_seq+2, 2):
            self._analyse_seq(seq, results)

        # divider is used to create a second table whose entries sum to 2000.
        # These are frequencies unaffected by the size of the range examimed.
        # 2000 is arbitrary but gives good results for this program.
        divider = (max_seq - min_seq)/2000
        self._output_results(results, divider)

    def _analyse_seq(self, seq, results):
        """For the input sequence add the result to results.

        For the given seq number, we find its aliquot sum and classify it based on
        remainer mod 12 and its ratio to seq.  This gives us a table with counts for
        each possible result.
        """

        if seq % 10000 == 0:
            print('.', end='', flush=True)
        data = self.aliquot_data.select_data(seq, True)
        num = data['num']
        aliquot_sum = data['aliquot_sum']
        if aliquot_sum >= 2 * num:
            ratio = 'double'
        elif aliquot_sum >= num:
            ratio = 'over'
        elif aliquot_sum >= (num * 3) // 4:
            ratio = 'under'
        else:
            ratio = 'dd'
        remainder = aliquot_sum % 12
        if remainder == 0:
            rem_type = '12'
        elif remainder == 6:
            rem_type = '6'
        elif remainder in (4,8):
            rem_type = '4'
        elif remainder in (2,10):
            rem_type = '2'
        else:
            rem_type = '1'
        results[ratio][rem_type] += 1

    @staticmethod
    def _output_results(results, divider):
        """Uses print to output the results.

        The results are two 4x5 tables.  The first shows a frequency where the values sum to 2000.
        This allows one to compare vs differrnt numbers of sequences.  The second table is the
        raw counts and so sums to the number of sequeces checked.
        """

        print('')
        print('|ratio   |div 2 |div 4 |div 6 |odd   |')
        print('|--------|------|------|------|------|')
        for row in results:
            print(f'|{row:<8}',end='')
            for col in results[row]:
                weight = results[row][col] // divider
                if results[row][col] % divider >= divider/2:
                    weight += 1
                print(f'|{weight:<6.0f}', end='')
            print('|')
        print('')
        print('')
        print('|ratio   |div 2 |div 4 |div 6 |odd   |')
        print('|--------|------|------|------|------|')
        for row in results:
            print(f'|{row:<8}',end='')
            for col in results[row]:
                weight = results[row][col]
                print(f'|{weight:<6}', end='')
            print('|')
        print('')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_4x5.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    analyze_sum = AnalyzeSum(pg)
    analyze_sum.analyze()
    logger.info('finished')
