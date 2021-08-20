# -*- coding: utf-8 -*-
#
# # qtUC communications
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
# ------------------------------------------------------------------------------- #
import threading
import sys
from time import time
import struct
import pyaudio
import audioop
from math import log10
import json
import hashlib
import qtUC_const as const
import qtUC_defs as defs
from qtUC_vars import qtUCVars as cfg  # configuration variables
import qtUC_util as ut

# message types
MSG_USRP = bytes("USRP", 'ASCII')
MSG_REG = bytes("REG:", 'ASCII')
MSG_UNREG = bytes("UNREG", 'ASCII')
MSG_OK = bytes("OK", 'ASCII')
MSG_INFO = bytes("INFO:", 'ASCII')
MSG_EXITING = bytes("EXITING", 'ASCII')


class qtUcRx(threading.Thread):
    def __init__(self, udp, pya):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.quit = False
        self.connected = False                      # valid audio optput
        self.udp = udp                              # udp port for rx data
        self.pya = pya                              # pyaudio device being used
        self.outIndex = cfg.out_index               # output device index
        self.portName = ''
        self.format = pyaudio.paInt16
        self.chunk = 160 if cfg.SAMPLE_RATE == 8000 else (160 * 6)     # Size of chunk to read
        self.channels = 1                           # output device channels
        self.rate = cfg.SAMPLE_RATE

        self.stream = None                          # output audio stream

        # runtime
        self.currentMode = ''                       # current operating mode
        self.lastKey = -1
        self.start_time = time()
        self.state = None
        self.rxCall = False                         # current Rx state
        self.lastseq = 0                            # previous packet sequence number
        self.rxlevelAvg = 0

        # rx call info
        self.call = ''
        self.mode = ''
        self.name = ''
        self.tg = ''
        self.loss = '0.00%'
        self.rxslot = '0'
        self.callmode = ''                          # group or private

        self.maxaudio = 0                           # debug only

        # packet decode
        # self.eye = None
        self.seq = 0
        # self.memory = None
        self.keyup = False
        # self.talkgroup = None                     # ?? what is this - maybe rx talkgroup??
        self.typestr = ''
        # self.mpxid = None
        # self.reserved = None
        self.audio = b''

        # external handlers
        self.onError = self.nullHandler
        self.onChangeMode = self.nullHandler        # change to YSF or passed AMBE mode
        self.onRegister = self.nullHandler
        self.onServerInfo = self.nullHandler
        self.onRxLevel = self.nullHandler
        self.onRxStart = self.nullHandler
        self.onRxEnd = self.nullHandler
        self.onNotifyMsg = self.nullHandler
        self.onRequestInfo = self.nullHandler
        self.onChangeTG = self.nullHandler
        self.onSetMode = self.nullHandler

        self.openAudioOut()                         # start the engine

    def shutdown(self):
        self.quit = True
        # while self.rxCall:                          # in a call?
        #    sleep(.25)                               # wait a bit before exiting

    def openAudioOut(self):
        if self.outIndex < 0:                       # unlikely but...
            self.connected = False
            return

        try:
            parms = self.pya.get_device_info_by_host_api_device_index(0, self.outIndex)
            self.channels = parms.get('maxOutputChannels')
            if self.channels <= 0:
                errmsg = 'Specified output device has no channels'
                ut.log.error(errmsg)
                self.onError(errmsg)
                return
        except Exception as e:
            errmsg = 'Specified output device does not exist ' + str(e)
            ut.log.error(errmsg)
            self.onError(errmsg)
            return

        #  open the output
        try:
            self.stream = self.pya.open(format=self.format,
                                        channels=self.channels,
                                        rate=self.rate,
                                        # input=False,
                                        output=True,
                                        frames_per_buffer=self.chunk,
                                        output_device_index=self.outIndex
                                        )
        except Exception:
            errmsg = defs.STRING_FATAL_OUTPUT_STREAM + str(sys.exc_info()[1])
            ut.log.critical(errmsg)
            self.connected = False                  # no rx audio available
            self.onError(errmsg)
            return

        # all is well
        self.portName = parms.get('name')
        ut.log.info("Output Device: {} Index: {}".format(self.portName, self.outIndex))
        self.connected = True

    def run(self):
        ut.log.info('Starting rx audio thread')
        while not self.quit:
            soundData, addr = self.udp.recvfrom(1024)
            # if self.quit:                         # exit whilst receiving
            #    # self.rxCall = False
            #    break
            if addr[0] != cfg.ip_address:           # not the same as configured?
                cfg.ip_address = addr[0]            # OK, this was supposed to help set the ip to a server, but multiple servers ping/pong.  I may remove it.
            self.rxAudioStream(soundData)

    # Null event handler
    def nullHandler(self, *args):
        return

    # RX data processing
    def rxAudioStream(self, soundData):
        if (soundData[0:4] == MSG_USRP):            # we only handle USRP packets
            # decode the packet
            eye = soundData[0:4]                                    # not used
            self.seq, = struct.unpack(">i", soundData[4:8])
            memory, = struct.unpack(">i", soundData[8:12])          # not used
            self.keyup, = struct.unpack(">i", soundData[12:16])
            talkgroup, = struct.unpack(">i", soundData[16:20])      # not used
            self.typestr, = struct.unpack("i", soundData[20:24])
            mpxid, = struct.unpack(">i", soundData[24:28])          # not used
            reserved, = struct.unpack(">i", soundData[28:32])       # not used
            self.audio = soundData[32:]

            # process it
            if (self.typestr == const.USRP_TYPE_VOICE):             # voice
                self.processAudio()
            elif (self.typestr == const.USRP_TYPE_TEXT):            # metadata
                # self.processMetadata()
                if (self.audio[0:4] == MSG_REG):
                    self.processRegistration()
                elif (self.audio[4:9] == MSG_UNREG):
                    self.processRegistration()
                elif (self.audio[0:5] == MSG_INFO):
                    self.processInfo()
                else:
                    self.processTLVText()
            elif (self.typestr == const.USRP_TYPE_PING):
                self.processPing()
            elif (self.typestr == const.USRP_TYPE_TLV):
                self.processTLV()

    def processAudio(self):
        # audio = soundData[32:]
        # print(eye, seq, memory, keyup, talkgroup, type, mpxid, reserved, audio, len(audio), len(soundData))
        if self.connected and len(self.audio) == 320:
            # audio output - input stream data is always mono
            if self.rate == 48000:
                (audio48, self.state) = audioop.ratecv(self.audio, 2, 1, 8000, 48000, self.state)
                if self.channels > 1:
                    audio48 = audioop.tostereo(audio48, 2, 1, 1)
                self.stream.write(bytes(audio48), self.chunk)

                # waggle the meter
                if (self.seq % cfg.level_every_sample) == 0:
                    rms = audioop.rms(self.audio, 2)        # Get a relative power value for the sample
                    self.rxLevel(rms)
            else:
                self.stream.write(self.audio, self.chunk)

        # change of state - idle > Rx, Rx > idle
        # print(self.keyup, self.lastKey)
        if self.keyup != self.lastKey:
            # print('key change ', self.keyup, self.lastKey)
            ut.log.debug('key' if self.keyup else 'unkey')
            if self.keyup > 0:
                self.callStart()
                # print('Rx start')
            else:                                       # self.keyup == False:
                # print('Rx end')
                self.endCall()

        self.lastKey = self.keyup                       # save key state of this packet

    def processRegistration(self):
        if (self.audio[4:6] == MSG_OK):
            self.onRegister(True)                       # we have connected to the server
        elif (self.audio[4:9] == MSG_UNREG):
            self.onRegister(False)                      # server disconnect
        elif (self.audio[4:11] == MSG_EXITING):
            tmp = self.audio[:self.audio.find(b'\x00')].decode('ASCII')     # C string
            args = tmp.split(" ")
            sleepTime = int(args[2])                    # requsted re-registration time
            ut.log.info("AB is exiting and wants a re-reg in %s seconds...", sleepTime)
            self.onRegister(False, sleepTime)

        ut.log.debug(self.audio[:self.audio.find(b'\x00')].decode('ASCII'))      # log restration info

    def processInfo(self):
        _json = self.audio[5:self.audio.find(b'\x00')].decode('ASCII')
        if (_json[0:4] == "MSG:"):
            ut.log.info("Text Message: " + _json[4:])
            self.onNotifyMsg('text', _json[4:])         # popup a text message
        elif (_json[0:6] == "MACRO:"):                  # An ad-hoc macro menu
            ut.log.debug("Macro: " + _json[6:])
            macs = _json[6:]
            macrosx = dict(x.split(",") for x in macs.split("|"))
            macros = {k: v.strip() for k, v in macrosx.items()}
            self.onNotifyMsg('macro', macros)           # do something with the supplied macros
        elif (_json[0:5] == "MENU:"):                   # An ad-hoc macro menu
            ut.log.debug("Menu: " + _json[5:])
            macs = _json[5:]
            macrosx = dict(x.split(",") for x in macs.split("|"))
            macros = {k: v.strip() for k, v in macrosx.items()}
            self.onNotifyMsg('menu', macros)            # do something with the supplied menu options
        else:
            obj = json.loads(self.audio[5:self.audio.find(b'\x00')].decode('ASCII'))
            ut.log.debug('ambe mode: ' + obj['tlv']['ambe_mode'] + ' - Tg: ' + obj['last_tune'])
            if (obj["tlv"]["ambe_mode"][:3] == "YSF"):
                self.changeRxMode('YSF', obj['last_tune'])
            else:
                self.changeRxMode(obj['tlv']['ambe_mode'], obj['last_tune'])

            # self.tg = obj["last_tune"]
            ut.log.debug('info packet received')
            ut.log.debug(obj['digital'])
            ut.log.debug(self.audio[:self.audio.find(b'\x00')].decode('ASCII'))
            self.onServerInfo(obj['digital'])             # current server params

            # self.onChangeStatus(defs.STRING_CONNECTED_TO + " " + obj["last_tune"])
            # self.onChangeStatus(True, obj["last_tune"])
            # self.onConnect(obj["last_tune"])        # connected to ...
            # self.selectTGByValue(obj["last_tune"])

    def processTLVText(self):
        # Tunnel a TLV inside of a USRP packet
        if self.audio[0] == const.TLV_TAG_SET_INFO:
            if self.rxCall:  # enableTX:    # EOT missed?
                ut.log.warning('Call EOT in tlv info')
                self.endCall()
            # print('info data ', self.audio)
            rxid = (self.audio[2] << 16) + (self.audio[3] << 8) + self.audio[4]          # Source
            # print('rid ', rid)
            # print(self.audio[5],self.audio[6],self.audio[7],self.audio[8])
            self.tg = (self.audio[9] << 16) + (self.audio[10] << 8) + self.audio[11]    # Dest
            # print('tg ', self.tg)
            self.rxslot = self.audio[12]
            # print('slot ', self.rxslot)
            rxcc = self.audio[13]
            # print('rxcc ', rxcc)
            self.callmode = defs.STRING_PRIVATE if (rxcc & 0x80) else defs.STRING_GROUP
            self.name = ""
            if self.audio[14] == 0:                             # C string termintor for call
                self.call = str(rxid)
            else:
                self.call = self.audio[14:self.audio.find(b'\x00', 14)].decode('ASCII')
                if self.call[0] == '{':                         # its a json dict
                    obj = json.loads(self.call)
                    self.call = obj['call']
                    self.name = obj['name'].split(' ')[0] if 'name' in obj else ""
            self.rxCallInfo()

            if ((rxcc & 0x80) and (rxid > 10000)):   # > 10000 to exclude "4000" from BM
                # a dial string with a pound is a private call, see if the current TG matches
                privateTG = str(rxid) + '#'
                ut.log.debug('rid {} - call tg {}'.format(rxid, self.tg))
                ut.log.debug('rx callmode ' + privateTG)
                self.onChangeTG(privateTG)              # add and select dialled TG

    def processPing(self):
        if self.rxCall:                         # Do we think we are receiving packets?, lets test for EOT missed
            if (self.lastseq + 1) == self.seq:
                ut.log.debug("Ping check - missed EOT")
                self.endCall()
                # self.onEndRX(self.call, self.rxslot, self.tg, self.loss, self.start_time)
                # self.log_end_of_transmission(call, rxslot, tg, loss, start_time)
                # self.enableTX = True    # Idle state, allow local transmit
            self.lastseq = self.seq

    def processTLV(self):
        tag = self.audio[0]
        length = self.audio[1]
        value = self.audio[2:]
        if tag == const.TLV_TAG_FILE_XFER:
            FILE_SUBCOMMAND_NAME = 0
            FILE_SUBCOMMAND_PAYLOAD = 1
            FILE_SUBCOMMAND_WRITE = 2
            FILE_SUBCOMMAND_READ = 3
            FILE_SUBCOMMAND_ERROR = 4
            if value[0] == FILE_SUBCOMMAND_NAME:
                file_len = (value[1] << 24) + (value[2] << 16) + (value[3] << 8) + value[4]
                file_name = value[5:]
                zero = file_name.find(0)
                file_name = file_name[:zero].decode('ASCII')
                ut.log.info("File transfer name: " + file_name)
                m = hashlib.md5()
            if value[0] == FILE_SUBCOMMAND_PAYLOAD:
                ut.log.debug("Payload len = " + str(length - 1))
                payload = value[1:length]
                m.update(payload)
                # ut.log.debug(payload.hex())
                # ut.log.debug(payload)
            if value[0] == FILE_SUBCOMMAND_WRITE:
                digest = m.digest().hex().upper()
                file_md5 = value[1:33].decode('ASCII')
                if (digest == file_md5):
                    ut.log.info("File digest matches")
                else:
                    ut.log.info("File digest does not match {} vs {}".format(digest, file_md5))
                # ut.log.info("write (md5): " + value[1:33].hex())
            if value[0] == FILE_SUBCOMMAND_ERROR:
                ut.log.error("error")

    def callStart(self):
        self.start_time = time()
        if not self.rxCall:     # missed call start?
            self.rxCall = True
            self.onRxStart(self.call, self.name, self.tg)

    def rxCallInfo(self):
        self.rxCall = True
        ut.log.debug('Begin RX: {} {} {} {}'.format(self.call, self.rxslot, self.tg, self.callmode))
        self.onRxStart(self.call, self.name, self.tg)

    def endCall(self):
        self.rxCall = False
        # update
        # print('end call ', self.call, self.tg)
        # print('max ', self.rxMax)
        self.onRxLevel(0)
        self.onRxEnd(self.call, self.name, self.currentMode, self.rxslot,
                     self.tg, self.callmode, self.loss, self.start_time)

        # end receive call
        # callinfo = [self.call, self.name, self.currentMode, self.rxslot,
        #             self.tg, self.callmode, self.loss, self.start_time]
        self.call = ''
        self.name = ''
        self.rxslot = '0'
        self.tg = ''
        self.loss = '0.00%'    # is this always zero?
        self.start_time = 0
        self.callmode = ''

    def changeRxMode(self, mode, tg):
        # Rx mode update
        self.currentMode = mode
        self.tg = tg
        self.onChangeMode(mode, tg)         # pass it on

    def rxLevel(self, level):
        # smooth out rx levels
        lvl = int(level / 100)
        avg = int((lvl + self.rxlevelAvg) / 2)
        if avg > self.rxlevelAvg:
            self.rxlevelAvg = avg

        if self.rxlevelAvg >= 0:
            if self.rxlevelAvg > 0:
                lvDB = int(20 * log10(self.rxlevelAvg))
            else:
                lvDB = 0
            # if lvDB > self.rxMax:
            #     self.rxMax = lvDB
            self.onRxLevel(lvDB)
            self.rxlevelAvg -= 2
            # print('max ', self.rxMax, ' avg ', lvDB)
