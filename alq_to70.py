#!/usr/bin/env python

""" Output is a sript to increase series to 70 digits.

"""
import logging
from sql import SQL
from alq_to60 import AliqueitScript

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(filename='alq_to70.log', level=logging.INFO)
    logger.info('Started')

    pg = SQL()

    aliqueit_script = AliqueitScript(pg, 'alq70', 70, 80)
    aliqueit_script.output_db_status()

    logger.info('finished')
