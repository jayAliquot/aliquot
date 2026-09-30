#!/usr/bin/env python

""" Use the remote factordb to extend known series.

For each open series in the range, the program queries the remote site for the factorization of the
final unknown number.  If the factorization is known we continue to extend the series up to a limit.
If we hit that limit, the series is added to a script to get the rest of it all at once.

The limit is specified with the -n option or uses a default of 50.  The script has a 30 second
pause between series to lower the usage. Getting each factor take a bit less than a second so both
methods take similar time around 50.

The remote site factors some numbers automatically so sequences around 60 digits end up with a few
new terms each time.   For series that start below 10 million, the series is mostly extended
because a user runs factorization and so add either a few or a lot of new terms depending on the
size of the final numbers and their computing power.

The script is of the form ext_<start series im millions>_<time/date>.sh.  It is output when the
program ends and should be run when this program ends to pick up the longer additions.
"""

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TextIO
from contextlib import ExitStack

from sql import SQL
from aliquot_data import AliquotData
from aliquot_factordb import AliquotFactorDB
from aliquot_status import AliquotStatus
from aliquot_main import AliquotMain
from aliquot_elf import AliquotElf
from aliquot_verify import AliquotVerify

logger = logging.getLogger(__name__)

@dataclass
class ExtendContext:
    """Pass in data needed for extending series"""
    seq: int
    num: int
    get_file: TextIO
    limit: int
    unchanged_count: int
    stack: ExitStack
    get_file_name: str

@dataclass
class ServiceContext:
    """Services used for extending a series"""    
    data_service: AliquotData
    status_service: AliquotStatus
    factordb_service: AliquotFactorDB
    main_service: AliquotMain
    elf_service: AliquotElf
    verify_service: AliquotVerify

def run_extention(sql_connection:SQL, min_seq:int, max_seq:int, limit: int) -> None:
    """Extends series with information from the remote site

    sql_connection: postgres sql connection.
    min_seq: Minimum sequence to verify.
    max_seq: Maximum sequence to verify.
    limit: How many factors to add before adding to script.
    """

    logger.info('get extend range %s to %s', min_seq, max_seq)
    service_ctx = ServiceContext(AliquotData(sql_connection),
                                 AliquotStatus(sql_connection),
                                 AliquotFactorDB(sql_connection),
                                 AliquotMain(sql_connection),
                                 AliquotElf(sql_connection),
                                 AliquotVerify(sql_connection)
                                 )

    unchanged_count = 0
    time_string = datetime.now().strftime('%H%M_%m%d%Y')
    subd = min_seq // 1000000
    get_file_name = f'ext_{subd}M_{time_string}.sh'
    get_file = None
    with ExitStack() as stack:
        data = service_ctx.data_service.get_incomplete()
        for pair in data:
            seq = pair[0]
            num = pair[1]
            if seq < min_seq or seq > max_seq:
                continue
            ctx = ExtendContext(seq, num, get_file, limit, unchanged_count, stack, get_file_name)
            get_file = _extend(ctx, service_ctx)
            unchanged_count = ctx.unchanged_count
    if get_file is not None:
        print(f'File name is {get_file_name}')

def _extend(ctx:ExtendContext, service_ctx:ServiceContext) -> TextIO | None:
    """Extend an individual series
    
    Args:
        seq: The sequence to extend.
        num: The current open number we don't know the factors for.
        get_file: The script file to add to if we reach the limit.
        error_file: remote site has had issues with certain numbers.  If no factor
            information is returned we add the number to this file.
    """

    done = False
    count = 0
    factors_added = False
    curr = ctx.num
    while not done:
        factors = service_ctx.factordb_service.find_factors(curr, 0, ctx.seq, None)
        if not factors:
            done = True
            if ctx.unchanged_count % 1000 == 0:
                print(f'Unchanged {ctx.unchanged_count}: {ctx.seq}')
            ctx.unchanged_count += 1
            continue
        if count < ctx.limit:
            aliquot_sum = service_ctx.main_service.add_factors(ctx.seq, curr, factors)
            if aliquot_sum == 0:
                #merged
                done = True
                continue
            factors_added = True
            print(f'Adding to {ctx.seq}')
            if not aliquot_sum:
                print(f'Error with factors for {ctx.seq}')
                done = True
            count += 1
            curr = aliquot_sum
        else:
            done = True
            subd = ctx.seq // 1000000
            ext_name = f'elf_{subd}/alq_{ctx.seq}.ext'
            if ctx.get_file is None:
                # enter_context handles lack of 'with' here.
                # pylint: disable=consider-using-with
                ctx.get_file = ctx.stack.enter_context(open(ctx.get_file_name, 'w+',
                                                            encoding='ascii'))
            ctx.get_file.write(f'echo {ctx.seq}\n')
            ctx.get_file.write(f'curl --cookie "$FDB_COOKIE" -s -o {ext_name} '
                           f'"http://factordb.com/elf.php?seq={curr}&type=1"\n')
            ctx.get_file.write('sleep 30\n')
            ctx.get_file.write(f'wc {ext_name}\n')
            ctx.get_file.write(f'python3 alq_extend.py {ctx.seq} {ctx.seq}\n')
            ctx.get_file.write('sleep 5\n')
            ctx.get_file.flush()
            done=True
    if factors_added:
        service_ctx.elf_service.create_elf_file(ctx.seq)
        service_ctx.elf_service.factor_check(ctx.seq, curr)
        service_ctx.status_service.update_stats(ctx.seq, True)
        service_ctx.verify_service.verify(ctx.seq, None)
    return ctx.get_file

if __name__ == "__main__":
    logging.basicConfig(filename='alq_get_extend.log', level=logging.INFO)
    logger.info('Started')

    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min', type=int, help='Minimum value of the range')
    parser.add_argument('max', type=int, help='Maximum value of the range')
    parser.add_argument('-n', type=int, default=50, help='Max number of items to return')
    argv = parser.parse_args()

    pg = SQL()

    run_extention(pg, argv.min, argv.max, argv.n)

    logger.info('finished')
