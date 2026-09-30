#!/usr/bin/env python

"""Verification of data for the elf/elg data and local data.

Checks aliquot series and writes functions to run to fix the issues if a 'fix_file' is given
"""

import sys
import os
import re
import logging
from pathlib import Path
from typing import TextIO
from dataclasses import dataclass

from aliquot_types import AlqData
from aliquot_data import AliquotData
from aliquot_status import AliquotStatus
from aliquot_statistics import AliquotStatistics
import aliquot_util

logger = logging.getLogger(__name__)

# Disabling so we can keep a single context
# pylint: disable=too-many-instance-attributes
@dataclass
class VerifyContext:
    """Pass in data needed for verifying the data"""
    seq: int
    index: int
    line: str
    data: AlqData
    prev_data: AlqData
    is_elg: bool
    fix_file: TextIO
    value: dict[str, bool]

class AliquotVerify:
    """Verification of sequences."""

    def __init__(self, sql):
        """Initializes subclasses used.

        Args:
            sql: postgres sql connection.
        
        Attributes:
            aliquot_data: Class to get and set local db data.
            aliquot_status: Class that sets status information.
            aliquot_statistics: Class that figures out run statistics.
        """

        self.aliquot_data = AliquotData(sql)
        self.status = AliquotStatus(sql)
        self.statistics = AliquotStatistics(sql)

    def verify(self, seq, fix_file):
        """Verify whether a sequence is correct.

        Due to a sequence merge affecting other sequences, any imperfection in the
        merge code can cause an issue.  Additionally, the elf file and local database
        can be out of sync, especially if aliqueit has extended the elf series but
        main.py was not run.

        This function looks for these errors and others.  If an issue is found, commands
        are added to the fix_file to attempt to fix the issue.  This works for most
        problems, but verify should be run after to check it.

        As a last resort, extending the series from the factordb and/or running aliqueit and
        then running main.py to update the localdb from the elf has been successful.  Running
        aliqueit also can be used to make sure the elf file is a valid one.

        One thing not check for is whether the numbers in the factor string are prime. Both
        aliqueit and the factordb take care of this for us.

        Args:
            seq: The sequence to check.
            fix_file: A (bash) script that is created to fix any issues found.  A description
            of the issue also goes to stdout.  It is optional in which case just the stdout
            error is written.
        """

        if seq == 0:
            return
        subd = seq // aliquot_util.INTERVAL
        elf_name = f'elf_{subd}/alq_{seq}.elf'
        elg_name = f'elg_{subd}/alq_{seq}.elg'
        if Path(elg_name).is_file():
            self.check_status(seq, False, 'unchecked')
            if Path(elf_name).is_file():
                print(f'Both {elg_name} and {elf_name} exist.', file=sys.stderr)
                self.check_verify_status(seq)
                if fix_file:
                    fix_file.write(f'python3 alq_elg.py {seq} {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                    fix_file.flush()
                self.status.update_elg(seq, True)
                os.remove(elg_name)
                return
            self._check_fdb(seq, fix_file, True)
            self.verify_file(seq, fix_file, elg_name, True)
        elif Path(elf_name).is_file():
            self.check_status(seq, True, 'unchecked')
            self._check_fdb(seq, fix_file, True)
            self.verify_file(seq, fix_file, elf_name, False)
        else:
            self.check_status(seq, False, 'NA')
            self._check_fdb(seq, fix_file, False)
            self.verify_db(seq, fix_file)

    def check_status(self, seq, complete, factordb_checked):
        """Check status exists and set to default if not"""

        status_data = self.status.get_status(seq)
        if not status_data:
            self.status.set_defaults(seq, complete, factordb_checked)

    def _check_fdb(self, seq, fix_file, has_file):
        """Helper functio to check fdb status.

        fdb status should be NA if there is no elf or elg file and
        not NA if the file exists.

        Args:
            seq: sequence being checked.
            fix_file: If it exists, information to fix the issue will be output to it.
            has_file: True if elg or elf exists.
        """

        status_data = self.status.get_status(seq)
        if has_file:
            if status_data['factordb'] == 'NA':
                print(f'Status should not be NA for {seq}')
                self.check_verify_status(seq)
                if fix_file:
                    fix_file.write(f'python3 alq_adjust_fdb_status.py {seq} {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
        else:
            if status_data['factordb'] != 'NA':
                print(f'Status should be NA for {seq}')
                self.check_verify_status(seq)
                if fix_file:
                    fix_file.write(f'python3 alq_adjust_fdb_status.py {seq} {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')

    def verify_file(self, seq, fix_file, file_name, is_elg):
        """Verification for a series that has an elg or elf.

        Elg and elf files line types are similar other than the final line.
        This function verifies the file and makes sure the localdb agrees
        with it.

        Arg:
            seq: The sequence being verified.
            fix_file: If it exists, a shell script to fix the error is written to it.
            file_name: The elf or elg file name.
            is_elg: If true the file is an elg file, otherwise and elf file.
        """

        value = {}
        with open(file_name, encoding="ascii") as file:
            lines = file.readlines()
            lines_length = len(lines)
            if lines_length == 0:
                print(f'Empty file {file_name}.', file=sys.stderr)
                self.check_verify_status(seq)
                self.status.update_elf(seq, True)
                if fix_file:
                    self._retrieve_elf(seq, fix_file, is_elg)
                return
            curr = seq
            prev_data = {}
            for index, line in enumerate(lines):
                data = self.aliquot_data.select_data(curr, True)
                if not data:
                    data = self.aliquot_data.select_data(curr, False)
                else:
                    temp = self.aliquot_data.select_data(curr, False)
                    if temp:
                        print('Found both complete and incomplete. Fixing...', file=sys.stderr)
                        self.aliquot_data.clean_incomplete()
                if not data:
                    print(f'missing data for {seq}: {index}', file=sys.stderr)
                    self.check_verify_status(seq)
                    self.status.update_localdb(seq, True)
                    if fix_file:
                        self._retrieve_elf(seq, fix_file, is_elg)
                    return
                if curr in value:
                    #loop found
                    if not is_elg or index != lines_length - 1:
                        self._elg_update_needed(seq, index, fix_file)
                        return
                value[curr] = True
                ctx = VerifyContext(seq=seq,
                                    index=index,
                                    line=line,
                                    data=data,
                                    is_elg = is_elg,
                                    prev_data=prev_data,
                                    fix_file=fix_file,
                                    value=value
                )
                has_error = False
                if index == lines_length - 1:
                    if not self._verify_final_line(ctx):
                        has_error = True
                    if is_elg:
                        # We are done
                        return
                base = data['base']
                if base != seq:
                    self._elg_update_needed(seq, index, fix_file)
                    has_error = True
                if not has_error and not self._verify_line_data(ctx):
                    has_error = True
                if has_error:
                    return
                curr = data['aliquot_sum']
                prev_data = data
        self.status.update_verify(seq, True)

    def _verify_final_line(self, ctx:VerifyContext) -> bool:
        is_elg = ctx.is_elg
        if is_elg:
            return self._handle_to_line(ctx)
        seq = ctx.seq
        index = ctx.index
        data = ctx.data
        fix_file = ctx.fix_file
        value = ctx.value
        if data['complete'] is True:
            if data['aliquot_sum'] in value:
                print(f'Cycle detected for elf {seq}')
                if fix_file:
                    fix_file.write(f'python3 alq_elg.py {seq} {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                    fix_file.flush()
                self.status.update_elg(seq, True)
                return False
            print(f'elf missing incomplete entry {seq}:{index}', file=sys.stderr)
            self.check_verify_status(seq)
            if fix_file:
                subd = seq // aliquot_util.INTERVAL
                merge_name = f'elf_{subd}/merge/alq_{seq}.merge'
                elf_name =  f'elf_{subd}/alq_{seq}.elf'
                if Path(merge_name).is_file():
                    fix_file.write(f'echo {seq}\n')
                    fix_file.write(f'cp {merge_name} {elf_name}\n')
                    fix_file.write(f'python3 alq_elg.py {seq} {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                else:
                    fix_file.write(f'echo {seq}\n')
                    fix_file.write(f'python3 alq_create_elf.py {seq}\n')
                    fix_file.write(f'python3 main.py {seq} {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                    fix_file.flush()
            self.status.update_factor(seq, True)
            return False
        return True

    def _handle_to_line(self, ctx:VerifyContext) -> bool:
        seq = ctx.seq
        index = ctx.index
        line = ctx.line
        data = ctx.data
        prev_data = ctx.prev_data
        fix_file = ctx.fix_file
        base = data['base']
        if base <= seq:
            base_index = data['index']
            to_line = f'To {base}:{base_index}\n'
            if to_line != line:
                print(f'elg update needed {seq}:{index}', file=sys.stderr)
                self.check_verify_status(seq)
                if fix_file:
                    fix_file.write(f'python3 alq_elg.py {seq} {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                    fix_file.flush()
                self.status.update_elg(seq, True)
                return False
            if not self._verify_merge_data(seq, base, base_index, prev_data, fix_file):
                return False
        else:
            print(f'For {seq}, bad elg file or incomplete data.')
            self.check_verify_status(seq)
            if fix_file:
                self._retrieve_elf(seq, fix_file, True)
            return False
        return True

    def _verify_merge_data(self, seq, base, base_index, prev_data, fix_file):
        merge_data = self.statistics.get_merge(seq)
        if 'index' in prev_data:
            err = (not merge_data or
                   merge_data['merge_from_sequence'] != seq or
                   merge_data['merge_from_index'] != prev_data['index'] or
                   merge_data['merge_to_sequence'] != base or
                   merge_data['merge_to_index'] != base_index or
                   merge_data['num_before_merge'] != prev_data['num'] or
                   merge_data['num_after_merge'] != prev_data['aliquot_sum'])
            if err:
                print(f'Elg: Issue with merge_data for {seq}')
                self.check_verify_status(seq)
                if fix_file:
                    fix_file.write(f'python3 alq_find_merges.py {seq} {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                    fix_file.flush()
                self.status.update_verify(seq, False)
                return False
        else:
            if merge_data:
                print(f'merge_data for {seq} is not needed')
                self.check_verify_status(seq)
                if fix_file:
                    fix_file.write(f'python3 alq_find_merges.py --clean {seq} {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                    fix_file.flush()
                    self.status.update_verify(seq, False)
                return False
        return True

    def _verify_line_data(self, ctx):
        seq = ctx.seq
        index = ctx.index
        line = ctx.line
        data = ctx.data
        is_elg = ctx.is_elg
        fix_file = ctx.fix_file
        line_data = aliquot_util.parse_elf_line(line.strip())
        if not line_data:
            print(f'missing line_data for {seq}:{index}', file=sys.stderr)
            self.status.update_elf(seq, True)
            self.check_verify_status(seq)
            if fix_file:
                self._retrieve_elf(seq, fix_file, is_elg)
            return False
        if line_data['complete'] and not data['complete']:
            print(f'db data needs updating from elf for {seq}', file=sys.stderr)
            self.check_verify_status(seq)
            subd = seq // aliquot_util.INTERVAL
            old_name = f'elf_{subd}/alq_{seq}.old'
            self.status.update_localdb(seq, True)
            if Path(old_name).is_file():
                if fix_file:
                    fix_file.write(f'python3 alq_update.py {seq} {seq}\n')
                    fix_file.write(f'python3 alq_elg.py {seq} {seq}\n')
            else:
                if fix_file:
                    fix_file.write(f'python3 main.py {seq} {seq}\n')
                    fix_file.write(f'python3 alq_elg.py {seq} {seq}\n')
            if fix_file:
                fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                fix_file.flush()
            return False
        if data['complete'] != line_data['complete']:
            self._handle_complete_mismatch(seq, index, data, fix_file, is_elg)
            return False
        if not line_data['complete'] and not data['complete']:
            factors = aliquot_util.compute_factors(data['num'])
            if not self._verify_factor_check(ctx, factors, line_data):
                return False
        if not self.verify_data(data['num'], index, data, line_data):
            print(f'verify failed for {seq}:{index}', file=sys.stderr)
            self.check_verify_status(seq)
            self.status.update_elf(seq, True)
            if fix_file:
                fix_file.write(f'python3 alq_create_elf.py {seq}\n')
                fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                fix_file.flush()
            return False
        return True

    def _verify_factor_check(self, ctx, factors, line_data):
        seq = ctx.seq
        index = ctx.index
        data = ctx.data
        fix_file = ctx.fix_file
        ld = aliquot_util.find_divisor_from_str(line_data['factor_string'])
        dd = aliquot_util.find_divisor_from_str(data['factor_string'])
        sd = aliquot_util.find_divisor(factors['factors'])
        if ld != dd or dd % sd != 0:
            print(f'divisor mismatch for elf for {seq}:{index} - {ld} vs {dd} '
                  f'vs {sd}', file=sys.stderr)
            self.check_verify_status(seq)
            self.status.update_factor(seq, True)
            if fix_file:
                fix_file.write(f'python3 alq_factor_check.py {seq} {seq}\n')
                fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                fix_file.flush()
            return False
        return True

    def _handle_complete_mismatch(self, seq, index, data, fix_file, is_elg):
        if data['complete']:
            print(f'Elf is incomplete at {seq}:{index}', file=sys.stderr)
            self.check_verify_status(seq)
            self.status.update_elf(seq, True)
            if fix_file:
                self._retrieve_elf(seq, fix_file, is_elg)
        else:
            #Elf file needs processing
            print(f'elf processing needed {seq}:{index}', file=sys.stderr)
            self.check_verify_status(seq)
            self.status.update_localdb(seq, True)
            if fix_file:
                fix_file.write(f'python3 main.py {seq} {seq}\n')
                fix_file.write(f'python3 alq_elg.py {seq} {seq}\n')
                fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                fix_file.flush()

    def _elg_update_needed(self, seq, index, fix_file):
        print(f'elg update needed {seq}:{index}', file=sys.stderr)
        self.check_verify_status(seq)
        if fix_file:
            fix_file.write(f'python3 alq_elg.py {seq} {seq}\n')
            fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
            fix_file.flush()
        self.status.update_elg(seq, True)

    def verify_db(self, seq, fix_file):
        """Verify a sequence that is in the localdb.

        There is no elf or elg file to compare so the local
        data is check for self consistency.

        Args:
            seq: The sequence to check.
            fix_file: If it exists, a shell script to fix the error is written to it.
        """

        curr = seq
        index = 0
        done = False
        prev_data = {}
        while not done:
            data = self.aliquot_data.select_data(curr, True)
            if not data:
                data = self.aliquot_data.select_data(curr, False)
            else:
                temp = self.aliquot_data.select_data(curr, False)
                if temp:
                    print('Found both complete and incomplete. Fixing...', file=sys.stderr)
                    self.aliquot_data.clean_incomplete()
            if not data:
                print(f'missing data for {seq}:{index}', file=sys.stderr)
                self.check_verify_status(seq)
                self.status.update_elf(seq, True)
                if fix_file:
                    fix_file.write(f'python3 alq_create_elf.py {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                    fix_file.flush()
                return
            if data['base'] < seq or (data['base'] == seq and data['index'] < index):
                if not self._verify_merge_data(seq, data['base'], data['index'],
                                               prev_data, fix_file):
                    return
                break
            if not self.verify_data(curr, index, data, None):
                print(f'verify failed for {seq}:{index}', file=sys.stderr)
                self.check_verify_status(seq)
                if fix_file:
                    fix_file.write(f'python3 alq_create_elf.py {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                    fix_file.flush()
                self.status.update_elf(seq, True)
                return
            if not data['complete']:
                print(f'data is incomplete at {seq}:{index}', file=sys.stderr)
                self.check_verify_status(seq)
                if fix_file:
                    fix_file.write(f'python3 alq_create_elf.py {seq}\n')
                    fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
                    fix_file.flush()
                self.status.update_elf(seq, True)
                return
            curr = data['aliquot_sum']
            prev_data = data
            if curr <= 1:
                done = True
            index += 1
        self.status.update_verify(seq, True)

    def verify_data(self, num, index, data, line_data):
        """Verify a single line of data along with line data.

        Args:
            num: The expected number from the previous value.
            index: The current index
            data: Data from the localdb.
            line_data: Data from an elf or elg file other than the last line.

        Returns:
            True if the data is ok, otherwise prints an error and returns False.
        """

        has_error = False
        if data['num'] != num or data['index'] != index:
            print(f'seq db mismatch for {num}.', file=sys.stderr)
            has_error = True
        factor_data = self.get_factor_data(num, data['factor_string'])
        if not factor_data:
            has_error = True
        if data['complete'] != factor_data['complete']:
            print(f'factor_string complete mismatch for {num}.', file=sys.stderr)
            has_error = True
        if factor_data['num'] != num:
            print(f'factor_string mismatch for {num}.', file=sys.stderr)
            has_error = True
        if factor_data['complete'] and factor_data['aliquot_sum'] != data['aliquot_sum']:
            print(f'factor_string aliquot sum mismatch for {num}.', file=sys.stderr)
            has_error = True
        if line_data:
            if data['num'] != line_data['num'] or line_data['index'] != data['index']:
                print(f'file mismatch for {num}.', file=sys.stderr)
                has_error = True
            if line_data['complete'] and line_data['aliquot_sum'] != data['aliquot_sum']:
                print(f'file aliquot sum mismatch for {num}.', file=sys.stderr)
                has_error = True
        return not has_error

    def get_factor_data(self, num, factor_string):
        """Given the number and it's factors as a string calculate the data for this step.

        The factor string may not have all the factors in which case we have an incomplete
        entry.  If we do have a complete entry we can calculate the aliquot sum for the next
        number in the series.

        Obviously all the factors listed must divide num for valid data.

        Args:
            num: The number in the sequence
            factor_string: The prime factors using * and ^ for times and power
        Returns:
            Returns the resulting data or None if an error.
        """

        alq = 1
        check_num = 1
        num_type = r'^\d+$'
        data = {
            'num': num,
            'aliquot_sum': 0,
            'complete': False
        }
        if factor_string == '':
            if num == 1:
                data['complete'] = True
            return data
        prime_powers = factor_string.split('*')
        for prime_power_string in prime_powers:
            if '^' in prime_power_string:
                items = prime_power_string.split('^')
                has_error = False
                if len(items) != 2:
                    print(f'factor_string {factor_string} extra ^ for {num}', file=sys.stderr)
                    has_error = True
                else:
                    prime_string = items[0].strip()
                    power_string = items[1].strip()
                    if (not re.search(num_type, prime_string) or
                        not re.search(num_type, power_string)):
                        print(f'factor_string {factor_string} not number for {num}',
                              file=sys.stderr)
                        has_error = True
                if has_error:
                    return None
                prime = int(prime_string)
                power = int(power_string)
            else:
                prime_string = prime_power_string.strip()
                if not re.search(num_type, prime_string):
                    print(f'factor_string {factor_string} not number for {num}', file=sys.stderr)
                    return None
                prime = int(prime_string)
                power = 1
            check_num *= prime**power
            term = 1
            for curr in range(1, power+1):
                term += prime**curr
            alq *= term
        alq -= num
        if check_num < num:
            # incomplete factorization
            if num % check_num != 0:
                print(f' factor_string {factor_string} failed to divide: {num} % {check_num}',
                      file=sys.stderr)
                self.status.update_factor(num, True)
                return None
            data['complete'] = False
            data['aliquot_sum'] = 0
        elif check_num == num:
            data['complete'] = True
            data['aliquot_sum'] = alq
        else:
            print(f'factor_string {factor_string} mismatch: {num} vs {check_num}', file=sys.stderr)
            self.status.update_factor(num, True)
            return None
        return data

    def check_verify_status(self, seq):
        """Report incorrect verify status"""
        status_data = self.status.get_status(seq)
        if not status_data:
            print(f'***Missing status for {seq}')
        if status_data and status_data['verified']:
            print(f'***Did not catch verify change for {seq}')

    def _retrieve_elf(self, seq, fix_file, is_elg):
        """There is an issue with the elf or elg file so renew it.

        Args:
            seq: The sequence with the issue.
            fix_file: bash file to fix the sequence's file.
            is_elg: True if this is an elg file, False if it is an elf file.
        """

        subd = seq // aliquot_util.INTERVAL
        if is_elg:
            elg_name = f'elg_{subd}/alq_{seq}.elg'
            if fix_file:
                fix_file.write(f'rm {elg_name}\n')
                fix_file.write(f'python3 alq_create_elf.py {seq}\n')
        if fix_file:
            fix_file.write(f'python3 main.py {seq} {seq}\n')
            fix_file.write(f'python3 alq_verify.py -c {seq} {seq}\n')
            fix_file.flush()
        else:
            print(f'Update for localdb may be needed for {seq}')
