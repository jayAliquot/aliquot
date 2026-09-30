#!/usr/bin/env python

""" Finds the aliquot seqence starting from an input number and adds it to the database.

    If an elf file exists for a starting number, all entries will be checked.  Otherwise it will
    stop when it finds a db entry already exists.
"""

import logging
from sql import SQL
from aliquot_data import AliquotData

logger = logging.getLogger(__name__)

def clean_delete(sql):
    aliquot_data = AliquotData(sql)
    aliquot_data.clean_incomplete()

if __name__ == "__main__":
    logging.basicConfig(filename='alq_clean_incomplete.log', level=logging.INFO)
    logger.info('Started')
    pg = SQL()
    clean_delete(pg)
    logger.info('finished')
