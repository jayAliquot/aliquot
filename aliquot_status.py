#!/usr/bin/env python

""" Access for the aliquot seqence data

The sequences are stored in postgres.  This class uses sql.py which has lower level SQL
functionality and the initial table creation.

The flags for verification, stats, and factordb are used.  The first two get set when verify or
stats is run and cleared if any change is made.  Factordb is a bit more complex with multiple
states. For elg, elf, factor, and localdb the code was changed to immediately fix up the sequence
to make it correct.  As such they are not really used for much other than to also set verified
to false (since a change was made it needs verification again).  The extend flag could be used,
but instead a shell script does the extension, so we only set this flag to false.

For factordb the possible states are:
NA: Series doesn't reach 25 digits before merging so is not stored remotely.  Note that the remote
    site generates series to 50 digits when asked, but will only do so if asked.
unchecked or unchecked_update:  Remote site does not know anything about this series yet.
fast_check or fast_check_update: alq_pre_compare_factordb was run to send the known
    factorization for the series.  The remote site has most of the information for the series but
    might have missed a term or two and the series itself may not yet exist.
needs_update:  The remote site already knows this sequence, but new factorization was done so it
    is missing the latest terms and the remote site needs updating done with alq_fdb_check.
up_to_date: Remote site knows all the terms.
"""

import logging
from aliquot_data import AliquotData

logger = logging.getLogger(__name__)

