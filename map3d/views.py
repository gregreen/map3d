from map3d import app

from flask import render_template, redirect, request, jsonify

from rate_limit import ratelimit

from redis_logger import Logger
import os
script_dir = os.path.dirname(os.path.realpath(__file__))
log_path = os.path.join(script_dir, '..', 'log', 'argonaut_requests.log')
logger = Logger('argonaut_request_log', log_path)

import postage_stamp
import loscurves

import time


@app.route('/')
def cover():
    return render_template('cover.html')

@app.route('/query')
def query():
    return render_template('query.html')

@app.route('/gal-lb-query', methods=['POST'])
@ratelimit(limit=30, per=60, send_x_headers=False)
def gal_lb_query():
    l, b = None, None
    
    try:
        l = float(request.json['l'])
        b = float(request.json['b'])
    except:
        return 400, 'Invalid Galactic coordinates: (' + str(l) + ', ' + str(b) + ')'
    
    ip = request.remote_addr
    
    if (b > 90.) or (b < -90.):
        return 400, 'Invalid Galactic coordinates: (' + str(l) + ', ' + str(b) + ')'
    
    dists = [300., 1000., 5000.]
    radius = 7.5
    
    t_start = time.time()
    
    img = postage_stamp.postage_stamps(l, b, dists=dists)
    img = [postage_stamp.encode_image(img_d) for img_d in img]
    
    t_ps = time.time()
    
    mu, best, samples, n_stars, converged, table_data = loscurves.get_encoded_los(l, b)
    
    t_los = time.time()
    
    txt_request = 'l,b = (%.2f, %.2f) requested by %s ' % (l, b, str(ip))
    txt_request += '(t: %.2fs, ps: %.2fs, los: %.4fs)' % (t_los-t_start, t_ps-t_start, t_los-t_ps)
    
    logger.write(txt_request)
    
    success = int(int(n_stars) != 0)
    
    label = ['%d pc' % d for d in dists]
    
    return jsonify(success=success,
                   l=l, b=b,
                   radius=radius,
                   label1=label[0], image1=img[0],
                   label2=label[1], image2=img[1],
                   label3=label[2], image3=img[2],
                   mu=mu, best=best, samples=samples,
                   n_stars=n_stars, converged=converged,
                   table_data=table_data)


@app.route('/gal-lb-query-light', methods=['POST'])
@ratelimit(limit=1000, per=5*60, send_x_headers=True)
def gal_lb_query_light():
    l, b = None, None
    
    try:
        l = float(request.json['l'])
        b = float(request.json['b'])
    except:
        return 400, 'Invalid Galactic coordinates: (' + str(l) + ', ' + str(b) + ')'
    
    ip = request.remote_addr
    
    if (b > 90.) or (b < -90.):
        return 400, 'Invalid Galactic coordinates: (' + str(l) + ', ' + str(b) + ')'
    
    t_start = time.time()
    
    mu, best, samples, n_stars, converged, table_data = loscurves.get_encoded_los(l, b)
    
    t_end = time.time()
    
    txt_request = 'l,b = (%.2f, %.2f) requested by %s ' % (l, b, str(ip))
    txt_request += '(t: %.2fs)' % (t_end-t_start)
    
    logger.write(txt_request)
    
    success = int(int(n_stars) != 0)
    
    return jsonify(success=success,
                   l=l, b=b, distmod=mu,
                   best=best, samples=samples,
                   n_stars=n_stars, converged=converged,
                   table_data=table_data)
