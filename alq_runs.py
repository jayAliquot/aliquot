#!/usr/bin/env python

"""Computes runs under a specific driver/power of 2 for statistics.

Walks the sequences between a maximum and minimum and for each sequence it steps through and
finds the runs based on the driver.  These runs are stored in the postgres database for later
analysis.

Example Usage:
    python3 alq_runs.py 0 1000000

Note that as sequence changes, the results can get less accurate due to sequence merging.

To get fully accurate results.
1 - use alq_statistics_reset.py to clear all runs data.
2 - stop any program that changes the data.
3 - if new sequences, then alq_find_merges.py and alq_init_status.py may be needed.
4 - At this point it may be worth making a dated copy to work with so updates can continue
5 - run alq_verify.py with -f to make sure all merge data is correct (slow)
6 - Run set_stats.py/alq_stats.py and alq_unbounded.py for the current stats and open sequences. 
7 - run alq_runs.py to recreate the runs data (also slow)
"""

import argparse
import sys
import signal
import logging
from sql import SQL
from aliquot_data import AliquotData
from aliquot_statistics import AliquotStatistics
import aliquot_util

logger = logging.getLogger(__name__)

class AliquotRuns():
    """Adds driver runs to the database for a range of aliquot sequences.

    For the sequences between the maximum and minumum, we step through the sequence to divide them
    into separate runs based on the current driver.  Drivers are a concept for aliquot series due to
    persistence of the power of 2 and odd numbers associated with driver.  Some powers of two are
    not drivers per se, so there is also the "No Driver" driver + power of 2 which may have very
    short runs.  The information for the runs is handled by the aliquot_statistics class which adds
    them to the database.

    Sequences can either merge into another smaller sequences or be open which means it is unknown
    if they eventually merge or not.   The merging and open series are handled seperately by the
    data base which means they are also separated here.  Note that open series may extend farther
    each time we run, while  merge series will be complete and only change if another merge from a
    smaller series occurs in the future.
    """
    def __init__(self, sql):
        """ Initializes main modules used by the class

        Variables:
           aliquot_data: Gets the sequence series from the data base.
           statistics: Called to set the run data from the series.
        """
        self.aliquot_data = AliquotData(sql)
        self.statistics = AliquotStatistics(sql)
        self._init_open_seq()
        self.finished = False
        signal.signal(signal.SIGINT, self.finish_up)

    def finish_up(self, _a, _b):
        """Catching keyboard interupt as completing the number is important."""

        print('Finishing up...')
        self.finished = True

    def _init_open_seq(self):
        """ Initializes the list of open sequences to determine open vs merged sequences. """
        self.sequences = {}
        data = self.aliquot_data.get_incomplete()
        for pair in data:
            seq = pair[0]
            self.sequences[seq] = pair[1]

    def is_open(self, seq):
        """ Returns True if we find seq in the list of open sequences, otherwise it returns False"""
        if seq in self.sequences:
            return True
        return False

    @staticmethod
    def mod_error():
        """Not a module warning"""

        print('This program is designed to be run seperately.')
        print('Refactor to enable module calls')

    def calc_statistics(self):
        """ Main public function to calculate the runs

        Args:
           min: The minumum sequence to add statistics for. 0 and 1 both start at 1.
           max: The maximum sequence to add statistics for.  This value cannot be above the
             maximum of the sequences processed so far. This is currently 20 million.
        """
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('min', type=int, help='Minimum value of the range')
        parser.add_argument('max', type=int, help='Maximum value of the range')
        argv = parser.parse_args()
        max_seq = argv.max
        min_seq = argv.min
        min_seq = max(min_seq, 2)
        self._init_step_data()
        for seq in range(min_seq, max_seq+1):
            if seq % 1000 == 0:
                print(seq, file=sys.stderr)
            if self.is_open(seq):
                last_data = self.statistics.open_done_status(seq)
                self._update_open(seq, last_data)
            else:
                done_data = self.statistics.merge_done_status(seq)
                if not done_data['done']:
                    self._update_merge(seq, done_data)
            if self.finished:
                print(f'Ending at {seq}')
                break
        self._save_step_data()

    def _update_open(self, seq, last_data):
        """ Add data to an open sequence.

        Args:
           seq: The current open sequence to add run data to.
           last_data: Information on any previous run data to start with.
        """

        in_data = {}
        in_data['merge_data'] = None
        in_data['in_no_driver_run'] = last_data['no_driver_run']
        in_data['in_run'] = None
        in_data['has_run'] = last_data['has_open']
        if last_data['has_open']:
            in_data['in_run'] = last_data['open_run']
        self._proc_series(seq, in_data, False)

    def _update_merge(self, seq, done_data):
        """ Will usually process a merge that is not yet complete.

        This will usually be a new sequence not yet done, or an open sequence that has now merged.
        More rarely it may be a merge already processed but has changed.

        Args:
           seq: The current open sequence to add run data to.
           done_data: Information on any previous run data for this sequence.
        """

        in_data = {}
        in_data['merge_data'] = done_data['merge_data']
        in_data['in_no_driver_run'] = done_data['no_driver_run']
        in_data['in_run'] = None
        in_data['has_run'] = False
        if not in_data['merge_data'] or not self._is_merge_correct(in_data['merge_data']):
            print(f'Merge data for {seq} is not up to date. Exiting...')
            self.finished = True
            return
        if done_data['was_open']:
            in_data['in_run'] = self.statistics.switch_to_merge(seq, done_data)
            in_data['has_run'] = True
        elif done_data['update_merge']:
            merge_run = self._update_for_new_merge(seq, done_data)
            if not merge_run:
                # The update removed the need to do the merge run
                # for this sequence so we can return.
                return
            in_data['in_run'] = merge_run
            in_data['has_run'] = True
        else:
            if done_data['merge_run']:
                in_data['in_run'] = done_data['merge_run']
                in_data['has_run'] = True

        self._proc_series(seq, in_data, True)

    def _is_merge_correct(self, merge_data):
        """Checks if the merge_data information up to date

        New merges invalidate older merge data so we catch this case
        before doing any processing.

        Args:
            merge_data: The data about the merge.
        Return:
            Return True if there is no issue, otherwise returns False
        """

        from_num = merge_data['num_before_merge']
        from_data = self.aliquot_data.select_data(from_num, True)
        to_num = merge_data['num_after_merge']
        to_data = self.aliquot_data.select_data(to_num, True)
        if (not from_data or not to_data or
            merge_data['merge_from_sequence'] != from_data['base'] or
            merge_data['merge_to_sequence'] != to_data['base']):
            return False
        return True

    def _proc_series(self, seq, in_data, is_merge):
        """Processes the current step in the sequence.

        This is shared code between update_open and update merge with only minor
        differences between them.

        Args:
            seq: The sequence that is being processed.
            in_data: The data needed for the next entry in the sequence.
            is_merge: If True then we have a merging sequence.  This only
                matters at the end, as we do different actions on hitting
                an incomplete entry vs a merge.
        """

        curr_no_driver_run = None
        if in_data['has_run']:
            curr_run = in_data['in_run']
            curr_no_driver_run = in_data['in_no_driver_run']
        else:
            driver_uid = aliquot_util.calc_driver_uid(seq)
            curr_run = self.statistics.init_run(seq, driver_uid)
            if not aliquot_util.is_driver(driver_uid):
                data = self.aliquot_data.select_data(seq, True)
                data['driver_uid'] = driver_uid
                curr_no_driver_run = self.statistics.start_no_driver_run(seq, data, None)
        curr = curr_run['end_num']
        prev_data = self.aliquot_data.select_data(curr, True)
        if prev_data:
            prev_data['driver_uid'] = aliquot_util.calc_driver_uid(curr)
            curr = prev_data['aliquot_sum']
        done = False
        has_change = False
        while not done:
            data = self.aliquot_data.select_data(curr, True)
            if not data:
                if has_change:
                    self._proc_open(curr_run, is_merge)
                    self._proc_no_driver(seq, prev_data, curr_no_driver_run)
                done = True
            else:
                has_change = True
                data['driver_uid'] = aliquot_util.calc_driver_uid(curr)
                if curr > 1:
                    data['next_driver'] = aliquot_util.calc_driver_uid(data['aliquot_sum'])
                    self._add_step_data(data)
                if ('index' in prev_data and
                    (data['base'] != seq or data['index'] != prev_data['index'] + 1)):
                    # An open sequence should not end in a merge. Data needs to be fixed first.
                    if not is_merge:
                        print(f'Sequence {seq} not open. Run verify')
                    else:
                        self._proc_merge(seq, data, curr_run, in_data['merge_data'])
                        self._proc_no_driver(seq, data, curr_no_driver_run)
                    done = True
                else:
                    # If driver is the same we extend, otherwise we start a new run
                    if not self.statistics.extend_run(data, curr_run):
                        curr_run = self.statistics.end_run(data, curr_run)
                    # Separate "no driver" run
                    curr_no_driver_run = self._update_no_driver_run(data, curr_no_driver_run,
                                                                    prev_data)
                curr = data['aliquot_sum']
                prev_data = data

    def _proc_merge(self, seq, data, curr_run, merge_data):
        """Save the run that merged instead of having a new driver"""

        if (merge_data['merge_to_sequence'] != data['base'] or
            merge_data['merge_to_index'] != data['index']):
            print(f'For {seq}, merge data is out of date and needs fixing')
        curr_run['merge_sequence'] = data['base']
        curr_run['merge_index'] = data['index']
        self.statistics.save_merge_run(seq, curr_run)
        self.statistics.mark_processed(seq)

    def _proc_open(self, curr_run, is_merge):
        """Handles ending the open sequence when we hit an incomplete sequence"""

        seq = curr_run['sequence_number']
        if is_merge:
            index = curr_run['end_index']
            print(f'Merge data not found for Seq = {seq}, Index = {index}')
        else:
            self.statistics.save_open_run(seq, curr_run)

    def _update_no_driver_run(self, data, no_driver_run, prev_data):
        """Update the 'no driver' run

        No driver run only occurs when series is between drivers. The power
        of two can change often in this case, so here we treat this as a single
        "no driver" state.
        """

        is_driver = aliquot_util.is_driver(data['driver_uid'])
        if no_driver_run:
            if is_driver:
                self.statistics.end_no_driver_run(data, no_driver_run)
                return None
            self.statistics.extend_no_driver_run(data, no_driver_run)
            return no_driver_run
        if not is_driver:
            seq = data['base']
            return self.statistics.start_no_driver_run(seq, data, prev_data)
        return None

    def _proc_no_driver(self, seq, data, no_driver_run):
        """Save any "no driver" run

        When we merge or hit the end of the open sequence we check if the
        "no driver" run exists and also needs saving.
        """

        if no_driver_run:
            no_driver_run['next_driver'] = data['driver_uid']
            self.statistics.save_no_driver_run(seq, no_driver_run)

    def _update_for_new_merge(self, seq, done_data):
        """Update existing runs based on new merge information

        A smaller sequence has changed the runs for this sequence.

        # TODO: Get all runs for seq
        # TODO: Alter runs that occurr after the new merge
        """
        merge_run = {}
        merge_data = done_data['merge_data']
        merge_run = done_data['merge_run']
        if merge_data['merge_from_index'] > merge_run['end_index']:
            #Merge run not complete
            return merge_run
        if merge_data['merge_from_index'] > merge_run['start_index']:
            #split the merge run.
            self.statistics.split_run_for_merge(merge_run, merge_data)
        else:
            all_runs = self.statistics.get_all_runs_for_seq(seq)
            for run in all_runs:
                if merge_data['merge_from_index'] > run['end_index']:
                    continue
                if merge_data['merge_from_index'] > run['start_index']:
                    #split the merge run.
                    self.statistics.split_run_for_merge(run, merge_data)
                else:
                    self.statistics.delete_driver_run(seq, run['start_index'])
        return None

    def _init_step_data(self):
        self.statistics.init_single()

    def _save_step_data(self):
        self.statistics.save_single()

    def _add_step_data(self, data):
        """Add the single step and factor count information for this step.

        Single step has counts of digits + driver + next_driver combination as well as num to
        aliquot sum ratio data.
        Factor count has counts of digits + driver + number of factors. For the first time a
        combo is seen we set to 1.  Getting the same combo again increments the count
        """
        digits = len(str(data['num']))
        driver_uid = data['driver_uid']
        next_driver = data['next_driver']
        num_factors = aliquot_util.count_factors_skip_driver(data['factor_string'], driver_uid)
        ratio = aliquot_util.get_ratio(data['num'], data['aliquot_sum'])

        common = {}
        common['digits'] = digits
        common['driver_uid'] = driver_uid

        single_step = {}
        single_step['next_driver'] = next_driver
        single_step['ratio'] = ratio
        factor_count = {}
        factor_count['num_factors'] = num_factors
        self.statistics.update_single(common, single_step, factor_count)

# Uses a class rather than globals.
if __name__ == "__main__":
    logging.basicConfig(filename='alq_runs.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    aliquot_runs = AliquotRuns(pg)
    aliquot_runs.calc_statistics()
    logger.info('finished')
