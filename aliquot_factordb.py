#!/usr/bin/env python

""" Handles accessing the remote factordb database for factorization.

The remote database stores known factorization of numbers for many projects and includes 
the aliquot series as well.  Work by others is uploaded there.  To keep the local database
up to date means fetching updates to series. Also extending series locally can be uploaded
for others.

There is an optional environmental variable FDB_COOKIE.  If this exists it is added to the
curl call.  If a user has a cookie from the remote site, setting FDB_COOKIE in the environment
will successfully use it.  If it fails to load the calls are made without using any cookie.

Class:
Aliquot
"""

import os
import re
import time
import json
import logging
import shutil
from pathlib import Path
import subprocess
#from factordb.factordb import FactorDB
import aliquot_util
from aliquot_data import AliquotData

logger = logging.getLogger(__name__)

class AliquotFactorDB():
    """Handles access to remove FactorDB database"""

    def __init__(self, sql):
        """sets cookie for FactorDB site.

        Attributes:
            cookie: FDB_COOKIE environmental variable.
        """

        self.cookie=os.environ.get('FDB_COOKIE')
        self.aliquot_data = AliquotData(sql)

    def find_factors(self, num_to_factor, index, seq, error_file = None):
        """Returns factors of a number from the remove FactorDB.

        seq and index are used for printing/logging.
        error_file exists to gather information on a type of error found in
        the FactorDB.  

        Args:
            num_to_factor: The number to factor as a string or int.
            index: Index in the sequence for num_to_factor
            seq: Sequence containing num_to_factor
            error_file: Optional file to list factor errors.
        Returns:
            Factor information if fully factored, otherwise None
        """

        status = ''
        data = None
        # Make sure we have an integer.
        num = int(num_to_factor)
        #Try 5 times to get valid data before failing.
        for _ in range(0, 5):
            if self.cookie:
                cmd_array = (['curl', '--cookie', f'{self.cookie}', '-s',
                              f'http://factordb.com/api?query={num}'])
            else:
                cmd_array = (['curl', f'http://factordb.com/api?query={num}'])
            try:
                output = subprocess.run(cmd_array, timeout=60, capture_output=True, text=True,
                                        check=False)
                if output.returncode == 0 and output.stdout and output.stdout[0]=='{':
                    data = json.loads(output.stdout)
                    break
            except subprocess.TimeoutExpired:
                print(f'Timeoutfor {seq}')
                #With the timeout we have 20 seconds for each timeout to give time to recover.
                time.sleep(20)
        if data:
            status = data['status']
            if status == 'FF':
                factors = data['factors']
                return factors
        else:
            #This is an error case where the factordb doesn't return valid data.
            print(f'Not able to reach db for {seq} at {num}')
            if error_file:
                error_file.write(f'Sequence: {seq}, index: {index}, number: {num} - '
                                 'query failed.\n')
                error_file.flush()

        return None

    def check_is_factored(self, num):
        """Returns if the number comes back as factored.

        seq and index are used for printing/logging.
        error_file exists to gather information on a type of error found in
        the FactorDB.  

        Args:
            num: The number to factor
        Returns:
            True if the number is factored (on first try).
        """

        if self.cookie:
            cmd_array = (['curl', '--cookie', f'{self.cookie}', '-s',
                          f'http://factordb.com/api?query={num}'])
        else:
            cmd_array = (['curl', f'http://factordb.com/api?query={num}'])
        data = None
        try:
            output = subprocess.run(cmd_array, timeout=60, capture_output=True, text=True,
                                    check=False)
            if output.returncode == 0 and output.stdout and output.stdout[0]=='{':
                data = json.loads(output.stdout)
        except subprocess.TimeoutExpired:
            return False
        if data:
            status = data['status']
            if status == 'FF':
                print('+',end='',flush=True)
                return True
        return False

    def find_existing_cmp_file_lines(self, seq):
        """Finds the number of lines if the cmp file already exists

        Uses regex to see if lines are valid for an elf file.  html will therefore return 0.
        
        Args:
            seq: The sequence to check
        Returns:
            A non-negative value if the cmp file exists.  Otherwise None is returned.
        """
        cmp_file_name = self._get_cmp_file_name(seq)
        return self._find_file_lines(cmp_file_name)

    def _find_file_lines(self, file_name):
        """Lines in the file name.

        Loads as utf8 because factordb sends errors this way

        Args:
           file_name: The file to count lines for.
        """

        line_count = None
        if Path(file_name).is_file():
            with open(file_name, encoding='utf8') as in_file:
                lines = in_file.readlines()
                if len(lines) > 0 and aliquot_util.is_valid_elf_line(lines[-1]):
                    #Assumption: if last line is ok, the rest are likely good as well.
                    #Speed is more important than full error checking for comparison.
                    line_count = len(lines)
                else:
                    #Likely returns 0 as the file is html, possibly an error, or empty.
                    line_count = 0
                    for line in lines:
                        if aliquot_util.is_valid_elf_line(line):
                            line_count += 1
        return line_count

    def find_last_index(self, seq, local_lines, get_allowed):
        """Finds the last file index.

        Will check for the existing last file index first. If get_allowed is true, and
        the last index + 1 is less than local_lines, then we get an updated last index.
        Note that the remote site is up to date if last_index + 1 is greater than or equal
        to the local_lines.

        Args:
            seq: The sequence to test.
            local_lines: The number of lines in the elf or elg file locally.
            get_allowed: If True we call get if the last index is short, False means no get done.
        Returns:
            Returns the index which is one less than number of lines since index is zero based.
        """

        index = self._find_last_index_noget(seq)
        if get_allowed and (not index or index + 1 < local_lines):
            index = self._find_last_index_get(seq)
        return index

    def find_cmp_file_lines_get(self, seq):
        """Finds the number of lines of the most recent cmp file

        Uses regex to see if lines are valid for an elf file.  html will therefore return 0.
        
        Args:
            seq: The sequence to check
        Returns:
            Existing value or value of the get whichever is greater.  Otherwise None is returned.
        """

        wget_file_name = self._get_wget_file_name(seq)
        cmp_file_name = self._get_cmp_file_name(seq)
        self._fetch_wget_file(seq, wget_file_name)
        wget_lines = self._find_file_lines(wget_file_name)
        cmp_lines = self._find_file_lines(cmp_file_name)
        if wget_lines is not None:
            if cmp_lines is None or wget_lines > cmp_lines:
                print(f'For {seq} update cmp: {cmp_lines}=>{wget_lines}')
                shutil.copy(wget_file_name, cmp_file_name)
                return wget_lines
        return cmp_lines

    def _get_cmp_file_name(self, seq):
        """Gets the name of the cmp file

        Located in cmp_# instead of elf_# or elg_#.  Becomes less reliable when
        sequence is very long.  Has the normal .elf extension
        
        Args:
           seq: The sequence number.
        Returns:
           The file name to use.
        """

        subd = seq // 1000000
        cmp_name = f'cmp_{subd}/alq_{seq}.elf'
        return cmp_name

    def _get_last_cmp_file_name(self, seq):
        """Gets the name of the last index file

        Faster to get a single line that indicates extent of the factordb.
        The downside is we need to extract the data from html format.

        Located in cmp_# instead of elf_# or elg_# with extension .last
        
        Args:
           seq: The sequence number.
        Returns:
           The file name to use.
        """

        subd = seq // 1000000
        last_name = f'cmp_{subd}/alq_{seq}.last'
        return last_name

    def _get_wget_file_name(self, seq):
        """Gets the name of the wget file

        Located in cmp_# instead of elf_# or elg_# with extension .wget
        When attempt to get the full elf from the remote site it is sent here.
        That way an error doesn't overwrite an existing valid compare file.
        
        Args:
           seq: The sequence number.
        Returns:
           The file name to use.
        """

        subd = seq // 1000000
        wget_name = f'cmp_{subd}/alq_{seq}.wget'
        return wget_name

    def _fetch_wget_file(self, seq, wget_name):
        """Call to get the file with the given name from the remote database.

        Args:
            seq: The sequence to fetch.
            cmp_name: File name to put the fetched data.
        """

        done = False
        while not done:
            for _ in range(0,5):
                try:
                    if self.cookie:
                        cmd_array = (['curl', '--cookie', f'{self.cookie}', '-s', '-o', wget_name,
                                      f'http://factordb.com/elf.php?seq={seq}&type=1'])
                    else:
                        cmd_array = (['curl', '-s', '-o', wget_name,
                                      f'http://factordb.com/elf.php?seq={seq}&type=1'])
                    result = subprocess.run(cmd_array, timeout=120, check=False)
                    if result.returncode:
                        logging.error('Error: %s', result.stderr)
                        print(f'Error occurred in fetch: {result.stderr}')
                        time.sleep(2)
                    else:
                        time.sleep(10)
                        done = True
                        break
                except subprocess.TimeoutExpired:
                    print(f'For{seq}, wget timed out')
                    time.sleep(120)

    def fetch_last_file(self, seq, last_name):
        """Call to get the last line of an aliquot series

        Args:
            seq: The sequence to fetch.
            last_name: File name to put the fetched data.
        """

        done = False
        while not done:
            for _ in range(0,5):
                try:
                    if self.cookie:
                        cmd_array = (['curl', '--cookie', f'{self.cookie}', '-s', '-o', last_name,
                                      (f'http://factordb.com/sequences.php?se=1&aq={seq}'
                                       '&action=last')])
                    else:
                        cmd_array = (['curl', '-s', '-o', last_name,
                                      (f'http://factordb.com/sequences.php?se=1&aq={seq}'
                                       '&action=last')])
                    result = subprocess.run(cmd_array, timeout=60, check=False)
                    if result.returncode != 0:
                        logging.error('Error: %s', result.stderr)
                        print(f'Fetch last file failed with {result.stderr}')
                        time.sleep(2)
                    else:
                        done = True
                        break
                except subprocess.TimeoutExpired:
                    print(f'For{seq}, wget last timed out')
                    time.sleep(120)

    def _extract_index(self, lines):
        """Extract the last index from the html returned for a last index call.

        This if dependent on the remote site returning an expected format.  If the format
        changes, this function would need updating.

        Args:
            lines: The lines from the last index file.
        Returns:
            The index if found.  Otherwise none.
        """

        count = 0
        found = False
        index = ''
        num_line = len(lines)
        for line in lines:
            count += 1
            if 'Number' in line:
                num_line = count
            if count == num_line + 2:
                if '<td' in line:
                    parts1 = line.split('>')
                    if len(parts1) > 1:
                        parts2 = parts1[1].split('<')
                        index = parts2[0]
                        found = True
                break
        if found:
            return index
        return None

    def _find_last_index_get(self, seq):
        """Gets the last index of the series from the remote FactorDB site.

        Gets the last index as html and extracts the index if it exists.
        Errors can occur with the fetch in which case the index won't be found.

        Args:
            seq: The sequence to find the remote last index for.
        Returns:
            The integer found to be the final index for the remote sequence, otherwise None.
        """

        last_name = self._get_last_cmp_file_name(seq)
        self.fetch_last_file(seq, last_name)
        if Path(last_name).is_file():
            with open(last_name, encoding='utf8') as file:
                lines = file.readlines()
                index = self._extract_index(lines)
                if index:
                    num_type = r'^\d+$'
                    if re.search(num_type, index):
                        return int(index)
        return None

    def _find_last_index_noget(self, seq):
        """Gets the last index if it has been downloaded previously.

        Will not access the remote site.

        Args:
            seq: The sequence to find the remote last index for.
        Returns:
            The integer found to be the final index for the remote sequence, otherwise None.
        """

        last_name = self._get_last_cmp_file_name(seq)
        if Path(last_name).is_file():
            with open(last_name, encoding='utf8') as file:
                lines = file.readlines()
                index = self._extract_index(lines)
                if index:
                    num_type = r'^\d+$'
                    if re.search(num_type, index):
                        return int(index)
        return None

    def send_factor_line(self, chunk):
        """Send factorization data to the remote site.

        This reports the factorization for a number.  All work locally to extend sequences
        gets sent on to the remote site has the information as well.
        Note that smaller factors don't need to be sent.

        Args:
            Chunk: Contains the number and the (larger) factors.
        Returns:
            True line was sent successully.
        """

        number = chunk['number']
        count = 0
        html_factor_string = ''
        for factor in chunk['factors']:
            count += 1
            if count == 1:
                html_factor_string += f'&factor={factor}'
            else:
                html_factor_string += f'&factor{count}={factor}'
        if self.cookie:
            cmd_array = (['curl', '-X', 'POST', '--cookie', f'{self.cookie}',
                          'https://factordb.com/reportfactor.php',
                          '-d', f'number={number}{html_factor_string}', '-s', '-o',
                          'curl.log'])
        else:
            cmd_array = (['curl', '-X', 'POST', 'https://factordb.com/reportfactor.php',
                          '-d', f'number={number}{html_factor_string}', '-s', '-o',
                          'curl.log'])
        done = False
        count = 0
        while not done:
            try:
                result = subprocess.run(cmd_array, check=True)
                done = True
            except subprocess.TimeoutExpired:
                print('Send Timout')
                time.sleep(20)
            except subprocess.CalledProcessError as e:
                # Triggered because check=True encountered a non-zero exit code
                print(f"Command failed with exit code: {e.returncode}")
                print(f"Error message output: {e.stderr}")
            count += 1
            if count == 3:
                return False
        return result.returncode == 0

    def send_factor_chunks(self, chunks):
        """Send multiple lines of factor data

        Args:
            chunks: A list of chunks
        """
        count = 0
        for chunk in chunks:
            self.send_factor_line(chunk)
            count += 1
            if count % 30 == 0:
                print('.', end='', flush=True)
        print('')


    def check_factors(self, num, seq):
        """Checks if we get back data from the remote site.

        This is due to an error where the remote site returns nothing for some factors.
        A program exists to find these cases.

        Args:
            num: The number to check
            seq: The sequence (used in timout warning).
        Returns:
            Returns true if (any) data exists and got returned.
        """

        data = None
        for _ in range(0, 5):
            if self.cookie:
                cmd_array = (['curl', '--cookie', f'{self.cookie}', '-s',
                              f'http://factordb.com/api?query={num}'])
            else:
                cmd_array = (['curl', f'http://factordb.com/api?query={num}'])
            try:
                output = subprocess.run(cmd_array, timeout=60, capture_output=True, text=True,
                                        check=True)
                if output.returncode == 0 and output.stdout and output.stdout[0]=='{':
                    data = json.loads(output.stdout)
                    break
            except subprocess.TimeoutExpired:
                print(f'Timeoutfor {seq}')
                #With the timeout we have 3 minutes for each timeout to give time to recover.
                time.sleep(120)
        return bool(data)

    def process_seq(self, seq, is_elg, is_processed = False):
        """Process a single sequence.

        Args:
            seq: The sequence to process.
            is_processed: Whether we have sent all values yet.  If so we just send the missing one.
        """

        up_to_date = False
        subd = seq // 1000000
        file_name = f'elg_{subd}/alq_{seq}.elg' if is_elg else f'elf_{subd}/alq_{seq}.elf'
        if not Path(file_name).is_file():
            #No longer elf file (when extending sequences this could occur)
            return True
        local_lines = aliquot_util.get_line_count(file_name)
        cmp_name = f'cmp_{subd}/alq_{seq}.elf'
        cmp_lines = self.find_existing_cmp_file_lines(seq)
        if cmp_lines and cmp_lines >= local_lines:
            print(f'already up to date for {seq}')
            return True
        call_count = 0
        done = False
        while not done:
            last_index = self.find_last_index(seq, local_lines, True)
            if last_index and last_index + 1 >= local_lines:
                shutil.copy(file_name, cmp_name)

                print(f'Can skip {seq}')
                return True
            print(f'No skip {seq}')
            if not last_index:
                cmp_lines = self.find_cmp_file_lines_get(seq)
                if cmp_lines > local_lines:
                    return True
            else:
                if not cmp_lines or last_index > cmp_lines:
                    cmp_lines = last_index

            call_count += 1
            if call_count > 6:
                time.sleep(60)
                print(f'For {seq} Reached max calls')
                break
            if cmp_lines is None:
                cmp_lines = 0
            if cmp_lines == 0:
                time.sleep(30)
                print(f'{cmp_name} was empty')
            elif local_lines > cmp_lines:
                if is_processed:
                    print('Processed already: adding line that failed')
                else:
                    print(f'cmp is {cmp_lines}; elf/elg is {local_lines}')
                print(f'{seq}',end='',flush=True)
                chunks = self._get_line_chunks(seq, cmp_lines, is_processed)
                count = 1
                for chunk in chunks:
                    if count % 10 == 0:
                        print('.',end='',flush=True)
                    if not self.check_is_factored(chunk['number']):
                        self.send_factor_line(chunk)
                        count += 1
                print('')
                done = True
            else:
                done = True
                print(f'up to date for {seq}')
                up_to_date = True
        return up_to_date

    def _get_line_chunks(self, seq, start, is_processed):
        """Get factoring chunks to send to remote site.

        Args:
            seq: The sequence to get.
            start: What index to start at
            is_processed: If True we sent the lines before so send the current missing line.
        """

        chunks = []
        values = {}
        done = False
        curr = seq
        index = 0
        while not done:
            values[curr] = True
            data = self.aliquot_data.select_data(curr, True)
            if not data:
                # At end
                done = True
                continue
            if is_processed:
                if index == start:
                    factor_strings = data['factor_string'].split('*')
                    chunk = {}
                    print(f'at {index}')
                    chunk['number'] = data['num']
                    chunk['index'] = index
                    chunk['factors'] = self._get_larger_factors(factor_strings, 6)
                    if len(chunk['factors']) >= 1:
                        chunks.append(chunk)
                    done = True
            elif index >= start - 1 and len(str(data['num'])) >= 40:
                factors = aliquot_util.to_factors(data['factor_string'])
                chunk = {}
                chunk['number'] = data['num']
                chunk['index'] = index
                chunk['factors'] = aliquot_util.get_larger_factors(factors, 12)
                if len(chunk['factors']) >= 1:
                    chunks.append(chunk)
            index += 1
            curr = data['aliquot_sum']
            if curr == 1 or curr == 0 or curr in values or seq != data['base']:
                done = True
        if index < start:
            print(f'Error with {seq}: elf file may be longer than internal db. Try '
                  f'"python3 alq_verify.py {seq} {seq}".')
        return chunks

    def _get_larger_factors(self, factor_strings, size):
        """Get factors with of a certain size

        Args:
            factor_strings: A list of factor strings that might have a power (^)
            size: The minimum number of digits to include the factor.
        """

        factors = []
        for factor in factor_strings:
            if len(factor) >= size:
                if '^' in factor:
                    factors.append(factor.split('^')[0])
                else:
                    factors.append(factor)
        return factors
