# -*- coding: utf-8 -*-
#
# qtUC - pyUC with a QT interface
# Based on the original pyUC code, modified for QT5 use
# Rowan Deppeler - VK3VW - greythane @ gmail.com
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
from PyQt5.QtCore import *
from PyQt5 import QtGui
from PyQt5.QtWidgets import *
from tgDlgUI import Ui_tgDlg
import qtUC_defs as defs
import resources_rc


class tgDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_tgDlg()
        self.ui.setupUi(self)
        self.setWindowTitle('Select talkgroup')
        icon = QtGui.QIcon(":/icons/chat")
        self.setWindowIcon(icon)

        self.mode = None
        self.dmr = False
        self.macros = None
        self.tgmac = ''
        self.tslot = 2
        self.pvtCall = False
        self.selectedMacro = ''

        self.ui.cbPvtCall.setText(defs.STRING_PRIVATE)
        # self.ui.selTgBtn.setText(defs.)
        # self.ui.cbPvtCall.stateChanged.connect(self.pvtCallClicked)
        self.ui.cbMacros.activated.connect(self.selMacro)
        self.ui.selTgBtn.clicked.connect(self.accept)
        self.ui.btnCancel.clicked.connect(self.reject)

    def accept(self):
        edTg = self.ui.editTgrp.text()
        if edTg != '':
            self.tgmac = edTg
        super().accept()

    def setMacros(self, mdict):
        # set the macro combo box from the supplied macro dict
        # macro name : value
        self.macros = mdict
        self.ui.cbMacros.clear()
        # for idx in range(len(self.macros)):
        #    self.ui.cbMacros.addItem(self.macros[idx][0])
        for mac in self.macros.keys():
            self.ui.cbMacros.addItem(mac)

    def setMode(self, mode):
        dmr = mode == 'DMR'
        self.dmr = dmr
        self.ui.lbTSlot.setEnabled(dmr)
        self.ui.sbTSlot.setEnabled(dmr)

    def setTG(self, tg):
        self.tgmac = tg
        self.ui.editTgrp.setText(tg)

    def selMacro(self, selIdx):
        # get the macro value and set as the returned 'tg'
        macName = self.ui.cbMacros.itemText(selIdx)
        self.selectedMacro = macName                            # displayed name
        self.tgmac = self.macros[macName]                       # macro value
        print(macName, self.tgmac)
        # for item in self.macros:
        #    if item[0].translate(cfg.noQuote) == macName:
        #        self.selectedTG = item[1]                        # this could be multiple entries??

    # def pvtCallClicked(self, checked):
    #    if checked and self.tgmac != '':
    #
    #        self.ui.voxThreshold.setEnabled(True)
    #        self.ui.voxDelay.setEnabled(True)

    def getSelected(self):
        if self.ui.cbPvtCall.isChecked():
            return self.tgmac + '*'                             # should ts be returned??
        return self.tgmac
