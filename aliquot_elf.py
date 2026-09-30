#!/usr/bin/env python

"""Handling of elf files for aliquot series

Elf files is a special format also used outside this project to store aliquot series.  The main
program is aliqueit which does factorization to extend elf files to further terms.

Elf files are located in elf_<subd> directories wheresubd is the sequence
number // aliquot_util.INTERVAL and INTERVAL is 1 million. So sequence 276 is in elf_0,

The form of elf files is:
<index> . <num> = <prime1>[^<power1] * <prime2>[^<power2>] * ...

For example for 276, the lowest open series, we have :
0 .   276 = 2^2 * 3 * 23
1 .   396 = 2^2 * 3^2 * 11
2 .   696 = 2^3 * 3 * 29
...
to over 210 digits.

The last line is incomplete for open series since the full factorization is not known.

There are also elg files created for this project to hold merging series without duplicating
information.  At the point they merge they contain a single line 'To <seq>:<index>' as the
last line of the file.  They are stored in the elg_<subd> directory instead of elf_<subd>.

"""

import os
import shutil
import logging
from pathlib import Path
from typing import TextIO

from aliquot_types import AlqData, ParseFileResult
from aliquot_data import AliquotData
from aliquot_status import AliquotStatus
from aliquot_statistics import AliquotStatistics
import aliquot_util

logger = logging.getLogger(__name__)

SeqData = dict[str, int | bool | str ] | None

