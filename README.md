secpy
=====

Security camera software for Raspberry Pi Camera Module.

This software enables Raspberry Pi hardware to take snapshots from the Pi Camera Module and work out if a significant change has occured from the last still-image, and store the image as JPG (with date/time etc).

Features
========
* Supports the official RaspberryPi Camera Module.
* Measures changes in image and takes a high-resolution snapshot which is only stored if the change is large enough - this saves on storage requirements.
* Web-based frontend with password protection.
* Various options to control image quality.

Installing
==========

1. This has only been testing on the offical Rasbian release
2. Make sure you enable the Camera Module (option found in raspi-config - just run that)
3. Install the Python Imaging Library : sudo apt-get install python-imaging
4. ...
5. Profit

