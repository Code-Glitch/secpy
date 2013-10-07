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
from PIL import Image
import math, operator

# pro-tip : to start an HTTP server:
# python -m SimpleHTTPServer 8080

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

#def capture(schedular):
def capture():
    try:
        subprocess.call(["raspistill", "-o", tmp_file, "-w", config.get('image_properties', 'width'), "-h", config.get('image_properties', 'height')])
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            # raspstill doesn't exist - so warn the user that it's required
            log.critical("Can't find the program 'raspistill'.  Have you enabled the cameramodule on Raspbian?")
            sys.exit(1)
        else:
            raise

    # compare the currently taken image with the last image, and see if there is a enough difference to bother storing it
    global last_filename, first_run
    diff = compare(last_filename, tmp_file)  
    print('Diff = ' + str(diff))
    if diff > 900.0 or first_run is True:
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


if __name__ == '__main__':
    log.debug("Starting secpy")
    while True:
        capture()

