#!/usr/bin/env python

""" Elg creation and check for aliquot series

When an series merges into another elf files are not able to express this merge information.
For this reason elg files (elf generalized) were created.  These keep sequences that reach 25
or more digits before merging.  The format is the same except for the final line.  This final
line has the format 'To <seq>:<index>' to indicate what series was merged to.  Note that the
number is not given.

The old elf file is saved: <name>.elf => <name>.merge which can later be moved to the merge
subdirectory by cleanup in case we need to recover it.

The new elg file is created in the elg_# instead of the elf_# directory. 
"""

import os
import sys
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import TypedDict
import shutil

from aliquot_types import ParseFileResult, AlqData
from aliquot_status import AliquotStatus
from aliquot_data import AliquotData
from aliquot_elf import AliquotElf
from aliquot_statistics import AliquotStatistics
import aliquot_util
logger = logging.getLogger(__name__)

class ElgResult(TypedDict):
    """Returned after elf file parse."""
    has_error: bool
    has_to: bool

@dataclass
class ElgContext:
    """Pass in data needed for checking elg files"""
    seq: int
    index: int
    line: str
    data: AlqData | None
    prev_data: AlqData | None
    current: int
    value: dict[int, bool]

class AliquotElg:
    """Updating elf->elg when merge occurs"""

    def __init__(self, sql):
        """Initializes subclasses used.

        Args:
            sql: postgres sql connection.
        
        Attributes:
            aliquot_data: Class to get and set local db data.
            aliquot_status: Class that sets status information.
        """

        self.aliquot_elf = AliquotElf(sql)
        self.aliquot_data = AliquotData(sql)
        self.status = AliquotStatus(sql)
        self.statistics = AliquotStatistics(sql)

    def update_elf_elg_for_merge(self, seq: int) -> None:
        """Check if the sequence needs updating for the new merge

        This is called if seq has an elf or elg file.  We update that file
        for the merge.  The elf file will become an elg file and an elg file
        may change how the merge occurred.

        Args:
            seq: The sequence to check.
        """

        subd = seq // aliquot_util.INTERVAL
        elf_name = f'elf_{subd}/alq_{seq}.elf'
        elg_name = f'elg_{subd}/alq_{seq}.elg'
        if Path(elf_name).is_file():
            #Make sure elf is complete
            print(f'Creating elf merge for {seq}')
            self.make_elg(seq)
        elif Path(elg_name).is_file():
            self.make_elg(seq)
            print(f'Updating elg merge for {seq}')

    def make_elg(self, seq: int) -> None:
        """Main function to handle creation of elg files.

        When a series merges it is no longer open so it switches from an elf to an elg
        file.  The elg file includes a 'To <seq>:<index>' line and has an elg extension.
        It is also located in the elg_# directory.

        Args:
            seq: The sequence to check if it merges and if so create/update the elg file.
        """

        subd = seq // aliquot_util.INTERVAL
        elf_name = f'elf_{subd}/alq_{seq}.elf'
        elg_name = f'elg_{subd}/alq_{seq}.elg'
        if Path(elf_name).is_file():
            result = self.is_merge(seq, elf_name)
            #Local db and elf need to match to make the elf file.
            if result['update_localdb']:
                self.aliquot_elf.get_from_file(seq, elf_name, False)
                result =self.is_merge(seq, elf_name)
            elif result['update_elf']:
                self.create_elf_file(seq)
                result = self.is_merge(seq, elf_name)
            if not result['update_localdb'] and not result['update_elf']:
                if result['merge']:
                    self.make_elg_file(seq, elf_name, elg_name)
                    elf_merge_name = f'elf_{subd}/alq_{seq}.merge'
                    os.rename(elf_name, elf_merge_name)
                    self.status.update_to_merged(seq)
            else:
                print('Unable to fix issue with sequence. Try getting latest from factordb'
                      ' or running aliqueit and running main.py')
                sys.exit(1)
        else:
            if Path(elg_name).is_file():
                self.check_elg(seq, elg_name)

    def check_elg(self, seq: int, elg_name: str) ->  None:
        """Checks whether an elg file is still accurate.

        A new merge can change how a sequence merges. This function checks for changes
        and updates the elg file if needed.

        Args:
            seq: The sequence for the elg file.
            elg_name: The name of the elg file to check.
        """

        current = seq
        index = 0
        prev_data = None
        value = {}
        has_to = False
        try:
            with open(elg_name, encoding="ascii") as elg_file:
                for line in elg_file:
                    if has_to:
                        print(f'Lines past to line in {elg_name}')
                        self.status.update_elf(seq, True)
                        return
                    if len(line) == 0:
                        print(f'Line in elg_file {elg_name} is blank')
                        self.status.update_elf(seq, True)
                        return
                    data: AlqData | None = self.aliquot_data.select_data(current, True)
                    if not data:
                        print(f'Sequence {seq}, index {index} elg but complete data missing.')
                        self.status.update_localdb(seq, True)
                        return
                    if data['num'] != current:
                        print(f'Sequence {seq}, index {index} num mismatch occurred')
                        self.status.update_localdb(seq, True)
                        return

                    base = data['base']
                    ctx = ElgContext(
                        seq=seq,
                        index=index,
                        line=line,
                        data=data,
                        prev_data=prev_data,
                        current=current,
                        value=value
                    )
                    if base == seq:
                        result: ElgResult = self._check_elg_same_base(ctx)
                    else:
                        result: ElgResult = self._check_elg_new_base(ctx)
                    if result['has_error']:
                        return
                    has_to = result['has_to']
                    index += 1
                    current = data['aliquot_sum']
                if not has_to:
                    print(f'For {seq}, elg_file is incomplete')
                    if data['aliquot_sum'] in value:
                        # Cycle
                        data = self.aliquot_data.select_data(current, True)
                        if not data:
                            print(f'For {seq}, Code error')
                            return
                        self.elg_update_to(seq, index, elg_name ,data['base'], data['index'])
                    else:
                        print(f'For {seq}, unexpected end of elf file')
                        self.status.update_elf(seq, True)

            self.status.update_elg(seq, False)
        except FileNotFoundError:
            print(f'elg file error for {elg_name}')
            self.status.update_elf(seq, True)

    def _check_elg_same_base(self, ctx: ElgContext) -> ElgResult:
        base = ctx.data['base']
        seq = ctx.seq
        index = ctx.index
        is_to = ctx.line[0] == 'T'
        subd = seq // aliquot_util.INTERVAL
        elg_name = f'elg_{subd}/alq_{seq}.elg'
        result = {}
        result['has_error'] = False
        result['has_to'] = False
        if is_to:
            result['has_to'] = True
            if ctx.current in ctx.value:
                base_index = ctx.data['index']
                to_line = f'To {base}:{base_index}\n'
                if  to_line != ctx.line:
                    base_index = ctx.data['index']
                    print(f'Updating To line for {seq}:{index}')
                    self.elg_update_to(seq, index, elg_name, base, base_index)
            else:
                print(f'Sequence {seq}, index {index} mismatch with '
                      f'{elg_name} To statement')
                self.status.update_elf(seq, True)
                result['has_error'] = True
        else:
            ctx.value[ctx.current] = True
            line_data: ParseFileResult | None = aliquot_util.parse_elf_line(ctx.line)
            if not line_data['complete']:
                print(f'Sequence {seq}, index {index} in {elg_name} not complete')
                self.status.update_elf(seq, True)
                result['has_error'] = True
            if not ctx.data['complete']:
                print(f'Sequence {seq}, index {index} is not complete')
                self.status.update_localdb(seq, True)
                result['has_error'] = True
            if (line_data['num'] != ctx.data['num'] or
                line_data['aliquot_sum'] != ctx.data['aliquot_sum']):
                print(f'Sequence {seq}, index {index} data mismatch with '
                      f'{elg_name}')
                self.status.update_elf(seq, True)
                result['has_error'] = True
            if index != ctx.data['index']:
                print(f'Sequence {seq}, index {index} has index mismatch')
                self.status.update_elf(seq, True)
                result['has_error'] = True
            if index != line_data['index']:
                print(f'Sequence {seq}, index {index} has index mismatch '
                      f'with {elg_name}')
                self.status.update_elf(seq, True)
                result['has_error'] = True
        return result

    def _check_elg_new_base(self, ctx: ElgContext) -> ElgResult:
        base = ctx.data['base']
        seq = ctx.seq
        index = ctx.index
        is_to = ctx.line[0] == 'T'
        result = {}
        subd = seq // aliquot_util.INTERVAL
        elg_name = f'elg_{subd}/alq_{seq}.elg'
        result['has_error'] = False
        result['has_to'] = False
        if base < seq:
            base_index = ctx.data['index']
            to_line = f'To {base}:{base_index}\n'
            if not is_to or to_line != ctx.line:
                print(f'Updating To line for {seq}:{index}')
                if ctx.prev_data:
                    merge = {
                        'merge_from_sequence': seq,
                        'merge_from_index': ctx.prev_data['index'],
                        'num_before_merge': ctx.prev_data['num'],
                        'merge_to_sequence': base,
                        'merge_to_index' : base_index,
                        'num_after_merge': ctx.data['num'],
                        'processed': False
                    }
                    self.statistics.add_merge(merge)
                self.elg_update_to(seq, index, elg_name, base, base_index)
            result['has_to'] = True
        else:
            print(f'Sequence {seq}, index {index} needs update. Old sequence found.')
            self.status.update_localdb(seq, True)
            result['has_error'] = True
        return result

    def is_merge(self, seq, elf_name):
        """Checks to see if a merge is needed.

        Now does error checking and returns results based on the check.

        Args:
            seq: The sequence being updated.
            elf_name: The elf file to check if it now merges.

        Return:
            a dict with:
                merge: If True there is a merge.
                update_localdb: If True localdb is out of date.
                update_elf: If True elf is out of date.
        """

        current = seq
        index = 0
        is_complete = True
        value = {}
        result = {'merge': False, 'update_localdb': False, 'update_elf': False}
        try:
            with open(elf_name, encoding="ascii") as elf_file:
                for line in elf_file:
                    if len(line) == 0:
                        print(f'Line in elf_file {elf_name} is blank')
                        self.status.update_elf(seq, True)
                        continue
                    if current in value:
                        break
                    value[current] = True
                    is_complete = True
                    data = self.aliquot_data.select_data(current, is_complete)
                    if not data:
                        is_complete = False
                        data = self.aliquot_data.select_data(current, is_complete)
                        if not data:
                            print(f'Sequence {seq}, index {index} missing db entry.')
                            result['update_localdb'] = True
                            break
                    base = data['base']
                    line_data = aliquot_util.parse_elf_line(line)
                    if base == seq:
                        if not data['complete'] and not line_data['complete']:
                            return result
                        if not data['complete'] and line_data['complete']:
                            print(f'Sequence {seq}, index {index} needs update from elf')
                            self.status.update_localdb(seq, True)
                            result['update_localdb'] = True
                            break

                        if not self._check_elf_ok(index, line_data, data, elf_name):
                            break

                    elif base < seq:
                        result['merge'] = True
                        break
                    else:
                        result['update_localdb'] = True
                        break
                    current = data['aliquot_sum']
                    index += 1
                if current in value:
                    result['merge'] = True
                if not result['merge'] and not result['update_localdb']:
                    result['update_elf'] = True
                return result
        except FileNotFoundError:
            print(f'elf file error for {elf_name}')
            result['update_elf'] = True
            return result

    def _check_elf_ok(self, index, line_data, data, elf_name):
        """Function that checks for issues with the elf file.

        Will return True if the elf file is out of date.
        Errors with the elf file are very rare but possible if the
        factordb has an issue.  I have seen a single case where the
        factordb had the wrong power of 3.

        Args:
            line_data: Data from the elf line
            data: Data from the localdb.

        Return:
            Returns True if line_data correct and up to date. False otherwise.
        """

        elf_complete = line_data['complete']
        is_complete = data['complete']
        seq = data['base']

        if is_complete and not elf_complete:
            self.status.update_elf(seq, True)
            print(f'Sequence {seq}, index {index} for {elf_name} '
                  '- elf needs update')
            return False

        if is_complete and elf_complete:
            if (line_data['num'] != data['num'] or
                line_data['aliquot_sum'] != data['aliquot_sum']):
                self.status.update_elf(seq, True)
                print(f'Sequence {seq}, index {index} data mismatch '
                      f'with {elf_name}')
                return False

            if index != data['index']:
                print(f'Sequence {seq}, index {index} has index mismatch')
                self.status.update_elf(seq, True)
                return False

            if index != line_data['index']:
                print(f'Sequence {seq}, index {index} has index mismatch '
                      f'with {elf_name}')
                self.status.update_elf(seq, True)
                return False
        return True

    def make_elg_file(self, seq, elf_name, elg_name):
        """Merge has occured and we are creating the elg file from the elf file.

        Args:
            seq: sequence being processed.
            elf_name: Name of the elf file.
            elg_name: Name of the elg file.
"""

        current = seq
        index = 0
        is_cycle = False
        value = {}
        try:
            with open(elf_name, encoding="ascii") as elf_file:
                with open(elg_name, 'w+', encoding="ascii") as elg_file:
                    for line in elf_file:
                        if current in value:
                            is_cycle = True
                        else:
                            value[current] = True
                        data = self.aliquot_data.select_data(current, True)
                        if not data:
                            data = self.aliquot_data.select_data(current, False)
                        if not data:
                            print(f'Sequence {seq}, index {index} missing db entry.')
                            self.status.update_localdb(seq, True)
                            return
                        base = data['base']
                        if base == seq:
                            if not is_cycle:
                                elg_file.write(line)
                            else:
                                self.elg_update_to_file(elg_file, base, data['index'])
                                self.status.update_elg(seq, False)
                                return
                        elif base < seq:
                            self.elg_update_to_file(elg_file, base, data['index'])
                            self.status.update_elg(seq, False)
                            return
                        else:
                            print(f'Sequence {seq}, index {index} needs update. Old '
                                  'sequence found.')
                            break
                        index += 1
                        current = data['aliquot_sum']
                    if current == 1:
                        self.elg_update_to_file(elg_file, 1, "0")
                    elif data['complete']:
                        if data['aliquot_sum'] in value:
                            # Cycle
                            data = self.aliquot_data.select_data(current, True)
                            base = data['base']
                            self.elg_update_to_file(elg_file,data['base'], data['index'])
                        else:
                            print(f'For {seq}, unexpected end of elf file')
                            self.status.update_elf(seq, True)
                            return
            self.update_merge(seq)
            self.status.update_elg(seq, False)
        except FileNotFoundError:
            print(f'elf file error for {elf_name}')
            self.status.update_elf(seq, True)

    def update_merge(self, seq):
        """ Update the merge table for a sequence

        Updates the merge information for the localdb merge table by comparing to
        the data already there, if any.

        If there is no previous data then our sequence is part of a smaller sequence
        so doesn't count as a merge.  In other words numbers that are part of an existing
        sequence are skipped over as they are already included by the existing squence.

        Args:
            seq: The sequence to check.
        """

        curr = seq
        index = 0
        done = False
        prev_data = {}
        while not done:
            data = self.aliquot_data.select_data(curr, True)
            if not data:
                # Likely open series
                return
            if data['base'] < seq or (data['base'] == seq and data['index'] < index):
                if 'index' in prev_data:
                    new_merge_data = {}
                    new_merge_data['merge_from_sequence'] = seq
                    new_merge_data['merge_from_index'] = prev_data['index']
                    new_merge_data['merge_to_sequence'] = data['base']
                    new_merge_data['merge_to_index'] = data['index']
                    new_merge_data['num_before_merge'] = prev_data['num']
                    new_merge_data['num_after_merge'] = data['num']
                    new_merge_data['processed'] = False
                    if self.statistics.add_merge_if_changed(new_merge_data):
                        print(f'Updated merge data for {seq}')
                else:
                    old_merge_data = self.statistics.get_merge(seq)
                    if old_merge_data:
                        print(f'Deleting unneeded merge for {seq}')
                        self.statistics.delete_merge(seq)


    def elg_update_to(self, seq, index, elg_name, base, base_index):
        """Update the to line in an elg file

        Args:
            seq: The sequence we are working with.
            index: The index for the To line.
            elg_name: The name of the elg_file.
            base: The sequence that is merged to.
            base_index: The index of the sequence that is merged to.
        """

        subd = seq // aliquot_util.INTERVAL
        bak_name = f'elf_{subd}/alq_{seq}.bak'
        if Path(bak_name).is_file():
            os.remove(bak_name)
        shutil.copy(elg_name, bak_name)
        try:
            with open(bak_name, encoding="ascii") as bak_file:
                with open(elg_name, 'w', encoding="ascii") as elg_file:
                    for line in bak_file:
                        if line[0] != 'T':
                            line_data = aliquot_util.parse_elf_line(line)
                            if line_data['index'] < index:
                                elg_file.write(line)
                            else:
                                break
                        else:
                            if line_data['index'] != index - 1:
                                print(f'Sequence {seq}:{index} issue with {elg_name} too short')
                                self.status.update_elf(seq, True)
                                return
                            break
                    self.elg_update_to_file(elg_file, base, base_index)
                    return

        except FileNotFoundError:
            print(f'elg file error for {elg_name}')
            self.status.update_elf(seq, True)

    def elg_update_to_file(self, elg_file, base, base_index):
        """Output to line to elg file."""

        to_line = f'To {base}:{base_index}\n'
        elg_file.write(to_line)
