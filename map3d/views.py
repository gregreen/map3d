from map3d import app

from flask import render_template, redirect, request, jsonify, Response
import numpy as np
import ujson as json
import time
import os

script_dir = os.path.dirname(os.path.realpath(__file__))
log_path = os.path.join(script_dir, '..', 'log', 'argonaut_requests.log')

from rate_limit import ratelimit
from gzip_response import gzipped

from redis_logger import Logger
logger = Logger('argonaut_request_log', log_path)

import postage_stamp
import loscurves
import snippets

from utils import array_like, filter_dict

max_request_size = {
    'full': 5000,
    'lite': 50000,
    'sfd':  500000
}


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

@app.route('/gal-lb-query', methods=['POST'])
@ratelimit(limit=30, per=60, send_x_headers=False)
def gal_lb_query():
    coords, valid, mode, msg = loscurves.get_coords(request.json, 0)
    
    if not valid:
        return msg, 400
    
    ip = request.remote_addr
    
    dists = [300., 1000., 5000.]
    radius = 7.5
    
    t_start = time.time()
    
    img = postage_stamp.postage_stamps(coords['l'], coords['b'], dists=dists)
    img = [postage_stamp.encode_image(img_d) for img_d in img]
    
    t_ps = time.time()
    
    los_info, table_data = loscurves.get_los(coords, mode='full', gen_table=True)
    
    t_los = time.time()
    
    txt_request = 'l,b = (%.2f, %.2f) requested by %s ' % (coords['l'], coords['b'], str(ip))
    txt_request += '(t: %.2fs, ps: %.2fs, los: %.4fs)' % (t_los-t_start, t_ps-t_start, t_los-t_ps)
    
    logger.write(txt_request)
    
    if np.isnan(los_info['DM_reliable_min']):
        los_info['DM_reliable_min'] = -999
    if np.isnan(los_info['DM_reliable_max']):
        los_info['DM_reliable_max'] = -999
    
    #success = int(int(los_info['n_stars']) != 0)
    
    label = ['%d pc' % d for d in dists]
    
    filter_dict(los_info, decimals=5)
    filter_dict(coords, decimals=8)
    los_info.update(**coords)
    
    for key in los_info.keys():
        los_info[key] = json.dumps(los_info[key])
    
    return jsonify(radius=radius,
                   label1=label[0], image1=img[0],
                   label2=label[1], image2=img[1],
                   label3=label[2], image3=img[2],
                   table_data=table_data,
                   **los_info)

@app.route('/gal-lb-query-light', methods=['POST'])
@ratelimit(limit=1000, per=5*60, send_x_headers=True)
@gzipped(6)
def gal_lb_query_light():
    # Validate input
    coords, valid, mode, msg = loscurves.get_coords(request.json, max_request_size)
    
    if not valid:
        return msg, 400
    
    # Retrieve the data
    t_start = time.time()
    
    los_info = None
    
    if mode == 'sfd':
        los_info = loscurves.get_sfd(coords)
    else:
        los_info = loscurves.get_los(coords, mode=mode, gen_table=False)
    
    t_end = time.time()
    
    # Write to log
    ip = request.remote_addr
    txt_request = None
    if array_like(coords['l']):
        n_coords = len(coords['l'])
        t_per_request = (t_end-t_start)/n_coords if n_coords != 0 else np.nan
        
        txt_request = '{:d} coordinates (mode: {}) requested by {:s} (t: {:.2f}s, t/request: {:.2g}s)'.format(
            len(coords['l']),
            mode,
            str(ip),
            t_end-t_start,
            t_per_request
        )
    else:
        txt_request = '(l: {:.2f}, b: {:.2f}, mode: {}) requested by {:s} (t: {:.2f}s)'.format(
            coords['l'],
            coords['b'],
            mode,
            str(ip),
            t_end-t_start,
        )
    
    logger.write(txt_request)
    
    # Return JSON
    filter_dict(los_info, decimals=5)
    filter_dict(coords, decimals=8)
    los_info.update(**coords)
    
    return Response(json.dumps(los_info), mimetype='application/json', status=200)
    #return jsonify(**los_info)
