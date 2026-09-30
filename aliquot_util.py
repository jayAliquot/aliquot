#!/usr/bin/env python

""" Utility function for aliquot series.

    This returns results quickly.
"""

import re
import logging
from pathlib import Path
from decimal import Decimal, getcontext

logger = logging.getLogger(__name__)

SeqData = dict[str, int | bool | str ] | None

#divides up elf files by one million so elf_24 has alq_24000096.elf to alq_24999990.elf
#(based on open series so example values may differ).
INTERVAL = 1000000

def get_line_count(file_name: str) -> int:
    """Gets the number of lines in a file

    Check that the file exists is done outside this function.
        
    Args:
        file_name: The file containing the lines.
    Returns:
        Number of lines in the file
    """

    with open(file_name, 'r', encoding='ascii') as file:
        count = 0
        for count, _ in enumerate(file, 1):
            pass
        return count

def get_valid_line_count(file_name: str) -> int:
    """Gets the number of valid elf lines in a file

    Check that the file exists is done outside this function.
        
    Args:
        file_name: The file containing the lines.
    Returns:
        Number of lines in the file
    """

    with open(file_name, 'r', encoding='ascii') as file:
        line_count = 0
        for line in file:
            if is_valid_elf_line(line):
                line_count += 1
            else:
                break
        return line_count

def is_valid_elf_line(line: str) -> bool:
    """Checks to see if the elf line is valid.

    Invalid cases include the final line of an elg file, partial or error lines sent from the
    remote FactorDB site (e.g. end in a * or ^) the word error followed by more text.

    Args:
        line: The line to validate.

    Returns:
        True of the line is valid, False otherwise.
    """

    elf_pattern = r'^\d+\s*\.\s*\d+\s*=\s*(\d+(\^\d+)?(\s*\*\s*\d+(\^\d+)?)*)?\s*$'
    return re.match(elf_pattern, line.strip()) is not None

def get_final_num(elf_name:str)->int:
    """Get final number from the elf file

    Args:
        elf_name: Name of elf file
    Return:
        Number from end of elf file if it exists. Otherwise returns 1
    """

    with open(elf_name, 'r', encoding='ascii') as file:
        lines = file.readlines()
        if len(lines) > 0:
            data = parse_elf_line(lines[-1])
            if data:
                return data['num']
    return 1

def parse_elf_line(line: str) -> SeqData:
    """Parses a single elf line

    Args:
        line - the line from the elf file.

    Returns:
        data dictiionary with the data from the line, or None if there is an error.
    """

    data = {}
    num_type = r'^\d+$'
    parts = line.split('=')
    no_factors_known = False
    if len(parts) == 1 or (len(parts) == 2 and parts[1].strip() == ''):
        no_factors_known = True
    elif len(parts) != 2:
        print(f'line {line} not an elf line')
        return None
    # starts with <index>.  <num> so not a float
    num_parts = parts[0].split('.')
    if len(num_parts) < 2:
        print(f'Line {line} has no number')
        return None
    num_string = num_parts[1].strip()
    if not re.search(num_type, num_string):
        return None
    num = int(num_string)
    index_string = num_parts[0].strip()
    index = int(index_string)
    if no_factors_known:
        data['num'] = num
        data['index'] = index
        data['factor_string'] = ''
        data['complete'] = False
        data['unfactor'] = num
        data['aliquot_sum'] = 0
        return data

    data['num'] = num
    data['index'] = index

    factor_string = parts[1]
    if _set_factor_string(factor_string, data):
        return data
    return None

def parse_to_line(line:str) -> SeqData:
    """Parse "To <seq>:<index> final line in elg files
    
    Args:
        line: To line from an elg file

    Return:
        data for successful parse with 'base' and 'index' set, otherwise None
    """

    data = {}
    num_type = r'^\d+$'
    parts = line.split(' ')
    if(len(parts) != 2 or parts[0] != 'To'):
        print(f'line {line} not a to line')
        return None
    # starts with <index>.  <num> so not a float
    num_parts = parts[1].split(':')
    base = num_parts[0].strip()
    index = num_parts[1].strip()
    if not re.search(num_type, base) or not re.search(num_type, index):
        print(f'line {line} not a correct to line')
        return None
    data['base'] = base
    data['index'] = index
    return data

