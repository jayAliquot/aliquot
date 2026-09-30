#!/usr/bin/env python

""" Access for the aliquot runs data

    The sequence runs are stored in postgres. Calls aliquot_data to get the sql.
    functionality and the initial table creation.
    Types are:
        driver_run:    For an aliquot series a driver is a set of factors that tend to remain 
                       once established.  A run is successive terms from when the driver appears
                       until it is lost.
        merge_run:     The final run just before the sequence merges.
        open_run:      A run for an open sequence that hasn't ended yet.
        no_driver_run: The sequence does not have any driver so the factors can change much more
                       frequently. This ends when a driver is started.

   More details on drivers is found in the aliquot_statistics classes.
"""

import logging

logger = logging.getLogger(__name__)

class AliquotDataRuns:
    """Class for inserting, updating, getting, and deleting runs."""

    def __init__(self, sql):
        """Sets logging and sql for postgres

        Attributes:
            sql: postgres sql connection.
            log: for logging warnings and errors.
        """

        self.sql = sql

    def insert_driver_run(self, run_data):
        """Insert driver run information

        Drivers are factors that usuually repeat. A driver run is a run of consecutive terms that
        all have the same driver.
        
        Args:
            run_data: The data for a driver run of a sequence.
        """

        table_name = 'driver_run'
        seq = int(run_data['sequence_number'])
        if seq < 1:
            logger.warning('Attempt to add zero to data skipped(insert_driver_run)')
            return
        update_entry = f'INSERT INTO {table_name} VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);'
        self.sql.insert(update_entry, (run_data['sequence_number'],run_data['start_index'],
                                       run_data['start_digits'],run_data['start_num'],
                                       run_data['end_index'],run_data['end_digits'],
                                       run_data['end_num'], run_data['end_factors'],
                                       run_data['driver_uid'], run_data['next_driver']))

    def update_driver_run(self, run_data):
        """Update driver run information

        Drivers are factors that usuually repeat. A driver run is a run of consecutive terms that
        all have the same driver.
        
        Args:
            run_data: The data for a driver run of a sequence.
        """

        table_name = 'driver_run'
        seq = int(run_data['sequence_number'])
        index = int(run_data['start_index'])
        if seq < 1:
            logger.warning('Attempt to add zero to data skipped(update_driver_run)')
            return
        update_entry = (f'UPDATE {table_name} ' +
                        'SET start_digits = %s, start_num = %s, '
                        'end_index = %s, end_digits = %s, end_num = %s, '
                        'end_factors = %s, driver_uid = %s, next_driver=%s '
                        f'WHERE sequence_number = {seq} and start_index = {index};')
        self.sql.insert(update_entry, (run_data['start_digits'], run_data['start_num'],
                                       run_data['end_index'], run_data['end_digits'],
                                       run_data['end_num'], run_data['end_factors'],
                                       run_data['driver_uid'], run_data['next_driver']))

    def has_driver_run(self, seq, index):
        """Checks to see if the driver run already exists

        Args:
            seq: The sequence number to get data for.
            index: The index that starts the driver run.
        Returns:
            True if the run exists, False Otherwise.
        """

        data = self.get_driver_run(seq, index)
        if data:
            return True
        return False

    def get_driver_run(self, seq, index):
        """Gets the existing driver run information for a sequence

        Args:
            seq: The sequence number to get data for.
            index: The index the driver run starts at.

        Returns:
            A structure storing the driver run data for the sequence if it exists.
            Otherwise None is returned.
        """

        if not isinstance(seq, int) or not isinstance(index, int):
            logger.critical('Sequence, index not int: %s, %s.', seq, index)
            raise TypeError(f'seq, index must be an int, received {type(seq).__name__}, '
                            f'{type(index).__name__}')
        table_name = 'driver_run'
        select = ('SELECT sequence_number, start_index, start_digits, start_num, '
                  'end_index, end_digits, end_num, end_factors, driver_uid, next_driver '
                  f'FROM {table_name} WHERE '
                  f'sequence_number = %s and start_index = %s;')
        raw_data = self.sql.select_one(select,(seq, index))
        if not raw_data:
            return None
        data = {
            'sequence_number': raw_data[0],
            'start_index': raw_data[1],
            'start_digits': raw_data[2],
            'start_num': raw_data[3],
            'end_index': raw_data[4],
            'end_digits': raw_data[5],
            'end_num': raw_data[6],
            'end_factors': raw_data[7],
            'driver_uid': raw_data[8],
            'next_driver': raw_data[9]
        }
        return data

    def get_all_driver_runs(self, seq):
        """Gets all existing driver runs for a sequence

        Args:
            seq: The sequence number to get data for.

        Returns:
            An array of structures storing any existing driver run data for the sequence.
        """

        if not isinstance(seq, int):
            logger.critical('Sequence not int: %s', seq)
            raise TypeError(f'seq must be an int, received {type(seq).__name__}')
        table_name = 'driver_run'
        data = []
        select_all = ('SELECT sequence_number, start_index, start_digits, start_num, '
                      'end_index, end_digits, end_num, end_factors, driver_uid, next_driver '
                      f'FROM {table_name} WHERE sequence_number = {seq};')
        raw_data = self.sql.select_all(select_all)
        for raw_item in raw_data:
            item = {
                'sequence_number': raw_item[0],
                'start_index': raw_item[1],
                'start_digits': raw_item[2],
                'start_num': raw_item[3],
                'end_index': raw_item[4],
                'end_digits': raw_item[5],
                'end_num': raw_item[6],
                'end_factors': raw_item[7],
                'driver_uid': raw_item[8],
                'next_driver': raw_item[9]
            }
            data.append(item)
        return data

    def delete_driver_run(self, seq, index):
        """Deletes the driver run for the given sequeince.

        Args:
            seq: The sequence number the driver run belongs to
            index: The index the driver run starts at.
        """

        if not isinstance(seq, int) or not isinstance(index, int):
            logger.critical('Sequence, index not int: %s, %s.', seq, index)
            raise TypeError(f'seq, index must be an int, received {type(seq).__name__}, '
                            f'{type(index).__name__}')

        table_name = 'driver_run'
        select = (f'Delete FROM {table_name} WHERE '
                  f'sequence_number = {seq} and start_index = {index};')
        self.sql.execute(select)

    def insert_merge_run(self, run_data, is_single):
        """Insert merge run information

        A merge run is the final run before a merge occurs. 
        If a number is part of a smaller sequence, it isn't considered to merge so no merge
        run will exist for that number.
        Over 90% of the sequence numbers (e.g. almost all odd numbers) have an aliquot sum 
        smaller than themselves and so merge at index 1.  These are considered singles.  
        By keeping singles in a separate table, the performance of the more significant merges
        is improved.

        Args:
            run_data: The data for a driver run of a sequence.
            is_single: The aliquot_sum is part of a smaller sequence, so the series merges
                immediately after the first value.
        """

        if is_single:
            table_name = 'merge_single'
        else:
            table_name = 'merge_run'
        seq = int(run_data['sequence_number'])
        if seq < 1:
            logger.warning('Attempt to add zero to data skipped(insert_merge_run)')
            return
        update_entry = f'INSERT INTO {table_name} VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);'
        self.sql.insert(update_entry, (seq, run_data['start_index'],
                                       run_data['start_digits'], run_data['start_num'],
                                       run_data['end_index'], run_data['end_digits'],
                                       run_data['end_num'], run_data['merge_sequence'],
                                       run_data['merge_index'], run_data['driver_uid']))

    def update_merge_run(self, run_data, is_single):
        """Update the merge run information

        Updates occur when a smaller sequence is extended and alters the larger sequence it
        overlaps with.  This is due to a number always being associated with the smallest sequence
        that reaches it.
  
        A merge run is the final run before a merge into a smaller sequence occurs. 
        If a number is part of a smaller sequence, it isn't considered to merge so no merge
        run will exist for that number.
        Over 90% of the sequence numbers (e.g. almost all odd numbers) have an aliquot sum 
        smaller than themselves and so merge at index 1.  These are considered singles.  
        By keeping singles in a separate table, the performance of the more significant merges
        is improved.

        Args:
            run_data: The data for a driver run of a sequence.
            is_single: The aliquot_sum is part of a smaller sequence, so the series merges
                immediately after the first value.
        """

        if is_single:
            table_name = 'merge_single'
        else:
            table_name = 'merge_run'
        seq = int(run_data['sequence_number'])
        if seq < 1:
            logger.warning('Attempt to add zero to data skipped(update_merge_run)')
            return
        update_entry = (f'UPDATE {table_name} ' +
                        'SET start_index = %s, start_digits = %s, start_num = %s, '
                        'end_index = %s, end_digits = %s, end_num = %s, '
                        'merge_sequence = %s, merge_index = %s, driver_uid = %s '
                        f'WHERE sequence_number = {seq};')
        self.sql.insert(update_entry, (run_data['start_index'], run_data['start_digits'],
                                       run_data['start_num'],
                                       run_data['end_index'], run_data['end_digits'],
                                       run_data['end_num'], run_data['merge_sequence'],
                                       run_data['merge_index'], run_data['driver_uid']))

    def has_merge_run(self, seq):
        """Checks to see if the merge run already exists

        Args:
            seq: The sequence number to get data for.
        Returns:
            True if the run exists, False Otherwise.
        """

        data = self.get_merge_run(seq)
        if data:
            return True
        return False

    def get_merge_run(self, seq):
        """Gets the existing merge run information for a sequence

        Args:
            seq: The sequence number to get data for.

        Returns:
            A structure storing the merge run data for the sequence if it exists.
            Otherwise None is returned.
        """

        if not isinstance(seq, int):
            logger.critical('Sequence not int: %s.', seq)
            raise TypeError(f'seq must be an int, received {type(seq).__name__}.')
        table_name = 'merge_run'
        select = ('SELECT sequence_number, start_index, start_digits,  start_num, '
                  'end_index, end_digits, end_num, merge_sequence, merge_index, driver_uid ' +
                  f'FROM {table_name} WHERE sequence_number = %s;')
        raw_data = self.sql.select_one(select,(seq,))
        if not raw_data:
            table_name = 'merge_single'
            select = ('SELECT sequence_number, start_index, start_digits,  start_num, '
                      'end_index, end_digits, end_num, merge_sequence, merge_index, driver_uid ' +
                      f'FROM {table_name} WHERE sequence_number = %s;')
            raw_data = self.sql.select_one(select, (seq,))
            if not raw_data:
                return None
        data = {
            'sequence_number': raw_data[0],
            'start_index': raw_data[1],
            'start_digits': raw_data[2],
            'start_num': raw_data[3],
            'end_index': raw_data[4],
            'end_digits': raw_data[5],
            'end_num': raw_data[6],
            'merge_sequence': raw_data[7],
            'merge_index': raw_data[8],
            'driver_uid': raw_data[9]
        }
        return data

    def delete_merge_run(self, seq, is_single):
        """Deletes the merge run for the given sequeince.

        Args:
            seq: The sequence number the driver run belongs to
            index: The index the driver run starts at.
        """

        if not isinstance(seq, int):
            logger.critical('Sequence not int: %s.', seq)
            raise TypeError(f'seq must be an int, received {type(seq).__name__}.')
        if is_single:
            table_name = 'merge_single'
        else:
            table_name = 'merge_run'
        select = (f'Delete FROM {table_name} WHERE '
                  f'sequence_number = {seq};')
        self.sql.execute(select)

    def insert_open_run(self, run_data):
        """Insert open run information

        An open run is a driver (or no-driver) run where not all terms are known for an open
        sequence
        
        Args:
            run_data: The data for an open run of a sequence.
        """

        table_name = 'open_run'
        update_entry = f'INSERT INTO {table_name} VALUES (%s, %s, %s, %s, %s, %s, %s, %s);'
        seq = int(run_data['sequence_number'])
        if seq < 1:
            logger.warning('Attempt to add zero to data skipped(insert_open_run)')
            return
        self.sql.insert(update_entry, (run_data['sequence_number'], run_data['start_index'],
                                       run_data['start_digits'], run_data['start_num'],
                                       run_data['end_index'], run_data['end_digits'],
                                       run_data['end_num'], run_data['driver_uid']))

    def update_open_run(self, run_data):
        """Update the open run information

        An open run is a driver (or no-driver) run where not all terms are known for an open
        sequence
        
        Args:
            run_data: The data for an open run of a sequence.
        """
        table_name = 'open_run'
        seq = int(run_data['sequence_number'])
        if seq < 1:
            logger.warning('Attempt to add zero to data skipped(update_open_run)')
            return
        update_entry = (f'UPDATE {table_name} ' +
                        'SET start_index = %s, start_digits = %s, start_num = %s, '
                        'end_index = %s, end_digits = %s, end_num = %s, driver_uid = %s '
                        f'WHERE sequence_number = {seq};')
        self.sql.insert(update_entry, (run_data['start_index'], run_data['start_digits'],
                                       run_data['start_num'],
                                       run_data['end_index'], run_data['end_digits'],
                                       run_data['end_num'], run_data['driver_uid']))

    def has_open_run(self, seq):
        """Checks to see if the merge run already exists

        Args:
            seq: The sequence number to get data for.
        Returns:
            True if the run exists, False Otherwise.
        """

        data = self.get_open_run(seq)
        if data:
            return True
        return False

    def get_open_run(self, seq):
        """Gets the existing open run information for a sequence

        Args:
            seq: The sequence number to get data for.

        Returns:
            A structure storing the open run data for the sequence if it exists.
            Otherwise None is returned.
        """

        if not isinstance(seq, int):
            logger.critical('Sequence not int: %s.', seq)
            raise TypeError(f'seq must be an int, received {type(seq).__name__}.')
        table_name = 'open_run'
        select = ('SELECT sequence_number, start_index, start_digits, start_num, '
                  'end_index, end_digits, end_num, driver_uid ' +
                  f'FROM {table_name} WHERE sequence_number = %s;')
        raw_data = self.sql.select_one(select,(seq,))
        if not raw_data:
            return None
        data = {
            'sequence_number': raw_data[0],
            'start_index': raw_data[1],
            'start_digits': raw_data[2],
            'start_num': raw_data[3],
            'end_index': raw_data[4],
            'end_digits': raw_data[5],
            'end_num': raw_data[6],
            'driver_uid': raw_data[7]
        }
        return data

    def delete_open_run(self, seq):
        """Deletes the merge run for the given sequeince.

        Args:
            seq: The sequence number the driver run belongs to
            index: The index the driver run starts at.
        """

        table_name = 'open_run'
        select = (f'Delete FROM {table_name} WHERE '
                  f'sequence_number = {seq};')
        self.sql.execute(select)


    def insert_no_driver_run(self, run_data):
        """Insert run information when there is no driver.

        When there is no driver the factors can change often.  A no driver run will
        continue until the sequence picks up a driver.  It does not merge nor will it be
        open.  Note that there are uids for the no-driver state based on the power of 2. 
        This is needed becaues open runs can have no driver.

        Args:
            run_data: The data for a driver run of a sequence.
        """

        table_name = 'no_driver_run'
        seq = int(run_data['sequence_number'])
        if seq < 1:
            logger.warning('Attempt to add zero to data skipped(insert_no_driver_run)')
            return
        update_entry = f'INSERT INTO {table_name} VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);'
        self.sql.insert(update_entry, (run_data['sequence_number'],run_data['start_index'],
                                       run_data['start_digits'], run_data['start_num'],
                                       run_data['prev_driver'], run_data['end_index'],
                                       run_data['end_digits'], run_data['end_num'],
                                       run_data['next_driver']))

    def update_no_driver_run(self, run_data):
        """Update run information when there is no driver.

        When there is no driver the factors can change often.  A no driver run will
        continue until the sequence picks up a driver.  It does not merge nor will it be
        open.  Note that there are uids for the no-driver state based on the power of 2. 
        This is needed becaues open runs can have no driver.

        Args:
            run_data: The data for a driver run of a sequence.
        """

        table_name = 'no_driver_run'
        seq = int(run_data['sequence_number'])
        index = run_data['start_index']
        if seq < 1:
            logger.warning('Attempt to add zero to data skipped(update_no_driver_run)')
            return
        update_entry = (f'UPDATE {table_name} ' +
                        'SET start_index = %s, start_digits = %s, start_num = %s, '
                        'prev_driver = %s, end_index = %s, end_digits = %s, '
                        'end_num = %s, next_driver = %s '
                        f'WHERE sequence_number = {seq} and start_index = {index};')
        self.sql.insert(update_entry, (run_data['start_index'], run_data['start_digits'],
                                       run_data['start_num'], run_data['prev_driver'],
                                       run_data['end_index'], run_data['end_digits'],
                                       run_data['end_num'], run_data['next_driver']))

    def has_no_driver_run(self, seq, index):
        """Checks to see if the driver run already exists

        Args:
            seq: The sequence number to get data for.
            index: The index that starts the driver run.
        Returns:
            True if the run exists, False Otherwise.
        """

        data = self.get_no_driver_run(seq, index)
        if data:
            return True
        return False

    def get_no_driver_run(self, seq, index):
        """Gets the existing no driver run information for a sequence

        Args:
            seq: The sequence number to get data for.
            index: The index the no-driver run starts at.

        Returns:
            A structure storing the no-driver run data for the sequence if it exists.
            Otherwise None is returned.
        """

        if not isinstance(seq, int) or not isinstance(index, int):
            logger.critical('Sequence, index not int: %s, %s.',seq, index)
            raise TypeError(f'seq, index must be an int, received {type(seq).__name__}, '
                            f'{type(index).__name__}')
        table_name = 'no_driver_run'
        select = ('SELECT sequence_number, start_index, start_digits, start_num, prev_driver, '
                  'end_index, end_digits, end_num, next_driver ' +
                  f'FROM {table_name} WHERE sequence_number = %s and start_index = %s;')
        raw_data = self.sql.select_one(select,(seq,index))
        if not raw_data:
            return None
        data = {
            'sequence_number': raw_data[0],
            'start_index': raw_data[1],
            'start_digits': raw_data[2],
            'start_num': raw_data[3],
            'prev_driver': raw_data[4],
            'end_index': raw_data[5],
            'end_digits': raw_data[6],
            'end_num': raw_data[7],
            'next_driver': raw_data[8]
        }
        return data

    def get_all_no_driver_runs(self, seq):
        """Gets all existing no-driver runs for a sequence

        Args:
            seq: The sequence number to get data for.

        Returns:
            An array of structures storing any existing no-driver run data for the sequence.
        """

        if not isinstance(seq, int):
            logger.critical('Sequence not int: %s', seq)
            raise TypeError(f'seq must be an int, received {type(seq).__name__}')
        table_name = 'no_driver_run'
        data = []
        select_all = ('SELECT sequence_number, start_index, start_digits, start_num, prev_driver, '
                  'end_index, end_digits, end_num, next_driver ' +
                  f'FROM {table_name} WHERE sequence_number = {seq};')
        raw_data = self.sql.select_all(select_all)
        for raw_item in raw_data:
            item = {
                'sequence_number': raw_item[0],
                'start_index': raw_item[1],
                'start_digits': raw_item[2],
                'start_num': raw_item[3],
                'prev_driver': raw_item[4],
                'end_index': raw_item[5],
                'end_digits': raw_item[6],
                'end_num': raw_item[7],
                'next_driver': raw_item[8]
            }
            data.append(item)
        return data

    def delete_no_driver_run(self, seq, index):
        """Deletes the no-driver run for the given sequeince.

        Args:
            seq: The sequence number the no-driver run belongs to
            index: The index the no-driver run starts at.
        """

        if not isinstance(seq, int) or not isinstance(index, int):
            logger.critical('Sequence, index not int: %s, %s.', seq, index)
            raise TypeError(f'seq, index must be an int, received {type(seq).__name__}, '
                            f'{type(index).__name__}')

        table_name = 'no_driver_run'
        select = (f'Delete FROM {table_name} WHERE '
                  f'sequence_number = {seq} and start_index = {index};')
        self.sql.execute(select)
