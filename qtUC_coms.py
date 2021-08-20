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
from time import time, sleep
import socket
import struct
import traceback
import pyaudio
from qtUC_rx import qtUcRx
from qtUC_tx import qtUcTx
import qtUC_const as const
import qtUC_defs as defs
from qtUC_vars import qtUCVars as var  # configuration variables
import qtUC_util as ut


from ctypes import *
from contextlib import contextmanager


def py_error_handler(filename, line, function, err, fmt):
    pass


ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)


@contextmanager
def noalsaerr():
    try:
        asound = cdll.LoadLibrary('libasound.so')
        asound.snd_lib_error_set_handler(c_error_handler)
        yield
        asound.snd_lib_error_set_handler(None)
    except Exception:
        yield
        pass


# -- Catch and display any socket errors  -- #
def socketFailure():
    # var.connected_msg = defs.STRING_CONNECTION_FAILURE
    ut.log.error(defs.STRING_SOCKET_FAILURE)


# -- keep alive -- #
class keepalive(threading.Thread):
    # class keepalive(qtComs):
    # initializes the class
    def __init__(self, parent=None):
        threading.Thread.__init__(self)
        self.parent = parent
        self.setDaemon(True)
        self.quit = False
        self.onPing = None

    def exit(self):
        self.quit = True
        print('keepalive exiting...')

    def run(self):
        while not self.quit:
            sleep(20.0)
            super().sendUSRPCommand(bytes("PING", 'ASCII'), const.USRP_TYPE_PING)
            print('ping...')