def _set_factor_string(factor_string: str, data: SeqData) -> bool:
    """Parse the factor string

    Input is a prime factorization string where multiply is * and powers are ^.

    Args:
        factor_string: Prime factorization string
        data: The data updated based on the factor string.

    Return:
        True if parsed correctly, False otherwise.
    """

    num_type = r'^\d+$'
    clean_factor_string = ''
    first = True
    num = data['num']
    prime_powers = factor_string.split('*')
    alq = 1
    check_num = 1
    for prime_power_string in prime_powers:
        if first:
            first = False
        else:
            clean_factor_string += '*'
        if '^' in prime_power_string:
            items = prime_power_string.split('^')
            if len(items) != 2:
                return False
            prime_string = items[0].strip()

            power_string = items[1].strip()
            clean_factor_string += f'{prime_string}^{power_string}'
            if not re.search(num_type, prime_string) or not re.search(num_type, power_string):
                seq = data['base']
                print(f'For {seq}, non-number found in factor_string {factor_string}')
                return False
            prime = int(prime_string)
            power = int(power_string)
        else:
            prime_string = prime_power_string.strip()
            prime = int(prime_string)
            if not re.search(num_type, prime_string):
                return False
            power = 1
            clean_factor_string += prime_string
        check_num *= prime**power
        term = 1
        for curr in range(1, power + 1):
            term += prime**curr
        alq *= term
    alq -= num
    if check_num < num:
        # incomplete factorization
        if num % check_num != 0:
            print(f'failed to divide: {num} % {check_num}')
            return False
        data['complete'] = False
        data['unfactor'] = num // check_num
        data['aliquot_sum'] = 0
    else:
        if num < check_num:
            print(f'failed to divide: {num} % {check_num}')
            return False
        data['complete'] = True
        data['aliquot_sum'] = alq
    data['factor_string'] = clean_factor_string
    return True

def to_factors(factor_string):
    """From the factor string, convert to the prime factor dictionary"""
    factors = {}
    if len(factor_string) == 0:
        return factors
    prime_powers = factor_string.split('*')
    for prime_power_string in prime_powers:
        if '^' in prime_power_string:
            items = prime_power_string.split('^')
            if len(items) != 2:
                print(f'Error in factor string {factor_string}')
                return None
            prime_string = items[0].strip()
            power_string = items[1].strip()
        else:
            prime_string = prime_power_string
            power_string = 1
        factors[prime_string] = power_string
    return factors

def count_factors(factor_string):
    """Count the total number of distinct factors in the string."""
    factors = to_factors(factor_string)
    return len(factors)

def count_factors_skip_driver(factor_string, driver_uid):
    """Count the total number of non-driver factors

    Driver factors are ones that divide 2**(pow+1) - 1 where pow is the
    power of two for the driver.  These can't be added or dropped for aliquot sums
    unless the power of two changes.
    """
    two_power = get_power_two(driver_uid)
    driver_dependent = Decimal(2 * (2 ** (two_power + 1) - 1))
    factors = to_factors(factor_string)
    factor_count = 0
    for factor in factors:
        if driver_dependent % Decimal(factor) != 0:
            factor_count += 1
    return factor_count

def get_ratio(curr_entry, next_entry):
    """Calculates next_entry/curr_entry where each can be many digits."""
    getcontext().prec = 6
    # Cast to decimal in case it is a string.
    ratio = Decimal(next_entry)/Decimal(curr_entry)
    return float(ratio)


