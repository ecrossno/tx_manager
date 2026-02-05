import os
import sys

import tx_manager.tx_create_view as tx_create_view

from qtpy import QtWidgets, QtCore, QtGui

EXTENSIONS = [ '.png', '.jpg', '.hdr', '.bmp', '.tif', '.tga', '.tex', '.exr', '.dpx', ]


class TxManager(QtWidgets.QWidget):
    def __init__(self , start_directory=None, parent=None):
        """A window that displays a list of textures in a directory that can add or remove tx files.

        Args:
            start_directory: the optional starting directory for the file dialog to point to.
            parent: the parent widget.
        """
        super(TxManager, self).__init__(parent)
        self.current_directory = start_directory
        self.build_ui()
        if start_directory:
            self.dir_select_line_edit.setText(start_directory)
            self.populate_from_directory()

    def build_ui(self):
        self.setWindowTitle("Tx Manager")
        layout = QtWidgets.QVBoxLayout(self)

        dir_select_layout = QtWidgets.QHBoxLayout()
        dir_select_label = QtWidgets.QLabel("Directory:")
        self.dir_select_line_edit = QtWidgets.QLineEdit()
        self.dir_select_line_edit.textChanged.connect(self.updated_directory)
        dir_select_btn = QtWidgets.QPushButton()
        dir_select_btn.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton))
        dir_select_btn.clicked.connect(self.get_directory)
        refresh_btn = QtWidgets.QPushButton('Refresh')
        refresh_btn.clicked.connect(self.populate_from_directory)

        dir_select_layout.addWidget(dir_select_label)
        dir_select_layout.addWidget(self.dir_select_line_edit)
        dir_select_layout.addWidget(dir_select_btn)
        dir_select_layout.addWidget(refresh_btn)

        self.file_tree_list = QtWidgets.QTreeWidget()
        self.file_tree_list.setHeaderHidden(True)
        self.file_tree_list.sortByColumn(0, QtCore.Qt.AscendingOrder)
        self.file_tree_list.setSortingEnabled(True)
        self.file_tree_list.setSelectionMode(QtWidgets.QTreeWidget.ExtendedSelection)
        self.file_tree_list.itemSelectionChanged.connect(self.select_section)
        self.file_tree_list.setMinimumSize(600, 250)

        footer_layout = QtWidgets.QHBoxLayout()
        make_btn = QtWidgets.QPushButton("Make Tx Textures")
        make_btn.clicked.connect(self.make_tx_textures)
        delete_btn = QtWidgets.QPushButton("Delete Tx")
        delete_btn.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        delete_btn.clicked.connect(self.delete_tx_files)
        footer_layout.addWidget(make_btn)
        footer_layout.addWidget(delete_btn)

        layout.addLayout(dir_select_layout)
        layout.addWidget(self.file_tree_list)
        layout.addLayout(footer_layout)

    def select_section(self):
        for item in self.file_tree_list.selectedItems():
            if item.parent() is not None:
                item.setSelected(False)

    def get_directory(self):
        file_dialog = QtWidgets.QFileDialog()
        if not self.current_directory:
            if os.getenv("PROJECT"):
                self.current_directory = f"O:/projects/{os.getenv('PROJECT')}"
        file_dir = file_dialog.getExistingDirectory(parent=self,
                                                    caption="Choose a Directory to Search for Textures",
                                                    directory=self.current_directory)
        if not os.path.exists(file_dir):
            return
        self.current_directory = file_dir
        self.dir_select_line_edit.setText(file_dir)
        self.populate_from_directory()

    def updated_directory(self):
        self.current_directory = self.dir_select_line_edit.text()
        self.populate_from_directory()

    def populate_from_directory(self):
        self.file_tree_list.clear()
        check_icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DialogApplyButton)
        x_icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_BrowserStop)
        bold_font = QtGui.QFont()
        bold_font.setBold(True)
        if not os.path.exists(self.current_directory):
            return
        file_list = os.listdir(self.current_directory)
        tx_list = []
        filtered_file_list = []
        for filename in file_list:
            if os.path.splitext(filename)[1] == '.tx':
                tx_list.append(filename)
                continue
            filtered_file_list.append(filename)
        for filename in filtered_file_list:
            for extension in EXTENSIONS:
                if filename.endswith(extension):
                    parent_item = QtWidgets.QTreeWidgetItem(self.file_tree_list)
                    parent_item.setText(0, filename)
                    parent_item.setFont(0, bold_font)
                    parent_item.setIcon(0, check_icon)
                    parent_item.setData(0, QtCore.Qt.UserRole, os.path.join(self.current_directory, filename))
                    tx_file = f"{os.path.splitext(filename)[0]}.tx"
                    if tx_file not in tx_list:
                        parent_item.setIcon(0, x_icon)
                        continue
                    item = QtWidgets.QTreeWidgetItem(parent_item)
                    item.setText(0, tx_file)
                    tx_list.remove(tx_file)
        for tx_file in tx_list:
            parent_item = QtWidgets.QTreeWidgetItem(self.file_tree_list)
            parent_item.setText(0, tx_file)
            parent_item.setFont(0, bold_font)
            parent_item.setIcon(0, check_icon)
            parent_item.setData(0, QtCore.Qt.UserRole, os.path.join(self.current_directory, tx_file))

    def delete_tx_files(self):
        reply = QtWidgets.QMessageBox.question(self,
                                                     "Are you sure?",
                                                     "Do you really want to delete these .tx files?",
                                                     QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
                                                     QtWidgets.QMessageBox.Cancel)
        if reply == QtWidgets.QMessageBox.Ok:
            for item in self.file_tree_list.selectedItems():
                file_path = item.data(0, QtCore.Qt.UserRole)
                full_path = os.path.join(self.current_directory, file_path)
                if os.path.splitext(full_path)[1] == ".tx":
                    continue
                tx_path = f"{os.path.splitext(full_path)[0]}.tx"
                if os.path.exists(tx_path):
                    os.remove(tx_path)
        self.populate_from_directory()

    def make_tx_textures(self):
        texture_list = []
        for item in self.file_tree_list.selectedItems():
            file_path = item.data(0, QtCore.Qt.UserRole)
            texture_list.append(file_path)
        create_window = tx_create_view.TxCreate(texture_list, result_message=True, parent=self)
        create_window.exec_()
        self.populate_from_directory()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = TxManager()
    window.show()
    app.exec_()