class qtComs():
    # initializes the class
    def __init__(self):
        # devices
        self.pya = None
        self.txa = None                             # Tx audio
        self.rxa = None                             # Rx audio
        self.keepalive = None
        self.udp = None                             # UDP socket for USRP traffic
        self.usrpSeq = 0                            # Each USRP packet has a unique sequence number

        # runtime
        self.txEnable = False                       # allow TX audio
        self.regState = False                       # registration state
        self.ptt = False                            # Current ptt state
        self.tx_start_time = 0                      # TX timer
        self.tx_duration = 0                        # Tx call duration
        self.transmit_enable = True                 # Make sure that UC is half duplex

        # configuration
        self.dmrid = var.subscriber_id
        self.mycall = var.my_call

        self.sp_vol = var.sp_vol
        self.audio_level = 0
        self.currentMode = ''                       # current operating mode
        self.currentTG = ''
        self.currentTgName = ''
        self.txSlot = var.slot
        self.colorC = '1'                           # not currently used but for reference

        # external handlers
        self.onError = self.nullHandler
        self.onRegisterStatus = self.nullHandler
        self.onNotifyMsg = self.nullHandler
        self.onTxEnable = self.nullHandler          # Enable/Disable state of the tx button
        self.onPttStatus = self.nullHandler         # current PTT state updates
        self.onVoxStatus = self.nullHandler         # vox enabled/disabled updates
        self.onVoxPtt = self.nullHandler            # vox avtive/inactive
        self.onEndTxCall = self.nullHandler         # end of tx
        self.onEndRxCall = self.nullHandler         # End of Rx call info
        self.onCallInfo = self.nullHandler          # Start call info, picture etc
        self.onTxRxLevel = self.nullHandler         # Tx/Rx levels
        self.onSelectTg = self.nullHandler          # rx talkgroup (mode)

        self.init_comms()                           # setup udp stream

    def exit(self):
        ut.log.debug('coms - ' + defs.STRING_EXITING)
        # shut it down
        if self.keepalive is not None:
            self.keepalive.exit()

        if self.regState:                           # If we were registered, tell AB we are done
            self.unregisterWithAB()
            sleep(1)                                # wait a moment to unregister
        if self.txa is not None:
            self.txa.shutdown()                     # tx audio stream

        self.rxa.shutdown()                         # rx audio stream

        # self.udp.shutdown(socket.SHUT_RDWR)
        # self.udp.close()
        # all done

    def initStart(self):
        ut.log.debug('starting registration')
        if var.asl_mode != 0:                       # Does this look like a ASL connection to USRP?
            self.regState = True                    # Yes, fake the registration
            self.setTxEnable(True)
        else:
            self.registerWithAB()

    # Null event handler
    def nullHandler(self, *args):
        return

    # -- setup coms -- #
    def init_comms(self):
        self.openUdpStream()                        # Open the UDP stream to AB
        with noalsaerr():
            self.pya = pyaudio.PyAudio()
            ut.log.debug('Setup pyaudio')

        self.init_rx()
        self.init_tx()

        if var.NAT_ping_timer > 0:
            ut.log.debug('Initialising keepalive')
            self.keepalive = keepalive()
            self.keepalive.start()

        self.regServer(False)                       # Start out in the disconnected state
        self.initStart()                            # Begin the handshake with AB (register)

    def init_tx(self):
        if var.in_index < 0:      # Do not link the TX thread if the user wants RX only access
            ut.log.warning('No tx input available')
            return

        self.txa = qtUcTx(self.pya)
        self.txa.onSendUDP = self.sendto
        self.txa.onError = self.onError
        self.txa.onNotifyMsg = self.notifyMsg
        self.txa.onVoxPtt = self.voxPttState
        self.txa.onTxLevel = self.txRxLevel
        self.txa.start()                            # start up (paused)
        if var.vox_enable:                          # tx using VOX
            ut.log.info('VOX operation enabled')
            self.txa.onVoxPtt = self.transmit
            self.txa.resume()                       # run the tx audio
        self.onVoxStatus(var.vox_enable)            # update UI

    def init_rx(self):
        self.rxa = qtUcRx(self.udp, self.pya)
        self.rxa.onError = self.onError
        self.rxa.onRegister = self.regServer
        self.rxa.onServerInfo = self.rxServerInfo
        self.rxa.onChangeMode = self.changeRxMode
        self.rxa.onChangeTG = self.changeRxTG
        self.rxa.onNotifyMsg = self.notifyMsg
        self.rxa.onRxLevel = self.txRxLevel
        self.rxa.onRxStart = self.rxCallStart
        self.rxa.onRxEnd = self.logRxCall
        self.rxa.start()

    # Open the UDP socket for TX and RX
    def openUdpStream(self):
        self.usrpSeq = 0
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except Exception:
            ut.log.warning(defs.STRING_WINDOWS_PORT_REUSE)
        # wake up the daemons...
        self.sendUSRPCommand(bytes("PING", 'ASCII'), const.USRP_TYPE_PING)

        ut.log.debug('ports ', var.usrp_rx_port, var.usrp_tx_port)
        if var.usrp_rx_port not in var.usrp_tx_port:    # single  port reply does not need a bind
            ut.log.debug('Binding rx port ' + str(var.usrp_rx_port))
            self.udp.bind(('', var.usrp_rx_port))
        msg = 'UDP stream opened on ' + str(var.usrp_tx_port)
        ut.log.debug(msg)

    def sendto(self, usrp):
        # -- Basic send to udp port --#
        try:
            for port in var.usrp_tx_port:
                # print('sending ' + str(usrp) + ' to ' + var.ip_address + ', ' + str(port))
                self.udp.sendto(usrp, (var.ip_address, port))
        except Exception as e:
            ut.log.error(str(e))
            self.regState = False

    # -- helpers -- #
    def getCurrentTG(self):
        return self.currentTG

    def getCurrentTGName(self):
        return self.currentTgName

    # -- Main process messaging -- #
    def notifyMsg(self, noteType, msg):
        # print('rx ', noteType, msg)
        self.onNotifyMsg(noteType, msg)

    def txRxLevel(self, level):
        self.onTxRxLevel(level)

    # -- Tx Handlers --#
    def setTxEnable(self, allowTx):
        # allowTx = False
        if self.txa is None or not self.txa.connected:  # we do not have tx capability
            allowTx = False
        else:
            if self.regState and self.txa.connected:    # registered and tx stream connected
                self.txa.transmit_enable = allowTx

        self.onTxEnable(allowTx)                        # update main ui

    # Start call and update UI with PTT info.
    def transmit(self, pttState):
        if self.txa is None:                            # no TX capability
            return

        self.ptt = pttState                             # keep track in case...
        if pttState:
            self.txa.transmit(pttState)                 # fire up...
            if self.txa.paused:                         # not transmitting - problem? no audio etc
                self.ptt = False
                ut.log.debug('Tx paused.. no resume from txa')
            else:
                self.txCallInfo()
        else:
            if not self.txa.paused:                     # we are transmitting
                self.txa.transmit(pttState)             # cease tx...
                self.endTxCall()
        self.onPttStatus(pttState)

    def txCallInfo(self):
        ut.log.debug("PTT ON - start TX call")
        self.tx_start_time = time()
        self.tx_duration = 0
        self.onCallInfo(self.mycall, 'Me', self.currentTgName)          # call, name & tg

    def endTxCall(self):
        ut.log.debug("PTT OFF - end TX call")
        self.tx_duration = time() - self.tx_start_time
        self.onEndTxCall(self.currentMode, self.currentTG, self.txSlot, self.tx_start_time, self.tx_duration)

    def voxPttState(self, voxOn):
        # vox ptt from tx
        if voxOn:
            self.txCallinfo()
        else:
            self.endTxCall()
        self.onVoxPtt(voxOn)

    def enableVox(self, enableVox):
        voxOn = False
        if self.txa is not None:
            if enableVox and self.txa.connected:            # we have tx capability
                ut.log.debug('vox ptt enabled')
                self.txa.onVoxPtt = self.transmit
                self.txa.resume()                           # run the tx audio
                self.txa.enableVox = True
                voxOn = True
            else:
                ut.log.debug('vox ptt disabled')
                self.txa.pause()
                self.txa.onVoxPtt = self.nullHandler
                self.txa.enableVox = False

        # update the UI
        self.onVoxStatus(voxOn)

    def updateServerInfo(self, tg, tgname):
        # update from server (current settings)
        self.currentTG = tg
        self.currentTgName = tgname

    # -- Rx handlers -- #
    def regServer(self, state, waitTime=0):
        if state:                                           # registration ok
            self.regState = True
            self.onRegisterStatus(True, var.ip_address)     # connectedvar.connected_msg.set(defs.STRING_REGISTERED)
            self.sendMetadata()
            self.requestInfo()
            self.setTxEnable(True)

        else:
            self.regState = False
            self.onRegisterStatus(False)
            self.setTxEnable(False)
            # update tx state
            if (waitTime > 0):
                sleep(waitTime)
                self.registerWithAB()                       # try to re-register

    def connectServer(self, mode, tg, tslot):
        if not self.regState:
            self.initStart()                                # try to re-register

        if not tg.startswith('*'):     # If it is not a macro, do a full dial sequence
            self.currentMode = mode
            self.setRemoteNetwork(mode)         # ?? mode not network - only logs
            self.setRemoteTS(tslot)
        self.setRemoteTG(tg)

    def disconnectServer(self):
        # disconnect from server
        if self.currentMode == 'YSF':
            dtg = 'disconnect'
        elif self.currentMode == 'NXDN' or self.currentMode == 'P25':
            dtg = '9999'
        elif self.currentMode == 'DSTAR':
            dtg = "       U"
        else:       # dmr
            dtg = '4000'

        self.setRemoteTG(dtg)
        self.regServer(False)                       # disconnected state
        # disconnect()

    def rxServerInfo(self, rxInfo):
        # update from server (current settings)
        # {'gw': '5053390', 'rpt': '505339011', 'tg': '91', 'ts': '2', 'cc': '1', 'call': 'VK3VW'}
        self.currentTG = rxInfo['tg']
        self.txSlot = rxInfo['ts']
        self.colorC = rxInfo['cc']
        self.onNotifyMsg('servertg', self.currentTG)            # ensure UI is in sync

    def changeRxMode(self, mode, tg):
        #  received mode change
        self.currentMode = mode
        self.currentTG = tg
        self.onSelectTg(tg, mode)                       # update ui selected talkgroup (mode)
        # self.setServerMode(mode)
        # self.selectTGByValue(obj["last_tune"])        # get tg name
        # self.setRemoteTG(tg)

    def changeRxTG(self, privateTG):
        # called from Rx to change to a private call tg, optionally add to tg list
        if (privateTG != self.currentTG):
            # Tune to new tg
            self.currentTG = privateTG
            self.sendRemoteControlCommandASCII("txTg=" + privateTG)
            self.onSelectTg(privateTG, '', True)           # add tgrp and update ui

    def rxCallStart(self, call, name, tg):
        # Rx call commenced
        self.setTxEnable(False)                         # no tx while Rx

        if self.currentMode == 'DSTAR' or tg == "YSF":  # for these modes the TG is not valid
            tg = self.currentTgName                     # need to get the tgrp if it is not set?
        elif tg == var.subscriber_id:                   # is the dest TG my dmr ID? (private call)
            tg = self.mycall

        self.onCallInfo(call, name, tg)                 # call, name & tg

    def logRxCall(self, *args):
        # log the end of a received call
        # [call, name, currentMode, rxslot, tg, callmode, loss, start_time]

        self.onEndRxCall(*args)
        self.setTxEnable(True)                  # allow tx if available

    # -- Commands -- #
    def sendUSRPCommand(self, cmd, packetType):
        # -- Send command to AB  --#
        ut.log.debug("sendUSRPCommand: " + str(cmd))
        try:
            # Send "text" packet to AB.
            usrp = 'USRP'.encode('ASCII') + (struct.pack('>iiiiiii',
                                             self.usrpSeq,
                                             0, 0, 0,
                                             packetType << 24,
                                             0, 0)) + cmd
            self.usrpSeq = (self.usrpSeq + 1) & 0xffff
            self.sendto(usrp)
        except Exception:
            ut.log.critical('barf...')
            traceback.print_exc()
            socketFailure()

    # -- Send commands to AB  -- #
    def sendRemoteControlCommand(self, cmd):
        ut.log.debug("sendRemoteControlCommand: " + str(cmd))
        # Use TLV to send command (wrapped in a USRP packet).
        tlv = struct.pack("BB", const.TLV_TAG_REMOTE_CMD, len(cmd))[0:2] + cmd
        self.sendUSRPCommand(tlv, const.USRP_TYPE_TLV)

    def sendRemoteControlCommandASCII(self, cmd):
        self.sendRemoteControlCommand(bytes(cmd, 'ASCII'))

    def registerWithAB(self):
        self.sendUSRPCommand(bytes("REG:DVSWITCH", 'ASCII'), const.USRP_TYPE_TEXT)

    def unregisterWithAB(self):
        self.sendUSRPCommand(bytes("REG:UNREG", 'ASCII'), const.USRP_TYPE_TEXT)

    # -- Request the INFO json from AB -- #
    def requestInfo(self):
        self.sendUSRPCommand(bytes("INFO:", 'ASCII'), const.USRP_TYPE_TEXT)

    def sendMetadata(self):
        dmr_id = self.dmrid
        call = bytes(self.mycall, 'ASCII') + bytes(chr(0), 'ASCII')
        tlvLen = 3 + 4 + 3 + 1 + 1 + len(var.my_call) + 1                      # dmrID, repeaterID, tg, ts, cc, call, 0
        cmd = struct.pack("BBBBBBBBBBBBBB",
                          const.TLV_TAG_SET_INFO,
                          tlvLen,
                          ((dmr_id >> 16) & 0xff),
                          ((dmr_id >> 8) & 0xff),
                          (dmr_id & 0xff),
                          0, 0, 0, 0, 0, 0, 0, 0, 0)[0:14] + call
        self.sendUSRPCommand(cmd, const.USRP_TYPE_TEXT)

    def setServerMode(self, mode):
        # Set the AB mode by running the named macro
        ut.log.info("New mode selected: %s", mode)
        self.currentMode = mode                         # keep track
        self.rxa.currentMode = mode                     # update rx mode for call info
        self.sendUSRPCommand(bytes("*" + mode, 'ASCII'), const.USRP_TYPE_DTMF)
        self.transmit_enable = True
        sleep(1)
        self.requestInfo()

    def setRemoteTG(self, tg):
        # Tell AB to select the passed tg
        # items = map(int, listbox.curselection())
        # if len(list(items)) > 1:                  # build comma separated string if multiple entries??
        #    tgs="tgs="
        #    comma = ""
        #    for atg in items:
        #        foo = listbox.get(atg)
        #        tgs = tgs + comma + foo.split(',')[1]
        #        comma = ","
        #    sendRemoteControlCommandASCII(tgs)             # ?? Maybe this is to listen to multiple tg's?
        #    sendRemoteControlCommandASCII("txTg=0")
        #    cfg.connected_msg.set(STRING_CONNECTED_TO)
        #    transmitButton.configure(state='disabled')
        # else :                                                # single entry only
        #    sendRemoteControlCommandASCII("tgs=" + str(tg))
        #    sendUSRPCommand(bytes(str(tg), 'ASCII'), USRP_TYPE_DTMF)

        ut.log.info('Selected tg: %s', tg)

        self.currentTG = tg
        self.sendRemoteControlCommandASCII("tgs=" + str(tg))
        self.sendUSRPCommand(bytes(str(tg), 'ASCII'), const.USRP_TYPE_DTMF)
        self.setTxEnable(True)                              # Enable tx if possible
        self.setDMRInfo()                                   # set id's etc
        sleep(.25)                                          # allow time for the server to setup
        self.requestInfo()                                  # retrieve current settings from server

    def setRemoteTS(self, ts):
        self.txSlot = ts
        self.sendRemoteControlCommandASCII("txTs=" + str(ts))

    def setDMRID(self, id):
        self.dmrid = id
        self.sendRemoteControlCommandASCII("gateway_dmr_id=" + str(id))

    def setPeerID(self, id):
        self.sendRemoteControlCommandASCII("gateway_peer_id=" + str(id))

    def setDMRCall(self, call):
        self.mycall = call
        self.sendRemoteControlCommandASCII("gateway_call=" + call)

    def setDMRInfo(self):
        rptrid = str(self.dmrid) + str(var.repeater_id).zfill(2)
        # print('dmr info ' + str(self.dmrid) + ',' + rptrid + ',' + str(self.currentTG) + ',' + str(self.txSlot))
        self.sendToGateway("set info " + str(self.dmrid) + ',' + rptrid + ',' + str(self.currentTG) + ',' + str(self.txSlot) + ',1')

    # -- these are log only -- #  - needed??
    def sendToGateway(self, cmd):
        ut.log.debug("sendToGateway: " + cmd)
        self.sendRemoteControlCommandASCII(cmd)
        # does not actually send anything??
        # maybe??
        # self.sendRemoteControlCommandASCII(cmd)

    # def getInfo(self):
    #    ut.log.info("getInfo")

    def setRemoteNetwork(self, netName):
        # xx_Bridge command: section  - future implementation??
        ut.log.debug("setRemoteNetwork: " + netName)

    # -- AMBE -- #
    def setAMBESize(self, size):
        # Set the size (number of bits) of each AMBE sample
        self.sendRemoteControlCommandASCII("ambeSize=" + size)

    def setAMBEMode(self, mode):
        # Set the AMBE mode to DMR|DSTAR|YSF|NXDN|P25

        # different to servermode ??
        # self.currentMode = mode
        # self.rxa.currentMode = mode
        self.sendRemoteControlCommandASCII("ambeMode=" + mode)

    # -- Vox/audio -- #
    def setVoxData(self):
        state = "true" if var.vox_enable > 0 else "false"
        self.sendToGateway("set vox " + state)
        self.sendToGateway("set vox_threshold " + str(var.vox_threshold))
        self.sendToGateway("set vox_delay " + str(var.vox_delay))

    def getVoxData(self):
        self.sendToGateway("get vox")
        self.sendToGateway("get vox_threshold ")
        self.sendToGateway("get vox_delay ")

    def setAudioData(self):
        dm = "true" if var.dongle_mode > 0 else "false"
        self.sendToGateway("set dongle_mode " + dm)
        self.sendToGateway("set sp_level " + str(self.sp_vol))
        self.sendToGateway("set mic_level " + str(self.mic_vol))

    def getValuesFromServer(self):
        ut.log.info('Requesting server setup')

        # Combined command to get all values from servers and display them on UI
        #   ip_address.set("127.0.0.1")
        #   loopback.set(1)

        # get values from Analog_Bridge (repeater ID, Sub ID, master, tg, slot)
        # ## Old Command ### sendRemoteControlCommand('get_info')
        self.sendToGateway('get info')
        #   current_tx_value.set(my_call)          #Subscriber  call
        #    master.set(servers[0])              #DMR Master
        #   repeater_id.set(311317)              #DMR Peer ID
        #   subscriber_id.set(3113043)           #DMR Subscriber radio ID
        self.txSlot = 2                          # current slot
        # listbox.selection_set(0)            #current TG
        # cfg.connected_msg.set(defs.STRING_CONNECTED_TO)    #current TG

        # get values from Analog_Bridge (vox enable, delay and threshold) (not yet: sp level, mic level, audio devices)
        self.getVoxData()                        # vox enable, delay and threshold
        self.dongle_mode = 1                   # dongle mode enable
        self.mic_vol = 50                      # microphone level
        self.sp_vol = 50                       # speaker level

    def sendValuesToServer(self):
        ut.log.info('Send server setup')
        # Update server data state to match GUI values
        # send values to Analog_Bridge
        self.setDMRInfo()
        # tg = getCurrentTG()
        # setRemoteNetwork(master.get())      #DMR Master
        # setRemoteTG(tg)                     #DMR TG
        # setRemoteTS(slot.get())             #DMR slot
        # setDMRID(subscriber_id.get())        #DMR Subscriber ID
        # setDMRCall(my_call)                  #Subscriber call
        # setPeerID(repeater_id.get())         #DMR Peer ID

        # send values to
        self.setVoxData()                        # vox enable, delay and threshold
        self.setAudioData()                      # sp level, mic level, dongle mode