DRIVER_MAP = {
    1:  [(3, '1', '1: 2*3 (6 driver)'), (1, '0', '0: 2 (downdriver)')],
    2:  [(7, '2', '2: 2^2*7 (28 driver)')],
    3:  [(15, '5', '5: 2^3*3*5 (120 driver)'), (3, '8', '8: 2^3*3 (24 driver)'),
         (5, '9', '9: 2^3*5')],
    4:  [(31, '3', '3: 2^4*31 (496 driver)')],
    5:  [(21, '6', '6: 2^5*3*7 (672 driver)'), (7, '9', '9: 2^5*7'), (3, '9', '9: 2^5*3')],
    6:  [(127, '4', '4: 2^6*127 (8128 driver)')],
    7:  [(255, '9', '9: 2^7*3*5*17'), (85, '9', '9: 2^7*5*17'), (51, '9', '9: 2^7*3*17'),
         (17, '9', '9: 2^7*17'), (15, '9', '9: 2^7*3*5'), (5, '9', '9: 2^7*5'),
         (3, '9', '9: 2^7*3')],
    8:  [(511, '9', '9: 2^8*7*73'), (73, '9', '9: 2^8*73'), (7, '9', '9: 2^8*7')],
    9:  [(1023, '7', '7: 2^9*3*11*31 (523776 driver)'), (341, '9', '9: 2^9*11*31'),
         (93, '9', '9: 2^9*3*31'), (33, '9', '9: 2^9*3*11'), (31, '9', '9: 2^9*31'),
         (11, '9', '9: 2^9*11'), (3, '9', '9: 2^9*3')],
    10: [(2047, '9', '9: 2^10*23*89'), (89, '9', '9: 2^10*89'), (23, '9', '9: 2^10*23')],
    11: [(1365, '9', '9: 2^11*3*5*7*13'), (455, '9', '9: 2^11*5*7*13'),
         (273, '9', '9: 2^11*3*7*13'), (195, '9', '9: 2^11*3*5*13'), (105, '9', '9: 2^11*3*5*7'),
         (91, '9', '9: 2^11*7*13'), (65, '9', '9: 2^11*5*13'), (39, '9', '9: 2^11*3*13'),
         (35, '9', '9: 2^11*5*7'), (21, '9', '9: 2^11*3*7'), (15, '9', '9: 2^11*3*5'),
         (13, '9', '9: 2^11*13'), (7, '9', '9: 2^11*7'), (5, '9', '9: 2^11*5'),
         (3, '9', '9: 2^11*3')],
    12: [(8191, 'A', 'A: 2^12*8191 (33550336 driver)')],
    16: [(131071, 'B', 'B: 2^16*131071 (8589869056 driver)')]
}

def calc_driver(num, include_string=False):
    """returns result['driver'] and optional result['driver_string']

    Basic driver is 0-9, A or B. The string contains more information and is
    fairly verbose.

    Args:
        num: The number to determine the driver for.
        include_string: If True return a string as well as driver uid.
    """

    result = {}

    if num == 0:
        print('Zero has no driver')
        result['driver'] = 9
        result['driver_string'] = 'Zero'
        return result
    pow2 = 0
    getcontext().prec = 300
    while num % 2 == 0:
        num //= 2
        pow2 += 1

    driver = '9'
    matched_string = None

    if pow2 in DRIVER_MAP:
        for divisor, drv_char, str_val in DRIVER_MAP[pow2]:
            if num % divisor == 0:
                driver = drv_char
                matched_string = str_val
                break

    result['driver'] = driver
    if include_string:
        if matched_string:
            result['driver_string'] = matched_string
        elif pow2 in DRIVER_MAP:
            result['driver_string'] = f'9: 2^{pow2}'
        else:
            result['driver_string'] = f'9: 2^{pow2}...'

    return result

UID_RETURN_MAP = {
    1:  [(3, 1), (1, 0)],
    2:  [(7, 2)],
    3:  [(15, 5), (3, 10)],
    4:  [(31, 3)],
    5:  [(21, 6)],
    6:  [(127, 4)],
    9:  [(1023, 7)],
    12: [(8191, 8)],
    16: [(131071, 9)]
}

