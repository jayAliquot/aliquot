#!/usr/bin/env python

""" Main creation of aliquot series using aliquot_sum and elf files.

This module can create the initial aliquot series up to 25 digits using aliquot_sum.py, get
data from the elf file to update the postgres database, and extend local data and elf files
from ext files downloaded from the remote site.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import TypedDict

from aliquot_types import ParseFileResult, AlqData
from aliquot_status import AliquotStatus
from aliquot_data import AliquotData
from aliquot_sum import AliquotSum
from aliquot_statistics import AliquotStatistics
from aliquot_elg import AliquotElg
from aliquot_elf import AliquotElf
from sql import SQL
import aliquot_util

logger = logging.getLogger(__name__)

class FactorResult(TypedDict):
    """Returned by compute_factors"""
    factor_string: str
    aliquot_sum: int

class AliquotMain:
    """Main aliquot local database creation"""
    def __init__(self, sql: SQL):
        """Initializes subclasses used.

        Args:
            sql: postgres sql connection.
        
        Attributes:
            aliquot_sum: Class to find initial sequences using python to 25 digits.
            aliquot_data: Class to get and set local db data.
            aliquot_status: Class that sets status information.
        """

        self.aliquot_sum = AliquotSum()
        self.aliquot_data = AliquotData(sql)
        self.status = AliquotStatus(sql)
        self.statistics = AliquotStatistics(sql)
        self.aliquot_elg = AliquotElg(sql)
        self.aliquot_elf = AliquotElf(sql)

    def calc_sequence(self, seq: int) -> None:
        """Sequence creation or expansion.

        If the elf/elg file exists, it is used to check the local data is up to date.
        If no data is found for the sequence, it is new so we create the series.  If the
        series reaches 25 digits it becomes an open sequence.
        If there is no elf and the sequence exists already, it is assumed it is
        created correctly so we simply return.


        Args:
            seq: The sequence to update/create.
        """

        if seq == 0:
            print('Zero sequence skipped')
            return
        subd = seq // aliquot_util.INTERVAL
        elf_name = f'elf_{subd}/alq_{seq}.elf'
        elg_name = f'elg_{subd}/alq_{seq}.elg'
        result = None
        if Path(elf_name).is_file():
            result = self.aliquot_elf.get_from_file(seq, elf_name)
        elif Path(elg_name).is_file():
            result = self.aliquot_elf.get_from_file(seq, elg_name)
        if result:
            self._handle_updates(seq, result)
        else:
            current = seq
            done = False
            index = 0
            status_data = self.status.get_status(seq)
            while not done:
                #If there is no elf file, the local database is checked.  If
                #the sequence is found we are done. Otherwise use aliquot_sum
                #to get to 25 digits.
                if self.aliquot_data.has_data(current, True):
                    if not status_data:
                        self.status.set_defaults(seq, True, 'NA')
                    done = True
                else:
                    seq_entry = self.aliquot_sum.calc_aliquot_sum(current)
                    seq_entry['index'] = index
                    seq_entry['base'] = seq
                    self.aliquot_data.insert_data(seq_entry)
                    if seq_entry['complete']:
                        current = seq_entry['aliquot_sum']
                        index += 1
                    else:
                        self.aliquot_elf.create_elf_file(seq)
                        self.status.set_defaults(seq, False, 'unchecked')
                        done = True


    def _handle_updates(self, seq: int, result: ParseFileResult) -> None:
        if result['elf_error']:
            print(f'Elf Error for {seq}')
            self.aliquot_elf.create_elf_file(seq)
        elif result['merge']:
            change_data = result['merge_info']
            for curr_seq in change_data['updates']:
                curr_seq = int(curr_seq)
                self.aliquot_elg.update_elf_elg_for_merge(curr_seq)
                self.status.update_localdb(curr_seq, True)
                print(f'Update for {curr_seq}')
            for curr_seq in change_data['verify']:
                print(f'Verify for {curr_seq}')
                curr_seq = int(curr_seq)
                self.statistics.fix_merge_if_needed(curr_seq)
                self.status.update_verify(curr_seq, False)
                print(f'Verify for {curr_seq}')
        else:
            if result['missing_open']:
                incomplete_data = {}
                incomplete_data['complete'] = False
                incomplete_data['base'] = seq
                incomplete_data['index'] = result['index']
                incomplete_data['num'] = result['final_num']
                self.aliquot_elf.add_incomplete(incomplete_data, result)
                self.aliquot_elf.create_elf_file(seq)
                self.aliquot_elf.factor_check(seq, result['final_num'])
                print(f'Missing open for {seq}')
            elif result['open']:
                self.aliquot_elf.factor_check(seq, result['final_num'])
                print(f'Open for {seq}')
            else:
                print(f'No Update for {seq}')

    def add_factors(self, seq: int, num: int, factors: list[tuple[int, int]]) -> int:
        """Called when we get full factorization from the factorDB.

        The factors come to us in yet another form to work with.  They also need to
        be complete, if not it is an error.

        The local database is updated with this information and the next value in the series
        returned.

        Args:
            seq: The sequence we are working with
            num: The number in the sequence.
            factors: A list of (prime, power) pairs.

        Return:
            The next number of the sequence if successful, otherwise zero.
        """

        factor_data = self._compute_from_factors(num, factors)
        if not factor_data:
            print(f'Add Factors for {seq} failed for {num}: {factors}')
            return None
        data: AlqData | None = self.aliquot_data.select_data(num, True)
        if not data:
            data: AlqData | None = self.aliquot_data.select_data(num, False)
        if not data:
            print(f'Add Factors for {seq} called on wrong number {num}')
            return None
        data['complete'] = True
        data['factor_string'] = factor_data['factor_string']
        data['aliquot_sum'] = factor_data['aliquot_sum']
        data['unfactor'] = 1
        result = self.aliquot_elf.update_single_local_data(data)
        if result['merge'] or result['elf_error']:
            self._handle_updates(seq, result)
        elif result['open']:
            # Don't call handle updates because it will recreate the elf every single time
            # The elf is called once by caller after finished.
            return data['aliquot_sum']
        return 0

    def _compute_from_factors(self, num: int, factors: list[tuple[int, int]]) -> FactorResult:
        """Using the factorDB factor information return the data based on the factors.

        Expects (prime, power) pairs in a list.  Returns None if the factors don't
        multiply to num.  The aliquot sum for the next value is calculated.

        Args:
            num: The number the factors belong to.
            factors: List of (prime, power) pairs.

        Return:
            dictionary with factor data and the aliquot sum.
        """

        check_num = 1
        aliquot_sum = 1
        factor_string = ''
        first = True
        for entry in factors:
            prime = int(entry[0])
            power = int(entry[1])
            check_num *= prime**power
            prime_string =  f'{prime}^{power}' if str(power) > '1' else f'{prime}'
            if first:
                factor_string = prime_string
                first = False
            else:
                factor_string += f'*{prime_string}'
            term = 1
            for curr in range(1, power+1):
                term += prime**curr
            aliquot_sum *= term
        aliquot_sum -= num
        if check_num != num:
            return None
        factor_data = {}
        factor_data['factor_string'] = factor_string
        factor_data['aliquot_sum'] = aliquot_sum
        return factor_data


    def extend_elf(self, seq):
        """Extend an elf file with factordb information.

        If the factordb has a bunch of new steps, we extend it by getting
        an extension rather than the whole sequence.  This works by asking
        the factordb for the sequence starting at the last number known locally.

        This code then has to take the number and factorizations to extend the
        series, changing to the correct index.

        The elf_file name with an ext extension must already exist as well as the elf
        file.  The download of the ext file is handled externally in a script.  The
        pre-extended elf sequence is saved as elf_name with extension bak

        Args:
            seq: The sequence to update.
        """

        subd = seq // aliquot_util.INTERVAL
        elf_name = f'elf_{subd}/alq_{seq}.elf'
        ext_name = f'elf_{subd}/alq_{seq}.ext'
        bak_name = f'elf_{subd}/alq_{seq}.bak'
        if Path(elf_name).is_file() and Path(ext_name).is_file():
            with open(ext_name, encoding="ascii") as ext_file:
                ext_lines = ext_file.readlines()
                if len(ext_lines) > 0:
                    if Path(bak_name).is_file():
                        os.remove(bak_name)
                    shutil.copy(elf_name, bak_name)
                    with open(bak_name, encoding="ascii") as bak_file:
                        elf_lines = bak_file.readlines()
                        if len(elf_lines) > 0:
                            elf_data = aliquot_util.parse_elf_line(elf_lines[-1])
                            num = elf_data['num']
                            if not elf_data:
                                print(f'For {seq}, unparsable elf file')
                                self.status.update_elf(seq, True)
                                return
                            ext_lines = self._find_ext_from(num, ext_lines)
                            if len(ext_lines) > 0:
                                try:
                                    with open(elf_name, 'w', encoding="ascii") as elf_file:
                                        index = 0
                                        for line in elf_lines[:-1]:
                                            elf_file.write(line)
                                            index += 1
                                        for new_line in ext_lines:
                                            parts = new_line.split('.')
                                            updated_line = f'{index} .{parts[1]}'
                                            index += 1
                                            elf_file.write(updated_line)
                                except OSError as e:
                                    shutil.copy(bak_name, elf_name)
                                    print(f'aborted update of {elf_name}, Error: {e}')
                                    return
                            else:
                                print(f'for {ext_name}: No extension found.')
                        else:
                            print(f'for sequence {seq} the elf file is empty.')
                            os.remove(ext_name)
                            self.status.update_elf(seq, True)
                            self.status.update_extend(seq, False)
                            return
                else:
                    print(f'for sequence {seq} the ext file is empty.')
                    os.remove(ext_name)
                    self.status.update_extend(seq, False)
                    return
            result = self.aliquot_elf.get_from_file(seq, elf_name, update_factordb = False)
            self._handle_updates(seq, result)
            os.remove(ext_name)
            self.status.update_stats(seq, True)
            self.status.update_extend(seq, False)

    def _find_ext_from(self, num, ext_lines):
        """Find ext line for num.

        Args:
            num: The open number from the elf file.
            ext_lines: lines that can extend the elf file.
        Returns:
            lines including num and all lines after.
        """

        found = False
        new_ext_lines = []
        for ext_line in ext_lines:
            ext_data =  aliquot_util.parse_elf_line(ext_line)
            if ext_data and num == ext_data['num']:
                found = True
            #The matching line and ones after will have found of true.
            if found:
                new_ext_lines.append(ext_line)
        return new_ext_lines
