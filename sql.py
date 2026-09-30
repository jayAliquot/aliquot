#!/usr/bin/env python

""" Handles the sql to add entries

postgres is used to hold all factor information for the aliquot series.  These functions are
called in aliquot_data.py (only).  They are specific to the aliquot project with the db name
 hardcoded.
"""

import sys
import logging
import psycopg2

logger = logging.getLogger(__name__)

class SQL:
    """The calls to the postgres db for aliquot series"""

    def __init__(self):
        """Initializes subclasses used.

        Attributes:
            connect: Used to call commit after sql call done.
            cursor: Used to call postgres execute, fetchall, and fetchone
        """

        try:
            self.connect = psycopg2.connect(
                dbname='aliquot',user='jay', host='/var/run/postgresql/', port=5433)
        except psycopg2.DatabaseError as e:
            print(f"Error connecting to the postgres: {e}")
            sys.exit(1)
        self.cursor = self.connect.cursor()

    def has_alq_table(self, table_name):
        """Whether the given table exists.

        Args:
            table_name: The name of the table to check.
        """

        show_tables = 'select tablename from pg_catalog.pg_tables;'
        self.cursor.execute(show_tables)
        data = self.cursor.fetchall()
        for item in data:
            if item[0] == f'{table_name}':
                return True
        return False

    def add_alq_table(self, table_name, size):
        """Adds a table holding factors.

        Because the tables are sorted based on the number of digits we can
        send in an maximum size for each entry that is often exact.  Note that
        the aliquot sum can be up to 1 digit more.

        Args:
            table_name: The name of the table to add.
            size: The maximum size of num.
        """

        if table_name in ('incomplete', 'plus100'):
            #The numbers can be 200+ digits so no limit imposed.
            num = 'num decimal PRIMARY KEY'
            aliquot = ', aliquot_sum decimal'
        else:
            num = f'num decimal({size}) PRIMARY KEY'
            aliquot = f', aliquot_sum decimal({size+1})'
        seq = ', sequence_number integer'
        index = ', sequence_index integer'

        factor = ', factor_string varchar(255)'
        if table_name == 'incomplete':
            unfactor = ', unfactored decimal'
            create_table = (f'CREATE TABLE IF NOT EXISTS {table_name} ({num}{seq}{index}{aliquot}'
                            f'{factor}{unfactor});')
        else:
            create_table = (f'CREATE TABLE IF NOT EXISTS {table_name} ({num}{seq}{index}{aliquot}'
                            f'{factor});')
        print(create_table)
        self.cursor.execute(create_table)
        self.connect.commit()

    def add_stats_table(self, table_name):
        """Adds a table holding basic statistical information for each sequence

        Args:
            table_name: The name of the table to add
        """

        seq = 'sequence_number integer PRIMARY KEY'
        base = ', base integer'
        num = ', num decimal'
        index = ', sequence_index integer'
        stats_string = ', stats_string varchar(255)'
        complete = ', complete boolean'
        maxd = ', max_digits integer'
        create_table = (f'CREATE TABLE IF NOT EXISTS {table_name} ({seq}{base}{num}{index}'
                        f'{stats_string}{complete}{maxd});')
        print(create_table)
        self.cursor.execute(create_table)
        self.connect.commit()

    def add_status_table(self, table_name):
        """Adds a table holding the status for each sequence

        Args:
            table_name: The name of the table to add
        """

        seq = 'sequence_number integer PRIMARY KEY'
        ver = ', verified boolean'
        time = ', timestamp TIMESTAMP WITH TIME ZONE'
        elg = ', elg_update boolean'
        stats = ', stats_update boolean'
        open_ended = ', open_ended boolean'
        elf = ', elf_update boolean'
        ext = ', extend_update boolean'
        local = ', localdb_update boolean'
        self.add_type('fdb_status', ['NA', 'up_to_date', 'fast_check', 'update_needed',
                                     'fast_check_update', 'unchecked_update', 'unchecked'])
        fdb = ', factordb fdb_status'
        factor = ', factor_update boolean'
        create_table = (f'CREATE TABLE IF NOT EXISTS {table_name} ({seq}{ver}{time}{elg}{stats}'
                        f'{open_ended}{elf}{ext}{local}{fdb}{factor});')
        print(create_table)
        self.cursor.execute(create_table)
        self.connect.commit()

    def add_statistics_tables(self):
        """Adds a table holding advanced statistical information for each sequence

        These tables hold driver and merge information within the sequences.
        The single_step gives ratios between sequence elements and factor count
        gives a count of the number of factors found.
        """

        self.add_sequence_merge_table()

        # Centralized dictionary for SQL schema definitions
        stat_schemas = {
            'driver_run': ('sequence_number integer, start_index integer, start_digits integer, '
                           'start_num decimal, end_index integer, end_digits integer, '
                           'end_num decimal, end_factors VARCHAR, driver_uid integer, '
                           'next_driver integer, PRIMARY KEY (sequence_number, start_index)'),
            'merge_run': ('sequence_number integer PRIMARY KEY, start_index integer, '
                          'start_digits integer, start_num decimal, end_index integer, '
                          'end_digits integer, end_num decimal, merge_sequence integer, '
                          'merge_index integer, driver_uid integer'),
            'merge_single': ('sequence_number integer PRIMARY KEY, start_index integer, '
                             'start_digits integer, start_num decimal, end_index integer, '
                             'end_digits integer, end_num decimal, merge_sequence integer, '
                             'merge_index integer, driver_uid integer'),
            'open_run': ('sequence_number integer PRIMARY KEY, start_index integer, '
                         'start_digits integer, start_num decimal, end_index integer, '
                         'end_digits integer, end_num decimal, driver_uid integer'),
            'no_driver_run': ('sequence_number integer, start_index integer, start_digits integer, '
                              'start_num decimal, prev_driver integer, end_index integer, '
                              'end_digits integer, end_num decimal, next_driver integer, '
                              'PRIMARY KEY (sequence_number, start_index)'),
            'single_step': ('digits integer, driver_uid integer, next_driver integer, '
                            'count integer, max_ratio real, min_ratio real, ratio_sum real, '
                            'PRIMARY KEY (digits, driver_uid, next_driver)'),
            'factor_count': ('digits integer, driver_uid integer, num_factors integer, '
                             'count integer, PRIMARY KEY (digits, driver_uid, num_factors)')
        }

        # Execute creation dynamically
        for table_name, schema in stat_schemas.items():
            create_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema});"
            print(create_query)
            self.cursor.execute(create_query)

        self.connect.commit()

    def add_sequence_merge_table(self):
        """Adds a table keeping track of merges when the occur"""

        table_name = 'sequence_merge'
        index_name = 'merge_into'
        from_seq = 'merge_from_sequence integer PRIMARY KEY'
        from_index = ', merge_from_index integer'
        to_seq = ', merge_to_sequence integer'
        to_index = ', merge_to_index integer'
        before = ', num_before_merge decimal'
        after = ', num_after_merge decimal'
        proc = ', processed boolean'
        create_table = (f'CREATE TABLE IF NOT EXISTS {table_name} ({from_seq}{from_index}{to_seq}'
                        f'{to_index}{before}{after}{proc});')
        print(create_table)
        self.cursor.execute(create_table)
        create_index = (f'CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} '
                        '(merge_to_sequence);')
        print(create_index)
        self.cursor.execute(create_index)

    def add_type(self, in_type, values):
        """Adds the status type as an enum into the db

        Args:
            in_type: The type to create.
            values: The possible values of the enum.
        """

        exec_string = f'CREATE TYPE {in_type} AS ENUM ('
        first = True
        for value in values:
            if first:
                exec_string += f"'{value}'"
                first = False
            else:
                exec_string += f", '{value}'"
        exec_string += ');'
        print(exec_string)
        self.cursor.execute(exec_string)

    def select_all(self, select_string):
        """Returns all selections

        Args:
            select_string: The sql call for the selection
        """

        self.cursor.execute(select_string)
        data = self.cursor.fetchall()
        return data

    def select_one(self, select_string, in_data):
        """Returns one selection

        Args:
            select_string: The sql call for the selection
        """

        self.cursor.execute(select_string, in_data)
        data = self.cursor.fetchone()
        return data

    def insert(self, insert_string, data):
        """Inserts a new element

        Args:
            insert_string: The string to insert the data.
            data: The data to insert.
        """

        self.cursor.execute(insert_string, data)
        self.connect.commit()

    def execute(self, execute_string, data=None):
        """Execute with or without associated data

        Used for deleting obsolete incomplete entries
        """
        if data:
            self.cursor.execute(execute_string, data)
        else:
            self.cursor.execute(execute_string)
        self.connect.commit()

    def close(self):
        """Close the postgres connection"""

        self.connect.close()
