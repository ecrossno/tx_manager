import os
import glob

from qtpy import QtWidgets, QtCore, QtGui
import logging

import tx_manager.tx_create_backend as tx_create_backend


class TxCreate(QtWidgets.QDialog):
    def __init__(self, texture_list=None, result_message=True, parent=None):
        """This widow is used to set options and run maketx on a list of provided texture files.

        Args:
            texture_list: a list of texture file paths to process.
            parent: the parent widget
        """
        super(TxCreate, self).__init__(parent)
        if not texture_list:
            self.warning_message()
            return
        self.result_message = result_message
        self.setModal(True)
        self.texture_list = texture_list
        self.failed_file_list = []
        self.handle_udims()
        self.texture_count = len(self.texture_list)
        self.mutex = QtCore.QMutex()
        self.progress_complete = False
        self.build_ui()

    def build_ui(self):
        self.setWindowTitle("Tx Create")
        layout = QtWidgets.QVBoxLayout(self)

        options_layout = QtWidgets.QHBoxLayout()
        self.wrap_mode_cbbx = self.add_label_row("Wrap Mode", QtWidgets.QComboBox(), options_layout)
        self.wrap_mode_cbbx.addItems(['clamp', 'black', 'periodic', 'mirror'])
        self.wrap_mode_cbbx.setCurrentText('black')
        self.env_chbx = self.add_label_row("Env Map", QtWidgets.QCheckBox(), options_layout)
        layout.addLayout(options_layout)
        self.compression_cbbx = self.add_label_row("Data Compression", QtWidgets.QComboBox(), layout)
        self.compression_cbbx.addItems(['none', 'rle', 'zip', 'pxr24', 'b44','b44a'])
        self.compression_cbbx.setCurrentText('zip')

        layout.addWidget(QHLine())
        colorspace_layout = QtWidgets.QHBoxLayout()
        colorspace_label = QtWidgets.QLabel('Override ColorSpace:')
        self.colorspace_chbx = QtWidgets.QCheckBox()
        self.colorspace_chbx.stateChanged.connect(self.enable_colorspace_override)
        self.colorspace_cbbx = QtWidgets.QComboBox()
        self.colorspace_cbbx.addItems(["Utility - Raw",
                                  "Utility - sRGB - Texture",
                                  "Utility - sRGB - linear",
                                  "ACES - ACEScg",
                                  "Output - sRGB"])
        self.colorspace_cbbx.setEnabled(False)
        colorspace_layout.addWidget(colorspace_label)
        colorspace_layout.addWidget(self.colorspace_chbx)
        colorspace_layout.addWidget(self.colorspace_cbbx)
        colorspace_layout.setContentsMargins(5, 0, 5, 0)
        colorspace_layout.addStretch(1)
        layout.addLayout(colorspace_layout)
        layout.addWidget(QHLine())


        self.options_line_edit = self.add_label_row("Additional Options:", QtWidgets.QLineEdit(), layout)
        self.options_line_edit.setMinimumWidth(200)
        self.options_line_edit.setText('-u -v --runstats --unpremult')
        layout.addWidget(QHLine())
        layout.addWidget(QHLine())

        choice_layout = QtWidgets.QHBoxLayout()
        self.ok_btn = QtWidgets.QPushButton("Ok")
        self.ok_btn.setMinimumHeight(35)
        self.ok_btn.clicked.connect(self.start_tx_baker)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(35)
        self.cancel_btn.clicked.connect(self.reject)
        choice_layout.addWidget(self.ok_btn)
        choice_layout.addWidget(self.cancel_btn)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        layout.addLayout(choice_layout)

    def handle_udims(self):
        texture_paths = []
        for texture_path in self.texture_list:
            if not "<UDIM>" in texture_path:
                texture_paths.append(texture_path)
                continue
            udim_paths = glob.glob(texture_path.replace("<UDIM>", "*"), recursive=True)
            if not udim_paths:
                self.failed_file_list.append(texture_path)
                continue
            texture_paths = texture_paths + udim_paths
        self.texture_list = texture_paths

    def add_label_row(self, label_text, widget, parent_layout):
        widget.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, 0)
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        label = QtWidgets.QLabel(label_text)
        layout.addWidget(label, 0, QtCore.Qt.AlignRight)
        layout.addWidget(widget, 0, QtCore.Qt.AlignBaseline)
        parent_layout.addLayout(layout)
        layout.addStretch(1)
        return widget

    def warning_message(self):
        layout = QtWidgets.QHBoxLayout(self)
        icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_BrowserStop)
        icon_label = QtWidgets.QLabel()
        icon_label.setPixmap(icon.pixmap(22))
        label = QtWidgets.QLabel('No Textures were provided to edit the textures of.')
        layout.addWidget(icon_label)
        layout.addWidget(label)
        self.reject()

    def enable_colorspace_override(self, state):
        self.colorspace_cbbx.setEnabled(state)

    def start_tx_baker(self):
        self.failed_tasks = 0
        self.progress_bar.show()
        self.ok_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        options_dict = {}
        options_dict['compression'] = self.compression_cbbx.currentText()
        options_dict['wrap_mode'] = self.wrap_mode_cbbx.currentText()
        options_dict['additional_options'] = self.options_line_edit.text()
        options_dict['env_map'] = self.env_chbx.isChecked()
        if self.colorspace_chbx.isChecked():
            options_dict['colorspace_override'] = self.colorspace_cbbx.currentText()


        self.thread_pool = QtCore.QThreadPool()
        #self.thread_pool.setMaxThreadCount(10)
        for filename in self.texture_list:
            worker = TxBaker(filename, options_dict)
            worker.signals.complete.connect(self.update_progress)
            worker.signals.error_file.connect(self.update_failed_file_list)
            self.thread_pool.start(worker)

    def update_failed_file_list(self, failed_file):
        self.failed_file_list.append(failed_file)

    def accept(self):
        self.thread_pool.waitForDone()
        super().accept()

    def locked_update_progress(self, status):
        with QtCore.QMutexLocker(self.mutex):
            self.update_progress(status)

    def update_progress(self, status):
        self.mutex.lock()
        progress_increment = int(100 / len(self.texture_list)) + 1
        new_value = max(0, min(self.progress_bar.value()+progress_increment, 100))
        self.progress_bar.setValue(new_value)
        if status != 'Success':
            self.failed_tasks = self.failed_tasks + 1
            logging.warning(status)
        self.mutex.unlock()
        if new_value >= 100:
            if self.progress_complete:
                return
            self.progress_complete = True
            self.progress_bar.setValue(99)
            self.thread_pool.waitForDone()
            self.progress_bar.setValue(100)
            if self.failed_tasks:
                fail_dialog = FailedDialog(self.texture_count, self.failed_file_list, self)
                fail_dialog.exec_()
            if not self.result_message:
                self.accept()
                self.close()
                return
            message = f"{str(self.texture_count-len(self.failed_file_list))} tx images were created Successfully!"
            QtWidgets.QMessageBox.information(None, 'Success', message, QtWidgets.QMessageBox.Ok)
            self.accept()
            self.close()

