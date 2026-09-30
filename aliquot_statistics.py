#!/usr/bin/env python

""" Stores statistics about aliquot series and their runs.

This class is called by the alq_runs.py file to create the statistics on run data.
alq_find_merges.py sets the merge data for all non open sequences.  Other modules call
this clas to to use the statistics data once it is created.

The data is stored in the postgres database.

Tables used:
    driver_run: Runs that reach the next drivwer.
    merge_run: Runs that merge into another sequence that are more than one step long.
    merge_single: Keeps the merge runs that merge after a single step. These are both common and
        uninteresting.  All primes not part of a smaller sequence for example.
    open_run: Runs for open sequences (so incomplete)
    no_driver_run: Run Table for the 'no driver' case until another driver is found.
    single_step: Stores counts of each step based on digits and driver.
    factor_count: Store counts of factors not involved in the driver.
    sequence_merge: Keeps track of sequence merge information unless part of a smaller sequence.
"""

import logging
from aliquot_data import AliquotData
from aliquot_data_runs import AliquotDataRuns
from aliquot_data_statistics import AliquotDataStatistics

logger = logging.getLogger(__name__)

# Haven't found a good way to split this up so the caller intuitively knows which class contains
# their function.  Could also make it a more pure interface class that doesn't do the work but
# calls other classes.
#
# pylint: disable=too-many-public-methods
class AliquotStatistics():
    """Handles access to the statistics tables in postgres.

    Routines to both set the statistics and also to fetch the statistics once generated.
    """
    def __init__(self, sql):
        """Initializes access to the postgres database.

        Args:
            sql: postgres sql connection.

        Attributes:
             aliquot_data_runs: Class to handle setting and getting the statistics for runs
             aliquot_data_statistics: Class to handle setting and getting the statistics tables.
             max_digits: An approximate maximum for digits
             max_driver_uild: An approximate maximum for drivers
        """
        self.aliquot_data = AliquotData(sql)
        self.aliquot_data_runs = AliquotDataRuns(sql)
        self.aliquot_data_statistics = AliquotDataStatistics(sql)
        self.max_digits = 200
        self.max_driver_uid = 40
        self.single_step = None
        self.factor_count = None
        #Comment in for sql.py change to add a table or index (has "if not exists")
        #self.aliquot_data.add_statistics_tables()

    def get_merge(self, seq):
        """Returns merge information for the sequence from the local db.

        This information on the merging of this seq into another lower sequence.
        """

        return self.aliquot_data_statistics.get_merge(seq)

    def has_merge(self, seq):
        """Looks for a merge for the sequence in the local db.

        Returns True if found, otherwise returns False.
        """
        return self.aliquot_data_statistics.has_merge(seq)

    def get_driver_run(self, seq, index):
        """Returns driver information for the sequence and index from the local db.

        This is one set of sequence values where the driver remains constant
        """

        return self.aliquot_data_runs.get_driver_run(seq, index)

    def has_driver_run(self, seq, index):
        """ Looks for a driver run for the sequence and index in the local db.

        Returns True if found, otherwise returns False.
        """

        return self.aliquot_data_runs.has_driver_run(seq, index)

    def get_open_run(self, seq):
        """Returns open information for the sequence from the local db.

        This is the final sequence values where the driver remains constant for an open sequence,
        """

        return self.aliquot_data_runs.get_open_run(seq)

    def has_open_run(self, seq):
        """Looks for an open run for the sequence in the local db.

        Returns True if found, otherwise returns False.
        """

        return self.aliquot_data_runs.has_open_run(seq)

    def get_merge_run(self, seq):
        """Returns merge run information for the sequence from the local db.

        This is the sequence values where the driver remains constant before it merges.
        """

        return self.aliquot_data_runs.get_merge_run(seq)

    def has_merge_run(self, seq):
        """Looks for a final merge run for sequence in the local db.

        Returns True if found, otherwise returns False.
        """

        return self.aliquot_data_runs.has_merge_run(seq)

    def get_no_driver_run(self, seq, index):
        """Returns info on run with no driver for the sequence and index from the local db."""

        return self.aliquot_data_runs.get_no_driver_run(seq, index)

    def has_no_driver_run(self, seq, index):
        """Looks for a driverless run for the sequence and index in the local db.

        Returns True if found, otherwise returns False.
        """
        return self.aliquot_data_runs.has_no_driver_run(seq, index)

    def merge_done_status(self, seq):
        """For a merging sequence, get the current run information for the sequence.

        Since this is called for each sequence, we want it fast if the sequence
        is already done.  We also have to check to make sure the sequence wasn't
        an open sequence previously.
        """
        merge_data = self.aliquot_data_statistics.get_merge(seq)
        done_data = {}

        if not merge_data:
            data = self.aliquot_data.select_data(seq, True)
            if data['base'] == seq:
                print(f'Merge Data is not up to date for {seq}.')
            else:
                done_data['done'] = True
                return done_data

        merge_run = self.aliquot_data_runs.get_merge_run(seq)

        if (merge_run and merge_data['processed'] and
            merge_data['merge_to_sequence'] == merge_run['merge_sequence']):
            done_data['done'] = True
            return done_data

        done_data['was_open'] = False
        done_data['done'] = False
        done_data['update_merge'] = False
        done_data['merge_run'] = merge_run
        done_data['merge_data'] = merge_data

        if not merge_run and self.aliquot_data_runs.has_open_run(seq):
            # Last run this was an open sequence so it needs to be converted
            # to a merge instead
            done_data['was_open'] = True
            done_data['open_run'] = self.aliquot_data_runs.get_open_run(seq)

        if  merge_run and merge_data['merge_to_sequece'] != merge_run['end_sequence']:
            # Last run the merge sequence was different. This means a smaller
            # sequence merged into this sequence.  This can involve a larger
            # update to existing runs.
            done_data['update_merge'] = True
        done_data['no_driver_run'] = self.get_curr_no_driver_run(merge_run)
        return done_data

    def get_curr_no_driver_run(self, curr_run):
        """ Find a no driver run that ends at the same place """

        if curr_run:
            index = curr_run['end_index']
            seq = curr_run['sequence_number']
            no_driver_runs = self.aliquot_data_runs.get_all_no_driver_runs(seq)
            for run in no_driver_runs:
                if run['end_index'] == index:
                    return run
        return None

    def open_done_status(self, seq):
        """Return information on any open run data for the sequence.

        For an open sequence return any existing open run for that sequence.
        If no open run exists it means the sequence was not yet processed.
        """

        last_data = {}
        open_run = self.aliquot_data_runs.get_open_run(seq)
        if open_run:
            last_data['has_open'] = True
            last_data['open_run'] = open_run
        else:
            last_data['has_open'] = False
        last_data['no_driver_run'] = self.get_curr_no_driver_run(open_run)
        return last_data


    def save_merge(self, seq, merge_data):
        """ Save the merge information for the sequence

        There is a merge for any non-open sequence.
        """
        if self.aliquot_data_statistics.has_merge(seq):
            self.aliquot_data_statistics.update_merge(merge_data)
        else:
            self.aliquot_data_statistics.insert_merge(merge_data)

    def save_open_run(self, seq, open_run):
        """ Save the open run information for the sequence

        The incomplete entry is not included in the open run.
        There is only a single final run for each open sequence.
        """
        if self.aliquot_data_runs.has_open_run(seq):
            self.aliquot_data_runs.update_open_run(open_run)
        else:
            self.aliquot_data_runs.insert_open_run(open_run)

    def save_no_driver_run(self, seq, no_driver_run):
        """ Save the no driver run information for the sequence"""

        index = no_driver_run['start_index']
        if self.aliquot_data_runs.has_no_driver_run(seq, index):
            self.aliquot_data_runs.update_no_driver_run(no_driver_run)
        else:
            self.aliquot_data_runs.insert_no_driver_run(no_driver_run)


    def save_merge_run(self, seq, merge_run):
        """ Save the open run information for the sequence

        Update would be called by the '_update_for_new_merge' in alq_runs.
        """
        if merge_run['start_index'] == merge_run['end_index']:
            if self.aliquot_data_runs.has_merge_run(seq):
                self.aliquot_data_runs.update_merge_run(merge_run, True)
            else:
                self.aliquot_data_runs.insert_merge_run(merge_run, True)
        else:
            if self.aliquot_data_runs.has_merge_run(seq):
                self.aliquot_data_runs.update_merge_run(merge_run, False)
            else:
                self.aliquot_data_runs.insert_merge_run(merge_run, False)

    @staticmethod
    def init_run(seq, driver_uid):
        """Start a run with the given driver_uid for the sequence."""

        new_run = {}
        new_run['sequence_number'] = seq
        new_run['start_index'] = 0
        new_run['start_digits'] = len(str(seq))
        new_run['start_num'] = seq
        new_run['end_index'] = 0
        new_run['end_digits'] = new_run['start_digits']
        new_run['end_num'] = seq
        new_run['driver_uid'] = driver_uid
        return new_run

    @staticmethod
    def extend_run(data, curr_run):
        """Add current data to open run if the driver matches."""

        if data['driver_uid'] == curr_run['driver_uid']:
            curr_run['end_index'] = data['index']
            curr_run['end_digits'] = len(str(data['num']))
            curr_run['end_num'] = data['num']
            return True
        return False

    @staticmethod
    def extend_no_driver_run(data, curr_run):
        """Add current data to open run if the driver matches."""

        curr_run['end_index'] = data['index']
        curr_run['end_digits'] = len(str(data['num']))
        curr_run['end_num'] = data['num']

    def end_run(self, data, curr_run):
        """ Save previous driver and start a new run.

        When the power of 2 changes, the driver has changed.  In this case,
        the old driver run information is saved to the database and a new run
        is started with the new driver
        """

        new_run = {}
        new_run['sequence_number'] = data['base']
        new_run['start_index'] = data['index']
        new_run['start_digits'] = len(str(data['num']))
        new_run['start_num'] = data['num']
        new_run['end_index'] = new_run['start_index']
        new_run['end_digits'] = new_run['start_digits']
        new_run['end_num'] = data['num']
        new_run['driver_uid'] = data['driver_uid']

        driver_run = {}
        driver_run['sequence_number'] = data['base']
        driver_run['start_index'] = curr_run['start_index']
        driver_run['start_digits'] = curr_run['start_digits']
        driver_run['start_num'] = curr_run['start_num']
        driver_run['driver_uid'] = curr_run['driver_uid']
        driver_run['end_index'] = curr_run['end_index']
        driver_run['end_digits'] = curr_run['end_digits']
        driver_run['end_num'] = curr_run['end_num']
        end_data = self.aliquot_data.select_data(curr_run['end_num'], True)
        if not end_data:
            print(f'Broken Sequence for {data} Run verify')
        driver_run['end_factors'] = end_data['factor_string']
        driver_run['next_driver'] = data['driver_uid']
        self.add_driver_run(driver_run)
        return new_run

    #Was open but now it merges.
    def switch_to_merge(self, seq, done_data):
        """ Switch from open run to merge run and delete the open run in the database.

        A sequence that was open last run is now a merging one.  We need to switch
        it to a merge run and continue until the merge occurs.
        """
        open_run = done_data['open_run']
        merge_run = {}
        merge_run['sequence_number'] = open_run['sequence_number']
        merge_run['start_index'] = open_run['start_index']
        merge_run['start_digits'] = open_run['start_digits']
        merge_run['start_num'] = open_run['start_num']
        merge_run['end_index'] = open_run['end_index']
        merge_run['end_digits'] = open_run['end_digits']
        merge_run['end_num'] = open_run['end_num']
        merge_run['driver_uid'] = open_run['driver_uid']
        self.aliquot_data_runs.delete_open_run(seq)
        return merge_run

    def add_merge(self, merge_data):
        """Save merge to the local db"""

        seq = merge_data['merge_from_sequence']
        if not self.aliquot_data_statistics.has_merge(seq):
            self.aliquot_data_statistics.insert_merge(merge_data)
        else:
            self.aliquot_data_statistics.update_merge(merge_data)

    def add_merge_if_changed(self, merge_data):
        """Save merge to the local db"""

        seq = merge_data['merge_from_sequence']
        old_merge_data = self.aliquot_data_statistics.get_merge(seq)
        if (not old_merge_data or
            old_merge_data['merge_from_index'] != merge_data['merge_from_index'] or
            old_merge_data['merge_to_sequence'] != merge_data['merge_to_sequence'] or
            old_merge_data['merge_to_index'] != merge_data['merge_to_index']):
            self.add_merge(merge_data)
            return True
        return False

    def fix_merge_if_needed(self, seq):
        """Check merge data matches localdb data and fix if needed.

        Args:
            seq: The sequence to check.
        """

        curr_merge_data = self.aliquot_data_statistics.get_merge(seq)
        if curr_merge_data:
            print(curr_merge_data)
            num_before = int(curr_merge_data['num_before_merge'])
            num_after = int(curr_merge_data['num_after_merge'])
            data_before = self.aliquot_data.select_data(num_before, True)
            data_after = self.aliquot_data.select_data(num_after, True)
            if data_before and data_after:
                if data_before['base'] == seq:
                    if data_after['base'] == curr_merge_data['merge_to_sequence']:
                        # No change
                        return
                    if data_after['base'] != seq:
                        # Updated endpoint for merge
                        curr_merge_data['merge_to_sequence'] = data_after['base']
                        curr_merge_data['merge_to_index'] = data_after['index']
                        self.add_merge(curr_merge_data)
                        return
        #For all the other cases the location of the merge is changed or is now gone.
        self.renew_merge_from_local_data(seq)

    def renew_merge_from_local_data(self, seq):
        """Find the merge from local data

        This is slower than finding from the elg where we can juump to the last line

        Args:
            seq: The sequence to check.
        """

        values = {}
        curr = seq
        done = False
        prev_data = {}
        while not done:
            data = self.aliquot_data.select_data(curr, True)
            if data:
                if curr in values or curr == 1:
                    # self merge
                    if 'num' in prev_data:
                        merge_data = {}
                        merge_data['merge_from_sequence'] = seq
                        merge_data['merge_from_index'] = prev_data['index']
                        merge_data['num_before_merge'] = prev_data['num']
                        merge_data['merge_to_sequence'] = data['base']
                        merge_data['merge_to_index'] = data['index']
                        merge_data['num_after_merge'] = curr
                        merge_data['processed'] = False
                        self.add_merge(merge_data)
                    done = True
                    continue
                next_base = data['base']
                values[curr] = True
                if next_base == seq:
                    prev_data = data
                    curr = data['aliquot_sum']
                elif next_base > seq:
                    # Error needs fixing before going further
                    print(f'For {seq} we found a larger base. Sequence should be verified')
                    done = True
                    continue
                else:
                    if 'num' in prev_data:
                        merge_data = {}
                        merge_data['merge_from_sequence'] = seq
                        merge_data['merge_from_index'] = prev_data['index']
                        merge_data['num_before_merge'] = prev_data['num']
                        merge_data['merge_to_sequence'] = next_base
                        merge_data['merge_to_index'] = data['index']
                        merge_data['num_after_merge'] = curr
                        merge_data['processed'] = False
                        self.add_merge(merge_data)
                    done = True
                    curr = data['aliquot_sum']
            else:
                print(f'For {seq} missing data. Sequence should be verified')
                done = True
                continue

    def delete_merge(self, seq):
        """Delete merge from the local db"""

        if self.aliquot_data_statistics.has_merge(seq):
            self.aliquot_data_statistics.delete_merge(seq)

    def add_driver_run(self, driver_run):
        """Save the driver run to the local db."""

        seq = driver_run['sequence_number']
        index = driver_run['start_index']
        if self.aliquot_data_runs.has_driver_run(seq, index):
            print(f'For {seq}:{index} driver run already existed')
            self.aliquot_data_runs.update_driver_run(driver_run)
        else:
            self.aliquot_data_runs.insert_driver_run(driver_run)

    def init_single(self):
        """ Initialize a pair of multi-level maps 

        This is so we don't call the db each time. That turned out to slow the progam 6x.
        """
        self.single_step = {}
        self.factor_count = {}
        for digits in range(1, self.max_digits + 1):
            self.single_step[digits] = {}
            self.factor_count[digits] = {}
            for driver_uid in range(0, self.max_driver_uid + 1):
                self.single_step[digits][driver_uid] = {}
                self.factor_count[digits][driver_uid] = {}

    def save_single(self):
        """Save the single step and factor count data when done"""
        self._save_single_step()
        self._save_factor_count()

    def _save_single_step(self):
        """For single step add to or insert every value into the db."""

        for digits in self.single_step:
            for driver_uid in self.single_step[digits]:
                for next_driver in self.single_step[digits][driver_uid]:
                    curr_step = self.single_step[digits][driver_uid][next_driver]
                    db_step = self.aliquot_data_statistics.get_single_step(digits, driver_uid,
                                                                           next_driver)
                    if db_step:
                        db_step['max_ratio'] = max(db_step['max_ratio'], curr_step['max_ratio'])
                        db_step['min_ratio'] = min(db_step['min_ratio'], curr_step['min_ratio'])
                        db_step['ratio_sum'] += curr_step['ratio_sum']
                        db_step['count'] += curr_step['count']
                        self.aliquot_data_statistics.update_single_step(db_step)
                    else:
                        db_step = {}
                        db_step['digits'] = digits
                        db_step['driver_uid'] = driver_uid
                        db_step['next_driver'] = next_driver
                        for entry in curr_step:
                            db_step[entry] = curr_step[entry]
                        self.aliquot_data_statistics.insert_single_step(db_step)

    def _save_factor_count(self):
        """For factor count insert add the counts into the db."""

        for digits in self.factor_count:
            for driver_uid in self.factor_count[digits]:
                for num_factors in self.factor_count[digits][driver_uid]:
                    curr_factor = self.factor_count[digits][driver_uid][num_factors]
                    db_factor = self.aliquot_data_statistics.get_factor_count(digits, driver_uid,
                                                                              num_factors)
                    if db_factor:
                        db_factor['count'] += curr_factor['count']
                        self.aliquot_data_statistics.update_factor_count(db_factor)
                    else:
                        db_factor = {}
                        db_factor['digits'] = digits
                        db_factor['driver_uid'] = driver_uid
                        db_factor['num_factors'] = num_factors
                        db_factor['count'] = curr_factor['count']
                        self.aliquot_data_statistics.insert_factor_count(db_factor)


    def update_single(self, common, single_step, factor_count):
        """ Handles update of data for a single step of the aliquot series.

        This information is put into a pair of multi-level maps for single_step
        and a count of factors not involved in the driver/guide.

        Args:
            common: holds the digits and driver_uid used by both mappings.
            single_step: holds data for the single step mapping.
            factor_count: hods data for the factor count mapping.
        """
        digits = int(common['digits'])
        driver_uid = int(common['driver_uid'])
        if digits <= self.max_digits and driver_uid <= self.max_driver_uid:
            # Created at initialization
            single_step_driver = self.single_step[digits][driver_uid]
            factor_count_driver = self.factor_count[digits][driver_uid]
        else:
            self._create_base_mapping(digits, driver_uid)
            single_step_driver = self.single_step[digits][driver_uid]
            factor_count_driver = self.factor_count[digits][driver_uid]

        self._update_single_step(single_step_driver, single_step)
        self._update_factor_count(factor_count_driver, factor_count)

    def _update_single_step(self, single_step_driver, single_step):
        """ Updates the single step map with a new step.

        The digits and driver_uid are already part of single_step_driver. This function
        adds a map for the next_driver and sets the ratio and count.  This data will be
        added to the single step table when we save.
        """
        next_driver = single_step['next_driver']
        ratio = single_step['ratio']
        if not next_driver in single_step_driver:
            single_step_driver[next_driver] = {}
            single_step_driver[next_driver]['max_ratio'] = ratio
            single_step_driver[next_driver]['min_ratio'] = ratio
            single_step_driver[next_driver]['ratio_sum'] = ratio
            single_step_driver[next_driver]['count'] = 1
        else:
            if ratio > single_step_driver[next_driver]['max_ratio']:
                single_step_driver[next_driver]['max_ratio'] = ratio
            if ratio < single_step_driver[next_driver]['min_ratio']:
                single_step_driver[next_driver]['min_ratio'] = ratio
            single_step_driver[next_driver]['ratio_sum'] += ratio
            single_step_driver[next_driver]['count'] += 1

    def _update_factor_count(self, factor_count_driver, factor_count):
        """Add to the number of factors based on driver and digits.

        If the combo of digits, driver, and factor_count is new we create it.
        Otherwise the count is increased by one.
        """

        num_factors = factor_count['num_factors']
        if not num_factors in factor_count_driver:
            factor_count_driver[num_factors] = {}
            factor_count_driver[num_factors]['count']  = 1
        else:
            factor_count_driver[num_factors]['count']  += 1

    def _create_base_mapping(self, digits, driver_uid):
        """ Create mapping for values not done at startup.
            
        This function is for values over self.max_digits or self.max_driver_uid
        """
        if not digits in self.single_step:
            self.single_step[digits] = {}
        if not digits in self.factor_count:
            self.factor_count[digits] = {}
        if not driver_uid  in self.single_step[digits]:
            self.single_step[digits][driver_uid] = {}
        if not driver_uid  in self.factor_count[digits]:
            self.factor_count[digits][driver_uid] = {}

    def get_all_runs_for_seq(self, seq):
        """Gets all driver runs for a given sequence.

        Sequences have different driver runs for each change of driver.    Note that these can
        change when a merge occurs. The run can now be under the new sequence.
        """
        return self.aliquot_data_runs.get_all_driver_runs(seq)

    def delete_driver_run(self, seq, index):
        """Delete an existing driver run usually due to a new merge."""
        self.aliquot_data_runs.delete_driver_run(seq, index)

    def handle_merge(self, old_data, new_data, prev_data):
        """This function is called when merge data needs to be changed due to a new merge.

        Ownership of steps of a series is based on the smallest number that can reach that number.
        Because of this ownership will change if another lower number is found.  This larger series
        merges into the smaller one, and the merge table keeps track of this.
        This function is tricky when a new lower sequence is found as it can change merge data of
        series that merge into the old sequence - in this case the number where it merges is the
        same but the sequence merged into and the index can be different.
        """
        changes = {}
        changes['updates'] = []
        changes['verify'] = []
        if old_data['num'] != new_data['num']:
            print('old vs new data mismatch for merge')
        old_seq = old_data['base']
        new_seq = new_data['base']
        changes['verify'].append(old_seq)
        changes['verify'].append(new_seq)
        if  old_seq < new_seq:
            changes['updates'].append(new_seq)
            print(f'Adding new {new_seq} as a change.')
            if not prev_data or prev_data['index'] + 1 != new_data['index']:
                print('Possible mismatch of data')
                print(prev_data)
                print(new_data)
            else:
                merge_data = {
                    'merge_from_sequence': new_seq,
                    'merge_from_index': prev_data['index'],
                    'num_before_merge': prev_data['num'],
                    'merge_to_sequence': old_seq,
                    'merge_to_index': old_data['index'],
                    'num_after_merge': old_data['num'],
                    'processed': False }
                if self.aliquot_data_statistics.has_merge(new_seq):
                    self.aliquot_data_statistics.update_merge(merge_data)
                else:
                    self.aliquot_data_statistics.insert_merge(merge_data)
        else:
            changes['updates'].append(old_seq)
            #print('-----------------------------------------------------')
            #print('Stopping to test code.')
            #print('-----------------------------------------------------')
            #sys.exit(0)
            print(f'Adding old {old_seq} as a change.')
            if not prev_data:
                if old_data['index'] == 0:
                    if self.aliquot_data_statistics.has_merge(old_seq):
                        self.aliquot_data_statistics.delete_merge(old_seq)
                all_merges = self.aliquot_data_statistics.get_all_merging_into(old_seq)
                print(f'All Merges: {all_merges}')
                for merge in all_merges:
                    changes['verify'].append(merge['merge_from_sequence'])
                    changes['updates'].append(merge['merge_from_sequence'])
                return changes
            if prev_data['index'] + 1 != old_data['index']:
                print('Possible mismatch of data')
                print(prev_data)
                print(old_data)
            merge_data = {
                'merge_from_sequence': old_seq,
                'merge_from_index': prev_data['index'],
                'num_before_merge': prev_data['num'],
                'merge_to_sequence': new_seq,
                'merge_to_index': new_data['index'],
                'num_after_merge': new_data['num'],
                'processed': False }
            self.add_merge(merge_data)
            all_merges = self.aliquot_data_statistics.get_all_merging_into(old_seq)
            print(f'All Merges: {all_merges}')
            for merge in all_merges:
                changes['verify'].append(merge['merge_from_sequence'])
                self._check_merge_into(new_data, old_data, merge, changes)
        return changes

    def _check_merge_into(self, new_data, old_data, merge, changes):
        """Helper class to check if a sequence needs update.

        The merge variable contains information about a sequence that merges into old data.
        We want to know if that sequence merge needs to be updated based on a change to the new
        data.
        """
        new_seq = new_data['base']
        curr_seq = merge['merge_from_sequence']
        curr_index = merge['merge_to_index']
        print(f'Indices {curr_index} vs {old_data["index"]}')
        if  curr_index > old_data['index']:
            # How much later the current merge occured.
            amount_after =  curr_index - old_data['index']
            changes['updates'].append(curr_seq)
            print('Merging {curr_seq} was added as a change.')
            merge_data = {}
            merge_data['merge_from_sequence'] = curr_seq
            merge_data['merge_from_index'] = merge['merge_from_index']
            merge_data['num_before_merge'] = merge['num_before_merge']
            merge_data['merge_to_sequence'] = new_seq
            # Calculate what the merge_to_index will be.
            merge_data['merge_to_index'] = new_data['index'] + amount_after
            merge_data['num_after_merge'] = merge['num_after_merge']
            merge_data['processed'] = False
            print('Merge, New Data, Old data, and merge data, '
                  f'amount_after = {amount_after}:')
            print(merge)
            print(old_data)
            print(new_data)
            print(merge_data)
            self.add_merge(merge_data)

    def split_run_for_merge(self, merge_run, merge_data):
        """ The old merge run is updated given the merge data.

        This is called when the merge_run doesn't properly end based on the merge_data.  This occurs
        because new merges can occur requiring an update to existing data. merge_run can also be a
        driver_run that needs convertion to the merge.
        """
        new_merge_run = {}
        seq = merge_run['sequence_number']
        new_merge_run['sequence_number'] = seq
        new_merge_run['start_index'] = merge_run['start_index']
        new_merge_run['start_digits'] = merge_run['start_digits']
        new_merge_run['start_num'] =  merge_run['start_num']
        new_merge_run['driver_uid'] = merge_run['driver_uid']
        new_merge_run['end_index'] = merge_data['merge_from_index']
        new_merge_run['end_digits'] = len(str(merge_data['num_before_merge']))
        new_merge_run['end_num'] = merge_data['num_before_merge']
        new_merge_run['merge_sequence'] = merge_data['merge_to_sequence']
        new_merge_run['merge_index'] = merge_data['merge_to_index']
        self.save_merge_run(seq, new_merge_run)

    @staticmethod
    def start_no_driver_run(seq, data, prev_data):
        """Start a run with the given data for the sequence.

        If this is the first element there is no previous driver so just
        use the driver_uid it starts on.  In other words if the prev driver is
        not a driver then there wasn't one to refer to.
        """

        new_run = {}
        new_run['sequence_number'] = seq
        new_run['start_index'] = data['index']
        new_run['start_digits'] = len(str(data['num']))
        new_run['start_num'] = data['num']
        if prev_data:
            new_run['prev_driver'] = prev_data['driver_uid']
        else:
            new_run['prev_driver'] = data['driver_uid']
        new_run['end_index'] = new_run['start_index']
        new_run['end_digits'] = new_run['start_digits']
        new_run['end_num'] = new_run['start_num']
        return new_run

    def end_no_driver_run(self, data, no_driver_run):
        """Ends the no-driver run

        data is used to set the next driver.
        """
        seq = no_driver_run['sequence_number']

        no_driver_run['next_driver'] = data['driver_uid']

        if self.aliquot_data_runs.has_no_driver_run(seq, no_driver_run['start_index']):
            self.aliquot_data_runs.update_no_driver_run(no_driver_run)
        else:
            self.aliquot_data_runs.insert_no_driver_run(no_driver_run)

    def mark_processed(self, seq):
        """Indicate that the merge has been completed.

        For this sequence we have processed all the runs  in it.
        Since it merges it won't get extended like open sequences.
        """
        merge_data = self.aliquot_data_statistics.get_merge(seq)
        if not merge_data:
            print(f'Missing merge data for {seq}')
        merge_data['processed'] = True
        self.aliquot_data_statistics.update_merge(merge_data)
