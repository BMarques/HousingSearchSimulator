# Reminders
# GetCapabilities: http://localhost:5000/wps?request=GetCapabilities&service=WPS

import os

import flask

from pywps import Service
from processes.house_searching_simulator import HouseSearchSimulator

# This is needed for local development, so that javascript is able to call the service
# This essentially instructs flask to put the access-control-allow-origin = * on the headers
from flask_cors import CORS

app = flask.Flask(__name__)
CORS(app)

processes = [
    HouseSearchSimulator()
]

# Start service processes
service = Service(processes, ['pywps.cfg'])

@app.route('/wps', methods=['GET', 'POST'])
def wps():
    return service

if __name__ == "__main__":
    # All the code in the main is copy pasted from the pywps-flask sample, it shall remain untouched
    import argparse

    parser = argparse.ArgumentParser(
        description="""Script for starting an example PyWPS
                       instance with sample processes""",
        epilog="""Do not use this service in a production environment.
         It's intended to be running in test environment only!
        For more documentation, visit http://pywps.org/doc
        """
        )
    parser.add_argument('-d', '--daemon',
                        action='store_true', help="run in daemon mode")
    parser.add_argument('-a','--all-addresses',
                        action='store_true', help="run flask using IPv4 0.0.0.0 (all network interfaces),"  +  
                            "otherwise bind to 127.0.0.1 (localhost).  This maybe necessary in systems that only run Flask") 
    args = parser.parse_args()
    
    if args.all_addresses:
        bind_host='0.0.0.0'
    else:
        bind_host='127.0.0.1'

    if args.daemon:
        pid = None
        try:
            pid = os.fork()
        except OSError as e:
            raise Exception("%s [%d]" % (e.strerror, e.errno))

        if (pid == 0):
            os.setsid()
            app.run(threaded=True,host=bind_host)
        else:
            os._exit(0)
    else:
        app.run(threaded=True,host=bind_host)