class AliquotStatus:
    """Class to handle status updates using postgres"""
    def __init__(self, sql):
        """Initializes subclasses used.

        Args:
            sql: postgres sql connection.
        
        Attributes:
            aliquot_data: Class to get and set local db data.
        """

        self.aliquot_data = AliquotData(sql)

    #update functions
    def update_elg(self, seq, elg):
        """Update elg status flag

        Will also set verified to false.
        
        Args:
            seq: The sequence to update status for.
            elg: Boolean value on what to set elg flag to.
        """

        if elg:
            self._update_status(seq, elg_update=elg, verified=False)
        else:
            self._update_status(seq, elg_update=elg)

    def update_elf(self, seq, elf):
        """Update elf status flag

        Will also set verified to false.
        
        Args:
            seq: The sequence to update status for.
            elf: Boolean value on what to set elf flag to.
        """

        if elf:
            self._update_status(seq, elf_update=elf, verified=False)
        else:
            self._update_status(seq, elf_update=elf)

    def update_extend(self, seq, ext):
        """Update extend status flag

        series has extension meaning data downloaded from remote site.
        Will also set verified to false.
        
        Args:
            seq: The sequence to update status for.
            extend: Boolean value on what to set extend flag to.
        """

        if ext:
            self._update_status(seq, extend_update=ext, verified=False)
        else:
            self._update_status(seq, extend_update=ext)

    def update_localdb(self, seq, localdb):
        """Update localdb status flag

        Will also set verified to false.
        
        Args:
            seq: The sequence to update status for.
            localdb: Boolean value on what to set localdb flag to.
        """

        if localdb:
            self._update_status(seq, localdb_update=localdb, verified=False)
        else:
            self._update_status(seq, localdb_update=localdb)

    def update_verify(self, seq, verified):
        """Mark as needing verification or is verified.

        Args:
            seq: The sequence to update status for.
            verified: Boolean value on what to set verified to.
        """

        self._update_status(seq, verified = verified)

    def update_stats(self, seq, stats):
        """Update stats status flag

        The stats aren't part of the sequence but statistics about the sequence.  set_stats
        creates the stats and alq_stats gathers the statistics together.

        Args:
            seq: The sequence to update status for.
            stats: Boolean value on what to set stats to.
        """

        self._update_status(seq, stats_update=stats)

    def update_factor(self, seq, factor):
        """Update factor status flag

        Will also set verified to false.
        
        Args:
            seq: The sequence to update status for.
            factor: Boolean value on what to set factor flag to.
        """

        if factor:
            self._update_status(seq, factor_update=factor, verified=False)
        else:
            self._update_status(seq, factor_update=factor)

    def update_to_merged(self, seq):
        """When a sequence merges its open_ended flag is set to False.

        Args:
            seq: The sequence that has merged.
        """

        self._update_status(seq, open_ended = False)

    def factordb_up_to_date(self, seq):
        """Returns True if the remote site is up to date.

        'up_to_date' or 'NA' mean no update is needed.

        Args:
            seq: The sequence to check.
        Returns:
            True if no remote update is needed, false otherwise.
        """

        data = self.get_status(seq)
        if data:
            return data['factordb'] in ('up_to_date', 'NA')
        return False


    def set_factordb(self, seq, value):
        """Set factordb flag to a given value.

        Args:
            seq: The sequence to update status for.
            value: One of the valid enum strings listed at top.
        """

        print(f'For {seq}, factordb status is {value}')
        self._update_status(seq, factordb=value)

    def factordb_update(self, seq, update_needed):
        """Set the flag to indicate a change was made so an update is needed.

        It is important to maintain whether it was unchencked, fast_checked, or previously
        up to date which is why 'fast_check_update' and 'unchecked_update' exist, though they are
        not fully differentiated (no way to go from unchecked_update->unchecked or
        fast_check_update->fast_check)

        Args:
            seq: The sequence to update
            update_needed: True if an update was done that affects the factordb.
        """

        if update_needed:
            print(f'factordb check update set for {seq}')
        data = self.get_status(seq)
        if data:
            has_change = False
            fdb_status = 'unchecked'
            if data['factordb'] == 'fast_check' and update_needed:
                fdb_status = 'fast_check_update'
                has_change = True
            elif data['factordb'] == 'fast_check_update' and not update_needed:
                fdb_status = 'fast_check'
                has_change = True
            elif data['factordb'] == 'up_to_date' and update_needed:
                fdb_status = 'update_needed'
                has_change = True
            elif data['factordb'] == 'update_needed' and not update_needed:
                fdb_status = 'up_to_date'
                has_change = True
            elif data['factordb'] == 'unchecked' and update_needed:
                fdb_status = 'unchecked_update'
                has_change = True
            elif data['factordb'] == 'unchecked_update' and not update_needed:
                fdb_status = 'unchecked'
                has_change = True
            if has_change:
                self._update_status(seq, factordb = fdb_status)

    def factordb_fast_check(self, seq):
        """Sets factordb status to fast check if unchecked or fast_check_update.

        This means 'up_to_data' and 'needs_update' don't change.  It is used for the
        initial alq_pre_compare_factordb.py run that sends the factors first.

        Args:
            seq: The sequence to set fast check for.
        """

        data = self.get_status(seq)
        if data:
            fdb = data['factordb']
            # Don't change full check to fast check.
            if  fdb in ('unchecked', 'unchecked_update', 'fast_check_update'):
                fdb_status = 'fast_check'
                self._update_status(seq, factordb = fdb_status)

    def factordb_full_check(self, seq):
        """Sets factordb status to 'up to date'.

        Args:
            seq: The up to date sequence.
        """

        fdb_status = 'up_to_date'
        self._update_status(seq, factordb = fdb_status)

    def set_defaults(self, seq, complete, factordb_checked, has_stats=False):
        """Sets default values for status.

        This is already done for current sequences and is only needed for new ones.
        """

        data = {}
        data['sequence_number'] = seq
        data['open_ended'] = complete
        data['factordb'] = factordb_checked
        data['verified'] = False
        data['elg_update'] = False
        data['elf_update'] = False
        data['extend_update'] = False
        data['localdb_update'] = False
        data['factor_update'] = False
        data['stats_update'] = not has_stats
        self.aliquot_data.set_status_data(data)

    def _update_status(self, seq, **kwargs):
        """Access the local db to set the status.

        Called by public methods above change postgres status table.
        
        Args:
           seq: The sequence to update.
           kwargs: List of changes to make.
        """

        data = self.get_status(seq)
        if not data:
            #print('No status for {seq}. Set to defaults first')
            return
        change_found = False
        for key, value in kwargs.items():
            if data[key] != value:
                data[key] = value
                change_found = True
        if change_found:
            self.aliquot_data.set_status_data(data)

    def get_status(self, seq):
        """Get the status of a sequence.

        Args:
            seq: Sthe sequence to get

        Returns:
            A mapping holding the status information if it exists, otherwise None.
        """

        return self.aliquot_data.get_status_data(seq)