def calc_driver_uid(num):
    """Calculates a uid for drivers and non-drivers based onthe power of 2.

    Changes in driver uid occur when the power of 2 has changed. Odd primes
    can also determine the driver.

    For example, pow2 will not add or drop a 7 because (4+2+1 = 7)
    7 remains supported/unsupported by the power of 2. Thus with/without
    7 remains the same.
    """

    if num == 0:
        return None
    pow2 = 0
    getcontext().prec = 300
    while num % 2 == 0:
        num //= 2
        pow2 += 1
    result = 11 if pow2 == 0 else pow2 + 10
    if pow2 in UID_RETURN_MAP:
        for divisor, return_val in UID_RETURN_MAP[pow2]:
            if num % divisor == 0:
                result = return_val
                break

    return result

# Array is based on pow2 in the function above.
driver_two_power = [1, 1, 2, 4, 6, 3, 5, 9, 12, 16, 3, 0]

def get_power_two(driver_uid):
    """Given a driver uid, returns the power of 2 for that driver"""

    if driver_uid > 11:
        return driver_uid - 10
    return driver_two_power[driver_uid]

def is_driver(driver_uid):
    """For the "no driver run, we need to know which uids are drivers.

    driver_uid 10 is 2^3*3 which is technically a guide.  However it's
    chance of escape is similar to the down driver. so its also considered
    a driver for this.
    """

    if driver_uid < 11:
        return True
    return False

def add_unique(data, new_data, key):
    """Add new_data to data for list under key

    Args:
        data: Mapping containing the complete set of data
        new_data: Mapping containing new data to add if it is not already in data.
        key: What key the list of items is under
    """

    seen = set(data[key])
    data[key].extend(item for item in new_data[key] if item not in seen)

def compute_factors(num):
    """Checks num for smaller factors.
    
    Aliqueit and new factordb entries may not be factored at all.  This checks
    the number for smaller primes.   Note that 127 is the largest driver prime for
    powers of two which are ten or less.  Thus this includes all common driver primes.
    Also added 8191 which is a driver prime for a very few series (5 or so) based on
    the perfect number 2^12*8191.

    Args:
        num: The number to test for small primes.
    Return:
        dict with the factors found, the unfactored part, and a factor string.
    """

    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67,
              71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 8191]
    curr = num
    first = True
    factor_data = {}
    factor_string = ''
    factors = {}
    for prime in primes:
        power = 0
        while curr % prime == 0:
            power += 1
            curr = curr // prime
        if power >= 1:
            factors[prime] = power
            prime_string =  f'{prime}^{power}' if power > 1 else f'{prime}'
            if first:
                factor_string = prime_string
                first = False
            else:
                factor_string += f'*{prime_string}'
    factor_data['unfactored'] = curr
    factor_data['factor_string'] = factor_string
    factor_data['factors'] = factors
    return factor_data

def find_divisor_from_str(factor_string):
    """Takes the string and computes the total

    This is a divisor because it part or all of the prime factorization of some number.

    Args:
        factor_string: The factors that make up the divisor

    Returns:
        the product of the primes and their powers.
    """

    factors = to_factors(factor_string)
    return find_divisor(factors)

def find_divisor(factors):
    """Takes the list of factors and computes the total

    This is a divisor because it part or all of the prime factorization of some number.

    Args:
        factors: The factors that make up the divisor. It is a dictionary with
    prime, power as the key, value pair.

    Returns:
        the product of the primes and their powers.
    """

    divisor = 1
    for prime in factors:
        power = factors[prime]
        prime_power = int(prime)**int(power)
        divisor *= prime_power
    return divisor

def combine_factors_str(num, factor_string1, factor_string2):
    """From two factor strings finds the least common multiple

    Args:
        num: The number that has factors given by the strings.
        factor_string1: First factor string.
        factor_string2: Second factor string.
    """

    factors1 = to_factors(factor_string1)
    return combine_factors(num, factors1, factor_string2)

def combine_factors(num, factors1, factor_string):
    """From one factor string and a set of factors finds the least common multiple.

    Args:
        num: The number that has factors given by the strings.
        factors1: First factors as a dictionary.
        factor_string: Factor string for the second set of factors.
    """

    factors2 = to_factors(factor_string)
    return combine_factor_lists(num, factors1, factors2)


