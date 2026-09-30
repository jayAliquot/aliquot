#!/usr/bin/env python

""" Calculations on when a number has k factors used to determine merge chances.

This module and alq_calc_escapte explore k factors and affects on escaping a driver.

It was a work in progress and may not be complete.
"""

import random
import subprocess
import argparse
import math
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_integers(digits, count):

    lower_bound = 10**(digits - 1)
    upper_bound = 10**digits

    num_array = []
    for _ in range (0, count):
        num_array.append(random.randint(lower_bound, upper_bound))
    return num_array

def calc_statistics():
    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('min_digits', type=int, help='min_number of digits of numbers')
    parser.add_argument('max_digits', type=int, help='max_number of digits of numbers')
    parser.add_argument('-s', type=int, default=5, help='step size for digits')
    parser.add_argument('-b', type=int, default=100, help='base count of factored per step')
    parser.add_argument('count', type=int, help='count of the numbers')
    argv = parser.parse_args()
    max_digits = argv.max_digits
    min_digits = argv.min_digits
    step_size = argv.s
    base_count = argv.b
    total = argv.count
    now = datetime.now()
    time_string=now.strftime('%H%M_%m%d%Y')
    kfactor_file_name = f'kfactor_{time_string}.txt'
    with open(kfactor_file_name, 'w+', encoding='ascii') as kfactor_file:
        sets = (total+base_count-1)//base_count
        prev_time = now
        for iq in range(0,sets):
            print(datetime.now())
            done_count = iq*base_count
            base_count = min(base_count, total - done_count)
            for digits in range(min_digits, max_digits + 1, step_size):
                num_array = generate_integers(digits, base_count)
                factors = {}
                for num in num_array:
                    run_strings = ['alq50/yafu','-xover', '101', f'{num}']
                    result = subprocess.run(run_strings, capture_output=True, text=True)
                    lines = result.stdout.splitlines()
                    factor_count = 0
                    for line in lines:
                        if len(line) > 1 and line[0] == 'P':
                            factor_count += 1
                    if factor_count == 0:
                        print(f'Issue: {lines} for {num}')
                    else:
                        if factor_count in factors:
                            factors[factor_count] += 1
                        else:
                            factors[factor_count] = 1
                ln_digits = math.log(10**digits)
                ln_ln_digits = math.log(ln_digits)
                for factor in factors:
                    factor_count = factors[factor]
                    factorial = math.factorial(factor - 1)
                    #chance = ln_ln_digits**(factor - 1)/(factorial * ln_digits)
                    #expected = count*chance
                    kfactor_file.write(f'{digits}, {base_count}, {factor}, {factor_count}\n')
                    kfactor_file.flush()
                curr_time = datetime.now()
                delta_time = curr_time - prev_time
                prev_time = curr_time
                print(f'{done_count}:{base_count} at {digits} digits in {delta_time}')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_kfactors.log', level=logging.INFO)
    logger.info('Started')
    calc_statistics()
    logger.info('finished')
