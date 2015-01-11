
import numpy as np
import healpy as hp

import json


def get_los(mapper, l, b):
    mu = np.linspace(4., 19., 31)
    mu_0 = np.random.normal(loc=10., scale=3.)
    sigma = 0.5 + 4.5 * np.random.random()
    dE = np.random.random(mu.shape) * np.exp(-0.5 * ((mu-mu_0)/sigma)**2.)
    E = np.cumsum(dE)
    
    return mu, E


def get_encoded_los(mapper, l, b):
    mu, E = get_los(mapper, l, b)
    
    return json.dumps(mu.tolist()), json.dumps(E.tolist())
