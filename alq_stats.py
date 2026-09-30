#!/usr/bin/env python

""" Outputs statistics for aliquot sequences from the db for a given range.

Whether a merge is listed depends if the length before the merge is longer than minimum merge 
report length.  This can be set with the -m flag and defaults at 100.
"""

import logging
import argparse
import sys

from sql import SQL
from aliquot_data_statistics import AliquotDataStatistics
import aliquot_util

logger = logging.getLogger(__name__)


def report_stats(sql_connection:SQL, min_seq:int, max_seq:int, min_report_length:int) -> None:
    """Output stats for the given range of sequences.

    Args:
        sql_connection: postgres sql connection
        min_seq: Minimum sequence to verify.
        max_seq: Maximum sequence to verify.
        min_report_length: Shortest for a sequence before merging to report individulally.
    """

    logger.info('Verify range %s to %s', min_seq, max_seq)

    statistics_server = AliquotDataStatistics(sql_connection)

    min_seq = max(min_seq, 1)
    stats = {}
    spec = ''

    spec = aliquot_util.get_seq_spec(min_seq, max_seq)
    stats_file_name = f'stats{spec}.txt'
    print(stats_file_name)
    with open(stats_file_name, 'w+', encoding='ascii') as stats_file:
        for iq in range(min_seq, max_seq+1):
            if iq % 10000 == 0:
                print(iq, file=sys.stderr)
            stats_data = statistics_server.get_stats_data(iq)
            if not stats_data:
                print(f'Skipping {iq}: No stats data.',file = sys.stderr)
                continue
            stat_string = stats_data['stats_string']
            if stat_string[0:5] == 'Merge':
                index_count = int(stat_string[12:16])
                if index_count < min_report_length:
                    stat_string = 'Merge'
            if stat_string in stats:
                stats[stat_string] += 1
            else:
                stats[stat_string] = 1
            stat_string2 = 'Summary ' + stat_string.split()[0]
            if stat_string2 in stats:
                stats[stat_string2] += 1
            else:
                stats[stat_string2] = 1

        for key in sorted(stats):
            if stats[key] == 1:
                stats_file.write(f'{key}\n')
            else:
                stats_file.write(f'{key}:{stats[key]}\n')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_stats.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Maximum value of the range')
    parser.add_argument('max', type=int, help='Minimum value of the range')
    parser.add_argument('-m', type=int, default=100, help='Minimum merge report length')
    argv = parser.parse_args()

    pg = SQL()

    report_stats(pg, argv.min, argv.max, argv.m)

    logger.info('finished')
