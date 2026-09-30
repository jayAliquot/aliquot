#!/usr/bin/env python

""" Outputs statistics from localdb for incomplete sequences for a given range.

    This returns results quickly.
"""

import argparse
import logging
from sql import SQL
from aliquot_data import AliquotData
import aliquot_util

logger = logging.getLogger(__name__)

def sort_seq(e):
    return int(e['sequence'])

def sort_to(e):
    return int(e['digits'])

def sort_driver(e):
    return e['driver']

def output_db_status(sql):
    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    argv = parser.parse_args()
    max_seq = argv.max
    min_seq = argv.min
    spec = ''
    interval = 1000000
    if min_seq == 0:
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
        spec = f'{min_spec}-{max_spec}'
    aliquot_data = AliquotData(sql)
    data = aliquot_data.get_incomplete()
    sequences = []
    for pair in data:
        seq = pair[0]
        if seq < min_seq or seq > max_seq:
            continue
        num = pair[1]
        sequence = {}
        sequence['sequence'] = seq
        sequence['digits'] = len(str(num))
        driver_data = aliquot_util.calc_driver(num, True)
        sequence['driver'] = driver_data['driver_string']
        sequences.append(sequence)
    unbounded_file_name = f'unbounded{spec}.txt'
    with open(unbounded_file_name, 'w+', encoding='ascii') as unbounded_file:
        sequences.sort(key=sort_seq)
        for sequence in sequences:
            seq = sequence['sequence']
            digits = sequence['digits']
            driver = sequence['driver']
            outstring = f'Sequence {seq} to {digits} digits with driver {driver}.\n'
            unbounded_file.write(outstring)
    to_file_name = f'unbounded_to{spec}.txt'
    with open(to_file_name, 'w+', encoding='ascii') as to_file:
        sequences.sort(key=sort_to)
        for sequence in sequences:
            seq = sequence['sequence']
            digits = sequence['digits']
            driver = sequence['driver']
            outstring = f'To {digits} digits for sequence {seq} with driver {driver}.\n'
            to_file.write(outstring)

    driver_file_name = f'unbounded_driver{spec}.txt'
    with open(driver_file_name, 'w+', encoding='ascii') as driver_file:
        sequences.sort(key=sort_driver)
        for sequence in sequences:
            seq = sequence['sequence']
            digits = sequence['digits']
            driver = sequence['driver']
            outstring = f'Driver {driver} for sequence {seq} to {digits} digits.\n'
            driver_file.write(outstring)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_unbounded.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    output_db_status(pg)
    logger.info('finished')
