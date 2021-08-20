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

from logging import exception
import sys
import os
from pathlib import Path
import configparser
from PyQt5.QtCore import QSettings
import qtUC_util as ut
import qtUC_defs as defs

DOCPATH = os.path.join(os.path.expanduser('~'), 'Documents', 'qtUC')
CFGFILE = 'qtUC.ini'
# LOCAL_CFGFILE = 'qtUC_local.ini'
TGMACFILE = 'qtUC_tgmac.ini'


# Class to hold all the configuration variables used
class qtUCVars():
    # flags / internal
    valid = False
    cfgfile = CFGFILE
    # local_cfgfile = LOCAL_CFGFILE
    tgmacfile = TGMACFILE

    # must have
    my_call = 'NOCALL'
    subscriber_id = 0
    repeater_id = 1
    ip_address = ''

    # should have
    usrp_tx_port = 50100
    usrp_rx_port = 50100
    defaultServer = 'DMR'
    useQRZ = True

    SAMPLE_RATE = 48000                     # Default audio sample rate for pyaudio (will be resampled to 8K)
    out_index = None                        # Current output (speaker) index in the pyaudio device list
    in_index = None                         # Current input (mic) index in the pyaudio device list

    loopback = False                        # NOT USED?
    dongle_mode = False                     # NOT USED?
    mic_vol = 50                            # NOT USED?
    sp_vol = 50                             # NOT USED?
    vox_enable = False
    vox_threshold = 200
    vox_delay = 50
    slot = 2
    asl_mode = 0

    minToTray = False                       # minimize to tray instead of closeing
    pttToggle = False
    txTimeout = 200
    shortCalls = True
    theme = 'system'
    loglevel = 'Info'

    # some basic details in case something barfs
    talk_groups = {
        'DMR': [('Disconnect', '4000'), ('Parrot', "9990#")],
        'P25': [('Disconnect', '9999'), ('Parrot', '10')],
        'YSF': [('Disconnect', 'disconnect'), ('Parrot', 'register.ysfreflector.de:42020')],
        'NXDN': [('Unlink', '9999'), ('Parrot', '10')],
        'DSTAR': [('Unlink', '       U'), ('Echo', 'REF001EL')]
    }
    macros = {}
    radmenu = {}

    noQuote = {ord('"'): ''}
    # servers = sorted(talk_groups.keys())
    # connected_msg = defs.STRING_CONNECTED_TO

    level_every_sample = 1
    NAT_ping_timer = 0

    def __init__(self):
        pass

    def setupPaths(self):
        # Assume the default config file name is in the same dir as .py file
        apppath = str(Path(sys.argv[0]).parent)
        # self.cfgfile = os.path.join(apppath, CFGFILE)
        self.cfgfile = os.path.join(apppath, CFGFILE)
        self.tgmacfile = os.path.join(apppath, TGMACFILE)

        # be smart - should have been created in utils if non existent
        if not os.path.isdir(DOCPATH):
            try:
                os.makedirs(DOCPATH)
                ut.log.info('Created qtUC documents directory - ' + DOCPATH)
            except Exception:
                pass
        else:
            self.cfgfile = os.path.join(DOCPATH, CFGFILE)
            # self.local_cfgfile = os.path.join(DOCPATH, LOCAL_CFGFILE)
            self.tgmacfile = os.path.join(DOCPATH, TGMACFILE)
            ut.log.info('Using base configuration ' + self.cfgfile)
            # ut.log.info('Local configuration ' + self.local_cfgfile)

    def validateConfigInfo(self):
        self.valid = (self.my_call != "N0CALL")               # Make sure they set a callsign
        self.valid &= (self.subscriber_id != 0)               # Make sure they set a DMR/CCS7 ID
        self.valid &= (self.ip_address != "")                 # Make sure they have a valid address for AB
        self.valid &= (self.ip_address != "1.2.3.4")
        if not self.valid:
            ut.log.info(defs.STRING_CONFIG_NOT_EDITED)
        # return valid

    def loadConfig(self):
        # Load data from the default or passed config file
        self.setupPaths(self)                           # setup some stuff

        # load base config from ini fil(s)
        if len(sys.argv) > 1:
            self.cfgfile = sys.argv[1]              # Use the command line argument for the path to the config file
        else:
            self.importConfig(self)                 # load 'em

        # local overrides
        self.importLocal(self)                          # local updates to talkgroups and/or macros
        self.loadLocalConfig(self)                      # local UI settings and local details override

    def importConfig(self):
        # Parse config details
        self.valid = False
        config = configparser.ConfigParser(inline_comment_prefixes=(';',))
        config.optionxform = lambda option: option

        try:
            try:
                config.read(['./qtUC_dist.ini', self.cfgfile])    # check local dist for basic setup
            except Exception:
                ut.log.error(defs.STRING_CONFIG_FILE_ERROR + str(sys.exc_info()[1]))
                # sys.exit('Configuration file \'' + cfgfile + '\' is not a valid configuration file! Exiting...')
                return

            # required
            self.my_call = config.get('DEFAULTS', 'myCall', fallback='NOCALL').split(None)[0]
            self.subscriber_id = int(config.get('DEFAULTS', 'subscriberID', fallback='0').split(None)[0])
            self.repeater_id = int(config.get('DEFAULTS', 'repeaterID', fallback='1').split(None)[0])
            self.ip_address = config.get('DEFAULTS', 'ipAddress', fallback='1.2.3.4').split(None)[0]
            self.usrp_tx_port = [int(i) for i in config.get('DEFAULTS', 'usrpTxPort', fallback='12345').split(',')]
            self.usrp_rx_port = int(config.get('DEFAULTS', 'usrpRxPort', fallback='50100').split(None)[0])             # normally the same port
            self.defaultServer = config.get('DEFAULTS', 'defaultServer', fallback='DMR').split(None)[0]

            # defaults
            self.useQRZ = config.getboolean('DEFAULTS', 'useQRZ', fallback=True)
            self.level_every_sample = int(config.get('DEFAULTS', 'levelEverySample', fallback='2'))
            self.NAT_ping_timer = int(config.get('DEFAULTS', 'pingTimer', fallback='0'))
            # self.loopback = bool(config.get('DEFAULTS', 'loopback', fallback=False).split(None)[0])
            # self.dongle_mode = bool(config.get('DEFAULTS', 'dongleMode', fallback=False).split(None)[0])
            self.vox_enable = config.getboolean('DEFAULTS', 'voxEnable', fallback=False)   # .split(None)[0]
            self.mic_vol = int(config.get('DEFAULTS', 'micVol', fallback='50').split(None)[0])
            self.sp_vol = int(config.get('DEFAULTS', 'spVol', fallback='50').split(None)[0])
            self.vox_threshold = int(config.get('DEFAULTS', 'voxThreshold', fallback='200').split(None)[0])
            self.vox_delay = int(config.get('DEFAULTS', 'voxDelay', fallback='50').split(None)[0])
            self.slot = int(config.get('DEFAULTS', 'slot', fallback='2').split(None)[0])
            self.asl_mode = int(config.get('DEFAULTS', 'aslMode', fallback='0').split(None)[0])

            # Audio devices
            in_index = config.get('DEFAULTS', 'in_index', fallback='default')
            if in_index.lower() == 'default':
                self.in_index = None
            else:
                self.in_index = int(in_index)
            out_index = config.get('DEFAULTS', 'out_index', fallback='default')
            if out_index.lower() == 'default':
                self.out_index = None                    # ?? or 0
            else:
                self.out_index = int(in_index)

            # internal
            self.minToTray = config.getboolean('DEFAULTS', 'minToTray', fallback=False)
            self.pttToggle = config.getboolean('DEFAULTS', 'pttToggle', fallback=False)
            self.shortCalls = config.getboolean('DEFAULTS', 'shortCalls', fallback=True)
            self.txTimeout = int(config.get('DEFAULTS', 'txTimeout', fallback='200').split(None)[0])

            # uc_background_color = readValue(config, 'DEFAULTS', 'backgroundColor', 'gray25', str)
            # uc_text_color = readValue(config, 'DEFAULTS', 'textColor', 'white', str)

            # talk_groups = {}
            for sect in config.sections():
                if (sect != "DEFAULTS") and (sect != "MACROS"):
                    self.talk_groups[sect] = config.items(sect)

            # macros = {}
            if "MACROS" in config.sections():
                for x in config.items("MACROS"):
                    # self.macros[x[1]] = x[0]
                    self.macros[x[0]] = x[1]                        # use key: val not val: key :(

            self.validateConfigInfo(self)

        except Exception:
            ut.log.error(defs.STRING_CONFIG_FILE_ERROR + str(sys.exc_info()[1]))
            ut.log.error('Configuration file \'' + self.cfgfile + '\' is not a valid configuration file!')

    def exportConfig(self):
        # save current details
        config = configparser.ConfigParser()
        config.optionxform = str                                    # preserve case ikeys/values

        config.add_section('DEFAULTS')
        config.set('DEFAULTS', 'myCall', self.my_call)
        config.set('DEFAULTS', 'subscriberID', str(self.subscriber_id))
        config.set('DEFAULTS', 'repeaterID', str(self.repeater_id))
        config.set('DEFAULTS', 'ipAddress', self.ip_address)
        config.set('DEFAULTS', 'usrpTxPort', str(self.usrp_tx_port))
        config.set('DEFAULTS', 'usrpRxPort', str(self.usrp_rx_port))
        config.set('DEFAULTS', 'defaultServer', self.defaultServer)

        # defaults
        config.set('DEFAULTS', 'useQRZ', self.useQRZ)
        config.set('DEFAULTS', 'levelEverySample', str(self.level_every_sample))
        config.set('DEFAULTS', 'pingTimer', str(self.NAT_ping_timer))
        config.set('DEFAULTS', 'loopback', self.loopback)
        config.set('DEFAULTS', 'dongleMode', self.dongle_mode)
        config.set('DEFAULTS', 'voxEnable', self.vox_enable)
        config.set('DEFAULTS', 'micVol', str(self.mic_vol))
        config.set('DEFAULTS', 'spVol', str(self.sp_vol))
        config.set('DEFAULTS', 'voxThreshold', str(self.vox_threshold))
        config.set('DEFAULTS', 'voxDelay', str(self.vox_delay))
        config.set('DEFAULTS', 'slot', str(self.slot))
        config.set('DEFAULTS', 'aslMode', str(self.asl_mode))

        # Audio devices
        config.set('DEFAULTS', 'in_index', str(self.in_index))
        config.set('DEFAULTS', 'out_index', str(self.out_index))

        # internal
        config.set('DEFAULTS', 'minToTray', self.minToTray)
        config.set('DEFAULTS', 'pttToggle', self.pttToggle)
        config.set('DEFAULTS', 'shortCalls', self.shortCalls)
        config.set('DEFAULTS', 'txTimeout', str(self.txTimeout))

        # talk_groups
        tgkeys = list(self.talk_groups.keys())
        for sect in tgkeys:
            config.add_section(sect)
            for itm in self.talk_groups[sect]:
                config.set(str(sect), str(itm[0]), str(itm[1]))     # itms are tuples (Disconnect, 4000) etc

        # macros
        config.add_section('MACROS')
        for key in self.macros:
            macval = str(self.macros[key])
            config.set('MACROS', key, macval)

        try:
            with open(self.cfgfile, 'w') as cf:
                config.write(cf)

        except Exception:
            ut.log.error(defs.STRING_CONFIG_FILE_ERROR + str(sys.exc_info()[1]))
            ut.log.error('Unable to write configuration file \'' + self.cfgfile + '\'')

    def importLocal(self):
        # import any local tg/macro info
        if not os.path.isfile(self.tgmacfile):
            ut.log.info('TG/Macro file \'' + self.tgmacfile + '\' does not exist for import!')
            return

        config = configparser.ConfigParser(inline_comment_prefixes=(';',))
        config.optionxform = lambda option: option
        try:
            try:
                config.read(self.tgmacfile)
            except Exception:
                # ignore if the file does not exist
                ut.log.error(defs.STRING_CONFIG_FILE_ERROR + str(sys.exc_info()[1]))
                ut.log.error('TG/Macro file \'' + self.tgmacfile + '\' is not a valid configuration file!')
                return

            # talk_groups
            for sect in config.sections():
                if sect != "MACROS":                                # no defaults here
                    self.talk_groups[sect] = config.items(sect)

            # macros
            if "MACROS" in config.sections():
                for x in config.items("MACROS"):
                    # self.macros[x[1]] = x[0]
                    self.macros[x[0]] = x[1]                        # use key: val not val: key :(

        except Exception:
            ut.log.error(defs.STRING_CONFIG_FILE_ERROR + str(sys.exc_info()[1]))
            ut.log.error('Local TG/Macros file \'' + self.tgmacfile + '\' is not a valid configuration file!')

    def exportLocal(self):
        # save current talk_groups and macros
        config = configparser.ConfigParser()
        config.optionxform = str                                    # preserve case ikeys/values

        # talkgroups
        tgkeys = list(self.talk_groups.keys())
        for sect in tgkeys:
            config.add_section(sect)
            for itm in self.talk_groups[sect]:
                config.set(str(sect), str(itm[0]), str(itm[1]))     # itms are tuples (Discount, 4000) etc

        # macros
        config.add_section('MACROS')
        for key in self.macros:                                     # keys of the macros dict
            macval = str(self.macros[key])
            config.set('MACROS', key, macval)

        try:
            with open(self.tgmacfile, 'w') as cf:
                config.write(cf)

        except Exception:
            ut.log.error(defs.STRING_CONFIG_FILE_ERROR + str(sys.exc_info()[1]))
            ut.log.error('Unable to write local talkgroup/macros file \'' + self.tgmacfile + '\'')

    def loadLocalConfig(self):
        # if not cfg.valid:
        ut.log.info('loading local configuration')
        settings = QSettings()
        self.my_call = settings.value('mycall', self.my_call, type=str)
        self.subscriber_id = settings.value('subscriber_id', self.subscriber_id, type=int)
        self.repeater_id = settings.value('repeater_id', self.repeater_id, type=int)
        self.ip_address = settings.value('ip_address', self.ip_address, type=str)
        # need to be carefull of tx ports as the list is saved as strings
        txlist = settings.value('usrp_tx_port', self.usrp_tx_port, type=list)
        txports = []
        for prt in range(len(txlist)):
            tp = int(txlist[prt])
            txports.append(tp)
        self.usrp_tx_port = txports
        self.usrp_rx_port = settings.value('usrp_rx_port', self.usrp_rx_port, type=int)
        self.defaultServer = settings.value('defaultServer', self.defaultServer, type=str)

        # additional settings
        # self.loopback = settings.value('loopback', self.loopback, type=bool)        # not used
        self.vox_enable = settings.value('voxenable', self.vox_enable, type=bool)
        self.vox_threshold = settings.value('voxthreshold', self.vox_threshold, type=int)
        self.vox_delay = settings.value('voxdelay', self.vox_delay, type=int)
        # self.dongle_mode = settings.value('donglemode', self.dongle_mode, type=bool)   # not used
        self.mic_vol = settings.value('txvol', self.mic_vol, type=int)
        self.sp_vol = settings.value('rxvol', self.sp_vol, type=int)
        self.in_index = settings.value('txinput', self.in_index, type=int)
        self.out_index = settings.value('rxoutput', self.out_index, type=int)

        self.useQRZ = settings.value('use_qrz', self.useQRZ, type=bool)
        self.minToTray = settings.value('mintotray', self.minToTray, type=bool)      # UI settings
        self.pttToggle = settings.value('ptttoggle', self.pttToggle, type=bool)
        self.shortCalls = settings.value('shortcalls', self.shortCalls, type=bool)
        self.txTimeout = settings.value('txtimeout', self.txTimeout, type=int)
        self.theme = settings.value('theme', self.theme, type=str)
        self.loglevel = settings.value('loglevel', self.loglevel, type=str)

        # set logging level
        ut.setLoglevel(self.loglevel)

        # recheck for valid settings
        self.validateConfigInfo(self)
