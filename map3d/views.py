from map3d import app

from flask import render_template, redirect, request, jsonify, Response, g
from cerberus import Validator
import numpy as np
import ujson as json
import time
import os

from astropy import units
from astropy.coordinates import SkyCoord

script_dir = os.path.dirname(os.path.realpath(__file__))
log_path = os.path.join(script_dir, '..', 'log', 'argonaut_requests.log')

from rate_limit import ratelimit
from gzip_response import gzipped
from validators import validate_json, validate_qstring, skycoords_from_args, get_n_coords

from redis_logger import Logger
logger = Logger('argonaut_request_log', log_path)

import postage_stamp
import mapdata
import loscurves
import snippets

from utils import array_like, filter_dict, filter_NaN

from dustmaps import json_serializers
app.json_decoder = json_serializers.MultiJSONDecoder
app.json_encoder = json_serializers.get_encoder(ndarray_mode='b64')


#
# Web pages
#

@app.route('/cover')
def cover():
    return render_template('cover.html')

@app.route('/')
def expo():
    return render_template('expo.html')

@app.route('/usage')
def usage():
    return render_template('usage.html', snippets=snippets)

@app.route('/query')
def query():
    return render_template('query.html')

#
# API v2
#

@app.route('/api/v2/<map_name>/query', methods=['POST'])
@ratelimit(limit=1000, per=5*60, send_x_headers=True)
@gzipped(6)
@validate_json('skycoord', 'gal', 'equ', 'distance', 'equ-frame', allow_unknown=True)
@skycoords_from_args()
def api_v2(coords, map_name):
    # Check map name
    if map_name not in mapdata.handlers:
        msg = 'Invalid map name: "{}".'.format(map_name)
        return msg, 400

    t_start = time.time()

    # Select correct map to query
    query_obj, n_coords_max = mapdata.handlers[map_name]
    if (n_coords_max is not None) and (g.n_coords > n_coords_max):
        msg = 'Too many coordinates requested (requested: {:d}, max: {:d})'.format(
            g.n_coords, n_coords_max)
        return msg, 413

    # Conduct the query
    try:
        res = query_obj(coords, **g.args)
    except TypeError as err:
        msg = 'Invalid keyword argument received.\n' + str(err)
        return msg, 400
    # except Exception as err:
    #     msg = 'An exception occurred in processing your query. This most\n'
    #     msg += 'likely means that there was an error in the query parameters.\n'
    #     msg += 'Please consult the "dustmaps" documentation at\n'
    #     msg += '<dustmaps.readthedocs.io/>.\n'
    #     msg += 'A readout of the error is as follows:\n'
    #     msg += str(err)
    #     return msg, 400

    t_end = time.time()

    # Log the query
    txt_request = ('/api/v2/{map_name}/query: ' +
                   '{n_coords} coordinates requested by {ip} ' +
                   '(t: {delta_t:.2f} s, t/coord: {t_per_coord:.2g} s)').format(
        map_name=map_name,
        ip=request.remote_addr,
        n_coords=g.n_coords,
        delta_t=t_end-t_start,
        t_per_coord=(t_end-t_start) / max(1, g.n_coords))
    logger.write(txt_request)

    # JSONify and return the results
    return jsonify(res)


###########################################################################
# Legacy API
###########################################################################

