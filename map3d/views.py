from map3d import app

from flask import render_template, redirect, request


@app.route('/')
def cover():
    return render_template('cover.html')

@app.route('/query')
def query():
    return render_template('query.html')

@app.route('/gal-lb-query', methods=['POST'])
def gal_lb_query():
    l = float(request.json['l'])
    b = float(request.json['b'])
    
    print 'l,b = (%.2f, %.2f)' % (l, b)
    
    # TODO:
    #   * Pass (l,b) to plot generating function
    #   * Get filename from function
    #   * Return filename through AJAX
    
    return str(request.json)

