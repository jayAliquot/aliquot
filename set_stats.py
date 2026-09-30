#!/usr/bin/env python

"""Computes stats data for each sequence in a given range.

The stats data includes whether the sequence merges, cycles, or is open ended, and maximum
digits reached (before merge). Running alq_stats.py outputs the data into stats files.

Note that running on large ranges should be expected to be slow, 500k entries can take an hour.
There is a status on whether stats needs to be rerun to speed this up.
"""

import argparse
import sys
import logging

from sql import SQL
from aliquot_types import AlqData, StatsData
from aliquot_data_statistics import AliquotDataStatistics
from aliquot_data import AliquotData
from aliquot_status import AliquotStatus

logger = logging.getLogger(__name__)

def run_calc_stats(sql_connection:SQL, min_seq:int, max_seq:int, force:bool) -> None:
    """Stores stats data into the local db for a given range.

    Args:
        sql_connection: postgres sql connection
        min_seq: Minimum sequence to process.
        max_seq: Maximum sequence to process.
        force: If True process all sequences, otherwise use status flag to decide.
    """

    logger.info('Set stats range %s to %s', min_seq, max_seq)

    statistics_data_service = AliquotDataStatistics(sql_connection)
    data_service = AliquotData(sql_connection)
    status_service = AliquotStatus(sql_connection)

    for seq in range(min_seq, max_seq+1):
        if seq % 10000 == 0:
            print(seq, file=sys.stderr)
        stats_data = statistics_data_service.get_stats_data(seq)
        status_data = status_service.get_status(seq)
        if not force and stats_data and status_data and not status_data['stats_update']:
            num = stats_data['num']
            complete = stats_data['complete']
            data:AlqData = data_service.select_data(num, complete)
            if _stats_match(stats_data, data):
                #no change found so skip.
                continue
            print(f'Error with stats status flag found for {seq}')
        stats_data = get_stats(seq, data_service)
        statistics_data_service.set_stats_data(seq, stats_data)
        status_service.update_stats(seq, False)

def _stats_match(stats_data: StatsData, num_data:AlqData) -> bool:
    if not num_data:
        return False
    if stats_data['base'] != num_data['base'] or stats_data['index'] != num_data['index']:
        return False
    return True

def get_stats(seq:int, data_service:AliquotData) -> StatsData:
    """Get stats data for a single sequence.

    Args:
        seq: The sequence to get stats for.
        data_service: Gets the sequence from the local db.
    """
    values = {}
    done = False
    curr = seq
    index = 0
    stats_data = {}
    complete = True
    prev_data = {}
    max_digits = 0
    final_data = None
    while not done:
        values[curr] = index
        max_digits = max(max_digits, len(str(curr)))
        data = data_service.select_data(curr, True)
        if data:
            next_value = data['aliquot_sum']
            final_data = _handle_data(seq, index, data, values, stats_data, prev_data)
            if final_data:
                done = True
        else:
            done = True
            complete = False
            data = data_service.select_data(curr, False)
            if data:
                final_data = data
                length = len(str(curr))
                factor_string = data['factor_string'][:20]
                stats_data['stats_string'] = (f'To {length:03d} digits for '
                                              f'{seq}({factor_string})')
            else:
                final_data = prev_data
                stats_data['stats_string']= f'Missing {seq}:{index}'
        if done:
            if final_data:
                stats_data['base'] = final_data['base']
                stats_data['index'] = final_data['index']
                stats_data['num'] = final_data['num']
                stats_data['max_digits'] = max_digits
                stats_data['complete'] = complete
            else:
                # Missing data should never occur.
                stats_data['base'] = None
                stats_data['index'] = None
                stats_data['max_digits'] = max_digits
                stats_data['num'] = curr
                stats_data['complete'] = complete
        else:
            curr = next_value
            index += 1
            prev_data = data
    return stats_data

def _handle_data(seq:int, index:int, data:AlqData, values:dict(int,int),
                 stats_data:StatsData, prev_data:AlqData|None) -> AlqData | None:
    final_data = None
    next_value = data['aliquot_sum']
    if next_value in values:
        cycle = index - values[next_value] +1
        stats_data['stats_string'] = (f'Cycle ({cycle}) for {seq}:{index} to '
                                      f'{next_value}')
        final_data = data
    elif seq > data['base']:
        into_string = str(data['base']) + ':' + str(data['index'])
        num_string = str(data['num'])
        stats_data['stats_string'] = (f'Merge index {index:04d} for {seq} into '
                                      f'{into_string} at {num_string}')
        if prev_data:
            final_data = prev_data
        else:
            final_data = data
    elif next_value in (0, 1):
        stats_data['stats_string'] = 'To_1'
        final_data = data
    elif seq < data['base']:
        into_string = str(data['base']) + ':' + str(data['index'])
        num_string = str(data['num'])
        print(f'For {seq} incorrect merge index')
        stats_data['stats_string'] = (f'Incorrect merge index {index:04d} for '
                                      f'{seq} into {into_string} at {num_string}')
        if prev_data:
            final_data = prev_data
        else:
            final_data = data
    return final_data

if __name__ == "__main__":
    logging.basicConfig(filename='set_stats.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    parser.add_argument('-f', action='store_true', help='Force set stats on all enties')
    argv = parser.parse_args()

    pg = SQL()

    run_calc_stats(pg, argv.min, argv.max, argv.f)

    logger.info('finished')
