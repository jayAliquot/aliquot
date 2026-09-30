#!/usr/bin/env python

""" Outputs statistics for aliquot sequences from the db for a given range.

    Note that running on large ranges should be expected to be slow, 500k entries can take an hour.
"""

import argparse
import sys
import logging
from sql import SQL
from aliquot_data_statistics import AliquotDataStatistics

logger = logging.getLogger(__name__)

class AliquotStats():
    def __init__(self, sql):
        self.aliquot_data_statistics = AliquotDataStatistics(sql)
        self.merge_counts=[]
        for iq in range(10,205,5):
            count = {}
            count['digits'] = iq
            count['not_reached'] = 0
            count['open_below'] = 0
            count['open_above'] = 0
            count['merged'] = 0
            self.merge_counts.append(count)

    def calc_all(self):
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('min', type=int, help='Maximum value of the range')
        parser.add_argument('max', type=int, help='Minimum value of the range')
        argv = parser.parse_args()
        max_seq = argv.max
        min_seq = argv.min
        self.output_stats(min_seq, max_seq)

    def output_stats(self, min_seq, max_seq):
        spec = ''
        interval = 1000000
        if min_seq in (0, 1):
            subd = max_seq // interval
            diff = max_seq - subd * interval
            if diff == 0:
                spec = f'_{subd}M'
            else:
                spec = f'_{subd}M_{diff}'
        else:
            min_subd = min_seq // interval
            min_diff = min_seq - min_subd * interval
            if min_diff == 0:
                min_spec = f'_{min_subd}M'
            else:
                min_spec = f'_{min_subd}M_{min_diff}'
            max_subd = max_seq // interval
            max_diff = max_seq - max_subd * interval
            if max_diff == 0:
                max_spec = f'{max_subd}M'
            else:
                max_spec = f'_{max_subd}M_{max_diff}'
            spec = f'_{min_spec}-{max_spec}'
        stats_file_name = f'merge_percent{spec}.txt'
        print(stats_file_name)
        with open(stats_file_name, 'w+', encoding='ascii') as stats_file:
            for iq in range(min_seq, max_seq+1):
                if iq == 0:
                    #No aliquot sum for zero so skip it.
                    continue
                if iq % 10000 == 0:
                    print(iq, file=sys.stderr)
                stats_data = self.aliquot_data_statistics.get_stats_data(iq)
                if not stats_data:
                    print(f'Skipping {iq}: No stats data.',file = sys.stderr)
                    continue
                for counts in self.merge_counts:
                    if stats_data['max_digits'] >= counts['digits']:
                        if stats_data['complete']:
                            counts['merged'] += 1
                        elif len(str(stats_data['num'])) >= counts['digits']:
                            counts['open_above'] += 1
                        else:
                            counts['open_below'] += 1
                    elif not stats_data['complete']:
                        counts['not_reached'] += 1
            stats_file.write('[TABLE="border: 1, cellpadding: 1, width: 500"]\n')
            stats_file.write('  [TR]\n')
            stats_file.write('    [TD]Digits[/TD]\n')
            stats_file.write('    [TD]Total[/TD]\n')
            stats_file.write('    [TD]Merged[/TD]\n')
            stats_file.write('    [TD]Open(below)[/TD]\n')
            stats_file.write('    [TD]% Merged[/TD]\n')
            stats_file.write('    [TD]Not Reached[/TD]\n')
            stats_file.write('  [/TR]\n')
            for counts in self.merge_counts:
                digits = counts['digits']
                merged = counts['merged']
                open_above = counts['open_above']
                open_below = counts['open_below']
                total_open = open_above + open_below
                not_reached = counts['not_reached']
                total = merged + total_open
                percent = merged * 100 / total
                string_open = f'{total_open}({open_below})'
                stats_file.write('  [TR]\n')
                stats_file.write(f'    [TD]{digits}[/TD]\n')
                stats_file.write(f'    [TD]{total}[/TD]\n')
                stats_file.write(f'    [TD]{merged}[/TD]\n')
                stats_file.write(f'    [TD]{string_open}[/TD]\n')
                stats_file.write(f'    [TD]{percent:4.2f}%[/TD]\n')
                stats_file.write(f'    [TD]{not_reached}[/TD]\n')
                stats_file.write('  [/TR]\n')
            stats_file.write('[/TABLE]\n')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_percent_merge.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    stats = AliquotStats(pg)
    stats.calc_all()
    logger.info('finished')
