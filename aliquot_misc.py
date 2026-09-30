#!/usr/bin/env python

"""Miscellaneous functions dealing with aliquot series.

These didn't really fit into the other categories and are left over from splitting aliquit.py.
"""

import sys
import logging
from pathlib import Path

from aliquot_types import AlqData
from aliquot_data import AliquotData
from aliquot_status import AliquotStatus
from aliquot_statistics import AliquotStatistics
import aliquot_util

logger = logging.getLogger(__name__)

class AliquotMisc:
    """Main aliquot class

    The different functions are called from python runnable programs starting with
    alq_*.py to do the many things possible.
    """

    def __init__(self, sql):
        """Initializes subclasses used.

        Args:
            sql: postgres sql connection.
        
        Attributes:
            aliquot_data: Class to get and set local db data.
            aliquot_status: Class that sets status information.
            aliquot_statistics: Class that figures out run statistics.
            open_list: The list of open sequences.
        """


        self.aliquot_data = AliquotData(sql)
        self.status = AliquotStatus(sql)
        self.statistics = AliquotStatistics(sql)
        self.open_list = None

    def calc_seq_persistence(self, seq, limit):
        """Outputs prine persistence for a sequence.

        Used to study how primes persist within a sequence. The number
        of digits is also tracked with d+ or d- output when the digits change.

        For the limit, a smaller value means more changes occur.  A new line is started
        whenever the primes change, so this means more lines get printed.  A larger value
        only outputs the more persistent primes.  The power of a prime is only printed if
        the power has also remained unchanged for limit steps.

        Args:
            seq: The sequence to list.
            limit: how long a prime must last before it is tracked.  Larger
                numbers will only track longer lived drivers primes.  For lower
                values non-driver primes will become more frequent.
        """

        curr = seq
        done = False
        prev_persist = {}
        prev_factors = []
        curr_output = ''
        prev_digits = 0
        while not done:
            data:AlqData | None = self.aliquot_data.select_data(curr, True)
            if data:
                index = data['index']
                alq = data['aliquot_sum']
                digits = len(str(curr))
                curr_persist = self._calc_prime_persistence(prev_persist, data['factor_string'])
                curr_factors = []
                persist_string = ''
                counter_string = ''
                self._calc_persist_string(curr_persist, curr_factors, persist_string,
                                          counter_string, limit)
                if set(curr_factors) != set(prev_factors):
                    if curr_output != '':
                        print(curr_output)
                    curr_output = (f'Index: {index}, Digits: {digits} {persist_string} '
                                   f'{counter_string}')
                else:
                    if digits != prev_digits:
                        if digits > prev_digits:
                            curr_output += 'd+'
                        else:
                            curr_output += 'd-'
                    else:
                        curr_output += '.'
                curr = alq
                prev_persist = curr_persist
                prev_factors = curr_factors
                prev_digits = digits
            else:
                done = True
                print(curr_output)
                data:AlqData | None = self.aliquot_data.select_data(curr, False)
                if data and data['factor_string']:
                    index = data['index']
                    digits = len(str(data['num']))
                    factors = data['factor_string']
                    print(f'Final - Index: {index}, Digits: {digits}, Known Factors: {factors}')

    def _calc_prime_persistence(self, prev_persist, factor_string):
        """Helper funtion for the prime persistance above

        Args:
        prev_persist: a dict with tuples for each prime.
            first element is steps the prime has been a factor
            second element is the power of the prime
            third element is the steps the prime has been at the same power.
        factor_string: The current factorization to check against previous persistence.

        Return:
            Returns the current dict with tuples for each prime
        """

        factors = aliquot_util.to_factors(factor_string)
        persist = {}
        for prime in factors:
            if prime in prev_persist:
                curr_tuple = prev_persist[prime]
                if curr_tuple[1] == factors[prime]:
                    persist[prime] = (curr_tuple[0]+1, curr_tuple[1], curr_tuple[2]+1)
                else:
                    persist[prime] = (curr_tuple[0]+1, factors[prime], 1)
            else:
                persist[prime] = (1, factors[prime], 1)
        return persist

    def _calc_persist_string(self, curr_persist, curr_factors, persist_string,
                             counter_string, limit):
        for num, entry in curr_persist.items():
            if entry[0] >= limit:
                if entry[2] >= limit:
                    item = f'{num}^{entry[1]}'
                    count = entry[2]
                else:
                    item = f'{num}'
                    count = entry[0]
                curr_factors.append(item)
                if persist_string == '':
                    persist_string = item
                    counter_string = f' ({count}'
                else:
                    persist_string += f'*{item}'
                    counter_string += f', {count}'
        counter_string += ') '

    def get_merge(self, seq):
        """Walks the local database to find the merges a sequence goes through

        Unlike most of the other functions, this function continues past the merge
        point to follow the sequence to its ultimate end.

        The information is not saved, rather it is printed to stdout.

        Args:
            seq: The sequence to follow
        """

        curr = seq
        index = 0
        done = False
        values = {}
        curr_seq = seq
        while not done:
            if curr <= 1:
                print(f'For {curr_seq}:{index}, {curr} was reached')
                done = True
            elif curr in values:
                print(f'For {curr_seq}:{index} cycle at {curr}')
                done = True
            else:
                values[curr] = index
                data:AlqData | None = self.aliquot_data.select_data(curr, True)
                if not data:
                    data:AlqData | None = self.aliquot_data.select_data(curr, False)
                if data:
                    base = data['base']
                    alq_sum = data['aliquot_sum']
                    if base != curr_seq:
                        new_index = data['index']
                        print(f'For {curr_seq}:{index} at {curr} becomes {base}:{new_index}')
                        index = new_index
                        curr_seq = base
                    if data['complete']:
                        index += 1
                        curr = alq_sum
                    else:
                        print(f'For {curr_seq}:{index} open sequence at {curr}')
                        done = True

    def analyze_elg(self, seq, prev_data, merge_stats):
        """Analysis of what elg files merge to

        Called by alq_analyze_elg, it calculates counts of what is merged into for elg
        files as well as other stats like the ratio of aliquot sum to the number.

        Args
            seq: The sequence we are computing the stats for.
            prev_data: The data right before the merge occurs.
            merge_stats: A bunch of statistics about the merge.
        """

        print(f'Seq:{seq}')
        aliquot_sum = prev_data['aliquot_sum']
        data:AlqData | None = self.aliquot_data.select_data(aliquot_sum, True)
        curr = aliquot_sum
        base = data['base']
        done = False
        values = {}
        while not done:
            if self.is_open(base):
                self.add_merge(seq, data, True, merge_stats)
                self.add_merge_step(prev_data, merge_stats)
                done = True
            else:
                subd = seq // 1000000
                elg_name = f'elg_{subd}/alq_{base}.elg'
                if Path(elg_name).is_file():
                    #skip elg entries.
                    elg_data = self.get_pre_merge_data(elg_name)
                    if elg_data:
                        curr = elg_data['aliquot_sum']
                        data:AlqData | None = self.aliquot_data.select_data(curr, True)
                        if not data:
                            print(f'Unexpected missing data for {seq}')
                            sys.exit(1)
                        if base == data['base']:
                            print(f'cycle for {aliquot_sum} in {base}')
                            done = True
                        base = data['base']
                    else:
                        values[curr] = True
                        curr = data['aliquot_sum']
                        data:AlqData | None = self.aliquot_data.select_data(curr, True)
                        if not data:
                            print(f'Unexpected missing data for {seq}')
                            sys.exit(1)
                        base = data['base']
                else:
                    aliquot_sum = data['aliquot_sum']
                    if curr == 1 or curr in values or aliquot_sum == 1:
                        self.add_terminating(seq, merge_stats)
                        done = True
                    else:
                        values[curr] = True
                        curr = data['aliquot_sum']
                        prev_data = data
                        data:AlqData | None = self.aliquot_data.select_data(curr, True)
                        base = data['base']
                        if not data:
                            print(f'Unexpected missing data for {seq}')
                            sys.exit(1)

    def get_pre_merge_data(self, elg_name):
        """ Get the last 2 lines of the elg file if they exist."""

        data = None
        with open(elg_name, encoding="ascii") as file:
            lines = file.readlines()
            if len(lines) < 2:
                print(f'Broken/short elg file: {elg_name}')
                return None
            pre_merge_line = lines[-2]
            data = aliquot_util.parse_elf_line(pre_merge_line)
        return data

    def add_terminating(self, seq, merge_stats):
        """Add to the counts of terminating sequences in merge stats"""
        merge_stats['terminations'] += 1
        merge_stats['terminating'][seq] = True

    def add_merge_step(self, data, merge_stats):
        """Handles counts of merging up vs down.

        A merge up means num is less than the aliquot sum.
        A merge down means num is more than the aliquot sum.
        The cound updates the merge stats.

        Args:
            data: The data from the current step
            merge_stats: The statistics to add to
        """

        num = data['num']
        aliquot_sum = data['aliquot_sum']
        if num < aliquot_sum:
            merge_stats['merge_step_up'][num] = aliquot_sum
            merge_stats['merge_up_count'] += 1
        else:
            merge_stats['merge_step_down'][num] = aliquot_sum
            merge_stats['merge_down_count'] += 1

    def add_merge(self, seq, data, is_open, merge_stats):
        """Adds information on what elg sequences merge into

        Here we see what merges into what and whether it is
        from above or below.

        Args:
            seq: The sequence analyzed.
            data: data for the number that has merged into another.
            is_open: Returns True if the sequence merged into is open
            merge_stats: The data is added to the existing merge statistics.
        """

        base = data['base']
        # For merges, base is what we merge to.
        if not base in merge_stats['merge_to']:
            merge_stats['merge_to'][base] = 1
        else:
            merge_stats['merge_to'][base] += 1

        if is_open:
            if not 'open_count' in merge_stats:
                merge_stats['open_count'] = 1
            else:
                merge_stats['open_count'] += 1
            merge_stats['open'][seq] = base
        else:
            if not 'merge_count' in merge_stats:
                merge_stats['merge_count'] = 1
            else:
                merge_stats['merge_count'] += 1
            merge_stats['merge'][seq] = base
        self.add_factor_stats(data, merge_stats)

    def add_factor_stats(self, data, merge_stats):
        """Adds statistics based on the aliquot sum to number ratio.

        Uses the power of two, small primes and odd primes associated with that prime.
        Uses the aliquot sum / number ratio ranges to group similar ratios.
        Adds ratio statistics to the combination of primes from above.

        Args:
            data: data about the merge occurance.
            merge_stats: Information added to the statistics.
        """

        ratio = data['aliquot_sum'] * 100 / data['num']
        factors = aliquot_util.to_factors(data['factor_string'])
        pow_two_primes = { 4: [31], 6: [127], 9: [11,31], 12: [8191]}

        mult = 1
        small_fact = ""
        for prime in factors:
            power = int(factors[prime])
            if prime == '2':
                mult *= 2 ** power
                small_fact = '2' if power == 1 else f'2^{power}'
            elif (int(prime) < 8 or
                  power in pow_two_primes and int(prime) in pow_two_primes[power]):
                small_fact += f'*{prime}' if power == 1 else f'*{prime}^{power}'
                mult *= int(prime) ** power

        small_factor_string = f'{small_fact}({mult})'

        # Global counter increment
        merge_stats['factors'][small_factor_string] = (
            merge_stats['factors'].get(small_factor_string, 0) + 1
        )

        # Determine ratio key category
        if ratio <= 75:
            category = 'factors_75'
        elif ratio <= 100:
            category = 'factors_100'
        elif ratio < 200:
            category = 'factors_200'
        else:
            category = 'factors_plus'

        # Categorized counter increment
        merge_stats[category][small_factor_string] = (
            merge_stats[category].get(small_factor_string, 0) + 1
        )

    def is_open(self, seq):
        """checks if a sequence is open-ended, returning true if so."""

        if not self.open_list:
            self.get_open_list()
        return seq in self.open_list

    def get_open_list(self):
        """Get the list of open-ended sequences from the database."""

        data = self.aliquot_data.get_incomplete()
        self.open_list = {}
        for pair in data:
            seq = pair[0]
            self.open_list[seq] = True
