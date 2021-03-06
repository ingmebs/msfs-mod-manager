import PySide2.QtCore as QtCore
import PySide2.QtWidgets as QtWidgets

from lib.version import get_version


class versions_widget(QtWidgets.QDialog):
    def __init__(self, flight_sim, parent=None, appctxt=None):
        """Game and application versions widget."""
        QtWidgets.QDialog.__init__(self)
        self.flight_sim = flight_sim
        self.parent = parent
        self.appctxt = appctxt

        self.setWindowTitle("Versions")
        self.setWindowFlags(
            QtCore.Qt.WindowSystemMenuHint
            | QtCore.Qt.WindowTitleHint
            | QtCore.Qt.WindowCloseButtonHint
        )
        self.setWindowModality(QtCore.Qt.ApplicationModal)

        self.layout = QtWidgets.QFormLayout()

        self.app_version_field = QtWidgets.QLineEdit(self)
        self.app_version_field.setReadOnly(True)
        self.layout.addRow("Application Version:", self.app_version_field)

        self.game_version_field = QtWidgets.QLineEdit(self)
        self.game_version_field.setReadOnly(True)
        self.layout.addRow("Game Version:", self.game_version_field)

        self.setLayout(self.layout)
        self.get_versions()

        self.show()
        self.setFixedSize(self.width(), self.height())

    def get_versions(self):
        self.app_version_field.setText(get_version(self.appctxt))
        self.game_version_field.setText(self.flight_sim.get_game_version())
