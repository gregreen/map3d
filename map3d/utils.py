#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  utils.py
#  
#  Copyright 2015 greg <greg@greg-UX301LAA>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  

import numpy as np

def array_like(x):
    return hasattr(x, '__len__') and not isinstance(x, basestring)

def filter_dict(d, decimals=5):
    # Round floats to requested number of decimal places
    for key in d.keys():
        if isinstance(d[key], np.ndarray):
            if issubclass(d[key].dtype.type, np.integer):
                d[key] = d[key].tolist()
            else:
                d[key] = np.around(d[key].tolist(), decimals=decimals).tolist()
        elif isinstance(d[key], float) or isinstance(d[key], np.floating):
            d[key] = np.around(np.array(d[key]).tolist(), decimals=decimals).tolist()
            #d[key] = float(round(d[key], decimals))
        elif isinstance(d[key], int) or isinstance(d[key], np.integer):
            d[key] = int(d[key])
        else:
            raise TypeError('{} has type {}'.format(key, str(type(d[key]))))
