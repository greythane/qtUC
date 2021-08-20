# -*- coding: utf-8 -*-
#
# qtUC - pyUC with a QT interface
# Based on the original pyUC code, modified for QT5 use
# Rowan Deppeler - VK3VW - greythane @ gmail.com
#
# pyUC ("puck")
# Copyright (C) 2014, 2015, 2016, 2019, 2020, 2021 N4IRR
#
# This software is for use on amateur radio networks only, it is to be used
# for educational purposes only. Its use on commercial networks is strictly
# prohibited.  Permission to use, copy, modify, and/or distribute this software
# hereby granted, provided that the above copyright notice and this permission
# notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND DVSWITCH DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS.  IN NO EVENT SHALL N4IRR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
# OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.
#
# --------------------------------------------------------------------------- #
import os
import logging
import logging.handlers
import pyaudio
# from PyQt5.Qt import QImage, QByteArray, QBuffer

DOCPATH = os.path.join(os.path.expanduser('~'), 'Documents', 'qtUC')
LOG_FILENAME = './qtUC.log'

# Make sure the documents directory exists
try:
    if not os.path.isdir(DOCPATH):
        os.makedirs(DOCPATH)
    LOG_FILENAME = os.path.join(DOCPATH, 'qtUC.log')
except Exception:
    pass            # oh well... :()

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=1000000, backupCount=5)
# handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s : %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)

# logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)


def setLoglevel(level):
    log.info('Setting log level to ' + level)
    log.setLevel(level.upper())


# ----------------- #
#      Helpers      #
# ----------------- #
def parseint(s):
    try:
        value = int(s)
    except ValueError:
        value = 0
    return value


def getAudioDevices():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    audiodevs = {
        'devices': {},
        'numdevices': info['deviceCount'],
        'defaultInput': info['defaultInputDevice'],
        'defaultOutput': info['defaultOutputDevice']
    }
    for devidx in range(info['deviceCount']):
        audev = p.get_device_info_by_host_api_device_index(0, devidx)
        audiodevs['devices'][devidx] = {'name': audev['name'],
                                        'is_input': (audev['maxInputChannels'] > 0),
                                        'is_output': (audev['maxOutputChannels'] > 0),
                                        }
        log.info("Device id {} - {}".format(devidx, audev))
    return audiodevs


'''
def pixmap_to_data(pixmap):
    # convert a pixmal to a bytearray suitable for caching
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pixmap.save(buf, 'PNG')
    return bytearray(ba.data())


def data_to_pixmap(data):
    # Create a pixmap from cached bytsearray
    ba = QByteArray(data)
    buf = QBuffer(ba)
    buf.open(QBuffer.ReadOnly)
    r = QImageReader(buf)
    # fmt = bytes(r.format()).decode('utf-8')
    return r.read()         # , fmt
'''
