#!/usr/bin/env python

""" Used to check the formula for as posted on Math Overflow

https://mathoverflow.net/questions/503931/
a-formula-for-the-chance-of-a-random-number-n-b-with-gcdn-d-1-for-some-d

"""

import random
import subprocess
import argparse
import math
from datetime import datetime
import logging
from sql import SQL
from aliquot_statistics import AliquotStatistics

logger = logging.getLogger(__name__)

class CheckFormula:

    def __init__(self, sql):
        self.statistics = AliquotStatistics(sql)

    def generate_integers(self, digits, count):

        lower_bound = 10**(digits - 1)
        upper_bound = 10**digits

        num_array = []
        for _ in range (0, count):
            num_array.append(random.randint(lower_bound, upper_bound))
        return num_array

    def add_to(self, factors, factor_count):
        if factor_count in factors:
            factors[factor_count] += 1
        else:
            factors[factor_count] = 1

    def get_factorials(self, max_num):
        mult = 1
        factorials = {}
        factorials[0] = 1
        for index in range(1, max_num + 1):
            mult *= index
            factorials[index] = mult
        print(factorials)
        return factorials

    def get_formula(self, digits, index, count, fact_count, factorials, a_k):
        ln_digits = math.log(10**(digits + 0.5))
        ln_ln_digits = math.log(ln_digits)
        a_k[digits][index] = {}
        if index == 1:
            a_k[digits][index]['b'] = count/ln_digits
            a_k[digits][index]['a'] = count/ln_digits
        else:
            k_minus_1 = index - 1
            k_minus_2 = index - 2
            a_k[digits][index]['b'] = count*ln_ln_digits**(k_minus_1)/(factorials[k_minus_1]*
                                                                       ln_digits)
            a_k[digits][index]['a'] = count*ln_ln_digits**(k_minus_2)/(factorials[k_minus_2]*
                                                                       ln_digits)
        a_k[digits][index]['x'] = (fact_count - a_k[digits][index]['b'])/a_k[digits][index]['a']

    def calc_statistics(self):
        tuples = [(2,), (2,3), (2,7), (2,31), (2,3,5), (2,3,11,31), (5,11)]
        parser = argparse.ArgumentParser(description =__doc__)
        parser.add_argument('min_digits', type=int, help='min_number of digits of numbers')
        parser.add_argument('max_digits', type=int, help='max_number of digits of numbers')
        parser.add_argument('-s', type=int, default=5, help='step size for digits')
        #parser.add_argument('-b', type=int, default=100, help='base count of factored per step')
        parser.add_argument('count', type=int, help='count of the numbers')
        argv = parser.parse_args()
        max_digits = argv.max_digits
        min_digits = argv.min_digits
        count = argv.count
        step_size = argv.s
        now = datetime.now()
        a_k = {}
        time_string=now.strftime('%H%M_%m%d%Y')
        max_factor_count = 1
        if max_digits == min_digits:
            digit_range = str(max_digits)
        else:
            digit_range = f'{min_digits}-{max_digits}'
        kfactor_file_name = f'formula_{digit_range}_{count}_{time_string}.txt'
        with open(kfactor_file_name, 'w+', encoding='ascii') as kfactor_file:
            for digits in range(min_digits, max_digits + 1, step_size):
                print(datetime.now())
                num_array = self.generate_integers(digits, count)
                factors = {}
                factors['all'] = {}
                a_k[digits] = {}
                index = 0
                for index in range(0, len(tuples)):
                    factors[index] = {}
                    factors[index]['tuple'] = tuples[index]
                    mult = 1
                    for prime in tuples[index]:
                        mult *= prime
                    factors[index]['mult'] = mult
                    factors[index]['div'] = {}
                for num in num_array:
                    run_strings = ['alq50/yafu','-xover', '101', f'{num}']
                    result = subprocess.run(run_strings, capture_output=True, text=True,
                                            check=False)
                    lines = result.stdout.splitlines()
                    factor_count = 0
                    for line in lines:
                        if len(line) > 1 and line[0] == 'P':
                            factor_count += 1
                    if factor_count == 0:
                        print(f'Issue: {lines} for {num}')
                    else:
                        max_factor_count = max(factor_count, max_factor_count)
                        self.add_to(factors['all'], factor_count)
                        for index in range(0, len(tuples)):
                            tup = tuples[index]
                            div = 1
                            for prime in tup:
                                if num % prime == 0:
                                    div *= prime
                            if not div in factors[index]['div']:
                                factors[index]['div'][div] = {}
                            self.add_to(factors[index]['div'][div], factor_count)

                #chance = ln_ln_digits**(factor - 1)/(factorial * ln_digits)
                factorials = self.get_factorials(max_factor_count)
                for index in range(1, max_factor_count+1):
                    if index in factors['all']:
                        fact_count = factors['all'][index]
                        self.get_formula(digits, index, count, fact_count, factorials, a_k)
                        print('')
                        print(f'For {index} factors, Total: {fact_count}')
                        kfactor_file.write(f'{digits}, {index}, 1, 1, {fact_count}\n')
                        for tup_index in range(0, len(tuples)):
                            tup = factors[tup_index]['tuple']
                            mult = factors[tup_index]['mult']
                            print(f'For tuple: {tup}')
                            for div in sorted(factors[tup_index]['div'].keys()):
                                if index in factors[tup_index]['div'][div]:
                                    fact_count = factors[tup_index]['div'][div][index]
                                else:
                                    fact_count = 0
                                print(f'    Div: {div}, Count: {fact_count}')
                                kfactor_file.write(f'{digits}, {index}, {mult}, {div}, '
                                                   f'{fact_count}\n')
                            kfactor_file.flush()
                for k in a_k[digits]:
                    a = a_k[digits][k]['a']
                    b = a_k[digits][k]['b']
                    x = a_k[digits][k]['x']
                    total = b + a * x
                    print(f'a_k for {digits} and {k} factors: {b} off by {a} * {x} = {total}')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_formula_check.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    check_formula = CheckFormula(pg)
    check_formula.calc_statistics()
    logger.info('finished')