@app.route('/gal-lb-query-light', methods=['POST'])
@ratelimit(limit=1000, per=5*60, send_x_headers=True)
@gzipped(6)
@validate_json('skycoord', 'gal', 'equ', 'distance', 'mode-legacy')
@skycoords_from_args()
def gal_lb_query_light(coords):
    t_start = time.time()

    n_coords_max = dict(full=5000, lite=50000, sfd=500000).get(g.args['mode'], None)
    if (n_coords_max is not None) and (g.n_coords > n_coords_max):
        msg = 'Too many coordinates requested: {}\n'.format(g.n_coords)
        msg += 'Max. allowed for mode "{}": {}'.format(g.args['mode'], n_coords_max)
        return msg, 413

    # Conduct the query
    res = {}

    if g.args['mode'] == 'full':
        query_obj, _ = mapdata.handlers['bayestar2015']
        samples, flags = query_obj(coords, mode='samples', return_flags=True)
        best = query_obj(coords, mode='best', return_flags=False)
        res['samples'] = samples
        res['best'] = best
        for key in flags.dtype.names:
            res[key] = flags[key]
        res['distmod'] = (query_obj.distmods / units.mag).decompose().value
    elif g.args['mode'] == 'lite':
        query_obj, _ = mapdata.handlers['bayestar2015']
        pctiles, flags = query_obj(
            coords,
            mode='percentile',
            pct=[15.8, 50., 84.2],
            return_flags=True)
        best = query_obj(coords, mode='best', return_flags=False)
        res['median'] = pctiles[...,1]
        res['sigma'] = 0.5 * (pctiles[...,2] - pctiles[...,0])
        res['best'] = best
        for key in flags.dtype.names:
            res[key] = flags[key]
        res['distmod'] = (query_obj.distmods / units.mag).decompose().value
    elif g.args['mode'] == 'sfd':
        query_obj, _ = mapdata.handlers['sfd']
        res['EBV_SFD'] = query_obj(coords)

    t_end = time.time()

    # Log the query
    txt_request = ('/gal-lb-query-light: ' +
                   '{n_coords} coordinates requested by {ip} ' +
                   '(t: {delta_t:.2f}s, t/coord: {t_per_coord:.2g}s)').format(
        ip=request.remote_addr,
        n_coords=g.n_coords,
        delta_t=t_end-t_start,
        t_per_coord=(t_end-t_start) / max(1,g.n_coords))
    logger.write(txt_request)

    # JSONify and return the results
    return jsonify(res)


@app.route('/gal-lb-query', methods=['GET'])
@ratelimit(limit=30, per=60, send_x_headers=False)
@validate_qstring('scalar-lonlat')
@skycoords_from_args()
def gal_lb_query(coords):
    t0 = time.time()

    if coords.frame.name != 'galactic':
        coords = coords.transform_to('galactic')

    t1 = time.time()

    # Execute query
    query_obj,_ = mapdata.handlers['bayestar2015']
    samples, flags = query_obj(
        coords,
        mode='samples',
        return_flags=True)

    t2 = time.time()

    best = query_obj(coords, mode='best')
    distmod = (query_obj.distmods/units.mag).decompose().value

    t3 = time.time()

    # Postage Stamps
    dists = [300., 1000., 5000.]
    radius = postage_stamp.radius
    img = postage_stamp.postage_stamps(
        coords.l.deg,
        coords.b.deg,
        dists=dists)

    t4 = time.time()

    img = [postage_stamp.encode_image(img_d) for img_d in img]
    label = ['{:.0f} pc'.format(d) for d in dists]

    t5 = time.time()

    # ASCII table
    table = loscurves.los_ascii_summary(
        coords,
        samples,
        best,
        flags,
        distmod=distmod)

    t6 = time.time()

    # Determine success of query
    success = np.all(np.isfinite(best))

    # Collect results
    res = filter_NaN({
        'success': success,
        'l': coords.l.deg,
        'b': coords.b.deg,
        'radius': radius,
        'table': table,
        'samples': samples.tolist(),
        'best': best.tolist(),
        'distmod': distmod.tolist(),
        'converged': flags['converged'],
        'min_reliable_distmod': flags['min_reliable_distmod'],
        'max_reliable_distmod': flags['max_reliable_distmod']})

    for k,(i,l) in enumerate(zip(img, label)):
        res['label{:d}'.format(k+1)] = l
        res['image{:d}'.format(k+1)] = i

    t7 = time.time()

    print('time inside query: {:.4f} s'.format(t7-t0))
    print('{: >7.4f} s : {: >6.4f} s : transform to galactic'.format(t1-t0, t1-t0))
    print('{: >7.4f} s : {: >6.4f} s : query samples'.format(t2-t0, t2-t1))
    print('{: >7.4f} s : {: >6.4f} s : query best'.format(t3-t0, t3-t2))
    print('{: >7.4f} s : {: >6.4f} s : rasterize postage stamps'.format(t4-t0, t4-t3))
    print('{: >7.4f} s : {: >6.4f} s : encode postage stamps'.format(t5-t0, t5-t4))
    print('{: >7.4f} s : {: >6.4f} s : ASCII table'.format(t6-t0, t6-t5))
    print('{: >7.4f} s : {: >6.4f} s : collect results'.format(t7-t0, t7-t6))

    return jsonify(res)
