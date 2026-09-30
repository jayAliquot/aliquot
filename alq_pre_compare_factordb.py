#!/usr/bin/env python

""" Assumes factordb has nothing and gives it first pass at factors.

Getting a sequence from the FactorDB for the first time usually results in a timeout.  This is
because it tries to generate the series to 50 digits.  The purpose of this pre-compare is to
place the series into the remote FactorDB before trying to get it the first time to reduce load
of new sequences.

This function changes the factordb status from 'unchecked' to 'fast_check' to keep from processing
the same sequence twice.  'fast_check' status therefore means this was run and FactorDB has the
factorization but the alqiuot sequence itself doesn't yet exist - this is created the first time
the series is queried.
"""

import argparse
import time
import sys
import logging
from pathlib import Path
from datetime import datetime
from sql import SQL
import aliquot_util
from aliquot_status import AliquotStatus
from aliquot_factordb import AliquotFactorDB

logger = logging.getLogger(__name__)

def run_pre_compare(sql_connection:SQL, min_seq:int, max_seq:int) -> None:
    """Send initial factorization data to remote FactorDB site

    Args:
        sql_connection: postgres sql connection.
        min_seq: Minimum sequence to run.
        max_seq: Maximum sequence to run.    
    """

    status_service = AliquotStatus(sql_connection)
    factordb_service = AliquotFactorDB(sql_connection)
    for seq in range(min_seq, max_seq+1):
        if seq % 10000 == 0:
            start = datetime.now()
            print(f'{seq} at {start}')
        status  = status_service.get_status(seq)
        if  status and status['factordb'] in ('NA', 'fast_check', 'needs_update',
                                              'up_to_date'):
            continue
        subd = seq // 1000000
        file_name = ''
        elf_name = f'elf_{subd}/alq_{seq}.elf'
        if Path(elf_name).is_file():
            file_name = elf_name
        else:
            elg_name = f'elg_{subd}/alq_{seq}.elg'
            if Path(elg_name).is_file():
                file_name = elg_name
        if file_name:
            with open(file_name, 'r', encoding='ascii') as elf_file:
                send_lines = elf_file.readlines()
                print(f'Elf/elg: {seq} ({len(send_lines)}):', end='', flush=True)
                count = 0
                start = time.time()
                fail_count = 0
                for line in send_lines:
                    count += 1
                    if count % 50 == 0:
                        print('.', end='', flush=True)
                    if send_line(line, factordb_service):
                        fail_count = 0
                    else:
                        time.sleep(600)
                        fail_count += 1
                        if fail_count >= 10:
                            print('Too many fails: exiting')
                            sys.exit(1)
                elapsed = time.time() - start
                avg = elapsed /count
                print(f'Average: {avg} Total: {elapsed}')
                status_service.factordb_fast_check(seq)

def send_line(line:str, factordb_service:AliquotFactorDB) -> bool:
    """Send a line to the remote site.
    
    Args:
        line: The line to parse.
    """

    if line[0] == 'T' or not aliquot_util.is_valid_elf_line(line):
        #Skip To <seq>:<index> line in elg
        return True
    data = aliquot_util.parse_elf_line(line)
    if not data:
        print(f'Error in parse_elf_line function with: {line}')
        return True
    number = data['num']
    length = len(str(number))
    if length < 19:
        return True
    factor_strings = data['factor_string'].split('*')
    factors = []
    for factor_string in factor_strings:
        if len(factor_string) >= 10:
            if '^' in factor_string:
                factors.append(factor_string.split('^')[0])
            else:
                factors.append(factor_string)
    if len(factors) == 0:
        return True
    chunk = {}
    chunk['number'] = number
    chunk['factors'] = factors
    if factordb_service.send_factor_line(chunk):
        return True
    return False

if __name__ == "__main__":
    logging.basicConfig(filename='alq_pre_compare_factordb.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    argv = parser.parse_args()

    pg = SQL()

    run_pre_compare(pg, argv.min, argv.max)

    logger.info('finished')
