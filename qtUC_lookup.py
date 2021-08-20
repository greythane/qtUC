# -*- coding: utf-8 -*-
#
# qtUC communications
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
import queue
import sys
import datetime
from time import sleep
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QPixmap
import qtUC_defs as defs
import qtUC_const as const
from qtUC_vars import qtUCVars as var  # configuration variables
import qtUC_util as ut

# -- HTML/QRZ import libraries  --#
try:
    from urllib.request import urlopen
    from bs4 import BeautifulSoup
    from PIL import Image
    from PIL.ImageQt import ImageQt
    import requests
except Exception:
    ut.log.info(defs.STRING_FATAL_ERROR + str(sys.exc_info()[1]))
    exit(1)


class qrzLookup(QThread):
    def __init__(self, ttl=3600):
        QThread.__init__(self)
        self.quit = False
        self.qrz_cache = {}                 # call cache to 1) speed execution 2) limit the lookup count on qrz.com. 3) cache the thumbnails we do find
        self.cache_ttl = ttl                # default ttl of 1 hour
        self.qrz_queue = queue.Queue()      # Each request is a callsign to lookup.
        self.defaultpix = QPixmap(':/images/netradio').scaled(100, 80)
        self.chatpix = QPixmap(':/images/genchat').scaled(100, 80)

        # callback when data available
        self.onLookup = self.nullHandler

    def shutdown(self):
        self.quit = True

    def nullHandler(self, *args):
        return

    def run(self):
        while not self.quit:
            try:
                callsign = self.qrz_queue.get()         # wait until a callsign is placed in the queue
                if callsign == '':                      # should not happen but...
                    self.onLookup(self.defaultpix)      # idle pix
                elif var.useQRZ:
                    callpix = self.getQRZImage(callsign)
                    if self.qrz_queue.empty():          # only update if there is nothing in the queue
                        self.onLookup(callpix)
            except queue.Empty:
                pass
            sleep(0.1)

    # Return the URL of an image associated with the callsign.  The URL may be cached or scraped from QRZ
    def getImgUrl(self, callsign):
        img_url = ""
        now_dt = datetime.datetime.now()
        if callsign in self.qrz_cache:
            exp = now_dt - self.qrz_cache[callsign]['timestamp']
            # print('cache secs ', exp)
            if exp.total_seconds() < self.cache_ttl:
                self.qrz_cache[callsign]['timestamp'] = now_dt
                return self.qrz_cache[callsign]['url']

        # try for QRZ image url for the callsign
        try:
            # specify the url
            quote_page = 'https://qrz.com/lookup/' + callsign

            # query the website and return the html to the variable ‘page’
            page = urlopen(quote_page, timeout=20).read()

            # parse the html using beautiful soup and store in variable `soup`
            soup = BeautifulSoup(page, 'html.parser')
            img_url = soup.find(id='mypic')['src']
        except Exception:
            pass

        self.qrz_cache[callsign] = {'url': img_url, 'timestamp': now_dt}     # url or blank
        return img_url

    def getQRZImage(self, callsign):
        # download the callsign image from the QRZ website
        photo = self.chatpix                        # If not found, general chat
        if len(callsign) > 0:
            image_url = self.getImgUrl(callsign)
            if len(image_url) > 0:
                if 'image' in self.qrz_cache[callsign]:
                    pix = self.qrz_cache[callsign]['image']
                    if pix is not None:
                        qphoto = ImageQt(pix)
                        photo = QPixmap.fromImage(qphoto)
                        return photo

                try:
                    resp = requests.get(image_url, stream=True).raw
                    image = Image.open(resp)
                    image.thumbnail((100, 80), Image.LANCZOS)
                    qphoto = ImageQt(image)
                    photo = QPixmap.fromImage(qphoto)
                    self.qrz_cache[callsign]['image'] = image
                except Exception:
                    self.qrz_cache[callsign]['image'] = None

        return photo

    def lookup_country(self, callsign):
        # use callsign to evaluate country
        chklen = 4                                  # start a four chars match
        ctry = ''
        flag = ''
        while chklen > 0:
            cs = callsign[0:chklen]
            if cs in const.CCODES:
                ctry = const.CCODES[cs][0]
                flag = const.CCODES[cs][3]
                break
            chklen -= 1                             # try for a shorter match

        return ctry, flag
