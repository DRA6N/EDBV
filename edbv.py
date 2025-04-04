import sys
import os
import json
import xml.etree.ElementTree as ET
import urllib.request
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QScrollBar, QPushButton, QLabel, QStatusBar, QMessageBox

VERSION = "1.0.1"
GITHUB_RELEASES_API = "RELEASES URL"
GITHUB_RELEASES_PAGE = "RELEASES URL"

class CustomScrollBar(QScrollBar):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)

        if orientation == Qt.Vertical:
            self.up_button = QPushButton("p", self)
            self.down_button = QPushButton("q", self)
        else:
            self.up_button = QPushButton("|", self)
            self.down_button = QPushButton("}", self)

        for btn in (self.up_button, self.down_button):
            btn.setStyleSheet("""
                QPushButton {
                    font-family: "Wingdings 3";
                    color: #2C0F07;
                    background-color: #F4A003;
                    border: none;
                    padding: 0;
                }
            """)
            btn.setFixedSize(16, 16)

        self.up_button.clicked.connect(self.decrease)
        self.down_button.clicked.connect(self.increase)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.orientation() == Qt.Vertical:
            self.up_button.move(0, 0)
            self.down_button.move(0, self.height() - 16)
        else:
            self.up_button.move(0, 0)
            self.down_button.move(self.width() - 16, 0)

    def increase(self):
        self.setValue(self.value() + self.singleStep())

    def decrease(self):
        self.setValue(self.value() - self.singleStep())


