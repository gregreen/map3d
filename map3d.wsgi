activate_this = '/home/appsfink/projects/map3d/venv/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

import sys
sys.path.insert(0, '/home/appsfink/projects/map3d')

sys.stderr.write('Python version: ' + sys.version + '\n')
sys.stderr.write('Path:\n')
sys.stderr.write('\n'.join(sys.path))
sys.stderr.write('\nImporting map3d ...\n')

from map3d import app as application
