# -*- coding: utf-8 -*-
#
# qtUC - pyUC with a QT interface
# Based on the original pyUC code, modified for QT5 use
# Rowan Deppeler - VK3VW - greythane @ gmail.com
#
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
from PyQt5.QtWidgets import *
from PyQt5 import QtGui
from settingsUI import Ui_settingsUI
import qtUC_util as ut
import qtUC_defs as defs
import resources_rc


class prefDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_settingsUI()
        self.ui.setupUi(self)
        self.setWindowTitle('qtUC Settings')
        icon = QtGui.QIcon(":/icons/config")
        self.setWindowIcon(icon)
        self.cfg = None
        self.audevs = ut.getAudioDevices()
        self.lastTxTimeout = 0
        self.input_index = 0
        self.output_index = 0

        # connect the internal dots
        self.ui.cbVoxEnable.stateChanged.connect(self.voxClicked)
        self.ui.txInput.activated.connect(self.selAudioInput)
        self.ui.rxOutput.activated.connect(self.selAudioOutput)
        # self.ui.pttTimeout.valueChanged.connect(self.txTimeoutChange)
        self.ui.cbLoglevel.activated.connect(self.selLoglevel)
        self.ui.pbImportConfig.clicked.connect(self.importConfig)
        self.ui.pbExportConfig.clicked.connect(self.exportConfig)
        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)

        # labeling
        self.ui.tabWidget.setTabText(0, defs.STRING_TAB_MAIN)
        self.ui.tabWidget.setTabText(1, defs.STRING_TAB_AUDIO)

        self.ui.lbCall.setText(defs.STRING_MYCALL)
        self.ui.lbDmrid.setText(defs.STRING_SUBSCRIBER_ID)
        self.ui.lbNetwork.setText(defs.STRING_NETWORK)
        self.ui.lbRepeaterid.setText(defs.STRING_REPEATER_ID)
        self.ui.lbServerIp.setText(defs.STRING_IP_ADDRESS)
        self.ui.lbUsrpPort.setText(defs.STRING_UDP_PORT)
        self.ui.lbStartupMode.setText(defs.STRING_STARTMODE)
        self.ui.cbServerLoopback.setText(defs.STRING_LOOPBACK)
        self.ui.cbMinToTray.setText(defs.STRING_TRAYMIN)
        self.ui.cbQrzLookup.setText(defs.STRING_QRZ_LOOKUP)
        self.ui.cbPttToggle.setText(defs.STRING_PTT_TOGGLE)
        self.ui.cbShortCalls.setText(defs.STRING_SHORT_CALLS)
        self.ui.lbTxTimeout.setText(defs.STRING_TX_TIMEOUT)

        self.ui.lbVox.setText(defs.STRING_VOX)
        self.ui.cbVoxEnable.setText(defs.STRING_VOX_ENABLE)
        self.ui.lbDelay.setText(defs.STRING_VOX_DELAY)
        self.ui.lbThreshold.setText(defs.STRING_VOX_THRESHOLD)
        self.ui.lbAudio.setText(defs.STRING_AUDIO)
        self.ui.lbTxAudio.setText(defs.STRING_MIC)
        self.ui.lbRxAudio.setText(defs.STRING_OUTPUT)
        self.ui.cbDongleMode.setText(defs.STRING_DONGLE_MODE)
        self.ui.lbTheme.setText(defs.STRING_THEME)
        self.ui.lbLoglevel.setText(defs.STRING_LOGLEVEL)

        self.addThemes()

    # intercept accepted signal
    def accept(self):
        # get and save required details
        self.cfg.my_call = self.ui.mycall.text().upper()
        self.cfg.subscriber_id = ut.parseint(self.ui.mydmr_id.text())
        self.cfg.loopback = self.ui.cbServerLoopback.isChecked()
        self.cfg.ip_address = self.ui.serverAddress.text()
        self.cfg.repeater_id = self.ui.repeater_id.value()
        self.cfg.defaultServer = self.ui.startup_mode.currentText()
        # need to check for multiple ports
        self.cfg.usrp_tx_port = [int(i) for i in self.ui.usrp_port.text().split(',')]
        self.cfg.usrp_rx_port = int(self.ui.usrp_port.text())
        self.cfg.vox_enable = self.ui.cbVoxEnable.isChecked()
        self.cfg.vox_threshold = self.ui.voxThreshold.value()
        self.cfg.vox_delay = self.ui.voxDelay.value()
        self.cfg.dongle_mode = self.ui.cbDongleMode.isChecked()
        self.cfg.mic_vol = self.ui.txLevel.value()
        self.cfg.sp_vol = self.ui.rxLevel.value()
        self.cfg.in_index = self.input_index
        self.cfg.out_index = self.output_index
        # system
        self.cfg.useQRZ = self.ui.cbQrzLookup.isChecked()
        self.cfg.minToTray = self.ui.cbMinToTray.isChecked()
        self.cfg.pttToggle = self.ui.cbPttToggle.isChecked()
        self.cfg.shortCalls = self.ui.cbShortCalls.isChecked()
        cval = self.ui.pttTimeout.value()
        if cval < 30:
            self.cfg.txTimeout = 0
        else:
            self.cfg.txTimeout = self.ui.pttTimeout.value()
        self.cfg.theme = self.ui.cbTheme.currentText()
        self.cfg.loglevel = self.ui.cbLoglevel.currentText()

        super().accept()

    def showMsg(self, title, msg, mtype):
        shmsg = QMessageBox()
        if mtype == 'error':
            shmsg.setIcon(QMessageBox.Information)
        elif mtype == 'info':
            shmsg.setIcon(QMessageBox.Information)

        shmsg.setWindowTitle(title)
        shmsg.setText(msg)
        shmsg.exec()

    def getConfig(self):
        return self.cfg

    def setCurrentConfig(self, cfg):
        # set current  configuration values
        self.cfg = cfg
        self.ui.mycall.setText(cfg.my_call.upper())
        self.ui.mydmr_id.setText(str(cfg.subscriber_id))

        self.ui.cbServerLoopback.setChecked(cfg.loopback)           # disabled - not currently used
        self.ui.serverAddress.setText(cfg.ip_address)               # dup'd from basic config
        self.ui.repeater_id.setValue(cfg.repeater_id)
        # tx port can be multiple
        txport = ''
        for i in range(len(cfg.usrp_tx_port)):
            txport += str(cfg.usrp_tx_port[i])
            if i > 0:
                txport += ', '
        self.ui.usrp_port.setText(txport)
        self.ui.startup_mode.setCurrentText(cfg.defaultServer)

        self.ui.cbVoxEnable.setChecked(cfg.vox_enable)
        self.ui.voxThreshold.setValue(cfg.vox_threshold)
        self.ui.voxDelay.setValue(cfg.vox_delay)
        self.ui.cbDongleMode.setChecked(cfg.dongle_mode)            # disabled - not currently used

        # audio
        self.input_index = cfg.in_index
        self.output_index = cfg.out_index
        self.setAudioDevices()
        self.ui.txLevel.setValue(cfg.mic_vol)
        self.ui.rxLevel.setValue(cfg.sp_vol)

        # system
        self.ui.cbQrzLookup.setChecked(cfg.useQRZ)
        self.ui.cbMinToTray.setChecked(cfg.minToTray)
        self.ui.cbPttToggle.setChecked(cfg.pttToggle)
        self.ui.cbShortCalls.setChecked(cfg.shortCalls)
        self.ui.pttTimeout.setValue(cfg.txTimeout)
        self.lastTxTimeout = cfg.txTimeout                              # for direction eval
        self.ui.cbTheme.setCurrentText(cfg.theme)
        self.ui.cbLoglevel.setCurrentText(cfg.loglevel)

    def addThemes(self):
        # populate the theme combo with available themes
        self.ui.cbTheme.clear()
        self.ui.cbTheme.addItem('System')
        self.ui.cbTheme.addItem('QLight')
        self.ui.cbTheme.addItem('QDark')
        self.ui.cbTheme.addItem('BreezeLight')
        self.ui.cbTheme.addItem('BreezeDark')
        self.ui.cbTheme.addItem('Easycode')
        self.ui.cbTheme.addItem('Integrid')
        self.ui.cbTheme.addItem('Medize')
        self.ui.cbTheme.addItem('Spybot')
        self.ui.cbTheme.addItem('DarkBlue')
        self.ui.cbTheme.addItem('DarkGray')
        self.ui.cbTheme.addItem('DarkOrange')

    def setAudioDevices(self):
        self.ui.txInput.clear()
        self.ui.rxOutput.clear()

        # audevs = ut.getAudioDevices()
        # print('audio in/out : ', self.input_index, self.output_index)
        for idx in range(len(self.audevs['devices'])):
            adev = self.audevs['devices'][idx]
            # print(adev)
            if adev['is_input']:
                self.ui.txInput.addItem(adev['name'])
                # print('in idx ', idx)
                if idx == self.input_index or idx == self.audevs['defaultInput']:
                    self.ui.txInput.setCurrentText(adev['name'])
            elif adev['is_output']:
                # print('out idx ', idx)
                self.ui.rxOutput.addItem(adev['name'])
                if idx == self.output_index or idx == self.audevs['defaultOutput']:
                    self.ui.rxOutput.setCurrentText(adev['name'])
            # there can be devices that are neither..

    def selAudioInput(self, selIdx):
        # evaulate audio input device
        txdev = self.ui.txInput.itemText(selIdx)
        for idx in range(len(self.audevs['devices'])):
            adev = self.audevs['devices'][idx]
            # print('tx dev ', adev['name'])
            if adev['is_input'] and adev['name'] == txdev:
                self.input_index = idx
                # print('in idx ', idx)
                break

    def selAudioOutput(self, selIdx):
        # evaulate audio output device
        rxdev = self.ui.rxOutput.itemText(selIdx)
        for idx in range(len(self.audevs['devices'])):
            adev = self.audevs['devices'][idx]
            if adev['is_output'] and adev['name'] == rxdev:
                self.output_index = idx
                break

    def voxClicked(self, checked):
        self.ui.voxThreshold.setEnabled(False)
        self.ui.voxDelay.setEnabled(False)

        if checked:
            self.ui.voxThreshold.setEnabled(True)
            self.ui.voxDelay.setEnabled(True)

    def txTimeoutChange(self):
        # cannot enter anything less than 300 : 0 > 30
        # any value below 30 is deemed 'off'
        cval = self.ui.pttTimeout.value()
        if cval < 30 and self.lastTxTimeout >= 30:                      # going down
            self.ui.pttTimeout.setValue(0)
            self.lastTxTimeout = 0
        elif cval >= 1 and self.lastTxTimeout == 0:                     # going up
            self.ui.pttTimeout.setValue(30)
            self.lastTxTimeout = 30
        else:
            self.lastTxTimeout = cval

    def importConfig(self):
        # load a selected configuration
        fname = QFileDialog.getOpenFileName(self, 'Load config')
        if fname[0] != '':
            cfgfile = fname[0]
            ut.log.info('Importing config ' + cfgfile)
            try:
                self.cfg.cfgfile = cfgfile
                self.cfg.importConfig(self.cfg)
                self.setCurrentConfig(self.cfg)
                ut.log.info("Configuration data imported")
                self.showMsg('', 'Config loaded', 'info')
            except Exception as e:
                ut.log.error("Unable to import configuration data")
                self.showMsg('Import failed', 'Unable to load config data\n' + str(e), 'error')

    def exportConfig(self):
        # export the current configuration
        cfgfile = 'qtUC_bak.ini'
        fname = QFileDialog.getSaveFileName(self, 'Save config', cfgfile, '*.ini')
        if fname[0] != '':
            ut.log.info('Saving config ' + fname[0])
            try:
                self.cfg.cfgfile = fname[0]
                self.cfg.saveConfig(self.cfg)
                ut.log.info("Configuration data exported")
                self.showMsg('', 'Config saved', 'info')
            except Exception as e:
                ut.log.error("Unable to export configuration data")
                self.showMsg('Export failed', 'Unable to save config\n' + str(e), 'error')

    def selLoglevel(self):
        # change logging level
        loglevel = self.ui.cbLoglevel.currentText()
        ut.setLoglevel(loglevel)