def combine_factor_lists(num, factors1, factors2):
    """From two sets of factors finds the least common multiple.

    Args:
        num: The number that has factors given by the strings.
        factors1: First set of factors as a dictionary.
        factor_string: Second set of factors as a dictionary.

    Returns:
        dictionary with the factor_string, divisor, and unfactored part of num.
    """

    full_factors = {}
    full_data = {}
    divisor = 1
    factor_string = ''
    first = True
    for prime in factors1:
        prime_string = str(prime)
        full_factors[prime_string] = str(factors1[prime])
    for prime in factors2:
        if prime in full_factors:
            full_factors[prime] = str(max(int(full_factors[prime]), int(factors2[prime])))
        else:
            full_factors[prime] = str(factors2[prime])
    full_data['factors'] = full_factors
    for prime, power in full_factors.items():
        prime_string =  f'{prime}^{power}' if str(power) > '1' else f'{prime}'
        if first:
            factor_string = prime_string
            first = False
        else:
            factor_string += f'*{prime_string}'
        divisor *= int(prime)**int(power)
    if num % divisor != 0:
        print(f'Issue with combine factors for {num}')
        return None
    full_data['factor_string'] = factor_string
    full_data['divisor'] = divisor
    full_data['unfactored'] = num // divisor
    return full_data

def get_line(file_name: str, index: int) -> str | None:
    """Get a specific line in a elf or elg file.

    The file name can be an elf or elg file. For those cases, the index is
    the 0 based line of the file.

    Args:
        file_name: The name of the elf/elg file.
        index: The index for the line which is 0,1,2,3,...
    Return:
        The line if found, otherwise None
    """

    with open(file_name, encoding="ascii") as file:
        lines = file.readlines()
        if len(lines) > index:
            return lines[index]
    print(f'{file_name} is too short for index {index}')
    return None

def get_lines(file_name: str) -> str | None:
    """Get all lines of an elf file
    
    Args:
        file_name: The name of the elf/elg file.
    Return:
        One or more lines if found, otherwise returns None
    """

    if Path(file_name).is_file():
        with open(file_name, encoding="ascii") as file:
            lines = file.readlines()
            if len(lines) > 0:
                return lines
    return None

def get_larger_factors(factors, min_digits):
    """ Keep factors with min_digits or more

    Args:
        factors: The list of factors.
        min_digits: The number of digits needed for a factor to be included
    """

    larger_factors = {}
    for prime in factors:
        if len(str(prime)) >= min_digits:
            larger_factors[prime] = factors[prime]
    return larger_factors

def get_smaller_factors(factors, max_digits):
    """ Keep factors with max digits or less

    Args:
        factors: The list of factors.
        max_digits: The maximum number of digits a factor can have to be included
    """
    smaller_factors = {}
    for prime in factors:
        if len(str(prime)) <= max_digits:
            smaller_factors[prime] = factors[prime]
    return smaller_factors

def get_seq_spec(min_seq, max_seq):
    """Use min and max to indicate the range in a file name

    If it starts from 0/1 we don't need to specify the min.
    
    Args:
        min_seq: The minimum value
        max_seq: The maximum value
    """

    if min_seq in (0, 1):
        subd = max_seq // INTERVAL
        diff = max_seq - subd * INTERVAL
        if diff == 0:
            spec = f'_{subd}M'
        else:
            spec = f'_{subd}M_{diff}'
    else:
        min_subd = min_seq // INTERVAL
        min_diff = min_seq - min_subd * INTERVAL
        if min_diff == 0:
            min_spec = f'_{min_subd}M'
        else:
            min_spec = f'_{min_subd}M_{min_diff}'
        max_subd = max_seq // INTERVAL
        max_diff = max_seq - max_subd * INTERVAL
        if max_diff == 0:
            max_spec = f'{max_subd}M'
        else:
            max_spec = f'_{max_subd}M_{max_diff}'
        spec = f'{min_spec}-{max_spec}'
    return spec