class AliquotElf:
    """Main aliquot class

    The different functions are called from python runnable programs starting with
    alq_*.py to do the many things possible.
    """

    def __init__(self, sql):
        """Initializes subclasses used.

        Args:
            sql: postgres sql connection.
            log: for logging warnings and errors.
        
        Attributes:
            aliquot_sum: Class to find initial sequences using python to 25 digits.
            aliquot_data: Class to get and set local db data.
            aliquot_status: Class that sets status information.
            aliquot_statistics: Class that figures out run statistics.
            interval: Set to 1 million for elf/elf subfolders.
            open_list: The list of open sequences.
        """

        self.aliquot_data = AliquotData(sql)
        self.status = AliquotStatus(sql)
        self.statistics = AliquotStatistics(sql)

    def get_from_file(self, seq: int, elf_name: str,
                      update_factordb: bool = True) -> ParseFileResult:
        """Create/update sequence from an elf file.

        The aliqueit program and factor database use elf files.  New entries can
        be added to these files.  This function checks for entries not in the local
        database.  If a merge is detected we update sequences based on the merge.

        Args:
            seq: The sequence being added to.
            elf_name: The name of the elf file (which is elf_<seq/million>/alq_<seq>.elf)
            update_factordb: Whether to set the status flag to indicate a need to check
                the factordb. It would be False if the data is from the factor db and true
                if aliqueit was run to extend the sequence for new unknown values.
        Returns:
            Result of 
        """

        print(f'getting {seq} from file')
        result: ParseFileResult = {
            'merge': False,
            'index': 0,
            'final_num': seq,
            'elf_error': False,
            'insert': False,
            'open': False,
            'missing_open': False,
            'merge_info': {
                'updates': [],
                'verify': []
            }
        }
        try:
            with open(elf_name, encoding="ascii") as elf_file:
                self._process_elf_file(seq, elf_file, result)
                index = result['index']
                if result['insert']:
                    if update_factordb:
                        self.status.factordb_update(seq, True)
                else:
                    print(f'No new element for fdb - {seq}:{index}')
            self.status.update_localdb(seq, False)
        except FileNotFoundError:
            print(f'elf file error for {elf_name}')
            result['elf_error'] = True
            self.status.update_elf(seq, True)
        return result

    def _process_elf_file(self, seq: int, elf_file: TextIO, result: ParseFileResult) -> None:
        """Update local data from an elf (elg) file

        Args:
           seq: The sequence to update.
           elf_file: The elf file.
           result: Result of the local data update with possible elf or elg update indicated.
        """

        line_processed = False
        value = {}
        for line in elf_file:
            curr = result['final_num']
            if line[0] == 'T':
                #elg_file
                result['merge'] = True
                if not self._check_valid_to(curr, line):
                    print(f'Invalid To line when processing elf/elg for {seq}:{index}')
                break
            if not aliquot_util.is_valid_elf_line(line):
                print(f'For {seq}:{index} halting at invalid: {line}')
                result['elf_error'] = True
                break
            line_processed = True
            data = aliquot_util.parse_elf_line(line.strip())
            if not data or curr != data['num'] or result['index'] != data['index']:
                index = result['index']
                print(f'Elf file for {seq} corrupt at {index}.')
                result['elf_error'] = True
                break
            data['base'] = seq
            local_data: AlqData | None = self.aliquot_data.select_data(curr, True)
            if not data['complete']:
                if local_data:
                    #Special case where data beyond current elf file is known
                    print(f'For {seq}: Data missing from elf.')
                    result['elf_error'] = True
                    break
                local_data = self.aliquot_data.select_data(curr, False)
            if (not local_data or data['base'] != local_data['base'] or
                data['index'] != local_data['index']):
                result['insert'] = True
                self._update_local_data(data, result)
                if result['merge']:
                    break
            if data['aliquot_sum'] > 0:
                result['final_num'] = data['aliquot_sum']
                if result['final_num'] in value or curr == 1:
                    result['merge'] = True
                    break
                value[result['final_num']] = True
            else:
                result['open'] = True
            result['index'] += 1
        if not line_processed:
            print(f'No lines in elf file for {seq}')
            result['elf_error'] = True
        if not result['merge'] and not result['open']:
            result['missing_open'] = True
        return result

    def _check_valid_to(self, curr: int, line: str) -> bool:
        """Check if 'To <seq>:<index>' in elg file is valid

        Args:
            curr: The current number
            line: The to line to check.
        Returns:
            True if line is correct, otherwise False.
        """

        local_data: AlqData | None = self.aliquot_data.select_data(curr, True)
        base = local_data['base']
        base_index = local_data['index']
        to_line = f'To {base}:{base_index}\n'
        return to_line == line

    def update_single_local_data(self, data: AlqData) -> ParseFileResult:
        """Update for a single new line.

        Will also add in a new incomplete entry at the end with factors unknnown.

        Args:
            data: The data to add to the local database.
        Returns:
            Result indicates a merge vs still open series
        """

        result: ParseFileResult = {
            'merge': False,
            'index': data['index'],
            'final_num': data['num'],
            'elf_error': False,
            'insert': False,
            'open': False,
            'missing_open': False,
            'merge_info': {
                'updates': [],
                'verify': []
            }
        }
        self._update_local_data(data, result)
        result['final_num'] = data['aliquot_sum']
        result['index'] += 1
        if not result['merge']:
            self.append_incomplete(data, result)
            if not result['merge']:
                result['open'] = True
        return result

    def append_incomplete(self, data: AlqData, result: ParseFileResult):
        """Add new incomplete entry based on previous entry.

        Args:
            data: Previous entry so aliquot_sum is the number.
            result: Result indicates a merge (extremely unlikely)
        """

        incomplete_data = {}
        incomplete_data['complete'] = False
        incomplete_data['base'] = data['base']
        incomplete_data['index'] = data['index'] + 1
        incomplete_data['num'] = data['aliquot_sum']
        self.add_incomplete(incomplete_data, result)

    def add_incomplete(self, incomplete_data, result: ParseFileResult):
        """Add new incomplete entry

        Args:
            incomplete_data: base, index, number, and complete already set.
            result: Result indicates a merge (extremely unlikely)
        """

        incomplete_factors = aliquot_util.compute_factors(incomplete_data['num'])
        incomplete_data['factor_string'] = incomplete_factors['factor_string']
        incomplete_data['unfactor'] = incomplete_factors['unfactored']
        incomplete_data['aliquot_sum'] = 0
        self._update_local_data(incomplete_data, result)
        result['final_num'] = incomplete_data['num']
        if not result['merge']:
            result['open'] = True
            result['missing_open'] = False

    def _update_local_data(self, data: AlqData, result: ParseFileResult) -> None:
        """Update local data and report any merge

        Args:
            data: The data to insert, skip, or update
            result: Contains merge information if it occurs.
        """

        check=self.insert_or_check(data)
        result['merge'] = False
        if 'merge' in check:
            result['merge'] = True
            result['merge_info'] = self.handle_new_merge(check['merge'])

    def insert_or_check(self, data: AlqData) -> dict[str, bool | dict[str, AlqData]]:
        """Insert data to the local db if new, or update if the new sequence is smaller.

        Args:
            data: The data to add to the local db.

        Returns:
            check with insert set to True if there was no existing data.
            check holds merge data if a merge occurred.
        """

        check = {}
        num = data['num']
        if not self.aliquot_data.has_data(num, True) and not self.aliquot_data.has_data(num, False):
            self.aliquot_data.insert_data(data)
            check['insert'] = True
            return check
        sql_complete = True
        curr_data: AlqData | None = self.aliquot_data.select_data(num, True)
        if not curr_data:
            curr_data: AlqData | None = self.aliquot_data.select_data(num, False)
            sql_complete = False
        if not curr_data:
            self.aliquot_data.insert_data(data)
            check['insert'] = True
            return check
        old_seq = curr_data['base']
        new_seq = data['base']
        if new_seq == old_seq:
            if sql_complete is False:
                if data['complete']:
                    self.aliquot_data.insert_data(data)
                    self.aliquot_data.delete_incomplete(num)
                    check['insert'] = True
                    return check
            if data['index'] == curr_data['index']:
                return check
        merge = {}
        merge['old_data'] = curr_data
        merge['new_data'] = data
        check['merge'] = merge
        return check

    def handle_new_merge(self, merge: dict[str, AlqData]) -> bool:
        """Code to handle merges.

        This code is hard to get right as the cases are complex.  When a merge
        occurs if the old sequence is smaller the new sequence merges into the old.

        The harder case is when the new sequence is smaller.
           1. Numbers that used to be part of the old sequence become part of the new sequence.
           2. If the old number merged into something else then it will change if the new sequence
              is less.  This is a change to the sequence data.
           3. The merge table can have numbers that merged into the old sequence.  The merge
              entry will change if the merge happens after the new sequence merge.  This is
              a change to the merge table.
           4. The change will also affect elg files for the above cases so these also need updating.
           5. Verify flag should be reset on any sequence affected so veriy knows to double check
              the sequence.
           6. If the new sequence doesn't hit a smaller sequence it is still an open sequence.

        The call self.statistics.handle_merge(old_data, new_data, prev_data) updates the merge
        table.  The need for prev_data complicates things, and can be None if the first of a
        sequence.  It finds the sequences that merge into the old sequence.

        Args:
           merge: Holds the old and new data.

        Return:
           result 
           elf file may have more information to parse.
        """

        old_data = merge['old_data']
        new_data = merge['new_data']
        old_seq = old_data['base']
        new_seq = new_data['base']
        self.status.update_verify(old_seq, True)
        self.status.update_verify(new_seq, True)
        if old_seq < new_seq:
            prev_data = self.get_prev_data(new_data)
        else:
            prev_data = self.get_prev_data(old_data)
        change_data = self.statistics.handle_merge(old_data, new_data, prev_data)
        change_data['old_data'] = old_data
        change_data['new_data'] = new_data
        if old_seq <= new_seq:
            print(f'Hit smaller seq: {old_seq} vs {new_seq}')
        else:
            print('Update older sequence to new')
            if new_data['aliquot_sum'] != 0:
                self._update_old_seq_to_new(change_data)
        return change_data

    def _update_old_seq_to_new(self, change_data):
        new_data = change_data['new_data']
        new_seq = new_data['base']
        old_data = change_data['old_data']
        old_seq = old_data['base']
        self.aliquot_data.update_data(new_data)
        index = new_data['index']
        curr = new_data['aliquot_sum']
        done = False
        prev_base = old_seq
        prev_data = new_data
        while not done:
            index += 1
            curr_data: AlqData | None = self.aliquot_data.select_data(curr, True)
            if not curr_data:
                curr_data: AlqData | None = self.aliquot_data.select_data(curr, False)
            if not curr_data:
                print(f'Issue with sequence {old_seq}/{new_seq} not complete '
                      f'at {index} (fixed)')
                incomplete_factors = aliquot_util.compute_factors(curr)
                seq_entry = {
                    'num': curr,
                    'index': index,
                    'base': new_seq,
                    'factor_string': incomplete_factors['factor_string'],
                    'unfactor': incomplete_factors['unfactored'],
                    'aliquot_sum': 0
                }
                self.aliquot_data.insert_data(seq_entry)
                done = True
                continue
            update_data = {}
            for entry in curr_data:
                update_data[entry] = curr_data[entry]
            update_data['base'] = new_seq
            update_data['index'] = index
            curr_base = curr_data['base']

            if curr_base != prev_base and curr_base > new_seq:
                # Another sequence now merges into the new sequence so
                # call self.statics.handle_merge for this
                curr_merge = self.statistics.get_merge(curr_base)
                if curr_merge:
                    self._change_data_update(change_data, curr_data, update_data)
            if new_seq < curr_base:
                print(f'Update:{curr_base}->{new_seq}')
                self.status.update_verify(curr_base, True)
                self.aliquot_data.update_data(update_data)
                if prev_base != curr_base:
                    self._change_data_update(change_data, curr_data, update_data)
            else:
                print(f'New smaller seq: {curr_base} vs {new_seq}')
                if prev_data:
                    new_change = self.statistics.handle_merge(curr_data,
                                                              update_data,
                                                              prev_data)
                    aliquot_util.add_unique(change_data, new_change, 'updates')
                    aliquot_util.add_unique(change_data, new_change, 'verify')
                    prev_base = curr_base
                done = True
            curr = curr_data['aliquot_sum']
            if curr == 0:
                break
            prev_data = update_data

    def _change_data_update(self, change_data, curr_data, update_data):
        if curr_data['index'] == 0:
            self.statistics.delete_merge(curr_data['base'])
        else:
            prev_data = self.get_prev_data(curr_data)
            new_change = self.statistics.handle_merge(curr_data, update_data, prev_data)
            aliquot_util.add_unique(change_data, new_change, 'updates')
            aliquot_util.add_unique(change_data, new_change, 'verify')

    def create_elf_file(self, seq):
        """Recreate the elf file from the local database.

        Note this will create an elf file for any series. It should not be called
        for aliquot sequences that don't reach 25 digits before merging. There is method
        to clean up unneeded elf files: alq_useful_elf.py

        Args:
            seq: The sequence to recreate.
        """

        subd = seq // aliquot_util.INTERVAL
        elf_name = f'elf_{subd}/alq_{seq}.elf'
        tmp_name = f'elf_{subd}/alq_{seq}.tmp'
        try:
            with open(tmp_name, 'w', encoding="ascii") as elf_file:
                curr = seq
                done = False
                values = {}
                index = 0
                while not done:
                    if curr == (1, 0):
                        done = True
                    elif curr in values:
                        done = True
                    else:
                        values[curr] = True
                        data: AlqData | None = self.aliquot_data.select_data(curr, True)
                        if not data:
                            data: AlqData | None = self.aliquot_data.select_data(curr, False)
                        if not data:
                            print(f'For {seq} data not complete for elf')
                            self.status.update_localdb(seq, True)
                            line = f'{index} .   {curr} ='
                            elf_file.write(f'{line}\n')
                            done = True
                        else:
                            line = f'{index} .   {curr} ='
                            factor_string = self._calc_factor_string(data)
                            line += factor_string
                            elf_file.write(f'{line}\n')
                            if data['complete']:
                                curr = data['aliquot_sum']
                                index += 1
                            else:
                                done = True
            if Path(elf_name).is_file():
                line_count = aliquot_util.get_valid_line_count(elf_name)
                if line_count > index:
                    print(f'current {elf_name} line count is {line_count} vs index {index}')
                    bak2_name = f'elf_{subd}/alq_{seq}.bak_longer'
                    shutil.copy(elf_name, bak2_name)
                bak_name = f'elf_{subd}/alq_{seq}.bak'
                shutil.move(elf_name, bak_name)
            shutil.move(tmp_name, elf_name)
            self.status.update_elf(seq, False)
            self.status.update_elg(seq, True)
        except  OSError as e:
            print(f'aborted update of {elf_name}: {e}')
            if Path(tmp_name).is_file():
                os.remove(tmp_name)

    def _calc_factor_string(self, data):
        """Find the full factor string when creating elf file

        Args:
            data: Local data which may contain none/some/all factors.
        """

        initial_factor_string = data['factor_string']
        curr = data['num']
        seq = data['base']
        final_factor_string = ''
        if initial_factor_string != '':
            factors = aliquot_util.to_factors(initial_factor_string)
        else:
            factor_data = aliquot_util.compute_factors(curr)
            factor_string = factor_data['factor_string']
            factors = factor_data['factors']
            if not data['complete']:
                data['factor_string'] = factor_string
                data['unfactor'] = factor_data['unfactored']
                print(f'For {seq} db factor string updated')
                self.aliquot_data.update_data(data)
        first = True
        if factors:
            for prime in factors:
                power = factors[prime]
                if power == 1:
                    curr_factor = f'{prime}'
                else:
                    curr_factor = f'{prime}^{power}'
                if first:
                    final_factor_string += f' {curr_factor}'
                    first = False
                else:
                    final_factor_string += f' * {curr_factor}'
        return final_factor_string

    def factor_check(self, seq, num):
        """combines all known factors for num.

        Uses compute_factors to find the smallest prime powers.
        Also checks the elf file for primes that might have come from the
        factordb.
        It also fixes errors if somehow we have a prime not in the prime
        factorization of num.  This might rarely occur if we get a partial number
        from the factordb.

        This changes the local database and elf file so return value.

        Args:
            seq: The sequence num belongs to.
            num: The number to find the factors for.
        """

        subd = seq // aliquot_util.INTERVAL
        elf_name = f'elf_{subd}/alq_{seq}.elf'
        data: AlqData | None = self.aliquot_data.select_data(num, False)
        if not data:
            print(f'Failed to find data for {num} of sequence {seq}')
            self.status.update_localdb(seq, True)
            return
        db_factor_str = data['factor_string']
        index = data['index']
        db_divisor = aliquot_util.find_divisor_from_str(db_factor_str)
        db_factor_str = self._check_divisor(data, db_divisor)
        if Path(elf_name).is_file():
            with open(elf_name, encoding="ascii") as elf_file:
                lines = elf_file.readlines()
                if len(lines) > 0:
                    line_data = aliquot_util.parse_elf_line(lines[-1])
                    if not line_data:
                        print(f'For {seq} fixing elf file.')
                        self.create_elf_file(seq)
                    elif line_data['num'] == num:
                        line_factor_str = line_data['factor_string']
                        #check for issue to fix...
                        if line_factor_str != db_factor_str:
                            self._update_final_factors(data, elf_name, line_factor_str,
                                                       db_factor_str)
                    else:
                        if line_data['index'] < index:
                            print(f'For {seq} - recreating elf.')
                            self.create_elf_file(seq)
                        else:
                            print(f'For {seq} line data mismatch')
                else:
                    print(f'For {seq} - Empty Elf File.')
        else:
            print(f'For {seq} - New elf for open sequence:')
            self.create_elf_file(seq)
        self.status.update_factor(seq, False)

    def _check_divisor(self, data, db_divisor):
        """Check divisor for issues

        Args:
            data: The data the divisor is based on.
            db_divisor: The current divisor to check.
        """

        num = data['num']
        seq = data['base']
        index = data['index']
        db_factor_str = data['factor_string']
        num_data = aliquot_util.compute_factors(num)
        num_factors = num_data['factors']
        num_divisor = aliquot_util.find_divisor(num_factors)
        num_factor_str = num_data['factor_string']

        if num % db_divisor != 0:
            #Error so reset values
            data['factor_string'] = num_factor_str
            data['unfactor'] = num_data['unfactored']
            print(f'For {seq}:{index} db factor string updated to correct error')
            self.aliquot_data.update_data(data)
            db_factor_str = data['factor_string']
            db_divisor = aliquot_util.find_divisor_from_str(db_factor_str)
        elif db_divisor % num_divisor != 0:
            if num_divisor % db_divisor == 0:
                data['factor_string'] = num_factor_str
                data['unfactor'] = num_data['unfactored']
                print(f'For {seq}:{index} db factor string updated')
                self.aliquot_data.update_data(data)
                db_factor_str = data['factor_string']
                db_divisor = aliquot_util.find_divisor_from_str(db_factor_str)
            else:
                full_factors = aliquot_util.combine_factors(num, num_factors, db_factor_str)
                if full_factors:
                    data['factor_string'] = full_factors['factor_string']
                    data['unfactor'] = full_factors['unfactored']
                    print(f'For {seq}:{index} db factor string combined')
                    self.aliquot_data.update_data(data)
                    db_factor_str = data['factor_string']
                    db_divisor = aliquot_util.find_divisor_from_str(db_factor_str)
        return db_factor_str

    def _update_final_factors(self, data, elf_name, line_factor_str, db_factor_str):
        num = data['num']
        index = data['index']
        seq = data['base']
        print(f'Update Final Factors for {elf_name}: {line_factor_str} vs {db_factor_str}')
        line_divisor = aliquot_util.find_divisor_from_str(line_factor_str)
        db_divisor = aliquot_util.find_divisor_from_str(db_factor_str)
        if line_divisor != db_divisor:
            #There is a difference
            if num % line_divisor != 0:
                self.create_elf_file(seq)
            if line_divisor % db_divisor == 0:
                # Elf has more factors
                data['factor_string'] = line_factor_str
                print(f'For {seq}:{index} db factor string updated')
                self.aliquot_data.update_data(data)
            else:
                if db_divisor % line_divisor == 0:
                    #db has more factors so recreate elf.
                    self.create_elf_file(seq)
                    print(f'For {elf_name}:{index} - factor string updated')
                else:
                    full_factors = aliquot_util.combine_factors_str(num, line_factor_str,
                                                                    db_factor_str)
                    if full_factors:
                        data['factor_string'] = full_factors['factor_string']
                        data['unfactor'] = full_factors['unfactored']
                        print(f'For {elf_name}:{index} - '
                              'factor string combined')
                        self.aliquot_data.update_data(data)
                        db_factor_str = data['factor_string']
                        db_divisor = aliquot_util.find_divisor_from_str(db_factor_str)

    def get_prev_data(self, data: AlqData) -> AlqData:
        """Finds the entry for the previous index

        data contains a base sequence and index.  If the index is zero there is no
        previous element so None is returned.

        Args:
            data: data to find the previous data of.

        Returns:
            previous data if it exists, otherwise None.
        """

        index = data['index']
        seq = data['base']
        if index == 0:
            return None
        prev_index =  index - 1
        subd = seq // aliquot_util.INTERVAL
        for prefix in ['elf', 'elg']:
            file_name = f'{prefix}_{subd}/alq_{seq}.{prefix}'
            file_result = self._read_file_prev_data(file_name, prev_index, seq)
            if file_result is not None:
                return file_result
        curr = seq
        done = False
        values = {}
        while not done:
            curr_data: AlqData | None = self.aliquot_data.select_data(curr, True)
            if curr_data:
                curr = curr_data['aliquot_sum']
                if curr in values or curr == 1:
                    break
                values[curr] = True
                if curr_data['index'] == prev_index:
                    if curr_data['base'] != seq:
                        print(':Failed to find correct prev_data')
                        print(data)
                        print(curr_data)
                        return None
                    return curr_data
            else:
                done = True
        print(f'Unable to get prev data for {seq}.  Run verify.')
        return None

    def _read_file_prev_data(self, file_name: str, prev_index: int, seq: int) -> AlqData | None:
        """Find previous data from an elf/elg file.

        Args:
            file_name: The name of the file to use.
            prev_index: The (previous) index to return data for.
            seq: The current sequence
        """

        if not Path(file_name).is_file():
            return None

        line = aliquot_util.get_line(file_name, prev_index)
        if line:
            curr_data = aliquot_util.parse_elf_line(line)
            if curr_data:
                num = curr_data['num']
                prev_data: AlqData | None = self.aliquot_data.select_data(num, True)
                if prev_data['base'] != seq or prev_data['index'] != prev_index:
                    print(f'{file_name}:Failed to find correct prev_data')
                    return None
                if prev_data:
                    return prev_data
        return None
