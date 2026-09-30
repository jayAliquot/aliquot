#!/usr/bin/env python

""" Verification check to make sure sequences have no errors.

Local data in sync with the elf file, correctly handled merges, and general correctness of the
data are all checked for the sequence.

Since merges change existing data, these are the most likely to be incorrect.  Conflicts can also
occur with more than one program running at once. For example, extending sequences updates the elf
file at the end.

A verify status is kept that is unset if a sequence changes and then reset once verify indicates
the sequence is ok.  This can occasionally be wrong due to merging so a -f checks all sequences,
and -u checks all open sequences.  This is very slow to run for all sequences.

Once verify is run, fix files are generated for each million sequences to fix any issues.  For a
single run the fix files get the same time stamp.  alq_run_fix.sh can run all the fixes by copying
the time stamp  (e.g. ./alq_run_fix.sh 2338_07142026) as given in the file names.
"""

import sys
import logging
import argparse
from datetime import datetime
from typing import TypedDict, TextIO, Unpack

from sql import SQL
from aliquot_verify import AliquotVerify
from aliquot_status import AliquotStatus

logger = logging.getLogger(__name__)

class VerifyRangeOptions(TypedDict, total=False):
    """Handles kwargs type for very_range"""
    check_all: bool
    check_unbounded: bool
    fix_file: TextIO | None

def run_verification(sql_connection:SQL, min_seq:int, max_seq:int, check_all:bool=False,
                     check_unbounded:bool=False, check_only:bool=False) -> None:
    """Executes verification routing across sequenced intervals.

    The intervals are curently every million sequences grouped into a fix file.

    Args:
        sql_connection: postgres sql connection.
        min_seq: Minimum sequence to verify.
        max_seq: Maximum sequence to verify.
        check_all: Ignores verify status and checks all sequences.
        check_unbounded: Ignores verify status for open sequences.
        check_only: Don't create a fix file to fix the issue.
    """

    logger.info('Verify range %s to %s', min_seq, max_seq)

    if check_all:
        logger.info('Verify all sequences')
    elif check_unbounded:
        logger.info('Verify open sequences')
    if check_only:
        logger.info('Verify check only (no fix file)')

    status_service = AliquotStatus(sql_connection)
    verify_service = AliquotVerify(sql_connection)

    min_seq = max(min_seq, 1)
    now = datetime.now()
    time_string = now.strftime('%H%M_%m%d%Y')

    start = min_seq
    interval = 1000000
    subd = start // interval

    while start <= max_seq:
        fix_file_name = f'fix_{subd}M_{time_string}.sh'
        end = min(max_seq, (subd + 1) * interval - 1)

        if start == end and start != min_seq:
            break

        if not check_only:
            with open(fix_file_name, 'w+', encoding="ascii") as fix_file:
                _verify_range(start, end, status_service, verify_service,
                             check_all=check_all,check_unbounded=check_unbounded,
                             fix_file=fix_file)
                bytes_written = fix_file.tell()
                if bytes_written > 0:
                    print(f'File {fix_file_name} has changes to run.')
                else:
                    print(f'File {fix_file_name} had no changes.')
        else:
            _verify_range(start, end, status_service, verify_service,
                         check_all=check_all,check_unbounded=check_unbounded, fix_file=None)

        subd += 1
        start = subd * interval

def _verify_range(start: int,
                 end:int ,
                 status_service:AliquotStatus,
                 verify_service:AliquotVerify,
                 **kwargs:Unpack[VerifyRangeOptions]):
    """Verifies an individual range of sequences and handles internal logs/fixes.

    Args:
        start: The starting value for the range verified.
        end: The ending value for the range verified.
        status_service: Sets the status for a sequence
        verify_service: Handles the verification.
        kwargs: Optional argumens
            check_all=False: Check every sequence ignoring verify status
            check_unbounded=False: Check every open sequence ignoring verify status 
            fix_file=None: File is created with the changes to fix.
    """

    check_all = kwargs.get('check_all', False)
    check_unbounded = kwargs.get('check_unbounded', False)
    fix_file = kwargs.get('fix_file', None)
    for seq in range(start, end + 1):
        if seq % 100000 == 0:
            print('', file=sys.stderr)
            print(f'{seq}', end='', file=sys.stderr, flush=True)
        elif seq % 1000 == 0:
            print('.', end='', file=sys.stderr, flush=True)

        if not check_all:
            status_data = status_service.get_status(seq)
            if not status_data:
                print(f'Missing status for {seq}')
                if fix_file:
                    fix_file.write(f'python3 alq_init_status.py {seq} {seq}\n')
                    fix_file.flush()
            if status_data and status_data['verified']:
                if not status_data['open_ended'] or not check_unbounded:
                    continue

        verify_service.verify(seq, fix_file)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_verify.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    parser.add_argument('-f', action='store_true', help='Force verify on all entities')
    parser.add_argument('-u', action='store_true', help='verify all unbounded entries')
    parser.add_argument('-c', action='store_true', help='check only (no fix file)')
    argv = parser.parse_args()

    pg = SQL()

    run_verification(pg, argv.min, argv.max,argv.f, argv.u, argv.c)

    logger.info('finished')
