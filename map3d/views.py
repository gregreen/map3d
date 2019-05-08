from map3d import app

from flask import render_template, redirect, request, jsonify, Response, g
from cerberus import Validator
import numpy as np
import json
import time
import os

from astropy import units
from astropy.coordinates import SkyCoord

script_dir = os.path.dirname(os.path.realpath(__file__))
log_path = os.path.join(script_dir, '..', 'log', 'argonaut_requests.log')

from rate_limit import ratelimit
from gzip_response import gzipped
from validators import validate_json, validate_qstring, skycoords_from_args, ExtendedValidator

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

@app.route('/papers')
def papers():
    return render_template('papers.html')


############################################################################
# API v2
############################################################################

def over_limit_message(rlimit):
    msg = (
        'You are issuing too many queries in a short period of time. '
        'You can reduce the number of queries required by requesting '
        'multiple coordinates with each call.'
    )
    return msg, 429

@app.route('/api/v2/<map_name>/query', methods=['POST'])
@ratelimit(limit=300, per=5*60,
           send_x_headers=True,
           over_limit=over_limit_message)
@gzipped(6)
@validate_json('skycoord', 'gal', 'equ',
               'distance', 'equ-frame',
               allow_unknown=True)
@skycoords_from_args()
def api_v2(coords, map_name):
    # Check map name
    if map_name not in mapdata.handlers:
        msg = 'Invalid map name: "{}".'.format(map_name)
        return msg, 400

    t_start = time.time()

    # Select correct map to query
    handler = mapdata.handlers[map_name]
    if 'schema' in handler:
        v = ExtendedValidator(handler['schema'], allow_unknown=False)
        if not v.validate(g.args):
            msg = 'Invalid keyword arguments.\n'
            msg += json.dumps(v.errors, indent=2)
            return msg, 400
    if 'size_checker' in handler:
        success, q_size, q_size_max = handler['size_checker'](coords, **g.args)
        if not success:
            msg = 'Requested output is too large (requested: {:d}, max: {:d})'
            msg = msg.format(q_size, int(q_size_max))
            return msg, 413

    # Conduct the query
    try:
        res = handler['q'](coords, **g.args)
    except Exception as err:
        msg = 'An unexpected error occurred while executing the query.\n'
        msg += str(err)
        return msg, 500
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
                   '(t: {delta_t:.2f} s, t/coord: {t_per_coord:.2g} s)')
    txt_request = txt_request.format(
        map_name=map_name,
        ip=request.remote_addr,
        n_coords=g.n_coords,
        delta_t=t_end-t_start,
        t_per_coord=(t_end-t_start) / max(1, g.n_coords))
    logger.write(txt_request)

    # JSONify and return the results
    return jsonify(res)


###########################################################################
# Interactive Website
###########################################################################

@app.route('/api/v2/interactive/<map_name>/losdata', methods=['GET'])
@ratelimit(limit=30, per=60, send_x_headers=False)
@validate_qstring('scalar-lonlat')
@skycoords_from_args()
def interactive_data(coords, map_name):
    t0 = time.time()

    # Check map name
    if map_name not in ['bayestar2015', 'bayestar2017', 'bayestar2019']:
        msg = 'Invalid map name: "{}".'.format(map_name)
        return msg, 400

    if coords.frame.name != 'galactic':
        coords = coords.transform_to('galactic')

    t1 = time.time()

    # Execute query
    query_obj = mapdata.handlers[map_name]['q']
    samples, flags = query_obj(
        coords,
        mode='samples',
        return_flags=True)

    t2 = time.time()

    best = query_obj(coords, mode='best')
    distmod = (query_obj.distmods/units.mag).decompose().value
    
    # Convert to E(g-r)
    samples *= 0.901
    best *= 0.901
    
    min_rel_dm = np.min([flags['min_reliable_distmod'], 999.])
    max_rel_dm = np.max([flags['max_reliable_distmod'], -999.])

    t3 = time.time()

    # Postage Stamps
    dists = [300., 1000., 5000.]
    radius = postage_stamp.radius
    img = postage_stamp.postage_stamps(
        map_name,
        coords.l.deg,
        coords.b.deg,
        dists=dists)

    t4 = time.time()

    img = [postage_stamp.encode_image(img_d) for img_d in img]
    label = ['{:.0f} pc'.format(d) for d in dists]

    t5 = time.time()

    # Determine success of query
    success = np.all(np.isfinite(best))

    # Collect results
    res = filter_NaN({
        'success': success,
        'l': coords.l.deg,
        'b': coords.b.deg,
        'radius': radius,
        'samples': samples.tolist(),
        'best': best.tolist(),
        'distmod': distmod.tolist(),
        'converged': flags['converged'],
        'min_reliable_distmod': min_rel_dm,
        'max_reliable_distmod': max_rel_dm})

    for k,(i,l) in enumerate(zip(img, label)):
        res['label{:d}'.format(k+1)] = l
        res['image{:d}'.format(k+1)] = i

    t6 = time.time()

    print('time inside query: {:.4f} s'.format(t6-t0))
    print('{: >7.4f} s : {: >6.4f} s : transform to galactic'.format(t1-t0, t1-t0))
    print('{: >7.4f} s : {: >6.4f} s : query samples'.format(t2-t0, t2-t1))
    print('{: >7.4f} s : {: >6.4f} s : query best'.format(t3-t0, t3-t2))
    print('{: >7.4f} s : {: >6.4f} s : rasterize postage stamps'.format(t4-t0, t4-t3))
    print('{: >7.4f} s : {: >6.4f} s : encode postage stamps'.format(t5-t0, t5-t4))
    print('{: >7.4f} s : {: >6.4f} s : collect results'.format(t6-t0, t6-t5))

    return jsonify(res)


