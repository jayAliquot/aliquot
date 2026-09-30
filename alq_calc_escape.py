#!/usr/bin/env python

"""Computes driver chances

Code is work in progress (not complete)

Args:
    min_digits: Min number of digits to output chances.
    max_digits: Max number of digits to output chances.


Example Usage:
    python3 alq_calc_escape.py 80 90 
"""

import sys
import logging
import aliquot_util

logger = logging.getLogger(__name__)

class CalcEscape():
    """Finds the escape chance for various drivers at a given size in deigits.

   """
    def __init__(self):
        """ Initializes main modules used by the class

        Variables:
           aliquot_data: Gets the sequence series from the data base.
           statistics: Called to set the run data from the series.
        """

        self.drivers = [{'driver_uid': 0, 'name': 'Down Driver', 'pow2': 1,
                         'include': [], 'exclude': [3]},
                        {'driver_uid': 1, 'name': '6 Driver', 'pow2': 1,
                         'include': [3], 'exclude': []},
                        {'driver_uid': 2, 'name': '28 Driver', 'pow2': 2,
                         'include': [7], 'exclude': []}]

    def _init_drivers(self):
        driver_data = []

        for driver in self.drivers:
            driver_entry = {}
            driver_entry['pow2'] = driver['pow2']
            for term_num in range(1, driver['pow2'] + 1):
                term_chance = self._calc_term(driver, term_num)
                term_string = f'term_{term_num}'
                driver_entry[term_string] = term_chance
            driver_data.append(driver_entry)
                
    def _calc_term(self, driver, term):
        combos = self._get_combos(term, driver['pow2'])
        term_chance = {}
        term_chance['name'] = self._get_term_name(term)
        term_chance['base_chance'] = self._get_base_chance(term, driver)
        for combo in combos:
            print(combo)
            combo_chance = self._get_combo_chance(combo)
            self._term_chance.append(combo_chance)
        term_chance['combo_total_chance'] = 1
        

    def _get_term_name(self, term):
        name = ''
        for index in range(0, term):
            if index == 0:
                name = 'p0'
            else:
                name += f'*p{index}'
        return name

    def _get_base_chance(self, term, driver):
        base = {}
        base['num_prime_chance'] = self._get_num_prime_chance(term)
        base['exclude_prime_chance'] = self._get_exclude_chance(driver.exclude)
        base['include_prime_chance'] = self._get_include_chance(driver.include)
        base['cube_free_modifier'] = self._get_cube_free(driver)
        base['size b term'] = self._get_size_b_term(term, driver)
        
    def _get_combo_chance(self, combo):
        combo_chance = {}
        combo_chance['name'] = f'{combo}'
        combo_chance['chance'] = self._count_permutations(combo)
        for entry in combo:
            value = self._get_entry_chance(entry)
            combo_chance['chance'] *= value
        return combo_chance

    def _get_entry_chance(self, pow2):
        return 1/(2**pow2)
    
    def _get_combos(self, term, pow2):
        sub_pow2 = []
        for index in range(0, term):
            sub_pow.append(1)
        left = pow2 - term
        done = false
        combos = []
        while not done:
            combo = tupble(sub_pow2)
            combos.append(combo)
            if sum(sub_pow2) < pow2:
                sub_pow2[0] += 1
            else:
                for index in range(1, term):
                    next = sub_pow2[index] + 1
                    next_sum = 0
                    found = False
                    next_combo = sub_pow2.copy()
                    for index2 in range(0, term):
                        if index2 <= index:
                            next_sum += next
                            next_combo[index2] = next
                        else:
                            next_sum += sub_pow2[index2]
                        if next_sum <= pow2:
                            sub_pow2 = next_combo
                            found = True
                            break
                    if not found:
                        done = true
        print(combos)
        return combos
            
            
    def calc_escape(self):
        """ Main public function to calculate the runs

        Args:
           min: The minumum sequence to add statistics for. 0 and 1 both start at 1.
           max: The maximum sequence to add statistics for.  This value cannot be above the
             maximum of the sequences processed so far. This is currently 20 million.
        """
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('min', type=int, help='Minimum digits for stats')
        parser.add_argument('max', type=int, help='Maximum digits for stats')
        parser.add_argument('-n',  type=int, default=1, help='group by n digits, default is 1.')
        argv = parser.parse_args()
        max_digits = argv.max
        min_digits = argv.min
        step = argv.n
        driver_data = self._init_drivers()
        for curr_digit in range(min_digits, max_digits+1, step):
            self.output_stats(driver_data, curr_digit, step)

    def output_stats(self):
        #to be written
        pass

        
# Uses a class rather than globals.
if __name__ == "__main__":
    logging.basicConfig(filename='alq_calc_escape.log', level=logging.INFO)
    logger.info('Started')
    escape = CalcEscape()
    escape.calc_escape()
    logger.info('finished')
