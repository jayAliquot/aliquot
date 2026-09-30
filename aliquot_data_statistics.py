#!/usr/bin/env python

""" Postgres access for statistics information on the aliquot sequences.

    The statistics are stored in the aliquot postgres database.  aliquot_statistics.py is the main
    module to use these.
"""

import logging
from aliquot_types import StatsData
from sql import SQL

logger = logging.getLogger(__name__)

class AliquotDataStatistics:
    """Class for updating and accessing aliquot statistics tables in postgres"""

    def __init__(self, sql:SQL):
        """Sets logging and sql for postgres

        Attributes:
            sql: postgres sql connection.
        """

        self.sql = sql

    def get_stats_data(self, seq):
        """Get overall stats data for a given series.

        This data includes the digits for the largest known term, whether the sequence merges,
        ends in a cycle (self merge), or is open.

        Args:
            seq: The sequence number to get data for.
        Returns:
            A structure storing the stats data for the sequence if it exists.
            Note that maximum digits is not currently returned.
            Otherwise None is returned.
        """

        if not isinstance(seq, int):
            logger.critical('Sequence not int: %s.', seq)
            raise TypeError(f'seq must be an int, received {type(seq).__name__}')
        table_name = 'stats'
        select = ('SELECT sequence_number, num, base, sequence_index, stats_string, complete, '
                      f'max_digits FROM {table_name} WHERE sequence_number = %s;')
        raw_data = self.sql.select_one(select, (seq,))
        if not raw_data:
            return None
        data: StatsData = {
            'num': int(raw_data[1]),
            'base': raw_data[2],
            'index': raw_data[3],
            'stats_string': raw_data[4],
            'complete': raw_data[5],
            'max_digits': raw_data[6]
        }
        return data

    def _has_stats_data(self, seq):
        """Whether the stats data already exists.

        Args:
            seq: The sequence number to get data for.
        Returns:
            True if the status data exists, False Otherwise.
        """

        if not isinstance(seq, int):
            logger.critical('Sequence not int: %s.', seq)
            raise TypeError(f'seq must be an int, received {type(seq).__name__}')
        data:StatsData | None = self.get_stats_data(seq)
        if data:
            return True
        return False

    def set_stats_data(self, seq: int, data: StatsData):
        """Set the basic stats for the sequence.

        Args:
            seq: The sequence number to get data for.
            data: The stats data for this sequence.
        """

        if not isinstance(seq, int):
            logger.critical('Sequence not int: %s.',seq)
            raise TypeError(f'seq must be an int, received {type(seq).__name__}')
        table_name = 'stats'
        if seq < 1:
            logger.warning('Attempt to add zero to data skipped(set_stats_data)')
            return

        if self._has_stats_data(seq):
            update_entry = (f'UPDATE {table_name} ' +
                            'SET sequence_number = %s, num = %s, sequence_index = %s,'
                            'stats_string = %s, base = %s, complete = %s, max_digits = %s ' +
                            f'WHERE sequence_number = {seq};')
        else:
            update_entry = f'INSERT INTO {table_name} VALUES (%s, %s, %s, %s, %s, %s, %s);'
        self.sql.insert(update_entry, (seq, data['num'], data['index'], data['stats_string'],
                                           data['base'], data['complete'], data['max_digits']))

    def add_statistics_tables(self):
        """Add statistic tables

        Since this is done only once at the start of the project, function is not fully tested.
        """

        self.sql.add_statistics_tables()

    def insert_merge(self, merge_data):
        """Insert merge information

        A merge will exist for any non-open sequence. All merges are cycles or a merge into a 
        smaller sequence.
        
        Args:
            merge_data: The data for a sequence merge.
        """

        table_name = 'sequence_merge'
        if int(merge_data['merge_from_sequence']) < 1 or int(merge_data['merge_to_sequence']) < 1:
            logger.warning('Attempt to add zero to data skipped(insert_merge)')
            return
        update_entry = f'INSERT INTO {table_name} VALUES (%s, %s, %s, %s, %s, %s, %s);'
        self.sql.insert(update_entry, (merge_data['merge_from_sequence'],
                                       merge_data['merge_from_index'],
                                       merge_data['merge_to_sequence'],
                                       merge_data['merge_to_index'],
                                       merge_data['num_before_merge'],
                                       merge_data['num_after_merge'],
                                       False))

    def update_merge(self, merge_data):
        """Update the merge information

        A merge will exist for any non-open sequence. All merges are  cycles or a merge into a 
        smaller sequence.
        
        Args:
            merge_data: The data for a sequence merge.
        """

        table_name = 'sequence_merge'
        seq = int(merge_data['merge_from_sequence'])
        if seq < 1 or int(merge_data['merge_to_sequence']) < 1:
            logger.warning('Attempt to add zero to data skipped(update_merge)')
            return
        update_entry = (f'UPDATE {table_name} '
                        'SET merge_from_index = %s, merge_to_sequence = %s, merge_to_index = %s, '
                        'num_before_merge = %s, num_after_merge = %s, processed = %s '
                        f'WHERE merge_from_sequence = {seq};')
        self.sql.insert(update_entry, ( merge_data['merge_from_index'],
                                        merge_data['merge_to_sequence'],
                                        merge_data['merge_to_index'],
                                        merge_data['num_before_merge'],
                                        merge_data['num_after_merge'],
                                        merge_data['processed']))

    def has_merge(self, seq):
        """Checks to see if the merge informtion already exists.

        Args:
            seq: The sequence number to get data for.
        Returns:
            True if the merge exists, False Otherwise.
        """

        data = self.get_merge(seq)
        if data:
            return True
        return False

    def get_merge(self, seq):
        """Gets the existing merge information for a sequence

        Args:
            seq: The sequence number to get data for.
        Returns:
            A structure storing the merge data for the sequence if it exists.
            Otherwise None is returned.
        """

        if not isinstance(seq, int):
            logger.critical('Sequence not int: %s.', seq)
            raise TypeError(f'seq must be an int, received {type(seq).__name__}')
        table_name = 'sequence_merge'
        select = ('SELECT merge_from_sequence, merge_from_index, merge_to_sequence, merge_to_index,'
                  ' num_before_merge, num_after_merge, processed '
                  f'processed FROM {table_name} WHERE merge_from_sequence = %s;')
        raw_data = self.sql.select_one(select, (seq,))
        if not raw_data:
            return None
        data = {
            'merge_from_sequence': raw_data[0],
            'merge_from_index': raw_data[1],
            'merge_to_sequence': raw_data[2],
            'merge_to_index': raw_data[3],
            'num_before_merge': raw_data[4],
            'num_after_merge': raw_data[5],
            'processed': raw_data[6]
        }
        return data

    def delete_merge(self,seq):
        """Deletes the merge data for the given sequeince.

        Args:
            seq: The sequence number to to delete merge data.
        """

        if not isinstance(seq, int):
            logger.critical('Sequence not int: %s.', seq)
            raise TypeError(f'seq must be an int, received {type(seq).__name__}')
        table_name = 'sequence_merge'
        select = f'Delete FROM {table_name} WHERE merge_from_sequence = {seq};'
        self.sql.execute(select)

    def get_all_merging_into(self, seq):
        """Find all sequences that merge into a given sequence.

        Given a sequence, this gives a list of sequences that merge into it.
        Sequences whose first element is already part of another sequence will
        return zero results; the merge is to the other sequence.

        Args:
            seq: The sequence number we are merging into.
        Returns:
            An array of structures storing the merge data for each of the merging
            sequences
        """

        if not isinstance(seq, int):
            logger.critical('Sequence not int: %s.', seq)
            raise TypeError(f'seq must be an int, received {type(seq).__name__}')
        table_name = 'sequence_merge'
        data = []
        select_all = ('SELECT merge_from_sequence, merge_from_index, merge_to_sequence, '
                      'merge_to_index, num_before_merge, num_after_merge, processed '
                      f'FROM {table_name} WHERE merge_to_sequence = {seq};')
        raw_data = self.sql.select_all(select_all)
        for raw_item in raw_data:
            item = {
                'merge_from_sequence': raw_item[0],
                'merge_from_index': raw_item[1],
                'merge_to_sequence': raw_item[2],
                'merge_to_index': raw_item[3],
                'num_before_merge': raw_item[4],
                'num_after_merge': raw_item[5],
                'processed': raw_item[6]
            }
            data.append(item)
        return data

    def insert_single_step(self, step_data):
        """Insert information for a step (consecutive term ratios) per drivers and digits.

        The table gives information on the growth rate per drivers and per number of digits 
        averaged over all consecutive values for many driver runs. It is difficult to get a 
        precise value as runs change based on new information so this is an estimate.
        
        Args:
            step_data: The data for a given driver and number of digits. Both the driver of the
            term and the driver of the aliquot sum are used as keys along with the number of digits.
        """

        table_name = 'single_step'
        update_entry = f'INSERT INTO {table_name} VALUES (%s, %s, %s, %s, %s, %s, %s);'
        self.sql.insert(update_entry, (step_data['digits'], step_data['driver_uid'],
                                       step_data['next_driver'], step_data['count'],
                                       step_data['max_ratio'], step_data['min_ratio'],
                                       step_data['ratio_sum']))

    def update_single_step(self, step_data):
        """Update information for a step (consecutive term ratios) per drivers and digits.

        The table gives information on the growth rate per drivers and per number of digits 
        averaged over all consecutive values for many driver runs. It is difficult to get a 
        precise value as runs change based on new information so this is an estimate.
        
        Args:
            step_data: The data for a given driver and number of digits. Both the driver of the
            term and the driver of the aliquot sum are used as keys along with the number of digits.
        """

        table_name = 'single_step'
        digits = int(step_data['digits'])
        driver_uid = int(step_data['driver_uid'])
        next_driver = int(step_data['next_driver'])
        update_entry = (f'UPDATE {table_name} ' +
                        'SET count = %s, max_ratio = %s, min_ratio = %s, '
                        f'ratio_sum = %s WHERE digits = {digits} and '
                        f'driver_uid = {driver_uid} and next_driver = {next_driver};')
        self.sql.insert(update_entry, (step_data['count'], step_data['max_ratio'],
                                       step_data['min_ratio'], step_data['ratio_sum']))

    def has_single_step(self, digits, driver_uid, next_driver):
        """Checks to see if the single step already exists.

        Args:
            digits: The number of digits for the step.
            driver_uid: The driver id for the initial term.
            next_driver: The driver id for the aliquot sum.
        Returns:
            True if the single step data exists, False Otherwise.
        """

        data = self.get_single_step(digits, driver_uid, next_driver)
        if data:
            return True
        return False

    def get_single_step(self, digits, driver_uid, next_driver):
        """Returns growth ratios given the digits and driver ids.

        The driver id's and digits must be integer or we raise an error.

        Args:
            digits: The number of digits for the step.
            driver_uid: The driver id for the initial term.
            next_driver: The driver id for the aliquot sum.
        Returns:
            A structure storing the step data for the inputs if it exists.
            Otherwise None is returned.
        """

        if (not isinstance(digits, int) or not isinstance(driver_uid, int) or
            not isinstance(next_driver, int)):
            logger.critical('digits or drivers not int: %s, %s, %s.', digits, driver_uid,
                            next_driver)
            raise TypeError(f'nums must be an int, received {type(digits).__name__}, '
                            f'{type(driver_uid).__name__}, {type(next_driver).__name__}')
        table_name = 'single_step'
        select = ('SELECT digits, driver_uid, next_driver, count, max_ratio, min_ratio, ratio_sum '
                  f'FROM {table_name} WHERE digits = %s and '
                  'driver_uid = %s and next_driver = %s;')
        raw_data = self.sql.select_one(select, (digits, driver_uid, next_driver))
        if not raw_data:
            return None
        data = {
            'digits': raw_data[0],
            'driver_uid': raw_data[1],
            'next_driver': raw_data[2],
            'count': raw_data[3],
            'max_ratio': raw_data[4],
            'min_ratio': raw_data[5],
            'ratio_sum': raw_data[6]
        }
        return data

    def insert_factor_count(self, factor_data):
        """Insert information about factor count per driver and digits.

        This is a straight up count of number of occurrances given the driver, number of digits
        and the number of factors.
        
        Args:
            factor_data: The data for a given driver and the number of digits and factors.
        """

        table_name = 'factor_count'
        update_entry = f'INSERT INTO {table_name} VALUES (%s, %s, %s, %s);'
        self.sql.insert(update_entry, (factor_data['digits'], factor_data['driver_uid'],
                                       factor_data['num_factors'], factor_data['count']))

    def update_factor_count(self, factor_data):
        """Update information about factor count per driver and digits and number of factors

        This is a straight up count of number of occurrances given the driver, number of digits
        and the number of factors.

        Args:
            factor_data: The data for a given driver and the number of digits and factors.
        """

        table_name = 'factor_count'
        digits = int(factor_data['digits'])
        driver_uid = int(factor_data['driver_uid'])
        num_factors = int(factor_data['num_factors'])
        update_entry = (f'UPDATE {table_name} ' +
                        f'SET count = %s WHERE digits = {digits} and '
                        f'driver_uid = {driver_uid} and num_factors = {num_factors};')
        self.sql.insert(update_entry, (factor_data['count'],))

    def has_factor_count(self, digits, driver_uid, num_factors):
        """Checks to see if the factor count already exists.

        Args:
            digits: The number of digits for the step
            driver_uid: The driver id for the initial term
            num_factors: The number of factors found.
        Returns:
            True if the single step data exists, False Otherwise.
        """

        data = self.get_factor_count(digits, driver_uid, num_factors)
        if data:
            return True
        return False

    def get_factor_count(self, digits, driver_uid, num_factors):
        """Returns the occcurance count given the digits, driver id, and number of factors.

        The driver id, digits, and number of factors must be integer or we raise an error.

        Args:
            digits: The number of digits for the step
            driver_uid: The driver id for the initial term
            num_factors: The driver id for the aliquot sum.
        Returns:
            A structure storing the factor count data for the inputs if it exists.
            Otherwise None is returned.
        """

        if (not isinstance(digits, int) or not isinstance(driver_uid, int) or
            not isinstance(num_factors, int)):
            logger.critical('digits or drivers not int: %s, %s, %s.', digits, driver_uid,
                            num_factors)
            raise TypeError(f'nums must be an int, received {type(digits).__name__}, '
                            f'{type(driver_uid).__name__}, {type(num_factors).__name__}')

        table_name = 'factor_count'
        select = ('SELECT digits, driver_uid, num_factors, count ' +
                  f'FROM {table_name} WHERE digits = %s and '
                  'driver_uid = %s and num_factors = %s;')
        raw_data = self.sql.select_one(select, (digits, driver_uid, num_factors))
        if not raw_data:
            return None
        data = {
            'digits': raw_data[0],
            'driver_uid': raw_data[1],
            'num_factors': raw_data[2],
            'count': raw_data[3]
        }
        return data

    def statistics_reset(self):
        """Deletes all statistics and runs data.

        Updatating the statistics data is difficult, so it is better to clear all the data
        and rerun through the current sequences.  This function clear all the tables before we
        start the rerun.
        """

        tables = ['factor_count', 'single_step', 'no_driver_run', 'driver_run', 'merge_run',
                  'merge_single', 'open_run']
        for table in tables:
            update_entry = f'DELETE FROM {table};'
            self.sql.execute(update_entry)
