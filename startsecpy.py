# Dependancies:
# 1) raspistill : this should be part of Raspbian
# 2) Python Imaging Library : can be install by the command: sudo apt-get install python-imaging

import ConfigParser
import os
import subprocess
import logging
import sys
import datetime
import time
from PIL import Image, ImageChops, ImageOps, ImageStat
import math, operator
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
import threading

# use RAM-backed temporary file store location - to reduce writes to the SD card
tmp_file = '/dev/shm/secpy.jpg'

# create the internal logger
log = logging.getLogger('secpy')
log.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
#create formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
#add formatter to ch
ch.setFormatter(formatter)
#add ch to logger
log.addHandler(ch)

# read configuration
config = ConfigParser.RawConfigParser()
config.read('secpy.cfg')

last_filename = tmp_file 
first_run = True

debug_last_motion_value = 0.0

#def capture(schedular):
def capture():
    try:
        subprocess.call(["raspistill", "-o", tmp_file, "-t", config.get('image_properties', 'exposure_time'), "-w", config.get('image_properties', 'width'), "-h", config.get('image_properties', 'height')])
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            # raspstill doesn't exist - so warn the user that it's required
            log.critical("Can't find the program 'raspistill'.  Have you enabled the cameramodule on Raspbian?")
            sys.exit(1)
        else:
            raise

    # compare the currently taken image with the last image, and see if there is a enough difference to bother storing it
    global last_filename, first_run
    diff = compare2(last_filename, tmp_file)  
    print('Diff = ' + str(diff))
    
    global debug_last_motion_value
    debug_last_motion_value = diff
    
    if diff > config.getfloat('image_properties', 'motion_threshold' ) or first_run is True:
        first_run = False
        log.debug('Change happened!')
        # create a filename using the current time and date
        now = datetime.datetime.now()
        timestr = now.strftime('/%Y-%m-%d_%H-%M-%S.jpg')
        dest_filename = config.get('image_properties', 'destination_folder') + timestr
        last_filename = dest_filename
        # copy tmp file to permanant storage
        subprocess.call(["mv", tmp_file, dest_filename])
    

def compare(file1, file2):
    image1 = Image.open(file1)
    image2 = Image.open(file2)
    h1 = image1.histogram()
    h2 = image2.histogram()
    rms = math.sqrt(reduce(operator.add,map(lambda a,b: (a-b)**2, h1, h2))/len(h1))
    return rms

def compare2(file1, file2):
    image1 = Image.open(file1)
    image2 = Image.open(file2)

    # 1) get the difference between the two images
    # 2) convert the resulting image into greyscale
    # 3) find the medium value of the grey pixels
    # 4) if over a certain threshold, then we have movement

    image_diff = ImageChops.difference(image1, image2)
    image_diff = ImageOps.grayscale(image_diff)
    image_stat = ImageStat.Stat(image_diff)
    return image_stat.mean[0]

class HTTPThread(threading.Thread):
    def run(self):
        log.debug('Starting HTTP server on port : ' + config.get('server', 'port'))
        server = HTTPServer(("", config.getint('server', 'port')), SecpyHttpHandler)
        server.serve_forever()

class SecpyHttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # see http://www.acmesystems.it/python_httpserver

        if self.path=="/":
            self.send_response(200)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write("""<!DOCTYPE html>
                                <html>
                                    <head>
                                        <title>Raspberry Pi Security System 1.0</title>
                                    </head>
                                    <body>""")

            # spin through all the files in the images folder and add links to them
            self.wfile.write("<p>Last motion-detection value = " + str(debug_last_motion_value) + "</p>\n")
            self.wfile.write("<p>Motion history:</p>\n")
            dest_dir = config.get('image_properties', 'destination_folder')
            dir_list=os.listdir(dest_dir)
            dir_list.sort(reverse=True)
            for fname in dir_list:
                self.wfile.write('<p><a href="' + dest_dir + os.sep + fname + '">' + fname + '</a></p>\n')

            self.wfile.write("""    </body>
                                </html>""")

            return

        try:
            send_reply = False
            print "JIMBO : " + self.path

            if self.path.endswith(".html"):
                mimetype='text/html'
                send_reply = True
            if self.path.endswith(".jpg"):
                mimetype='image/jpg'
                send_reply = True
            if self.path.endswith(".gif"):
                mimetype='image/gif'
                send_reply = True
            if self.path.endswith(".js"):
                mimetype='application/javascript'
                send_reply = True
            if self.path.endswith(".css"):
                mimetype='text/css'
                send_reply = True

            if send_reply == True:
                #Open the static file requested and send it
                f = open(os.curdir + os.sep + self.path) 
                self.send_response(200)
                self.send_header('Content-type',mimetype)
                self.end_headers()
                self.wfile.write(f.read())
                f.close()
            return

        except IOError:
            self.send_error(404,'File Not Found: %s' % self.path)


if __name__ == '__main__':
    log.debug("Starting secpy")

    # fire up the HTTP server?
    if config.getboolean('server', 'server_enable') is True:
        http_thread = HTTPThread()
        http_thread.daemon = True
        http_thread.start()

    while True:
        capture()

