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
import threading
import sys
from math import log10
import struct
import pyaudio
import audioop
import qtUC_const as const
import qtUC_defs as defs
from qtUC_vars import qtUCVars as cfg               # configuration variables
import qtUC_util as ut


class qtUcTx(threading.Thread):
    # initializes the class
    def __init__(self, pya):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.quit = False
        self.paused = True                          # startup paused
        self.pause_cond = threading.Condition(threading.Lock())
        self.connected = False                      # valid audio input
        # self.udp = udp                            # tx socket
        self.pya = pya                              # audio device
        self.inIndex = cfg.in_index                 # audio input (mic) device index
        self.portName = ''
        self.format = pyaudio.paInt16
        self.chunk = 160 if cfg.SAMPLE_RATE == 8000 else (160 * 6)     # Size of chunk to read
        self.channels = 1
        self.rate = cfg.SAMPLE_RATE

        self.stream = None                          # input audio stream

        # external handlers
        self.onSendUDP = self.nullHandler
        self.onError = self.nullHandler
        self.onTxLevel = self.nullHandler
        self.onVoxPtt = self.nullHandler            # used for vox mode

        # runtime
        self.enableVox = cfg.vox_enable             # default vox
        self.vox_decay = -1                         # vox decay
        self.transmit_enable = False                # allow transmit - assume no until setup
        self.lastptt = False                        # previous ptt state
        self.ptt = False                            # Current ptt state
        self.usrpSeq = 0                            # Each USRP packet has a unique sequence number
        self.txLevelAvg = 0

        self.openAudioInput()

    def shutdown(self):
        ut.log.debug('tx - ' + defs.STRING_EXITING)
        self.quit = True

    def openAudioInput(self):
        if self.inIndex < 0:                        # no audio input
            self.transmit_enable = False
            ut.log.warning('No tx input ')
            return

        try:
            parms = self.pya.get_device_info_by_host_api_device_index(0, self.inIndex)
            self.portName = parms.get('name')
            self.channels = parms.get('maxInputChannels')
            if self.channels <= 0:
                errmsg = 'Specified input device has no channels'
                ut.log.error(errmsg)
                self.onError(errmsg)
                return
        except Exception as e:
            errmsg = 'Specified input device does not exist ' + str(e)
            ut.log.error(errmsg)
            self.onError(errmsg)
            return

        #  open the input
        try:
            self.stream = self.pya.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                # output=False,
                frames_per_buffer=self.chunk,
                input_device_index=self.inIndex
            )
        except Exception as e:
            errmsg = defs.STRING_FATAL_INPUT_STREAM + str(sys.exc_info()[1])
            # print(' tx audio barf ', str(e), errmsg)
            ut.log.error(errmsg)
            self.onError(errmsg)
            return

        # all is well
        ut.log.info("Input Device: {} Index: {}".format(self.portName, self.inIndex))
        self.connected = True

    # Null event handler
    def nullHandler(self, *args):
        return

    def sendto(self, usrp):
        return
        self.onSendUDP(usrp)
        # return  # don't send anything yet

        # for port in cfg.usrp_tx_port:
        #     self.udp.sendto(usrp, (cfg.ip_address, port))

    def resume(self):
        # print('tx resuming...')
        with self.pause_cond:
            self.paused = False
            self.pause_cond.notify()                # Unblock self if waiting.

    def pause(self):
        # print('tx pausing...')
        with self.pause_cond:
            self.paused = True                      # Block self.
            self.pause_cond.notify()

    def transmit(self, pttState):
        self.ptt = pttState
        if pttState:
            self.resume()
        else:
            self.pause()

    # TX thread, send audio to AB
    def run(self):
        state = None

        ut.log.info('Starting tx audio thread')
        self.lastPtt = self.ptt
        if not self.connected:                      # we have input capability
            ut.log.error('No audio input connected, pausing tx audio thread')
            self.onError('No audio input connected, pausing tx audio thread')
            self.pause()
            return

        # self.resume()
        while not self.quit:
            if not self.enableVox:
                # print('no vox')
                with self.pause_cond:
                    # print('checking pause')
                    if self.paused:
                        # print('paused')
                        self.pause_cond.wait()          # Block execution until notified.

            # good to go...
            try:
                # print('sampling...')
                if self.rate == 48000:                  # If we are reading at 48K we need to resample to 8K
                    audio48 = self.stream.read(self.chunk, exception_on_overflow=False)
                    (self.audio, state) = audioop.ratecv(audio48, 2, 1, 48000, 8000, state)
                else:
                    self.audio = self.stream.read(self.chunk, exception_on_overflow=False)

                # print('chunk...')
                rms = audioop.rms(self.audio, 2)        # Get a relative power value for the sample

                # -- Vox processing -- #
                if self.enableVox:
                    # print('vox check')
                    if rms > cfg.vox_threshold:                     # is it loud enough?
                        self.vox_decay = cfg.vox_delay              # Yes, reset the decay value (wont unkey for N samples)
                        if not self.ptt and self.transmit_enable:   # Are we changing ptt state to True?
                            self.ptt = True                         # Set it
                            self.onVoxPtt(True)                     # Update the UI (turn transmit button red, etc)
                    elif self.ptt:                                  # Are we too soft and transmitting?
                        self.vox_decay -= 1                         # Decrement the decay counter
                        if self.vox_decay <= 0:                     # Have we passed N samples, all of them less then the threshold?
                            self.ptt = False                        # Unkey
                            self.onVoxPtt(False)                    # Update the UI
                # -------------------- #

                # change of state Tx > idle or Idle > Tx (Vox)
                if self.ptt or (self.ptt != self.lastPtt):
                    # print('sending...', self.audio)
                    bUsrp = 'USRP'.encode('ASCII') + struct.pack('>iiiiiii',
                                                                 self.usrpSeq,
                                                                 0, self.ptt, 0,
                                                                 const.USRP_TYPE_VOICE, 0, 0) + self.audio
                    self.sendto(bUsrp)
                    self.usrpSeq += 1
                self.lastPtt = self.ptt
                if self.ptt:
                    self.txLevel(rms)

            except Exception:
                ut.log.warning("TX thread:" + str(sys.exc_info()[1]))

    def voxState(self, state):
        # enable/disable vox
        currentState = self.enableVox
        self.enableVox = state                      # new state
        if currentState:                            # currently enabled
            self.pause()                            # back to ptt mode
        else:
            self.resume()                           # vox mode

    def txLevel(self, level):
        # smooth out rx levels
        lvl = int(level / 100)
        avg = int((lvl + self.txLevelAvg) / 2)
        if avg > self.txLevelAvg:
            self.txLevelAvg = avg

        if self.txLevelAvg >= 0:
            if self.txLevelAvg > 0:
                lvDB = int(20 * log10(self.txLevelAvg))
            else:
                lvDB = 0
            # if lvDB > self.rxMax:
            #     self.rxMax = lvDB
            self.onTxLevel(lvDB)
            self.txLevelAvg -= 2
