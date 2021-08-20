# -*- coding: utf-8 -*-
#
# qtUC - pyUC with a QT interface
#   Rowan Deppeler - VK3VW
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
from tgEditDlgUI import Ui_tgEditDlg
from qtUC_vars import qtUCVars as localcfg                # configuration variables for import/export
import qtUC_util as ut
import qtUC_defs as defs


class tgEditDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_tgEditDlg()
        self.ui.setupUi(self)
        self.setWindowTitle('qtUC Editor')
        icon = QtGui.QIcon(":/icons/edit")
        self.setWindowIcon(icon)
        # self.ui.plTextEdit.NoWrap()
        self.nodes = None                                       # talkgroups/nodes
        self.macros = None                                      # macros

        # connect the internal dots
        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)

        # labeling - cannot modify standard buttons yet  :()
        # self.ui.buttonBox.Save.setText(defs.STRING_SAVE)
        # self.ui.buttonBox.Cancel.setText(defs.STRING_CANCEL)

    # intercept accepted signal
    def accept(self):
        # get edited text and rebuild as a dict()
        edText = self.ui.plTextEdit.toPlainText()
        newList = edText.split('\n')
        flgNodes = self.nodes is not None
        edList = []
        edDict = {}

        for itm in newList:
            # print('editm ', itm)
            itms = itm.split('=')
            if len(itms) == 2:
                key = str(itms[0]).strip()
                val = str(itms[1]).strip()
                if flgNodes:                                    # we are editing talkgroups/nodes (list)
                    edList.append((key, val))                   # adding tuples to a list here
                else:
                    edDict[key] = val                           # set dict key: val

        # set both... caller will sort out which one is required
        self.nodes = edList
        self.macros = edDict

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

    def getNodes(self):
        return self.nodes

    def getMacros(self):
        return self.macros

    def setEditNodes(self, edNodes):
        # set a node list for editing [(info, cmd),...]
        self.nodes = edNodes
        self.macros = None

        lines = ''
        for key, val in edNodes:
            lines += str(key) + ' = ' + str(val) + '\n'

        self.ui.plTextEdit.setPlainText(lines)

    def setEditMacros(self, edMacros):
        # set the macro dict for editing
        self.macros = edMacros
        self.nodes = None

        lines = ''
        for mac in edMacros.keys():
            lines += mac + ' = ' + edMacros[mac] + '\n'
        self.ui.plTextEdit.setPlainText(lines)

    def importLocalEdit(self):
        # load local configuration
        macros = False
        if self.macros is None:                                 # must be editing talkgroups
            msg = 'Load talkgroups'
            macros = True
        else:
            msg = 'Load macros'

        fname = QFileDialog.getOpenFileName(self, msg)
        if fname[0] != '':
            cfgfile = fname[0]
            ut.log.info('Importing local data ' + cfgfile)
            try:
                localcfg.setupPaths(localcfg)                   # separate copy here
                localcfg.local_tgmacfile = cfgfile
                localcfg.importLocal(localcfg)                  # get talkgroups and macros in the file
                if macros:
                    self.setEditMacros(localcfg.macros)
                else:
                    self.setEditNodes(localcfg.talk_groups)

                ut.log.info("Local data imported")
                self.showMsg('', 'Local data loaded', 'info')
            except Exception as e:
                ut.log.error("Unable to import local data")
                self.showMsg('Import failed', 'Unable to load local data\n' + str(e), 'error')

    def exportLocalEdit(self):
        # export the current configuration
        macros = False
        if self.macros is None:                                 # must be editing talkgroups
            msg = 'Save talkgroups'
            macros = True
        else:
            msg = 'Save macros'
        cfgfile = 'qtUC_local.ini'
        fname = QFileDialog.getSaveFileName(self, msg, cfgfile, '*.ini')
        if fname[0] != '':
            cfgfile = fname[0]
            ut.log.info('Saving local data ' + cfgfile)
            try:
                localcfg.setupPaths(localcfg)                   # separate copy here
                localcfg.local_tgmacfile = cfgfile
                localcfg.importLocal(localcfg)                  # get local talkgroups and macros if present
                if macros:
                    localcfg.macros = self.macros
                else:
                    localcfg.talk_groups = self.nodes

                localcfg.exportLocal(localcfg)
                ut.log.info("Local data exported")
                self.showMsg('', 'Local data saved', 'info')
            except Exception as e:
                ut.log.error("Unable to export local data")
                self.showMsg('Export failed', 'Unable to save local data \n' + str(e), 'error')
