import os
import sys
import json
from subprocess import Popen
from pype import lib as pypelib
from avalon.vendor.Qt import QtWidgets, QtCore
from avalon import api, style, schema
from avalon.tools import lib as parentlib
from .widgets import *
# Move this to pype lib?
from avalon.tools.libraryloader.io_nonsingleton import DbConnector

module = sys.modules[__name__]
module.window = None

class Window(QtWidgets.QDialog):
    _db = DbConnector()
    _jobs = {}
    valid_family = False
    valid_components = False
    initialized = False
    WIDTH = 1100
    HEIGHT = 500
    NOT_SELECTED = '< Nothing is selected >'

    def __init__(self, parent=None):
        super(Window, self).__init__()
        self._db.install()

        self.setWindowTitle("Standalone Publish")
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setStyleSheet(style.load_stylesheet())

        # Validators
        self.valid_parent = False

        # statusbar - added under asset_widget
        label_message = QtWidgets.QLabel()
        label_message.setFixedHeight(20)

        # assets widget
        widget_assets_wrap = QtWidgets.QWidget()
        widget_assets_wrap.setContentsMargins(0, 0, 0, 0)
        widget_assets = AssetWidget(self)

        layout_assets = QtWidgets.QVBoxLayout(widget_assets_wrap)
        layout_assets.addWidget(widget_assets)
        layout_assets.addWidget(label_message)

        # family widget
        widget_family = FamilyWidget(self)

        # components widget
        widget_components = ComponentsWidget(self)

        # Body
        body = QtWidgets.QSplitter()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        body.setOrientation(QtCore.Qt.Horizontal)
        body.addWidget(widget_assets_wrap)
        body.addWidget(widget_family)
        body.addWidget(widget_components)
        body.setStretchFactor(body.indexOf(widget_assets_wrap), 2)
        body.setStretchFactor(body.indexOf(widget_family), 3)
        body.setStretchFactor(body.indexOf(widget_components), 5)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(body)

        self.resize(self.WIDTH, self.HEIGHT)

        # signals
        widget_assets.selection_changed.connect(self.on_asset_changed)

        self.label_message = label_message
        self.widget_assets = widget_assets
        self.widget_family = widget_family
        self.widget_components = widget_components

        self.echo("Connected to Database")

        # on start
        self.on_start()

    @property
    def db(self):
        return self._db

    def on_start(self):
        # Refresh asset input in Family widget
        self.on_asset_changed()
        self.widget_components.validation()
        self.shadow_widget = ShadowWidget(self)
        self.shadow_widget.setVisible(False)

    def resizeEvent(self, event=None):
        position_x = (self.frameGeometry().width()-self.shadow_widget.frameGeometry().width())/2
        position_y = (self.frameGeometry().height()-self.shadow_widget.frameGeometry().height())/2
        self.shadow_widget.move(position_x, position_y)
        w = self.frameGeometry().width()
        h = self.frameGeometry().height()
        self.shadow_widget.resize(QtCore.QSize(w, h))
        if event:
            super().resizeEvent(event)

    def get_avalon_parent(self, entity):
        parent_id = entity['data']['visualParent']
        parents = []
        if parent_id is not None:
            parent = self.db.find_one({'_id': parent_id})
            parents.extend(self.get_avalon_parent(parent))
            parents.append(parent['name'])
        return parents

    def echo(self, message):
        self.label_message.setText(str(message))
        QtCore.QTimer.singleShot(5000, lambda: self.label_message.setText(""))

    def on_asset_changed(self):
        """Callback on asset selection changed

        This updates the task view.

        """
        selected = self.widget_assets.get_selected_assets()
        if len(selected) == 1:
            self.valid_parent = True
            asset = self.db.find_one({"_id": selected[0], "type": "asset"})
            self.widget_family.change_asset(asset['name'])
        else:
            self.valid_parent = False
            self.widget_family.change_asset(self.NOT_SELECTED)
        self.widget_family.on_data_changed()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_V and event.modifiers() == QtCore.Qt.ControlModifier:
            clip = QtWidgets.QApplication.clipboard()
            self.widget_components.process_mime_data(clip)
        super().keyPressEvent(event)

    def working_start(self, msg=None):
        if msg is None:
            msg = 'Please wait...'
        self.shadow_widget.message = msg
        self.shadow_widget.setVisible(True)
        self.resizeEvent()
        QtWidgets.QApplication.processEvents()

    def working_stop(self):
        if self.shadow_widget.isVisible():
            self.shadow_widget.setVisible(False)

    def set_valid_family(self, valid):
        self.valid_family = valid
        if hasattr(self, 'widget_components'):
            self.widget_components.validation()

    def collect_data(self):
        data = {}
        data.update(self.widget_assets.collect_data())
        data.update(self.widget_family.collect_data())
        data.update(self.widget_components.collect_data())

        return data

def show(parent=None, debug=False):
    try:
        module.window.close()
        del module.window
    except (RuntimeError, AttributeError):
        pass

    with parentlib.application():
        window = Window(parent)
        window.show()

        module.window = window


def cli(args):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("asset")

    args = parser.parse_args(args)
    # project = args.project
    # asset = args.asset

    show()
