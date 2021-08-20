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
from aboutUI import Ui_qtUCAbout
import qtUC_const as const
import resources_rc


class abtDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_qtUCAbout()
        self.ui.setupUi(self)
        self.setWindowTitle('About qtUC')
        icon = QtGui.QIcon(":/icons/info")
        self.setWindowIcon(icon)

        self.sa = QScrollArea(self)
        self.sa.setWidgetResizable(True)
        al_content = QWidget(self)
        self.sa.setWidget(al_content)
        lay = QVBoxLayout(al_content)
        self.sa.setGeometry(5, 5, 310, 230)

        # creating labels
        self.aboutLabel = QLabel(al_content)
        self.aboutLabel.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.aboutLabel.setWordWrap(True)
        lay.addWidget(self.aboutLabel)
        self.aboutLabel.setText(self.getQtUCInfo())

        self.pyucLabel = QLabel(al_content)
        self.pyucLabel.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.pyucLabel.setWordWrap(True)
        lay.addWidget(self.pyucLabel)
        self.pyucLabel.setText(self.getPyUCInfo())

    def getQtUCInfo(self):
        infoText = "qtUC Client Version " + const.qtUC_VERSION + "<br/>"
        infoText += "(C) 2021 VK3VW<br/>"
        infoText += "<a href='https://github.com/greythane/qtUC'>https://github.com/greythane/qtUC</a>"
        return infoText

    def getPyUCInfo(self):
        aboutText = "Based on the USRP Client (pyUC) Version " + const.UC_VERSION + "<br/>"
        aboutText += "(C) 2019, 2020, 2021 DVSwitch, INAD.<br/>"
        aboutText += "Created by Mike N4IRR and Steve N4IRS<br/>"
        aboutText += "pyUC comes with ABSOLUTELY NO WARRANTY<br/><br/>"
        aboutText += "This software is for use on amateur radio networks only, "
        aboutText += "and is to be used for educational purposes only. Use on "
        aboutText += "commercial networks is strictly prohibited.<br/><br/>"
        aboutText += "Code improvements are encouraged, please "
        aboutText += "contribute to the development branch at<br/>"
        aboutText += "Flag icons courtesy of 'flagpedia.net'<br/>"
        linkText = "<a href='https://github.com/DVSwitch/USRP_Client'>https://github.com/DVSwitch/USRP_Client</a>"
        return aboutText + linkText