@app.route('/api/v2/interactive/<map_name>/lostable', methods=['GET'])
@ratelimit(limit=30, per=60, send_x_headers=False)
@validate_qstring('scalar-lonlat')
@skycoords_from_args()
def interactive_table(coords, map_name):
    t0 = time.time()

    # Check map name
    if map_name not in ['bayestar2015', 'bayestar2017', 'bayestar2019']:
        msg = 'Invalid map name: "{}".'.format(map_name)
        return msg, 400

    if coords.frame.name != 'galactic':
        coords = coords.transform_to('galactic')

    t1 = time.time()

    # Execute query
    query_obj = mapdata.handlers[map_name]['q']
    samples, flags = query_obj(
        coords,
        mode='samples',
        return_flags=True)

    t2 = time.time()

    best = query_obj(coords, mode='best')
    distmod = (query_obj.distmods/units.mag).decompose().value
    
    # Convert to E(g-r)
    samples *= 0.901
    best *= 0.901
    
    t3 = time.time()

    # ASCII table
    table = loscurves.los_ascii_summary(
        coords,
        samples,
        best,
        flags,
        distmod=distmod,
        encode=False)

    t4 = time.time()

    print('time inside query: {:.4f} s'.format(t4-t0))
    print('{: >7.4f} s : {: >6.4f} s : transform to galactic'.format(t1-t0, t1-t0))
    print('{: >7.4f} s : {: >6.4f} s : query samples'.format(t2-t0, t2-t1))
    print('{: >7.4f} s : {: >6.4f} s : query best'.format(t3-t0, t3-t2))
    print('{: >7.4f} s : {: >6.4f} s : ASCII table'.format(t4-t0, t4-t3))

    fname = "{:s}_l_{:.4f}_b_{:.4f}.txt".format(
        map_name, coords.l.deg, coords.b.deg)
    headers = {
        "Content-Disposition": 'inline; filename="{:s}"'.format(fname)}

    return Response(
        table,
        mimetype="data:text/plain; charset=US-ASCII",
        headers=headers)


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
        query_obj = mapdata.handlers['bayestar2015']['q']
        samples, flags = query_obj(coords, mode='samples', return_flags=True)
        best = query_obj(coords, mode='best', return_flags=False)
        res['samples'] = samples
        res['best'] = best
        for key in flags.dtype.names:
            res[key] = flags[key]
        res['distmod'] = (query_obj.distmods / units.mag).decompose().value
    elif g.args['mode'] == 'lite':
        query_obj = mapdata.handlers['bayestar2015']['q']
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
        query_obj = mapdata.handlers['sfd']['q']
        res['EBV_SFD'] = query_obj(coords)

    # Convert numpy arrays to lists before sending back
    def _sanitize_output(x, n_digits=5):
        if isinstance(x, np.ndarray):
            if (n_digits is not None) and (x.dtype.kind == 'f'):
                return np.round(x.astype(float), decimals=n_digits).tolist()
            return x.tolist()
        elif isinstance(x, float) or isinstance(x, np.floating):
            if n_digits is not None:
                return round(x, ndigits=n_digits)
        return x

    for key in res:
        res[key] = _sanitize_output(res[key])

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
    query_obj = mapdata.handlers['bayestar2015']['q']
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
        'bayestar2015',
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