class TxBaker(QtCore.QRunnable):
    def __init__(self, file_name, options_dict):
        """A QRunnable that calls the backend maketx method, and signals complete when finished.

        Args:
            file_name: name of the texture to process
            options_dict: make tx options for the texture
        """
        super(TxBaker, self).__init__()
        self.file_name = file_name
        self.options_dict = options_dict
        self.signals = TxBakerSignals()
        self.mutex = QtCore.QMutex()

    @QtCore.Slot()
    def run(self):
        try:
            result = tx_create_backend.run_make_tx(self.options_dict, self.file_name)
            self.signals.complete.emit(result)
            if result != "Success":
                self.signals.error_file.emit(self.file_name)
        except Exception as e:
            self.signals.complete.emit(result)
            self.signals.error_file.emit(self.file_name)


class FailedDialog(QtWidgets.QDialog):
    def __init__(self, texture_count, failed_list, parent):
        """A QRunnable that calls the backend maketx method, and signals complete when finished.

        Args:
            file_name: name of the texture to process
            options_dict: make tx options for the texture
        """
        super(FailedDialog, self).__init__(parent)
        self.texture_count = texture_count
        self.failed_list = failed_list
        self.build_ui()

    def build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        list_widget = QtWidgets.QListWidget()
        for failed_file in self.failed_list:
            item = QtWidgets.QListWidgetItem(failed_file)
            list_widget.addItem(item)
        text = f"{str(len(self.failed_list))} out of {str(self.texture_count)} images failed to generate tx files."
        label = QtWidgets.QLabel(text)
        button = QtWidgets.QPushButton("Ok")
        button.clicked.connect(self.accept)
        button.setMaximumSize(75, 75)
        layout.addWidget(list_widget)
        layout.addWidget(label)
        layout.addWidget(button, alignment=QtCore.Qt.AlignCenter)


class TxBakerSignals(QtCore.QObject):
    '''Defines the signals available from a running worker thread'''
    complete = QtCore.Signal(str)
    error_file = QtCore.Signal(str)

class QHLine(QtWidgets.QFrame):
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.setPalette(QtGui.QPalette(QtGui.QColor(41, 42, 44)))


