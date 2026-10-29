import sys
from .dashboard import start
if __name__=='__main__':
    start(sys.argv[1],open_browser=('--no-browser' not in sys.argv))
