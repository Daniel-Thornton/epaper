#!/usr/bin/python3
# -*- coding:utf-8 -*-
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'data', 'epaper.log')),
    ]
)

from app import App

if __name__ == '__main__':
    app = App()
    app.run()