class BindingViewer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Elite Dangerous Bindings Viewer")
        self.setWindowIcon(QtGui.QIcon("images/icon.png"))
        self.setGeometry(100, 100, 1500, 600)

        main_layout = QtWidgets.QVBoxLayout()

        # Menu bar
        menu_bar = QtWidgets.QMenuBar()
        file_menu = menu_bar.addMenu("File")

        settings_menu = file_menu.addMenu("Settings")

        self.show_unbound_action = QtWidgets.QAction("Show Unbound", self)
        self.show_unbound_action.setCheckable(True)
        self.show_unbound_action.triggered.connect(self.toggle_unbound_highlight)
        settings_menu.addAction(self.show_unbound_action)

        self.keep_on_top_action = QtWidgets.QAction("Keep On Top", self)
        self.keep_on_top_action.setCheckable(True)
        self.keep_on_top_action.triggered.connect(self.toggle_keep_on_top)
        settings_menu.addAction(self.keep_on_top_action)

        settings_menu.addSeparator()

        set_dir_action = QtWidgets.QAction("Set Bindings Directory", self)
        set_dir_action.triggered.connect(self.set_bindings_directory)
        settings_menu.addAction(set_dir_action)

        file_menu.addSeparator()

        help_menu = menu_bar.addMenu("Help")

        how_to_use_action = QtWidgets.QAction("How to Use the App", self)
        how_to_use_action.triggered.connect(self.show_how_to_use)
        help_menu.addAction(how_to_use_action)

        about_action = QtWidgets.QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        close_action = QtWidgets.QAction("Close", self)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

        menu_bar.setStyleSheet("""
            QMenuBar::separator {
                background-color: #F4A003;
                height: 1px;
                margin: 4px 0;
            }
            QMenu::item:selected {
                background-color: #2C0F07;
                color: #F4A003;
            }
        """)

        self.current_file_label = QLabel("Current Binding File:")
        self.current_file_label.setStyleSheet("color: #F4A003; padding: 4px 8px;")
        self.binding_dropdown = QtWidgets.QComboBox()
        self.binding_dropdown.setStyleSheet("background-color: #111; color: #F4A003; border: 1px solid #F4A003;")
        self.binding_dropdown.currentIndexChanged.connect(self.load_selected_binding)

        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QHBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.current_file_label)
        right_layout.addWidget(self.binding_dropdown)
        right_widget.setLayout(right_layout)
        menu_bar.setCornerWidget(right_widget, Qt.TopRightCorner)

        main_layout.setMenuBar(menu_bar)

        search_layout = QtWidgets.QHBoxLayout()
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search for a binding (e.g., Landing Gear)...")
        self.search_bar.textChanged.connect(self.filter_table)

        clear_button = QtWidgets.QPushButton("Clear")
        clear_button.clicked.connect(self.clear_search)

        search_layout.addWidget(self.search_bar)
        search_layout.addWidget(clear_button)
        main_layout.addLayout(search_layout)

        self.table = QtWidgets.QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Area", "Category", "Action", "Primary", "Secondary"])
        main_layout.addWidget(self.table)

        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("color: #F4A003; background-color: #111; border-top: 1px solid #F4A003;")
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)
        self.all_bindings = []
        self.mappings = self.load_mappings()
        self.highlight_unbound = False

        self.table.setVerticalScrollBar(CustomScrollBar(Qt.Vertical))
        self.table.setHorizontalScrollBar(CustomScrollBar(Qt.Horizontal))

        self.last_dir_file = ".last_directory.edbv"
        self.bindings_files = []
        self.load_last_directory()

        self.setStyleSheet("""
        QWidget {
            background-color: black;
            color: #F4A003;
            font-family: Consolas, monospace;
        }
        QTableWidget::item:selected {
            background-color: #2C0F07;
            color: #F4A003;
        }
        QLineEdit {
            border: 2px solid #F4A003;
            background-color: #111;
            color: #F4A003;
            padding: 4px;
        }
        QPushButton {
            border: 2px solid #F4A003;
            background-color: #111;
            color: #F4A003;
            padding: 6px 12px;
        }
        QPushButton:hover {
            background-color: #222;
        }
        QTableWidget {
            gridline-color: #F4A003;
            background-color: #111;
            color: #F4A003;
        }
        QHeaderView::section {
            background-color: #111;
            color: #F4A003;
            border: 1px solid #F4A003;
            padding: 4px;
        }
        QTableCornerButton::section {
            background-color: #111;
            border: 1px solid #F4A003;
        }
        QStatusBar {
            background-color: #111;
            color: #F4A003;
        }
        QComboBox {
            background-color: #111;
            color: #F4A003;
            border: 1px solid #F4A003;
            min-width: 100px;
            padding: 2px 6px;
        }
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
            background: #F4A003;
            min-height: 20px;
            min-width: 20px;
            border: 1px solid black;
        }
        """)

        self.check_for_updates()

    def load_mappings(self):
        try:
            with open("mappings.edbv", "r") as f:
                mappings = json.load(f)
                return {entry["code"]: entry for entry in mappings}
        except Exception as e:
            print("Failed to load mappings.edbv:", e)
            return {}

    def check_for_updates(self):
        try:
            with urllib.request.urlopen(GITHUB_RELEASES_API) as response:
                data = json.loads(response.read())
                latest_version = data["tag_name"].lstrip("v")
                if latest_version != VERSION:
                    if QMessageBox.information(self, "Update Available",
                            f"A new version ({latest_version}) is available. You are using version {VERSION}.\n\nVisit the release page?",
                            QMessageBox.Ok | QMessageBox.Cancel) == QMessageBox.Ok:
                        QtGui.QDesktopServices.openUrl(QtCore.QUrl(GITHUB_RELEASES_PAGE))
        except Exception as e:
            print("Error checking for updates:", e)

    def toggle_keep_on_top(self):
        is_checked = self.keep_on_top_action.isChecked()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, is_checked)
        self.show()

    def set_bindings_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Key Bindings Folder")
        if directory:
            with open(self.last_dir_file, 'w') as f:
                json.dump({"last_directory": directory}, f)
            self.populate_dropdown(directory)
            self.status_bar.showMessage(f"Current Bindings Directory: {directory}")

    def load_last_directory(self):
        directory = ""
        if os.path.exists(self.last_dir_file):
            with open(self.last_dir_file, 'r') as f:
                data = json.load(f)
                directory = data.get("last_directory", "")

        if directory and os.path.exists(directory):
            self.populate_dropdown(directory)
            self.status_bar.showMessage(f"Current Bindings Directory: {directory}")

    def populate_dropdown(self, directory):
        self.binding_dropdown.blockSignals(True)
        self.binding_dropdown.clear()
        self.bindings_files = []
        for file in os.listdir(directory):
            if file.endswith(".xml") or file.endswith(".binds"):
                full_path = os.path.join(directory, file)
                self.bindings_files.append(full_path)
                self.binding_dropdown.addItem(os.path.splitext(file)[0])
        self.binding_dropdown.blockSignals(False)

        if self.bindings_files:
            self.binding_dropdown.setCurrentIndex(0)
            self.load_file(self.bindings_files[0])

    def load_selected_binding(self):
        index = self.binding_dropdown.currentIndex()
        if 0 <= index < len(self.bindings_files):
            self.load_file(self.bindings_files[index])

    def toggle_unbound_highlight(self):
        self.highlight_unbound = self.show_unbound_action.isChecked()
        self.populate_table(
            self.all_bindings if not self.search_bar.text()
            else self.filter_bindings(self.search_bar.text())
        )

    def filter_bindings(self, text):
        text = text.lower()
        return [b for b in self.all_bindings if
                text in self.mappings.get(b["Code"], {}).get("action", b["Code"]).lower() or
                text in self.mappings.get(b["Code"], {}).get("area", "").lower() or
                text in self.mappings.get(b["Code"], {}).get("category", "").lower()]

    def load_file(self, file_path):
        self.all_bindings = self.parse_bindings(file_path)
        self.populate_table(self.all_bindings)

    def parse_bindings(self, file_path):
        tree = ET.parse(file_path)
        root = tree.getroot()

        bindings = []
        for child in root:
            code = child.tag
            primary = child.find("Primary")
            secondary = child.find("Secondary")

            primary_str = f"{primary.attrib.get('Device', '{NoDevice}')} - {primary.attrib.get('Key', '')}" if primary is not None else "{NoDevice}"
            secondary_str = f"{secondary.attrib.get('Device', '{NoDevice}')} - {secondary.attrib.get('Key', '')}" if secondary is not None else "{NoDevice}"

            bindings.append({
                "Code": code,
                "Primary": primary_str,
                "Secondary": secondary_str
            })

        return bindings

    def populate_table(self, bindings):
        filtered_bindings = [b for b in bindings if self.mappings.get(b["Code"], {}).get("area") or self.mappings.get(b["Code"], {}).get("category")]
        self.table.setRowCount(len(filtered_bindings))

        for row, binding in enumerate(filtered_bindings):
            code = binding["Code"]
            mapping = self.mappings.get(code, {})

            area = mapping.get("area", "")
            category = mapping.get("category", "")
            action = mapping.get("action") or code

            primary = binding["Primary"]
            secondary = binding["Secondary"]

            items = [
                QtWidgets.QTableWidgetItem(area),
                QtWidgets.QTableWidgetItem(category),
                QtWidgets.QTableWidgetItem(action),
                QtWidgets.QTableWidgetItem(primary),
                QtWidgets.QTableWidgetItem(secondary),
            ]

            if self.highlight_unbound:
                if primary.startswith("{NoDevice}") and secondary.startswith("{NoDevice}"):
                    for item in items:
                        item.setBackground(QtGui.QColor("#2C0F07"))
                        item.setForeground(QtGui.QColor("#F4A003"))

            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

        self.table.resizeColumnsToContents()

    def filter_table(self, text):
        filtered = self.filter_bindings(text)
        self.populate_table(filtered)

    def clear_search(self):
        self.search_bar.clear()
        self.populate_table(self.all_bindings)

    def show_how_to_use(self):
        QMessageBox.information(self, "How to Use", "1. Set your bindings directory under File > Settings > Set Bindings Directory.\n"
                                "2. Use the dropdown to switch between different .binds files.\n"
                                "3. Use the search bar to filter by action, area, or category.\n"
                                "4. Enable 'Show Unbound' to highlight unbound commands.")

    def show_about(self): #If you compile this yourself, please give credit where credit is due.
        QMessageBox.about(self, "About", "Elite Dangerous Bindings Viewer\nVersion 1.0.0\n\nCreated by CMDR Aeldwulf\nJoin the Elite Dangerous Community Discord: \nhttps://discord.gg/elite")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    viewer = BindingViewer()
    viewer.show()
    sys.exit(app.exec_())
