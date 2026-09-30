#!/usr/bin/env python

"""Test formula from math overlow

Partially written/incomplete. 
"""

import argparse
import math
import logging

logger = logging.getLogger(__name__)

def get_factorials(max_num):
    mult = 1
    factorials = {}
    factorials[0] = 1
    for index in range(1, max_num + 1):
        mult *= index
        factorials[index] = mult
    print(factorials)
    return factorials

def get_formula(digits, index, count, fact_count, factorials, a_k):
    ln_digits = math.log(10**(digits + 0.5))
    ln_ln_digits = math.log(ln_digits)
    a_k[digits][index] = {}
    if index == 1:
        a_k[digits][index]['b'] = count/ln_digits
        a_k[digits][index]['a'] = count/ln_digits
    else:
        k_minus_1 = index - 1
        k_minus_2 = index - 2
        a_k[digits][index]['b'] = count*ln_ln_digits**(k_minus_1)/(factorials[k_minus_1]*ln_digits)
        a_k[digits][index]['a'] = count*ln_ln_digits**(k_minus_2)/(factorials[k_minus_2]*ln_digits)
    a_k[digits][index]['x'] = (fact_count - a_k[digits][index]['b'])/a_k[digits][index]['a']

def calc_statistics():
    tuples = [(2,), (2,3), (2,7), (2,31), (2,3,5), (2,3,11,31), (5,11)]
    parser = argparse.ArgumentParser(description =__doc__)
    parser.add_argument('form_file', type=int, help='The file with formula information.')
    argv = parser.parse_args()
    form_file_name = argv.form_file
    a_k = {}
    with open(form_file_name, 'r', encoding='ascii') as form_file:
        #for line in form_file:
        #TODO - partial written code above
        prev_time = now
        for digits in range(min_digits, max_digits + 1, step_size):
            print(datetime.now())
            num_array = generate_integers(digits, count)
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
                result = subprocess.run(run_strings, capture_output=True, text=True)
                lines = result.stdout.splitlines()
                factor_count = 0
                for line in lines:
                    if len(line) > 1 and line[0] == 'P':
                        factor_count += 1
                if factor_count == 0:
                    print(f'Issue: {lines} for {num}')
                else:
                    if factor_count > max_factor_count:
                        max_factor_count = factor_count
                    add_to(factors['all'], factor_count)
                    for index in range(0, len(tuples)):
                        tup = tuples[index]
                        div = 1
                        for prime in tup:
                            if num % prime == 0:
                                div *= prime
                        if not div in factors[index]['div']:
                            factors[index]['div'][div] = {}
                        add_to(factors[index]['div'][div], factor_count)

            #chance = ln_ln_digits**(factor - 1)/(factorial * ln_digits)
            factorials = get_factorials(max_factor_count)
            for index in range(1, max_factor_count+1):
                if index in factors['all']:
                    fact_count = factors['all'][index]
                    get_formula(digits, index, count, fact_count, factorials, a_k)
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
                            kfactor_file.write(f'{digits}, {index}, {mult}, {div}, {fact_count}\n')
                        kfactor_file.flush()
            for k in a_k[digits]:
                a = a_k[digits][k]['a']
                b = a_k[digits][k]['b']
                x = a_k[digits][k]['x']
                total = b + a * x
                print(f'a_k for {digits} and {k} factors: {b} off by {a} * {x} = {total}')

if __name__ == "__main__":
    logging.basicConfig(filename='alq_test_formula.log', level=logging.INFO)
    logger.info('Started')
    calc_statistics()
    logger.info('finished')
