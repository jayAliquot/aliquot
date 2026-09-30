#!/usr/bin/env python

""" Compares local db to FactorDB and makes a list of elg and elf entries that need updating.

    For a number that:
    1) Is within the interval between the minimum and maximum value
    2) Has either an elg file or an elf file.
    3) FactorDB status indicates the number is not up to date already.

    then the local aliquot series and factordb series are compared.  This is done by checking the
    existing using curl to
    set the file in the cmp_# directory to the current FactorDB series.  If this is equal to or
    longer than the elf or elg file, then FactorDB is up to date.  
    If FactorDB is out of date then the number is added to: 'missing_<elg|elf>_<data>.txt'.

    For arguments, including '--no-get' will not reget the cmp file if it already exists. This is
    faster but less accurate.
    Including '-f' will ignore the fully FactorDB status flag and should only be used if there is
    a reason to suspect the status flag for a number is not accurate.
"""

import argparse
import time
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import TextIO

from sql import SQL
from aliquot_status import AliquotStatus
from aliquot_factordb import AliquotFactorDB
import aliquot_util

logger = logging.getLogger(__name__)

@dataclass
class CompareContext:
    """Pass in data needed for comparing series to remote factordb"""
    seq: int
    compare_lines: int
    list_file: TextIO
    status_service: AliquotStatus
    factordb_service: AliquotFactorDB
    get_remote: bool

def run_compare(sql_connection:SQL, min_seq:int, max_seq:int, get_remote:bool, force:bool) -> None:
    """Compare current elf file to downloaded file from remote site.

    cmp_# stores elf files from remote and last index html as well.
    compare normally does not get a new compare file, but can with the --get flag.

    Args:
        sql_connection: postgres sql connection
        min_seq: The minimum sequence to compare.
        max_seq: The mximimum sequence to compare.
        get_remote: Get new download before compare.
        force: If false we do not test those whose fdb_status is 'up_to_date'.
    """
    status_service = AliquotStatus(sql_connection)
    factordb_service = AliquotFactorDB(sql_connection)
    time_string = datetime.now().strftime('%H%M_%m%d%Y')
    elg_file_name = f'missing_elg_{time_string}.txt'
    elf_file_name = f'missing_elf_{time_string}.txt'
    with open(elf_file_name, 'w+', encoding='ascii') as elf_file:
        with open(elg_file_name, 'w+', encoding='ascii') as elg_file:
            checked = 0
            for seq in range(min_seq, max_seq+1):
                subd = seq // 1000000
                elf_name = f'elf_{subd}/alq_{seq}.elf'
                elg_name = f'elg_{subd}/alq_{seq}.elg'
                do_compare = False
                is_elg = False
                if seq % 10000 == 0 and seq != min_seq:
                    print(f'{seq}:{checked}')
                if force or not status_service.factordb_up_to_date(seq):
                    compare_lines = 0
                    if Path(elf_name).is_file():
                        compare_lines = aliquot_util.get_line_count(elf_name)
                        do_compare = True
                    elif Path(elg_name).is_file():
                        # Skip 'To blah' line so minus 1
                        compare_lines = aliquot_util.get_line_count(elg_name) - 1
                        is_elg = True
                        do_compare = True
                    if do_compare:
                        checked += 1
                        print(f'Compare: {time.ctime()}, {seq}, count: {checked}')
                        list_file = elg_file if is_elg else elf_file
                        ctx = CompareContext(seq, compare_lines, list_file, status_service,
                                             factordb_service, get_remote)
                        process_seq(ctx)
    print(f'File names are {elf_file_name} and {elg_file_name}')

def process_seq(ctx:CompareContext) -> None:
    """Compare a single sequence to remote to determine the need to update.

    Args:
        ctx: Context for processing the sequence.
    """

    seq = ctx.seq
    cmp_lines = ctx.factordb_service.find_existing_cmp_file_lines(seq)
    if cmp_lines and cmp_lines >= ctx.compare_lines:
        print(f'already up to date for {seq}')
        ctx.status_service.factordb_full_check(seq)
        return
    last_index = ctx.factordb_service.find_last_index(seq, ctx.compare_lines, ctx.get_remote)
    if last_index and last_index + 1 >= ctx.compare_lines:
        ctx.status_service.factordb_full_check(seq)
        print(f'up to date by last index for {seq}')
        return
    if ctx.get_remote:
        cmp_lines = ctx.factordb_service.find_cmp_file_lines_get(seq)
        if cmp_lines and cmp_lines >= ctx.compare_lines:
            print(f'up to date after get for {seq}')
            ctx.status_service.factordb_full_check(seq)
            return

    ctx.list_file.write(f'{seq}\n')
    ctx.list_file.flush()
    print(f'Adding {seq}')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_compare_factordb.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    parser.add_argument('--get', action='store_true',
                        help='Will fetch the cmp file even if it already exists(slower)')
    parser.add_argument('-f', action='store_true',
                        help='Ignores the fully checked status flag (slow)')
    argv = parser.parse_args()

    pg = SQL()

    run_compare(pg, argv.min, argv.max, argv.get, argv.f)

    logger.info('finished')
