all : qtUCUI.py tgDlgUI.py tgEditDlgUI.py aboutUI.py settingsUI.py  notificationUI.py resources_rc.py

qtUCUI.py : qtUC.ui
	pyuic5 qtUC.ui -o qtUCUI.py

tgDlgUI.py : tgDlgUI.ui
	pyuic5 tgDlgUI.ui -o tgDlgUI.py

tgEditDlgUI.py : tgEditDlgUI.ui
	pyuic5 tgEditDlgUI.ui -o tgEditDlgUI.py

aboutUI.py : aboutUI.ui
	pyuic5 aboutUI.ui -o aboutUI.py

settingsUI.py : settingsUI.ui
	pyuic5 settingsUI.ui -o settingsUI.py

notificationUI.py : notificationUI.ui
	pyuic5 notificationUI.ui -o notificationUI.py

resources_rc.py : resources.qrc
	pyrcc5 resources.qrc -o resources_rc.py

clean cleandir:
	rm -rf $(CLEANFILES)

CLEANFILES = qtUCUI.py tgDlgUI.py tgEditDlgUI.py aboutUI.py settingsUI.py notificationUI.py resources_rc.py *.pyc