#!/usr/bin/env python

""" Output is a sript to increase series to min_digits digits.

Finds series with less than min_digits+1 digits or having the downdriver and less than 
min_downdriver digits.  The script will then run aliqueit and main.py to update the local data. 
 The factordb is a separate step handled by alq_fdb_check.py.

The 'main' is for 60 digits with other alq_to<num>.py for other values.
"""

import argparse
import sys
from datetime import datetime
import logging
from pathlib import Path

from sql import SQL
from aliquot_data import AliquotData

logger = logging.getLogger(__name__)

class AliqueitScript:
    """Generate script to extend sequences"""
    def __init__(self, sql_connection, wdir:str, min_digits:int, min_downdriver:int) -> None:
        self.aliquot_data = AliquotData(sql_connection)
        self.working_dir = wdir
        self.min_digits = min_digits
        self.min_downdriver = min_downdriver
        #rfactor is used by aliqueit to allow down driver sequences more digits.
        self.rfactor = min_downdriver - min_digits
        #cofactor allows aliqueit to factor the easy stuff without stopping.
        self.do_all = False
        self.debug_merge = False

    def output_db_status(self):
        """Generate script to get series to min_digits digits"""

        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('min', type=int, help='Minimum value of the range')
        parser.add_argument('max', type=int, help='Maximum value of the range')
        parser.add_argument('-a', action='store_true', help='All including adding to factordb')
        parser.add_argument('-d', action='store_true', help='Allows debugging of merges')
        argv = parser.parse_args()
        max_seq = argv.max
        min_seq = argv.min
        self.do_all = argv.a
        self.debug_merge = argv.d
        now = datetime.now()
        time_string=now.strftime('%H%M_%m%d%Y')
        alq_file_name = f'to_{self.min_digits}_{time_string}.sh'
        with open(alq_file_name, 'w+', encoding='ascii') as alq_file:
            data = self.aliquot_data.get_incomplete()
            count = 0
            alq_file.write(f'cd {self.working_dir}\n')
            alq_file.write('rm *.log\n')
            alq_file.write('cd ..\n')
            for pair in data:
                seq = pair[0]
                num = pair[1]
                if seq < min_seq or seq > max_seq:
                    continue
                digits = len(str(num))
                is_downdriver = (num % 2 == 0) and (num % 3 != 0) and (num % 4 != 0)
                if  digits <= self.min_digits or (digits <= self.min_downdriver and is_downdriver):
                    num_data = self.aliquot_data.select_data(num, False)
                    if not num_data:
                        print(f'For {seq}, Missing data entry.')
                        continue
                    self.add_seq(seq, alq_file)
                    if count % 1000 == 0:
                        print(f'{count}: {seq}', file=sys.stderr)
                    count += 1
                    if count > 50000:
                        break
        print(f'File name is {alq_file_name}; Count is {count} ')
        if self.debug_merge:
            print('Warning: the main.py is not run so this has to be done later')

    def add_seq(self, seq, alq_file):
        """Out to the script for a single sequence"""
        alq_file.write(f'echo {seq}\n')
        subd = seq // 1000000
        elf_name = f'elf_{subd}/alq_{seq}.elf'
        if Path(elf_name).is_file():
            alq_file.write(f'cp {elf_name} {self.working_dir} \n')
            alq_file.write(f'cd {self.working_dir}\n')
        else:
            alq_file.write(f'cd {self.working_dir}\n')
            alq_file.write(f'touch alq_{seq}.elf\n')
        cofactor = self.min_digits - 10
        if self.min_digits < 90:
            alq_file.write(f'./aliqueit -d {self.min_digits + 1} -c {cofactor} -b -r '
                           f'{self.rfactor} {seq} > /dev/null\n')
        else:
            alq_file.write(f'./aliqueit -d {self.min_digits + 1} -c {cofactor} -b -r '
                           f'{self.rfactor} {seq}\n')
        alq_file.write('cd ..\n')
        alq_file.write(f'mv {self.working_dir}/alq_{seq}.elf {elf_name} \n')
        if self.debug_merge:
            alq_file.write(f'tail -n 2 {elf_name}\n')
        else:
            alq_file.write(f'python3 main.py {seq} {seq}\n')
            # The following can take 3+ minutes each so call only if -a flag was used.
            if self.do_all:
                alq_file.write(f'python3 alq_verify.py {seq} {seq}\n')
                alq_file.write(f'python3 alq_update_factordb.py {seq} {seq}\n')
                alq_file.write(f'python3 alq_elg.py {seq} {seq}\n')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_to60.log', level=logging.INFO)
    logger.info('Started')

    pg = SQL()

    aliqueit_script = AliqueitScript(pg, 'alq60', 60, 70)
    aliqueit_script.output_db_status()

    logger.info('finished')
