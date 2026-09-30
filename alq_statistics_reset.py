#!/usr/bin/env python

"""Complete reset of statistics data.

Running this file will completely clear the statistics.  The idea is to do a clean run from
the start.  The reason for this is that it is very difficult to avoid duplicates when 
sequences change due to a new merge.  The amount of accuracy lost is not large so full resets
can be rarely.

To get fully accurate results.
1 - use alq_statistics_reset.py to clear all runs data.
2 - stop any program that changes the data.
3 - if new sequences, then alq_find_merges.py and alq_init_status.py may be needed.
4 - At this point it may be worth making a dated copy to work with so updates can continue
5 - run alq_verify.py with -f to make sure all merge data is correct (slow)
6 - Run set_stats.py/alq_stats.py and alq_unbounded.py for the current stats and open sequences. 
7 - run alq_runs.py to recreate the runs data (also slow)
"""

import sys
import logging
from sql import SQL
from aliquot_data_statistics import AliquotDataStatistics

logger = logging.getLogger(__name__)

def reset_stats(sql):
    """Delete the statistics table data"""
    aliquot_data_statistics = AliquotDataStatistics(sql)
    aliquot_data_statistics.statistics_reset()

if __name__ == "__main__":
    logging.basicConfig(filename='alq_statistics_reset.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    while True:
        confirmation = input('Are you sure you want to delete all current statistics '
                             'data? (yes/no): ').strip().lower()

        if confirmation == 'yes':
            print("Proceeding with deletion...")
            logger.info('Deleting existing statistics.')
            break
        if confirmation == "no":
            print('Action canceled.')
            logger.info('Action canceled.')
            sys.exit()
        print('Invalid input. Please enter "yes" or "no".')
    reset_stats(pg)
    logger.info('finished')
