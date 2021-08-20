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
import sys
import os
import platform
import ctypes
from time import time, localtime, strftime
from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QTranslator, Qt, QSettings, QTimer, QThread, QCoreApplication, QFile, QTextStream
from ledwidget import LedIndicator
from qtUCUI import Ui_MainWindow        # main GUI
from settings import prefDlg            # settings dialog
from aboutDlg import abtDlg             # 'About'
from tgDlg import tgDlg                 # TG.Node selection
from tgEditDlg import tgEditDlg         # TG/Node editing
import qtUC_defs as defs
from qtUC_vars import qtUCVars as cfg   # configuration variables
import qtUC_util as ut
import qtUC_lookup
from qtUC_coms import qtComs            # communication processing
import queue
import webbrowser
from notificationUI import Ui_notification

QCoreApplication.setOrganizationName("VK3VW")
QCoreApplication.setOrganizationDomain("vk3vw.net")
QCoreApplication.setApplicationName("qtUC")

os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

# some windows stuff
if "Windows" in platform.system():
    try:
        from PyQt5.QtWinExtras import QtWin
        appId = 'net.vk3vw.qtUC'
        QtWin.setCurrentProcessExplicitAppUserModelID(appId)
    except ImportError:
        pass


# notifications
class Notification(QWidget):
    def __init__(self, parent=None):
        super(QWidget, self).__init__(parent=None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.ui = Ui_notification()
        self.ui.setupUi(self)
        self.opacity = 1
        self.ticks = 3000 // 50
        self.timer = QTimer()
        self.timer.timeout.connect(self.timeout)
        # self.setStyleSheet("background: #d3d7cf; padding: 0;")

    def setNotify(self, title, message, timeout):
        if self.isVisible:
            self.timer.stop

        self.ticks = timeout // 50
        self.opacity = 1
        self.ui.titleLabel.setText(title)
        self.ui.msgLabel.setText(message)
        self.timer.start(100)
        self.show()

    def timeout(self):
        self.ticks -= 1
        if self.ticks > 0:
            self.opacity -= 0.02
            self.setWindowOpacity(self.opacity)
        else:
            self.close()


# GUI update thread
class Gui_Coms(QtCore.QObject):
    signal_process = QtCore.pyqtSignal(str, dict)
    # signal_appear = QtCore.pyqtSignal()
    # signal_dissappear = QtCore.pyqtSignal()


class qtUC_GuiUpdate(QThread):
    def __init__(self, msg_queue, ttl=3600):
        QThread.__init__(self)
        self.signals = Gui_Coms()

        self.quit = False
        self.cache_ttl = ttl                # default ttl of 1 hour
        self.msg_queue = msg_queue
        # self.msg_queue = queue.Queue()

        # callback when data available
        self.onData = self.nullHandler
        ut.log.debug("GUI Queue successfully initialised.")

    def shutdown(self):
        self.quit = True

    def nullHandler(self, *args):
        return

    def run(self):
        while not self.quit:
            try:
                msg = self.msg_queue.get()         # wait for a message in the queue
                for mtype in msg:
                    self.signals.signal_process.emit(mtype, msg)
            except queue.Empty:
                pass


# ---   Main qtUC UI   --- #
class qtUC(QMainWindow):
    def __init__(self):
        super(qtUC, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle(defs.STRING_USRP_CLIENT)
        icon = QtGui.QIcon(":/icons/appicon")
        self.setWindowIcon(icon)
        self.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        self.prefsDlg = None
        self.tgDlg = None
        self.tgEditDlg = None
        # self.minizeToTray = False
        self.defaultpix = QtGui.QPixmap(':/images/netradio').scaled(100, 80)
        self.chatpix = QtGui.QPixmap(':/icons/chat').scaled(100, 80)
        self.showStatus('Initialising...')

        # Bypass needed to set taskbar icon if on windows
        if "Windows" in platform.system():
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appId)

        # some runtime helpers
        self.currentMode = ''       # current operating mode
        self.currentTx = False      # Tx in operation
        self.currentTG = ''         # currently selected TG number
        self.currentTGName = ''     # seleccted TG name
        self.currentSlot = 2        # DMR slot
        self.pttDown = False        # ptt button state
        self.txTimeout = 0
        self.tgrps = {}             # current talkgroups
        self.macros = {}            # ?? needed??

        # clear some stuff
        self.ui.lbCallsign.clear()
        self.ui.lbCallName.clear()
        self.ui.lbFlag.clear()
        self.ui.lbCtry.clear()

        # add the toolbar talkgroup combo
        self.selTg = QComboBox()
        self.selTg.setMaxVisibleItems(20)
        self.selTg.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.selTg.setFixedWidth(150)
        self.ui.toolBar.addWidget(self.selTg)

        # add a label to the statusbar for info
        self.connTG = QLabel("Disconnected")
        self.connTG.setStyleSheet("border :2px solid;")
        self.statusBar().addPermanentWidget(self.connTG)

        # connect the window menu items
        self.ui.actionPreferences.triggered.connect(self.showPrefsDlg)
        self.ui.actionAbout.triggered.connect(self.helpAbout)
        self.ui.actionDMR.triggered.connect(lambda: self.selectMode('DMR'))
        self.ui.actionDStar.triggered.connect(lambda: self.selectMode('DSTAR'))
        self.ui.actionNXDN.triggered.connect(lambda: self.selectMode('NXDN'))
        self.ui.actionP25.triggered.connect(lambda: self.selectMode('P25'))
        self.ui.actionYSF.triggered.connect(lambda: self.selectMode('YSF'))
        self.ui.actionEdit_tgrps.triggered.connect(self.editTalkgroups)
        self.ui.actionEdit_macros.triggered.connect(self.editMacros)
        self.ui.actionRadio_menu.triggered.connect(self.editRadioMenus)
        self.ui.actionServer_read.triggered.connect(getValuesFromServer)
        self.ui.actionServer_write.triggered.connect(sendValuesToServer)

        # connect the toolbar options
        self.ui.actionTbDMR.triggered.connect(lambda: self.selectMode('DMR'))
        self.ui.actionTbDStar.triggered.connect(lambda: self.selectMode('DSTAR'))
        self.ui.actionTbNXDN.triggered.connect(lambda: self.selectMode('NXDN'))
        self.ui.actionTbP25.triggered.connect(lambda: self.selectMode('P25'))
        self.ui.actionTbYSF.triggered.connect(lambda: self.selectMode('YSF'))
        self.ui.actionTbTalkgroup.triggered.connect(self.enterTalkgroup)
        self.selTg.activated.connect(self.selTalkgroup)

        # some internal dots
        self.ui.txButton.setCursor(Qt.PointingHandCursor)
        self.ui.txButton.mousePressEvent = self.pttON
        self.ui.txButton.mouseReleaseEvent = self.pttOFF
        self.pttTimer = QTimer()
        self.pttTimer.timeout.connect(self.pttTimeout)
        self.pttEnable(False)                               # start disabled

        self.ui.lbCallPic.mousePressEvent = self.clickCallImage

        # Server connection led
        self.serverled = LedIndicator(self)
        # self.serverled.setDisabled(True)                  # Make the led non clickable
        # self.serverled.clicked.connect(lambda: serverState(self.serverled.isChecked()))
        self.serverled.clicked.connect(serverState)         # connect/disconnect server
        self.serverled.setToolTip('DVSwitch status')
        self.serverled.resize(25, 25)
        self.serverled.setCursor(Qt.PointingHandCursor)
        self.statusBar().addPermanentWidget(self.serverled)

        # meter
        # self.ui.lbSmeter.move(350, 15)
        self.ui.wgMeter.set_start_scale_angle(230)
        self.ui.wgMeter.set_total_scale_angle_size(80)
        self.ui.wgMeter.set_MaxValue(55)
        self.ui.wgMeter.set_gauge_color_outer_radius_factor(1000)
        self.ui.wgMeter.set_gauge_color_inner_radius_factor(750)
        self.ui.wgMeter.set_enable_CenterPoint(False)
        self.ui.wgMeter.set_enable_ScaleText(False)
        self.ui.wgMeter.set_enable_value_text(False)
        self.ui.wgMeter.set_enable_fine_scaled_marker(False)
        self.ui.wgMeter.set_scala_main_count(9)
        self.ui.wgMeter.set_enable_Needle_Polygon(False)
        self.ui.wgMeter.set_enable_barGraph(False)
        # self.ui.wgMeter.background = ":/images/smeter"        # need to modify for non square canvas
        self.ui.wgMeter.resize(120, 120)

        # tx/rx led
        self.ui.txrxLed.setDisabled(True)                              # Make the led non clickable
        self.ui.txrxLed.setOff()
        self.ui.txrxLed.setToolTip('Tx/Rx status')

        # vox led
        # self.ui.voxLed.setDisabled(True)                              # Make the led non clickable
        self.setVoxEnable(cfg.vox_enable)
        self.ui.voxLed.setCursor(Qt.PointingHandCursor)
        self.ui.voxLed.clicked.connect(self.setVox)

        self.initLastHeard()

        # labeling
        self.ui.txButton.setText(defs.STRING_TRANSMIT)
        self.ui.actionAbout.setText(defs.STRING_ABOUT)
        self.ui.actionServer_read.setText(defs.STRING_READ)
        self.ui.actionServer_write.setText(defs.STRING_WRITE)

        # Init QSystemTrayIcon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(icon)   # self.style().standardIcon(QStyle.SP_ComputerIcon))
        show_action = QAction("Show", self)
        hide_action = QAction("Hide", self)
        quit_action = QAction("Exit", self)
        show_action.triggered.connect(self.show)
        hide_action.triggered.connect(self.hide)
        quit_action.triggered.connect(qApp.quit)
        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # setup the gui update queue
        self.gui_queue = queue.Queue(maxsize=0)
        self.guiUpdate = qtUC_GuiUpdate(self.gui_queue)
        self.guiUpdate.signals.signal_process.connect(self.process_gui_queue)
        self.guiUpdate.start()

        # qrz lookup
        self.lkQrz = qtUC_lookup.qrzLookup()
        self.lkQrz.onLookup = self.showCallImage
        self.lkQrz.start()

    # UI update queue processing
    def process_gui_queue(self, mtype, mdata):
        if mtype == 'audiolevel':
            self.setAudioLevel(mdata[mtype])
        elif mtype == 'lastheard':
            self.setLastHeard(mdata[mtype])
        elif mtype == 'status':
            self.showStatus(mdata[mtype])
        elif mtype == 'infomsg':
            self.infoMsg(mdata[mtype])
        elif mtype == 'servertg':
            self.serverTgMsg(mdata[mtype])
        elif mtype == 'connected':
            self.connectedState(mdata[mtype])
        elif mtype == 'pttenable':
            self.pttEnable(mdata[mtype])
        elif mtype == 'pttstate':
            self.setPttOnOff(mdata[mtype])
        elif mtype == 'voxptt':
            self.setVoxPtt(mdata[mtype])
        elif mtype == 'voxenable':
            self.setVoxEnable(mdata[mtype])
        elif mtype == 'qrz':
            self.setCall(mdata[mtype])

    # Override closeEvent, to intercept the window closing event
    # The window will be closed only if the 'Minimize to tray' option has not been selected
    def closeEvent(self, event):
        if cfg.minToTray:
            event.ignore()
            self.hide()
            self.infoMsg("Minimized to Tray")
        else:
            ut.log.info(defs.STRING_EXITING)
            coms.exit()
            self.lkQrz.shutdown()                   # kill the qrz lookup
            self.guiUpdate.shutdown()               # ensure gui queue dies
            self.tray_icon.hide()
            qApp.quit()

    def showNotification(self, msg, title='qtUC Information', timeout=3000):
        self.notification = Notification()
        self.notification.setStyleSheet(self.styleSheet())
        # self.notification.setNotify("Message Title", "Message line 1\nMessage line 2\nMessage line 3", 3000)
        self.notification.setNotify(title, msg, timeout)
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        size = self.notification.geometry()
        new_left = screen.width() - size.width() - 20
        new_top = 20
        self.notification.move(new_left, new_top)

    def infoMsg(self, message):
        # print('got infoMsg')
        if self.isMinimized():
            self.tray_icon.showMessage(
                "qtUC",
                message,
                QSystemTrayIcon.Information,
                2000
            )
        else:
            self.showNotification(message)

    def serverTgMsg(self, serverTg):
        self.setConnectedTgVal(serverTg, '', False)

    def helpAbout(self):
        about = abtDlg()
        about.setStyleSheet(self.styleSheet())
        about.exec()

    def showStatus(self, msg):
        self.ui.statusbar.showMessage(msg)

    def connectedState(self, state):        # should this be status bar
        if state:
            self.connTG.setText(defs.STRING_CONNECTED)
            self.serverled.setToolTip(defs.STRING_CONNECTED)
        else:
            self.connTG.setText(defs.STRING_DISCONNECTED)
            self.serverled.setToolTip(defs.STRING_DISCONNECTED)
        self.serverled.setChecked(state)

    def showPrefsDlg(self):
        if self.prefsDlg is None:
            self.prefsDlg = prefDlg()
            self.prefsDlg.setStyleSheet(self.styleSheet())

        # set current values
        self.prefsDlg.setCurrentConfig(cfg)
        currentTheme = cfg.theme

        # update preferences
        if self.prefsDlg.exec():
            # get and save required details
            settings = QSettings()

            settings.setValue('mycall', cfg.my_call)
            settings.setValue('subscriber_id', cfg.subscriber_id)
            settings.setValue('repeater_id', cfg.repeater_id)
            settings.setValue('ip_address', cfg.ip_address)
            settings.setValue('usrp_tx_port', cfg.usrp_tx_port)
            settings.setValue('usrp_rx_port', cfg.usrp_rx_port)             # currently tx and rx on the same port
            settings.setValue('defaultServer', cfg.defaultServer)
            # settings.setValue('loopback', cfg.loopback, type=bool)        # not used

            settings.setValue('voxenable', cfg.vox_enable)
            settings.setValue('voxthreshold', cfg.vox_threshold)
            settings.setValue('voxdelay', cfg.vox_delay)
            # settings.setValue('donglemode', cfg.dongle_mode, type=bool)   # not used
            settings.setValue('txvol', cfg.mic_vol)
            settings.setValue('rxvol', cfg.sp_vol)
            settings.setValue('txinput', cfg.in_index)
            settings.setValue('rxoutput', cfg.out_index)

            settings.setValue('use_qrz', cfg.useQRZ)
            settings.setValue('mintotray', cfg.minToTray)
            settings.setValue('ptttoggle', cfg.pttToggle)
            settings.setValue('shortcalls', cfg.shortCalls)
            settings.setValue('txtimeout', cfg.txTimeout)
            settings.setValue('theme', cfg.theme)
            settings.setValue('loglevel', cfg.loglevel)

            settings.sync()
            ut.log.info('Local configuration settings saved')

        cfg.validateConfigInfo(cfg)
        if not cfg.valid:
            self.infoMsg('Configuration is not valid!')

        # set stylesheet
        theme = cfg.theme.lower()
        if theme != currentTheme:
            if theme == 'system':
                app.setStyleSheet('')
            else:
                file = QFile(':/theme/' + theme)
                file.open(QFile.ReadOnly | QFile.Text)
                stream = QTextStream(file)
                app.setStyleSheet(stream.readAll())

    def editTalkgroups(self):
        # edit current talkgroup details
        if self.tgEditDlg is None:
            self.tgEditDlg = tgEditDlg()
            self.tgEditDlg.setStyleSheet(self.styleSheet())

        edNodes = cfg.talk_groups[self.currentMode]
        self.tgEditDlg.setEditNodes(edNodes)

        # update if 'saved'
        if self.tgEditDlg.exec():
            edNodes = self.tgEditDlg.getNodes()
            cfg.talk_groups[self.currentMode] = edNodes
            cfg.exportLocal(cfg)            # save local updates

            # update current listing
            self.selTg.clear()
            for idx in range(len(edNodes)):
                self.selTg.addItem(edNodes[idx][0])

    def editMacros(self):
        # edit current macros
        if self.tgEditDlg is None:
            self.tgEditDlg = tgEditDlg()
            self.tgEditDlg.setStyleSheet(self.styleSheet())

        # edList = cfg.macros
        # print('cfg list ', edList)
        self.tgEditDlg.setEditMacros(cfg.macros)

        # update if 'saved'
        if self.tgEditDlg.exec():
            edMacros = self.tgEditDlg.getMacros()
            cfg.macros = edMacros
            cfg.exportLocal(cfg)            # save local updates - macros will be reloaded when required

    def editRadioMenus(self):
        # edit current menu options
        if self.tgEditDlg is None:
            self.tgEditDlg = tgEditDlg()
            self.tgEditDlg.setStyleSheet(self.styleSheet())

        # edList = cfg.macros
        # print('cfg list ', edList)
        self.tgEditDlg.setEditMacros(cfg.radmenu)

        # update if 'saved'
        if self.tgEditDlg.exec():
            edMenu = self.tgEditDlg.getMacros()
            cfg.radmenu = edMenu
            # cfg.saveLocal(cfg)            # save local updates - macros will be reloaded when required
            # send to server?

    def getSelectedTgName(self):
        return self.currentTGName

    def getSelectedTg(self):
        return self.currentTG

    def setConnectedTgVal(self, tgrpVal, mode='', addTg=False):
        # select/display the required talkgroup, mode = '' - use current mode
        if mode == '':
            mode = self.currentMode
        if mode != self.currentMode:                    # mode has changed.. update selections
            self.setup_mode(mode)

        if addTg:
            idx = self.selTg.findText(tgrpVal)
            if idx < 0:                                 # new tg to add
                cfg.talk_groups[tgrpVal] = tgrpVal
                self.setupMode(mode)                    # reload available talkgroups

        # select/get talkgroup name
        idx = 0
        tgName = ''
        for item in self.tgrps:
            if item[1].translate(cfg.noQuote) == tgrpVal:
                self.selTg.setCurrentIndex(idx)
                tgName = self.selTg.currentText()
            idx += 1
        if tgName == '':
            tgName = str(tgrpVal)
        self.connTG.setText('Tg: ' + tgName)
        self.currentTG = tgrpVal
        self.currentTGName = tgName

        # ensure coms is in sync
        coms.updateServerInfo(tgrpVal, tgName)

    def setAudioLevel(self, level):
        self.ui.wgMeter.update_value(level)

    def setup_mode(self, mode):
        self.setCall(['', ''])
        self.setAudioLevel(0)
        self.selTg.clear()
        self.currentMode = mode
        self.tgrps = cfg.talk_groups[mode]
        for idx in range(len(self.tgrps)):
            self.selTg.addItem(self.tgrps[idx][0])
        self.selTg.adjustSize()

    def setCall(self, call):
        self.ui.lbCallsign.setText(call[0])
        self.ui.lbCallName.setText(call[1])
        # print('call start')
        if call[0] != '':
            if self.currentTx:
                self.ui.txrxLed.setRed()
            else:
                self.ui.txrxLed.setGreen()
            self.ui.txrxLed.setChecked(True)

            ctry, flag = self.lkQrz.lookup_country(call[0])
            self.showCtry(ctry, flag)

            if cfg.useQRZ:
                self.lkQrz.qrz_queue.put(call[0])    # get photo
            else:
                self.showCallImage(self.chatpix)
            self.showNotification(call[0] + ' -> ' + call[1], 'qtUC receiving')
        else:
            self.ui.txrxLed.setOff()
            self.ui.txrxLed.setChecked(False)
            self.showCtry('', '')

            if cfg.useQRZ:
                self.lkQrz.qrz_queue.put('')        # ensure any pic in the queue is cleared
            else:
                self.showCallImage(self.defaultpix)

    def showCallImage(self, callpix):
        self.ui.lbCallPic.setPixmap(callpix)

    def showCtry(self, ctry, flag):
        if ctry != '':
            flgres = ':/flags/' + flag
            flagpix = QtGui.QPixmap(flgres)
            self.ui.lbFlag.setPixmap(flagpix)
            self.ui.lbCtry.setText(ctry)
        else:
            self.ui.lbFlag.clear()
            self.ui.lbCtry.clear()

    def setLastHeard(self, calldata):
        # add current call details to the last heard table
        # calldata (info - array for inserting last heard, duration)
        self.ui.txrxLed.setOff()                   # end of call
        self.ui.txrxLed.setChecked(False)
        self.setAudioLevel(0)
        # print('call end')
        info = calldata[0]
        duration = calldata[1]
        if duration > 1 or cfg.shortCalls:
            self.ui.tblLastHeard.insertRow(0)        # add row at the top
            col = 0
            # print('set ', info)
            for item in info:
                cell = QTableWidgetItem(str(item))
                self.ui.tblLastHeard.setItem(0, col, cell)      # adding at the top
                col += 1

            # keep it managable
            lhrows = self.ui.tblLastHeard.rowCount()
            if lhrows > 10:
                self.ui.tblLastHeard.removeRow(lhrows - 1)

        # clear call details
        self.showStatus('Listening...')
        self.setCall(['', ''])

    def tblLastHeardMenu(self, position):
        row = self.ui.tblLastHeard.rowAt(position.y())
        if row < 0:         # clicked outside a valid row
            return
        self.ui.tblLastHeard.selectRow(row)
        callSign = self.ui.tblLastHeard.item(row, 1).text()

        rgtmenu = QMenu()
        rgtmenu.setTitle('Lookup')
        lkqrzAction = rgtmenu.addAction('QRZ')
        lkaprsAction = rgtmenu.addAction('APRS')
        lkbmAction = rgtmenu.addAction('Brandmeister')
        lkhamAction = rgtmenu.addAction('Hamdata')
        pvtcallAction = rgtmenu.addAction('Private Call')

        action = rgtmenu.exec_(self.ui.tblLastHeard.mapToGlobal(position))
        if action == lkqrzAction:
            lookup_call_on_web('QRZ', 'http://www.qrz.com/lookup/', callSign)
        elif action == lkaprsAction:
            lookup_call_on_web('aprs.fi', 'https://aprs.fi/#!call=a%2F', callSign)
        elif action == lkbmAction:
            lookup_call_on_web('Brandmeister', 'https://brandmeister.network/index.php?page=profile&call=', callSign)
        elif action == lkhamAction:
            lookup_call_on_web('Hamdata.com', 'http://hamdata.com/getcall.html?callsign=', callSign)
        elif action == pvtcallAction:
            # setup private call
            pass

    def initLastHeard(self):
        cols = [defs.STRING_CALLTIME,
                defs.STRING_CALL,
                # defs.STRING_MODE,
                defs.STRING_NAME,
                defs.STRING_TG,
                # defs.STRING_LOSS,
                defs.STRING_DURATION,
                # ''
                ]
        # widths = [100, 70, 55, 125, 50, 60]     # , 30]
        widths = [100, 70, 125, 125, 60]     # , 30]
        self.ui.tblLastHeard.setColumnCount(5)
        # self.ui.tblLastHeard.setHorizontalHeaderLabels(['Calltime', 'Call', 'Mode', 'Talkgroup', 'Loss', 'Duration'])
        # self.ui.tblLastHeard.setHorizontalHeaderLabels(['Calltime', 'Call', 'Name', 'Talkgroup', 'Duration'])
        self.ui.tblLastHeard.setHorizontalHeaderLabels(cols)
        # self.ui.tblLastHeard.setColumnHidden(2, True)    # hide the actual commands
        # self.ui.tblLastHeard.setColumnHidden(3, True)
        for idx in range(len(widths)):
            self.ui.tblLastHeard.setColumnWidth(idx, widths[idx])

        # setup right click menu options
        self.ui.tblLastHeard.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.tblLastHeard.customContextMenuRequested['QPoint'].connect(self.tblLastHeardMenu)

        # self.setLastHeard([])
        # print('last heard right click setup')

    # -- UI actions -- #
    def enterTalkgroup(self):
        # get user entered talkgroup/private call id
        if self.tgDlg is None:
            self.tgDlg = tgDlg()
            self.tgDlg.setStyleSheet(self.styleSheet())

        # set macros
        if len(cfg.macros) == 0:
            self.tgDlg.ui.cbMacros.setEnabled(False)
        else:
            self.tgDlg.setMacros(cfg.macros)
            self.tgDlg.ui.cbMacros.setEnabled(True)
        self.tgDlg.setMode(self.currentMode)                # enable/disable time slot
        self.tgDlg.setTG(self.currentTG)

        # get input
        if self.tgDlg.exec():
            tgval = self.tgDlg.getSelected()                # this could be a macro
            if tgval != '':
                # self.connTG.setText('Tg: ' + str(tgval))
                # self.currentTG = tgval
                # self.currentTGName = tgval                  # displayed name
                coms.setRemoteTG(str(tgval))
                # selectTalkgroup(tgval)

    def selTalkgroup(self, selIdx):
        # select preset talkgroup/call
        tgName = self.selTg.itemText(selIdx)
        self.currentTGName = tgName                         # displayed name
        for item in self.tgrps:
            if item[0].translate(cfg.noQuote) == tgName:
                self.currentTG = item[1]                    # this could be multiple entries??

        self.connTG.setText('Tg: ' + tgName)
        # ensure coms is in sync
        coms.setRemoteTG(self.currentTG)
        # coms.updateServerInfo(self.currentTG, tgName)
        # selectTalkgroup(self.currentTG)                 # set tx to tg number

    def clickCallImage(self, event):
        if event.button() == Qt.LeftButton:
            event.accept()
            call = self.ui.lbCallsign.text()
            # print(' looking up ' + call)
            if len(call) > 0:
                webbrowser.open_new_tab("http://www.qrz.com/lookup/" + call)

    def pttEnable(self, state):
        self.ui.txButton.setEnabled(state)

    def setPttOnOff(self, txOn):
        if txOn:       # transmitting
            self.ui.txButton.setStyleSheet('background-color: red')
            self.ui.txrxLed.setRed()
        else:
            self.ui.txButton.setStyleSheet('')
            self.ui.txrxLed.setGreen()

        self.currentTx = txOn
        self.ui.txrxLed.setChecked(txOn)

    # mouse events for ptt button
    def pttTimeout(self):
        self.txTimeout -= 1
        if self.txTimeout < 0:
            self.pttTimer.stop()
            transmit(False)
            self.setPttOnOff(False)
            self.ui.txButton.setText(defs.STRING_TRANSMIT)
        else:
            mins = self.txTimeout // 60
            secs = self.txTimeout % 60
            self.ui.txButton.setText(str(mins) + ':' + str(secs).zfill(2))

    def pttON(self, event):
        # ptt button press
        if event.button() == Qt.LeftButton:
            event.accept()
            self.showNotification('Transmitting')
            # already in tx mode?
            if self.pttDown:
                self.pttDown = False
                self.pttTimer.stop()
                transmit(False)
                self.ui.txButton.setText(defs.STRING_TRANSMIT)
            else:
                self.pttDown = True
                transmit(True)
                if cfg.txTimeout > 0:
                    self.txTimeout = cfg.txTimeout - 2      # account for initial delay and zero count
                    self.pttTimer.start(1000)

    def pttOFF(self, event):
        # ptt button release
        if event.button() == Qt.LeftButton:
            event.accept()
            if not cfg.pttToggle:                           # next ptt press will clear if toggle
                self.pttDown = False
                self.pttTimer.stop()
                transmit(False)
                self.ui.txButton.setText(defs.STRING_TRANSMIT)

    # --  UI functions -- #
    def clearUiModes(self):
        # main menu items
        self.ui.actionDMR.setChecked(False)
        self.ui.actionDStar.setChecked(False)
        self.ui.actionNXDN.setChecked(False)
        self.ui.actionP25.setChecked(False)
        self.ui.actionYSF.setChecked(False)
        # toolbar
        self.ui.actionTbDMR.setChecked(False)
        self.ui.actionTbDStar.setChecked(False)
        self.ui.actionTbNXDN.setChecked(False)
        self.ui.actionTbP25.setChecked(False)
        self.ui.actionTbYSF.setChecked(False)

    def selectMode(self, mode):
        self.clearUiModes()
        ut.log.info('Selecting ' + mode + ' mode')

        if mode == 'DSTAR':
            self.ui.actionTbDStar.setChecked(True)
            self.ui.actionDStar.setChecked(True)
        elif mode == 'NXDN':
            self.ui.actionTbNXDN.setChecked(True)
            self.ui.actionNXDN.setChecked(True)
        elif mode == 'P25':
            self.ui.actionTbP25.setChecked(True)
            self.ui.actionP25.setChecked(True)
        elif mode == 'YSF':
            self.ui.actionTbYSF.setChecked(True)
            self.ui.actionYSF.setChecked(True)
        else:                                           # default to 'DMR'
            self.ui.actionTbDMR.setChecked(True)
            self.ui.actionDMR.setChecked(True)
            mode = 'DMR'                                # ensure mode is correct (unlikely but...)
        self.setup_mode(mode)

    def setVoxPtt(self, voxOn):
        self.ui.voxLed.setChecked(voxOn)

    def setVox(self):
        # vox led click
        state = not self.ui.voxLed.isChecked()
        setVoxState(state)                          # toggle and pass it on

    def setVoxEnable(self, voxEnabled):
        # cfg.vox_enable = voxEnabled
        if voxEnabled:
            self.ui.voxLed.setYellow()
            self.ui.voxLed.setChecked(True)
            self.ui.voxLed.setToolTip('Vox enabled')
        else:
            self.ui.voxLed.setOff()
            self.ui.voxLed.setChecked(False)
            self.ui.voxLed.setToolTip('Vox disabled')


# -- Inter process access -- #
def selectServerMode(mode):
    mode = mode.upper()         # just in case  :)
    app.selectMode(mode)        # toggle ui options
    ut.log.info("New mode selected: %s", mode)
    coms.setServerMode(mode)


# def selectTalkgroup(tgid):
#    # set the selected talkgroup/private call id
#    ut.log.info('Selected tg: %s', tgid)
#    coms.setRemoteTG(tgid)


def selectTGByValue(tgVal, mode=''):
    # select/display a talkgroup (number)
    app.setConnectedTgVal(tgVal, mode)


def getValuesFromServer():
    # Query server data state and display them on UI
    # ut.log.info('Requesting server setup')
    coms.getValuesFromServer()


def sendValuesToServer():
    # Update server data state to match GUI values
    # ut.log.info('Sender server setup')
    coms.sendValuesToServer()


def lookup_call_on_web(service, url, call):
    ut.log.debug("Lookup call " + call + " on service " + service)
    webbrowser.open_new_tab(url + call)


# --  Callbacks -- #
def errorMsg(msg):
    ut.log.error(' - ' + msg)


def connectedStatus(state, server=''):
    if state:
        if server == '':
            stMsg = defs.STRING_CONNECTED
        else:
            stMsg = defs.STRING_CONNECTED_TO + ' ' + server
    else:
        stMsg = defs.STRING_DISCONNECTED

    app.gui_queue.put({'status': stMsg, 'connected': state})


def notifyMsg(msgType, msg):
    # popup messaging..
    msgType = msgType.lower()
    if msgType == 'text':
        # print('text: ', msg)
        app.gui_queue.put({'infomsg': msg})
    elif msgType == 'macro':
        # macro list is passed in msg - unsure here as not verified
        cfg.macros = msg
        ut.log.debug('macros rx: ' + str(msg))

    elif msgType == 'menu':
        # macro/menu dict is passed in msg
        cfg.radmenu = msg
        ut.log.debug('radio menu rx: ' + str(msg))
        # for key in msg:
        #    menuval = str(msg[key])
        #    cfg.radmenu[key] = menuval
        # print('menu dict: ', cfg.radmenu)

    elif msgType == 'servertg':
        app.gui_queue.put({'servertg': msg})       # current server tg


def pttEnable(state):
    # enable/disable the Transmit button
    app.gui_queue.put({'pttenable': state})


def pttState(state):
    # update the current PTT state and call start/end
    app.gui_queue.put({'pttstate': state})


def voxPttState(state):
    app.gui_queue.put({'voxptt': state})


def setVoxEnabled(state):
    app.gui_queue.put({'voxenable': state})


def setVoxState(state):
    # enable/disable vox operation - vox led click
    coms.enableVox(state)


def transmit(state):
    coms.transmit(state)                        # start/stop tx audio


def callinfo(call, name, tg):
    # get and display call picture and name etc
    if tg == 'DSTAR' or tg == "YSF":            # for these modes the TG is not valid
        tg = app.getSelectedTgName()            # need to get the tgrp is it is not set?
    elif tg == cfg.subscriber_id:               # is the dest TG my dmr ID? (private call)
        tg = cfg.my_call
    else:
        app.setConnectedTgVal(str(tg), '')       # select/display tg for current mode
        tg = app.getSelectedTgName()

    ut.log.debug('Call start - ' + str(call) + ', tg: ' + str(tg))

    calldata = '{} {} -> {}'.format(name, call, tg)
    app.gui_queue.put({'status': calldata, 'qrz': [call, name]})


def logEndRxCall(call, name, mode, slot, tg, callmode, loss, start_time):
    ut.log.debug('End RX:   {} {} {} {} {:.2f}s'.format(call, mode, tg, loss, time() - start_time))

    # a bit of error checking
    callstart = strftime('%b %d %H:%M', localtime(start_time))
    if call == '':
        call = '??'

    tgname = str(tg)
    if tgname == '' or tgname == app.getSelectedTg():
        tgname = str(app.getSelectedTgName())          # use the TG we are listening to

    if callmode == 'Private':
        tgname += ' *'
    duration = time() - start_time

    info = [callstart,
            call,   # .ljust(10),
            # mode,   # + ' ' + str(slot),
            name,
            tgname,    # tg,
            # loss,
            '{:.2f}s'.format(time() - start_time)
            ]
    calldata = (info, duration)
    app.gui_queue.put({'lastheard': calldata})


def logEndTxCall(mode, tg, slot, start_time, duration):
    #  callinfo = [call, name, mode, slot, tg, callmode, loss, start_time]
    call = cfg.my_call
    loss = '0.0%'               # ?? not being sent from dvswitch?

    callstart = strftime('%b %d %H:%M', localtime(start_time))

    ut.log.debug('End TX:   {} {} {} {} {:.2f}s'.format(call, mode, slot, loss, duration))
    info = [callstart,
            call.ljust(10),
            # mode,
            'Me',
            # slot,
            tg,
            # loss,
            '{:.2f}s'.format(duration)
            ]
    calldata = (info, duration)
    app.gui_queue.put({'lastheard': calldata})


def txrxLevel(level):
    app.gui_queue.put({'audiolevel': level})


def serverState():
    # connect/disconnect server - server led click
    if coms.regState:
        disconnectServer()
    else:
        connectServer(app.currentTG)


def connectServer(tgTup):
    # connect the server to a tg/slot
    # tgTup = (tg, name, slot)
    if not coms.regState:
        coms.initStart()

    if tgTup is not None:                   # tg passed
        tg = tgTup[0]
        tg_name = tgTup[1]
    else:
        tg = app.currentTG                  # setCurrentTG()
        tg_name = app.currentTGName         # getCurrentTGName()

    if not tg.startswith('*'):              # If it is not a macro, do a full dial sequence
        ut.log.info(defs.STRING_CONNECTED_TO + ' ' + tg_name)
        coms.connectServer(app.currentMode, tg, app.currentSlot)
    else:
        coms.setRemoteTG(tg)


def disconnectServer():
    pttEnable(False)
    coms.disconnectServer()
    app.showStatus(defs.STRING_DISCONNECTED)


'''
def loadLocalConfig():
    # if not cfg.valid:
    ut.log.info('loading local configuration')
    settings = QSettings()
    cfg.my_call = settings.value('mycall', cfg.my_call, type=str)
    cfg.subscriber_id = settings.value('subscriber_id', cfg.subscriber_id, type=int)
    cfg.repeater_id = settings.value('repeater_id', cfg.repeater_id, type=int)
    cfg.ip_address = settings.value('ip_address', cfg.ip_address, type=str)
    # need to be carefull of tx ports as the list is saved as strings
    txlist = settings.value('usrp_tx_port', cfg.usrp_tx_port, type=list)
    txports = []
    for prt in range(len(txlist)):
        tp = int(txlist[prt])
        txports.append(tp)
    cfg.usrp_tx_port = txports
    cfg.usrp_rx_port = settings.value('usrp_rx_port', cfg.usrp_rx_port, type=int)
    cfg.defaultServer = settings.value('defaultServer', cfg.defaultServer, type=str)

    # additional settings
    # cfg.loopback = settings.value('loopback', cfg.loopback, type=bool)        # not used
    cfg.vox_enable = settings.value('voxenable', cfg.vox_enable, type=bool)
    cfg.vox_threshold = settings.value('voxthreshold', cfg.vox_threshold, type=int)
    cfg.vox_delay = settings.value('voxdelay', cfg.vox_delay, type=int)
    # cfg.dongle_mode = settings.value('donglemode', cfg.dongle_mode, type=bool)   # not used
    cfg.mic_vol = settings.value('txvol', cfg.mic_vol, type=int)
    cfg.sp_vol = settings.value('rxvol', cfg.sp_vol, type=int)
    cfg.in_index = settings.value('txinput', cfg.in_index, type=int)
    cfg.out_index = settings.value('rxoutput', cfg.out_index, type=int)

    cfg.useQRZ = settings.value('use_qrz', cfg.useQRZ, type=bool)
    cfg.minToTray = settings.value('mintotray', cfg.minToTray, type=bool)      # UI settings
    cfg.pttToggle = settings.value('ptttoggle', cfg.pttToggle, type=bool)
    cfg.shortCalls = settings.value('shortcalls', cfg.shortCalls, type=bool)
    cfg.txTimeout = settings.value('txtimeout', cfg.txTimeout, type=int)
    cfg.theme = settings.value('theme', cfg.theme, type=str)
    cfg.loglevel = settings.value('loglevel', cfg.loglevel, type=str)

    # set logging level
    ut.setLoglevel(cfg.loglevel)

    # chek for valid settings
    cfg.validateConfigInfo(cfg)
'''

# -- The main bit -- #
if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    application = QApplication([])
    # application.setStyle('Fusion')
    app = qtUC()

    # qtUCTranslator = QTranslator();
    # qtUCTranslator.load(QLocale(), QLatin1String("myapp"), QLatin1String("_"), QLatin1String(":/i18n"));
    # app.installTranslator(&qtUCTranslator);
    # cfg.setupPaths(cfg)             # setup some stuff
    cfg.loadConfig(cfg)             # read configuration from ini
    # cfg.importLocal(cfg)            # load any local updates to talkgroups and/or macros
    # cfg.loadLocalConfig(cfg)        # local UI settings and local details override

    # set stylesheet
    theme = cfg.theme.lower()
    if theme != '' and theme != 'system':
        file = QFile(':/theme/' + theme)
        file.open(QFile.ReadOnly | QFile.Text)
        stream = QTextStream(file)
        app.setStyleSheet(stream.readAll())

    if not cfg.valid:
        app.showPrefsDlg()                          # need to get user configuration

    # setup and connect the dots
    coms = qtComs()
    coms.onError = errorMsg
    coms.onRegisterStatus = connectedStatus
    coms.onNotifyMsg = notifyMsg
    coms.onSelectTg = app.setConnectedTgVal         # selectTGByValue
    coms.onTxEnable = pttEnable                     # enable/disable PTT
    coms.onPttStatus = pttState
    coms.onVoxStatus = setVoxEnabled                # vox enabled/disabled state
    coms.onVoxPtt = voxPttState                     # vox active/inactive
    coms.onTxRxLevel = txrxLevel
    coms.onCallInfo = callinfo
    coms.onEndRxCall = logEndRxCall
    coms.onEndTxCall = logEndTxCall

    if cfg.valid:
        selectServerMode(cfg.defaultServer)
    else:
        errmsg = 'Invalid configuration'
        app.gui_queue.put({'infomsg': errmsg, 'status': errmsg})

    if cfg.minToTray:
        app.hide()
    else:
        app.show()

    sys.exit(application.exec())
