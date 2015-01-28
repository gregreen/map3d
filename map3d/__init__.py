from flask import Flask
from jinja2 import Environment, PackageLoader
from config import basedir

app = Flask(__name__)

from redis import Redis
redis = Redis()

from map3d import views
