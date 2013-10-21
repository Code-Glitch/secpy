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
import fnmatch
from PIL import Image, ImageChops, ImageOps, ImageStat
import math, operator
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
import urlparse
import base64
import threading
from collections import namedtuple

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
force_shot = True

debug_last_motion_value = 0.0
recording_enabled = True

#def capture(schedular):
def capture():
    if recording_enabled is False:
        return
    # get the config settings for image capture
    exposure_time = config.get('image_properties', 'exposure_time')
    width = config.get('image_properties', 'width')
    height = config.get('image_properties', 'height')
    exposure_options = config.get('image_properties', 'exposure_options')
    try:
        subprocess.call(["raspistill", "-o", tmp_file, "-t", exposure_time, "-w", width, "-h", height, "-ex", exposure_options])
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            # raspstill doesn't exist - so warn the user that it's required
            log.critical("Can't find the program 'raspistill'.  Have you enabled the cameramodule on Raspbian?")
            sys.exit(1)
        else:
            raise

    # compare the currently taken image with the last image, and see if there is a enough difference to bother storing it
    global last_filename, force_shot
    diff = compare2(last_filename, tmp_file)  
    
    global debug_last_motion_value
    debug_last_motion_value = diff
    
    if diff > config.getfloat('image_properties', 'motion_threshold' ) or force_shot is True:
        force_shot = False
        log.debug('Change happened!')
        # create a filename using the current time and date
        now = datetime.datetime.now()
        timestr = now.strftime('/%Y-%m-%d_%H-%M-%S.jpg')
        dest_folder = config.get('image_properties', 'destination_folder') 
        dest_filename = dest_folder + timestr
        last_filename = dest_filename
        # copy tmp file to permanant storage
        # check the file will fit in the destination folder
        file_size = os.path.getsize(tmp_file)
        disk_usage_stats = disk_usage(dest_folder)
        if file_size > disk_usage_stats.free:
            ensure_free_space(dest_folder, file_size)
        
        subprocess.call(["cp", tmp_file, dest_filename])
    

def compare(file1, file2):
    try:
        image1 = Image.open(file1)
        image2 = Image.open(file2)
    except IOError as e:
        log.critical(e)
        return 0.0

    h1 = image1.histogram()
    h2 = image2.histogram()
    rms = math.sqrt(reduce(operator.add,map(lambda a,b: (a-b)**2, h1, h2))/len(h1))
    return rms

def compare2(file1, file2):
    try:
        image1 = Image.open(file1)
        image2 = Image.open(file2)
    except IOError as e:
        log.critical(e)
        return 0.0

    # 1) get the difference between the two images
    # 2) convert the resulting image into greyscale
    # 3) find the medium value of the grey pixels
    # 4) if over a certain threshold, then we have movement

    image_diff = ImageChops.difference(image1, image2)
    image_diff = ImageOps.grayscale(image_diff)
    image_stat = ImageStat.Stat(image_diff)
    return image_stat.mean[0]

# following is from : http://stackoverflow.com/questions/787776/find-free-disk-space-in-python-on-os-x
_ntuple_diskusage = namedtuple('usage', 'total used free')
def disk_usage(path):
    """Return disk usage statistics about the given path.

    Returned values is a named tuple with attributes 'total', 'used' and
    'free', which are the amount of total, used and free space, in bytes.
    """
    st = os.statvfs(path)
    free = st.f_bavail * st.f_frsize
    total = st.f_blocks * st.f_frsize
    used = (st.f_blocks - st.f_bfree) * st.f_frsize
    return _ntuple_diskusage(total, used, free)

def ensure_free_space(path, free_space_bytes):
    """WARNING: This function is dangerous as it will delete .jpg files in the given path.  It ensures that there's enough free space at the given location - by deleting old .jpg files.""" 
    
    # gather list of .jpg files
    file_list = []
    for filename in os.listdir(path):
        if fnmatch.fnmatch(filename, '*.jpg'):
            full_fname = path + os.sep + filename
            file_list.append((os.stat(full_fname).st_mtime, full_fname))

    # reverse-sort by modified date
    file_list.sort(key=lambda a: a[0])
    file_list.reverse()

    # while we don't have enough space...
    while True:
        disk_usage_stats = disk_usage(path)
        dst_free_space = disk_usage_stats.free

        if len(file_list) == 0:
            break

        if dst_free_space < free_space_bytes:
            try:
                # delete oldest file
                log.debug("Removed : " + file_list[0][1])
                os.remove(file_list[0][1])
                file_list.pop(0)
            except IOError as e:
                log.critical(e)
        else:
            # we have enough space, so break out
            break

class HTTPThread(threading.Thread):
    def run(self):
        # check password isn't the default
        if config.get('server', 'password') == 'changeme':
            log.warning('Password is set to default!  Consider changing it to a unique password in secpy.cfg.')
        
        log.debug('Starting HTTP server on port : ' + config.get('server', 'port'))

        server_address = ("", config.getint('server', 'port'))
        server = HTTPServer(server_address, SecpyHttpHandler)
        server.serve_forever()


class SecpyHttpHandler(BaseHTTPRequestHandler):
    ''' Main class to present webpages and authentication. '''
    def do_HEAD(self):
        print "send header"
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_AUTHHEAD(self):
        print "send header"
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"Test\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        ''' Present frontpage with user authentication. '''

        # generate base64 encoding of the username and password
        credentials64 = base64.b64encode ( config.get('server', 'username') + ":" + config.get('server', 'password') )
        
        if self.headers.getheader('Authorization') == None:
            self.do_AUTHHEAD()
            self.wfile.write('no auth header received')
            pass
        elif self.headers.getheader('Authorization') == ('Basic ' + credentials64):
            return self.index_page()
        else:
            self.do_AUTHHEAD()
            self.wfile.write(self.headers.getheader('Authorization'))
            self.wfile.write(' - not authenticated')
            pass

    def index_page(self):
        # see http://www.acmesystems.it/python_httpserver

        # discover any parameters
        query_str = urlparse.urlsplit(self.path).query
        params = None
        if len(query_str) > 0:
            params = urlparse.parse_qsl(query_str, 0, 1)

        global recording_enabled
        global force_shot
        if params is not None:
            if ('enable_recording', 'False') in params:
                # stop recording
                recording_enabled = False
            elif ('enable_recording', 'True') in params:
                # start recording
                recording_enabled = True
            
            if ('force_shot', 'True') in params:
                # force a shot to be taken and stored
                force_shot = True


        try:
            send_reply = False

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
                f = open(config.get('image_properties', 'destination_folder') + self.path) 
                self.send_response(200)
                self.send_header('Content-type',mimetype)
                self.end_headers()
                self.wfile.write(f.read())
                f.close()
            else:
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
                if recording_enabled:
                    self.wfile.write("<p><a href='?enable_recording=False'>Disable recording</a></p>\n")
                else:
                    self.wfile.write("<p><a href='?enable_recording=True'>Enable recording</a></p>\n")
                self.wfile.write("<p><a href='?force_shot=True'>Force shot</a> (forces a picture to be taken and saved)</p>\n")
                self.wfile.write("<p>Last motion-detection value = " + str(debug_last_motion_value) + "</p>\n")
                self.wfile.write("<p>Motion history:</p>\n")
                dest_dir = config.get('image_properties', 'destination_folder')
                dir_list=os.listdir(dest_dir)
                dir_list.sort(reverse=True)
                for fname in dir_list:
                    self.wfile.write('<p><a href="' + fname + '">' + fname + '</a></p>\n')

                self.wfile.write("""    </body>
                                    </html>""")
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

