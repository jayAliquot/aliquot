#!/usr/bin/env python

""" Access for the aliquot seqence data

The sequences are stored in postgres.  This class uses sql.py which has lower level SQL
functionality and the initial table creation.

Added changing verify status when a postgres change is first made so that a programs that end
prematurely still record making a change to verify.
"""

import logging
import typing

logger = logging.getLogger(__name__)

class AlqData(typing.TypedDict):
    """Type for returning data from local database"""
    num: int
    base: int
    index: int
    aliquot_sum: int
    factor_string: str
    complete: bool
    unfactor: typing.NotRequired[int]

class StatusData(typing.TypedDict):
    """Type for returning status data from local database"""
    sequence_number: int
    verified: bool
    timestamp: str
    elg_update: bool
    stats_update: bool
    open_ended: bool
    elf_update: bool
    extend_update: bool
    localdb_update: bool
    factordb: str
    factor_update: bool

class TableNameData(typing.TypedDict):
    """Type for table names"""
    name: str
    size: int | None

class AliquotData:
    """Class for accessing postgres local data

    Handles basic and status calls to postgres. Other classes that access sql are
    aliquot_data_runs.py for runs with the same driver, and aliquot_data_statistics.py for 
    statistics on the aliquot sequences.
    """

    def __init__(self, sql):
        """Sets sql for postgres

        Attributes:
            sql: postgres sql connection.
            update_list: So we update status only once.
        """

        self.sql = sql
        self.update_list = {}

    def has_data(self, num: int, complete: bool) -> bool:
        """Indicates whether num is part of an aliquot series.

        Data exists for all numbers that are part of some aliquot series. Used to determine when
        sequences merge.  Complete is true if the number is fully factored.  
        To be sure if a number exists, both complete and not complete should be checked, though
        in practice the incomplete numbers are too large to expect a merge.

        Args:
            num: The number to check if it is already in the data.
            complete: True if the number is fully factored, False otherwise.

        Returns:
            True if the number is found, False otherwise.

        Raises:
            TypeError: If num is not an integer.
        """

        data = self._select_sql(num, complete)
        if data:
            return True
        return False

    def insert_data(self, data: AlqData) -> None:
        """Inserts aliquot sequence entry into the local data

        Inserts a number into the local postgres database.  Complete data where all factors
        are known is entered into one of the tables based on the size of the number.  A single
        table holds the rest of the numbers where data['complete'] is False.
        
        Args:
            data: The data to be inserted into the local data.
        """

        num = data['num']
        self._check_status(data['base'])
        if not isinstance(num, int):
            logger.critical('Number is not int: %s.', num)
            raise TypeError(f'Number must be an int, received {type(num).__name__}')
        if num < 1:
            print('Attempt to add zero to data skipped(insert_data)')
            return
        if data['complete']:
            table_name = self._get_table_name(num)
        else:
            table_name = 'incomplete'
        self._insert_sql(table_name, data)

    def update_data(self, data: AlqData) -> None:
        """Updates an aliquot sequence entry in the local data

        The number and its factors remain the same, however, which sequence it belongs to
        and its index can change.  This occurs when there is a merge.
        
        Args:
            data: The data to be updated in the local data.
        """

        num = data['num']
        self._check_status(data['base'])
        if not isinstance(num, int):
            logger.critical('Number is not int: %s.', num)
            raise TypeError(f'Number must be an int, received {type(num).__name__}')
        if num < 1:
            print('Attempt to add zero to data skipped(update_data)')
            return
        if data['complete']:
            table_name = self._get_table_name(num)
        else:
            table_name = 'incomplete'
        self._update_sql(table_name, data)

    def _check_status(self, seq :int) -> None:
        """Update status if seq not yet updated

        Args:
            seq: The sequence to update
        """

        if seq not in self.update_list:
            data = self.get_status_data(seq)
            if data:
                data['verified'] = False
                data['stats_update'] = False
                self.set_status_data(data)
            self.update_list[seq] = True

    def select_data(self, num: int, complete: bool) -> AlqData | None:
        """Select data matching a given number

        The output includes known factors and the sequence and index the number belongs to
        
        Args:
            num: The number to find data for.
        Returns:
            A structure with data from the local postgres database.
        """

        raw_data = self._select_sql(num, complete)
        if not raw_data:
            return None
        data: AlqData = {
            'num': int(raw_data[0]),
            'base': int(raw_data[1]),
            'index': int(raw_data[2]),
            'aliquot_sum': int(raw_data[3]),
            'factor_string': raw_data[4],
            'complete': True
        }
        if len(raw_data) == 6:
            data['unfactor'] = int(raw_data[5])
            data['complete'] = False
        return data

    def _select_sql(self, num: int, complete: bool) -> tuple[str, ...] | None:
        """Select data matching a given number

        Constructs the postgres call for selection.
        
        Args:
            num: The number to find data for.
        Returns:
            A structure with data from the local postgres database.
        """

        if not isinstance(num, int):
            logger.critical('Number is not int: %s.', num)
            raise TypeError(f'Number must be an int, received {type(num).__name__}')
        if complete:
            table_name = self._get_table_name(num)
        else:
            table_name = 'incomplete'
        if table_name == 'incomplete':
            select = ('SELECT num, sequence_number, sequence_index, aliquot_sum, factor_string, '
                      f'unfactored FROM {table_name} WHERE num = %s;')
        else:
            select = ('SELECT num, sequence_number, sequence_index, aliquot_sum, factor_string '
                      f'FROM {table_name} WHERE num = %s;')
        data = self.sql.select_one(select, (num,))
        return data

    def _insert_sql(self, table_name: str, data: AlqData) -> None:
        """Inserts the data into the local postgres db.

        Constructs the postgres call for insertion.  Currently the caller needs to determine
        if insert or update needs to be used.

        The table name is based on whether the data is complete and the size of the number
        being inserted.  
        
        Args:
            table_name: The table name to insert the data into.
            data: The data to be inserted.
        """

        if table_name == 'incomplete':
            update_entry = f'INSERT INTO {table_name} VALUES (%s, %s, %s, %s, %s, %s);'
            self.sql.insert(update_entry, (data['num'], data['base'], data['index'],
                                           data['aliquot_sum'], data['factor_string'],
                                           data['unfactor']))
        else:
            update_entry = f'INSERT INTO {table_name} VALUES (%s, %s, %s, %s, %s);'
            self.sql.insert(update_entry, (data['num'], data['base'], data['index'],
                                           data['aliquot_sum'],
                                           data['factor_string']))

    def _update_sql(self, table_name: str, data: AlqData) -> None:
        """Updates the data in the local postgres db.

        Constructs the postgres call for an update.  Currently the caller needs to determine
        if insert or update needs to be used.

        The table name is based on whether the data is complete and the size of the number
        being inserted.  
        
        Args:
            table_name: The table name containing the data to be updated.
            data: The data to be updated.
        """

        num = int(data['num'])
        if table_name == 'incomplete':
            update_entry = (f'UPDATE {table_name} SET num = %s, sequence_number = %s, '
                            'sequence_index = %s, aliquot_sum = %s, factor_string = %s, '
                            'unfactored = %s WHERE num = %s;')
            self.sql.insert(update_entry, (num, data['base'], data['index'],
                                           data['aliquot_sum'], data['factor_string'],
                                           data['unfactor'], num))
        else:
            update_entry = (f'UPDATE {table_name} SET num = %s, sequence_number = %s, '
                            'sequence_index = %s, aliquot_sum = %s, factor_string = %s '
                            'WHERE num = %s;')
            self.sql.insert(update_entry, (num, data['base'], data['index'], data['aliquot_sum'],
                                           data['factor_string'], num))

    def clean_incomplete(self) -> None:
        """Removes incomplete entry if complete entry exists.

        Fixes a potential issue where both complete and incomplete data both exist for a
        number.  This could occur if we add the complete version first and then the program
        terminates before removing the incomplete entry.  
        """

        update_entry = 'SELECT num FROM incomplete'
        data = self.sql.select_all(update_entry)
        count = 0
        for item in data:
            num = int(item[0])
            count += 1
            if self.has_data(num, True):
                self.delete_incomplete(num)

    def get_incomplete(self) -> list[tuple[int, int]]:
        """Gets the list of incompletely factored entries.

        An incomplete entry corresponds to the end of an open sequence, so to get the list of
        all open sequences we can simply get the table of incomplete entries.
        
        Returns:
            List of pairs with base being the sequence and num the final unfactored number.
        """

        update_entry = 'SELECT sequence_number,num FROM incomplete order by sequence_number'
        data = self.sql.select_all(update_entry)
        pairs = [(int(item[0]), int(item[1])) for item in data]
        return pairs

    def get_incomplete_base(self) -> list[int]:
        """Gets a list of open sequences.

        This is like get_incomplete except it is just a list of the base sequence that is open.
        
        Return:
            List of numbers for open sequences.
        """

        update_entry = 'SELECT sequence_number FROM incomplete order by sequence_number'
        data = self.sql.select_all(update_entry)
        pairs = [int(item[0]) for item in data]
        return pairs

    def delete_incomplete(self, num: int) -> None:
        """Delete an entry from the incomplete table.

        When we know the factors we add it to the complete table and delete the incomplete 
        entry from the incomplete table.
        
        Args:
            num: The number to be deleted from the incomplete table.
        """

        if not isinstance(num, int):
            logger.critical('Number is not int: %s.', num)
            raise TypeError(f'Number must be an int, received {type(num).__name__}')
        update_entry = 'DELETE FROM incomplete WHERE num = %s;'
        self.sql.execute(update_entry, (num, ))

    def get_all_digit_table(self, digits: int) -> list[tuple[int, int, int, str]] | None:
        """For 11 to 99 digits, get a list of existing numbers

        Numbers in the range of 11 to 99 digits are stored based on their number of digits.
        It is therefore easy to return all numbers with a given number of digits.

        Returns:
            List of tuples with the number, sequence, aliquot sum, and factor string
        """

        if not isinstance(digits, int):
            logger.critical('Digits is not int: %s.', digits)
            raise TypeError(f'Digits must be an int, received {type(digits).__name__}')
        if digits < 11 or digits > 99:
            print(f'Digits {digits} is not between 11 and 99')
            return None
        get_entry = ('SELECT sequence_number,num,aliquot_sum, factor_string FROM '
                     f'digits_{digits} order by sequence_number')
        data = self.sql.select_all(get_entry)
        # tuple is (num, seq, alq_sum, factor_string)
        tuples = [(int(item[1]), int(item[0]), int(item[2]), item[3]) for item in data]
        return tuples

    def _get_table_name(self, num: int) -> str:
        """Get the table name to store a given number
        
        The table to store a number in is determined by its size.  The tables are arranged so
        they are likely to have no more than 50 million numbers. Once numbers reach 11 digits,
        they gets stored based on the number of digits. Above 99 digits is currently a single table.
        
        This is for complete numbers.  Numbers whose factors are not fully known get stored together
        in the single incomplete table.

        Args:
            num: The number to be found in the postgres tables.
        Returns:
            The name of the table for that number.
        """

        if not isinstance(num, int):
            logger.critical('Number is not int: %s.', num)
            raise TypeError(f'Number must be an int, received {type(num).__name__}')
        str_num: str = str(num)
        digits:int = len(str_num)
        if digits >= 100:
            table_name = 'plus100'
        elif digits >= 11:
            # Very large numbers go into a table based on the digits
            table_name = f'digits_{str(len(str_num))}'
        elif num <  10**9:
            # A table for each 50 million (0 to 19)
            index = num // (5 * 10**7)
            table_name = f'alq_{index}'
        elif num < 4*10**9:
            # A table for each 100 million (10 to 39)
            index = num // (10**8)
            table_name = f'alqg_{index}'
        else:
            # A table for each billion
            index = num // (10**9)
            table_name = f'alq4g_{index}'
        return table_name

    def add_tables(self, digits: bool, stats: bool, status: bool) -> None:
        """Code to initially add the tables to postgres
        
        This function was called early on to add the tables to postgres.  It has undergone changes
        since then so there is no guarantee it is still accurate, so should be tested first.
        
        Args:
            digits: If True add the main tables for aliquot series.
            stats: If True add the stats table for statistics on each series.
            status: If True add the status table that holds series statuses.
        """

        if stats:
            self.sql.add_stats_table('stats')
        if status:
            self.sql.add_status_table('status')
        if digits:
            tables: list[TableNameData] = []
            tables.append({
                'name': 'incomplete',
                'size': None
            })
            tables.append({
                'name': 'plus100',
                'size': None
            })
            for digit in range(11, 100):
                tables.append({
                    'name': f'digits_{digit}',
                    'size': digit
                })
            for index in range(0, 20):
                tables.append({
                    'name': f'alq_{index}',
                    'size': 9
                })
            for index in range(10, 40):
                tables.append({
                    'name': f'alqg_{index}',
                    'size': 10
                })
            for index in range(4, 10):
                tables.append({
                    'name': f'alq4g_{index}',
                    'size': 10
                })
            for table in tables:
                self.sql.add_alq_table(table['name'], table['size'])

    def get_status_data(self, seq: int):
        """Get the status data for a given sequence

        The status is used for verification and whether the remote factor db has all
        the information on a seires.  There is other information as well.

        See the aliquot_status.py file for how status data is used.

        Args:
            seq: The sequence to get data for.
        Returns:
            Status data for the given sequence from postgres.
        """

        if not isinstance(seq, int):
            logger.critical('Sequence is not int: %s.', seq)
            raise TypeError(f'Sequence must be an int, received {type(seq).__name__}')
        table_name = 'status'
        select = ('SELECT sequence_number, verified, timestamp, elg_update, stats_update, '
                  'open_ended, elf_update, extend_update, localdb_update, factordb, '
                  f'factor_update FROM {table_name} WHERE sequence_number = %s;')
        raw_data = self.sql.select_one(select, (seq,))
        if not raw_data:
            return None
        data = {
            'sequence_number': int(raw_data[0]),
            'verified': raw_data[1],
            'timestamp': raw_data[2],
            'elg_update': raw_data[3],
            'stats_update': raw_data[4],
            'open_ended': raw_data[5],
            'elf_update': raw_data[6],
            'extend_update': raw_data[7],
            'localdb_update': raw_data[8],
            'factordb': raw_data[9],
            'factor_update': raw_data[10]
        }
        return data

    def _has_status_data(self, seq: int) -> bool:
        """Whether status data exists.

        Status data already exists for all sequences up to 40 million.  This will be
        extended if to 50 million in the future.

        Args:
            seq: The sequence to check status for.
        Returns:
            True if the sequence is in the status table.
        """

        data = self.get_status_data(seq)
        if data:
            return True
        return False

    def set_status_data(self, data: StatusData) -> None:
        """Sets the status data
        
        Unlike the main tables there is no separate insert and update.  Both cases are handled.
        
        Args:
            data: Mapp with the status to update postgres to.
        """

        table_name = 'status'
        seq = data['sequence_number']
        if not isinstance(seq, int):
            logger.critical('Sequence is not int: %s.', seq)
            raise TypeError(f'Sequence must be an int, received {type(seq).__name__}')
        if seq  < 1:
            print('Attempt to add zero to data skipped(set_status_data)')
            return
        if self._has_status_data(seq):
            update_entry = (f'UPDATE {table_name} '
                            'SET sequence_number = %s, verified = %s, timestamp = current_timestamp'
                            ', elg_update = %s, stats_update = %s, open_ended = %s, '
                            'elf_update = %s, extend_update = %s, localdb_update = %s, '
                            f'factordb = %s, factor_update = %s WHERE sequence_number = %s;')
            self.sql.insert(update_entry, (seq, data['verified'], data['elg_update'],
                                           data['stats_update'], data['open_ended'],
                                           data['elf_update'], data['extend_update'],
                                           data['localdb_update'],  data['factordb'],
                                           data['factor_update'], seq))
        else:
            update_entry = (f'INSERT INTO {table_name} VALUES (%s, %s, current_timestamp, %s, %s, '
                            '%s, %s, %s, %s, %s, %s);')
            self.sql.insert(update_entry, (seq, data['verified'], data['elg_update'],
                                           data['stats_update'], data['open_ended'],
                                           data['elf_update'], data['extend_update'],
                                           data['localdb_update'],  data['factordb'],
                                           data['factor_update']))
