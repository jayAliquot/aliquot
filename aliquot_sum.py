#!/usr/bin/env python

""" Finds the aliquot sum which is the next term in an aliqout sequence.

Class to help find aliquot series for new numbers.  The sequences are calculated to 10**24
(25 digits) which is small enough that we can do it in python/sympy.

The number is fully factored which allows us to find the aliquot sum
"""


import logging
from sympy.ntheory import factorint, isprime

logger = logging.getLogger(__name__)

class AliquotSum:
    """Finds initial factors (to 25 digits) for aliquot sequences)"""

    def __init__(self):
        """Set limit to stop factoring when reached

        Attributes:
            max: The maximum size to factor
        """

        self.max = 10**24

    def calc_aliquot_sum(self, num):
        """Calculate the data for one step of the sequence.

        Args:
            num: The number to get the data for:
        Returns:
            The data for this step of the sequence.
        """

        data = {}
        data['num'] = num
        self.factor(data)
        if data['complete']:
            self._calc_sum(data)
        return data

    def factor(self, data):
        """Factor the number.

        Args:
            The data stores the number and the results.
        """

        num = data['num']
        if num > self.max:
            data['complete'] = False
            data['unfactor'] = num
            data['aliquot_sum'] = 0
            data['factors'] = []
            data['factor_string'] = ''
        else:
            data['factors'] = []
            data['factor_string'] = ''
            first = True
            factor_dict = factorint(num)
            data['complete'] = True
            for key in factor_dict.keys():
                value = factor_dict[key]
                if isprime(key):
                    factor = (key, value)
                    data['factors'].append(factor)
                    if first:
                        first = False
                    else:
                        data['factor_string'] += '*'
                    if value == 1:
                        data['factor_string'] += str(key)
                    else:
                        data['factor_string'] += str(key) + '^' + str(value)
                else:
                    # Should not occur for values of 25 digits or less
                    data['complete'] = False
                    data['unfactored'] = key
                    print('unfactored comp', flush=True)

    def _calc_sum(self, data):
        """Calculate the aliquot sum

        Uses a formula for the sum of the divisors, then we subtract off the number itself
        to get the sum of the proper divisors.

        Args:
            data: The data with the number and the results.
        """

        alq = 1
        for factor in data['factors']:
            term = 1
            prime = factor[0]
            for power in range(1, factor[1]+1):
                term += prime**power
            alq *= term
        data['aliquot_sum'] = alq - data['num']
