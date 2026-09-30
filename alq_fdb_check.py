#!/usr/bin/env python

""" If aliqueit was run, this program will update the factordb with new entries.

Only checks open series so merges get skipped. Use alq_compare_factordb for both merged and open.
Also works on a range by inputting a minimum and maximum.  If factordb status is not 'up_to_date'
it will use curl to check via last index or elf in the cmp_# directory. If the elf is longer it
uses the api to update each missing factor.

If any factors are added, the series is added to a queue to check again in 3 or more minutes.
"""

import argparse
import time
import logging

from sql import SQL
from aliquot_data import AliquotData
from aliquot_status import AliquotStatus
from aliquot_factordb import AliquotFactorDB
from aliquot_timed_queue import AliquotTimedQueue

logger = logging.getLogger(__name__)

def run_fdb_check(sql_connection: SQL, min_seq:int, max_seq:int, force:bool) -> None:
    """Run factordb check over a given range

    Args:
        sql_connection: postgres sql connection
        min_seq: minimum sequence for the range
        max_seq: maximum sequence for the range
        force: If True, all sequences are checked, otherwise we check based on the status.
    """

    logger.info('FDB check range %s to %s', min_seq, max_seq)

    local_data_service = AliquotData(sql_connection)
    status_service = AliquotStatus(sql_connection)
    factordb_service = AliquotFactorDB(sql_connection)
    #180 is a 3 minute wait before a sequence is tried again
    finish_update_queue = AliquotTimedQueue(180)

    data = local_data_service.get_incomplete()
    count = 0
    next_seq = None
    for pair in data:
        seq = pair[0]
        if seq < min_seq or seq > max_seq:
            continue
        count += 1
        if count % 1000 == 0:
            print(f'{count}:{seq}')
        proc_seq(seq, status_service, factordb_service, finish_update_queue, force)

    print('Final:')
    while not finish_update_queue.is_empty():
        while (next_seq := finish_update_queue.get_item()) is not None:
            if factordb_service.process_seq(next_seq, False):
                status_service.factordb_full_check(next_seq)
            else:
                finish_update_queue.add_item(next_seq)
        print('.',end='', flush=True)
        time.sleep(10)
    print('Complete')

def proc_seq(seq:int, status_service:AliquotStatus, factordb_service:AliquotFactorDB,
             finish_update_queue: AliquotTimedQueue, force:bool) -> None:
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
        if factordb_service.process_seq(next_seq, False, True):
            status_service.factordb_full_check(next_seq)
        else:
            finish_update_queue.add_item(next_seq)
    if force or not status_service.factordb_up_to_date(seq):
        if factordb_service.process_seq(seq, False):
            status_service.factordb_full_check(seq)
        else:
            finish_update_queue.add_item(seq)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_fdb_check.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    parser.add_argument('-f', action='store_true',
                        help='Ignores the fully checked status flag (slow)')
    argv = parser.parse_args()

    pg = SQL()

    run_fdb_check(pg, argv.min, argv.max, argv.f)

    logger.info('finished')
