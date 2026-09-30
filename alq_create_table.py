#!/usr/bin/env python

""" Initial creation of tables for postgres

    This is untested as it was only run once long ago.  Changes occur but there is
    no easy way to make sure the code remains correct.
"""

import logging
import argparse
from sql import SQL
from aliquot_data import AliquotData
from aliquot_data_statistics import AliquotDataStatistics

logger = logging.getLogger(__name__)

def main(sql):
    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('--status', action='store_true', help='Add status table')
    parser.add_argument('--digits', action='store_true', help='Add digits table')
    parser.add_argument('--stats',  action='store_true', help='Add stats table')
    parser.add_argument('--statistics',  action='store_true', help='Add statistics table')    
    argv = parser.parse_args()

    status = argv.status
    digits = argv.digits
    stats = argv.stats
    statistics = argv.statistics
    aliquot_data = AliquotData(sql)
    aliquot_data.add_tables(digits = digits, status = status, stats = stats)
    if statistics:
        aliquot_data_statistics = AliquotDataStatistics(sql)
        aliquot_data_statistics.add_statistics_tables()

if __name__ == "__main__":
    logging.basicConfig(filename='alq_create_table.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    main(pg)
    logger.info('finished')
