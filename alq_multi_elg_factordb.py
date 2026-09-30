#!/usr/bin/env python

"""Updates remote factordb for merging (elg) aliquot series.

Only needs to handle update to the point of the merge.
It also assumes we created a file with a list of series potentially needing merging
using alq_compare_factordb.py.
"""

import argparse
import time
import logging
from pathlib import Path

from sql import SQL
from aliquot_factordb import AliquotFactorDB
from aliquot_status import AliquotStatus
from aliquot_timed_queue import AliquotTimedQueue

logger = logging.getLogger(__name__)

def run_elg_update(sql_connection:SQL, elg_file_name:str):
    """Updates remote factorDB site for elg files from a list

    Args:
        sql_connection: postgres sql connection
        file_name: Name of a file with a list of elg sequences needing update.
    """

    status_service = AliquotStatus(sql_connection)
    factordb_service = AliquotFactorDB(sql_connection)
    #180 is a 3 minute wait before a sequence is tried again
    finish_update_queue = AliquotTimedQueue(180)

    elg_list = []
    if Path(elg_file_name).is_file():
        elg_list = _get_elg_list(elg_file_name)
    else:
        print(f'File {elg_file_name} not found')
        return
    count = 0
    next_seq = None
    for seq in elg_list:
        count += 1
        if count % 1000 == 0:
            print(f'{count}:{seq}')
        proc_seq(seq, status_service, factordb_service, finish_update_queue)
    print('Final:')
    while not finish_update_queue.is_empty():
        while (next_seq := finish_update_queue.get_item()) is not None:
            if factordb_service.process_seq(next_seq, True):
                status_service.factordb_full_check(next_seq)
            else:
                finish_update_queue.add_item(next_seq)
        print('.',end='', flush=True)
        time.sleep(10)
    print('Complete')

def _get_elg_list(file_name:str) -> list[int]:
    """Get entries in elg list created by alq_compare_factordb.py.

    Args:
        file_name: File name with missing elg aliquot series listed.

    Returns:
        List of elg
    """

    elg_list = []
    with open(file_name, 'r', encoding='ascii') as file:
        for line in file:
            trim = line.strip()
            if trim.isdigit():
                elg_list.append(int(trim))
            else:
                print(f'Input: {line} is not a positive integer.')
    return elg_list


def proc_seq(seq:int, status_service:AliquotStatus, factordb_service:AliquotFactorDB,
             finish_update_queue: AliquotTimedQueue) -> None:
    """Process the next sequence.
    
    Also checks for sequences previously processed for which 3 minutes have passed.
    
    Args:
        seq: The sequence to process
        status_service: Set the status to 'up_to_date'
        factordb_service: Makes calls to remote site.
        finish_update_queue: Used to check again 3 or more minutes later if processed.
        force: If True, all sequences are checked, otherwise only those not 'up_to_date'.
    """

    while (next_seq := finish_update_queue.get_item()) is not None:
        if factordb_service.process_seq(next_seq, True, True):
            status_service.factordb_full_check(next_seq)
        else:
            finish_update_queue.add_item(next_seq)
    if factordb_service.process_seq(seq, True):
        status_service.factordb_full_check(seq)
    else:
        finish_update_queue.add_item(seq)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_multi_elg_factordb.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('file_name', help='File name with elg listed one per line')
    argv = parser.parse_args()

    pg = SQL()

    run_elg_update(pg, argv.file_name)

    logger.info('finished')
