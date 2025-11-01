# pdf_compressor_gui.py
#
# Graphical interface for the PDF compressor.  Requires:
#   pip install pyside6
#
# Make sure pdf_compressor.py is in your PYTHONPATH so it can be imported.

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSpinBox, QWidget,
    QGridLayout
)

from pdf_compressor import compress_pdf  # import the function you previously wrote

class CompressorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Compressor")
        self._build_ui()

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QFormLayout()
        central.setLayout(layout)

        # Input PDF selection
        self.input_edit = QLineEdit()
        input_btn = QPushButton("Browse…")
        input_btn.clicked.connect(self._browse_input)
        input_container = QWidget()
        ilayout = QGridLayout()
        ilayout.setContentsMargins(0,0,0,0)
        ilayout.addWidget(self.input_edit, 0, 0)
        ilayout.addWidget(input_btn, 0, 1)
        input_container.setLayout(ilayout)
        layout.addRow(QLabel("Input PDF:"), input_container)

        # Output PDF selection
        self.output_edit = QLineEdit()
        output_btn = QPushButton("Browse…")
        output_btn.clicked.connect(self._browse_output)
        output_container = QWidget()
        olayout = QGridLayout()
        olayout.setContentsMargins(0,0,0,0)
        olayout.addWidget(self.output_edit, 0, 0)
        olayout.addWidget(output_btn, 0, 1)
        output_container.setLayout(olayout)
        layout.addRow(QLabel("Output PDF:"), output_container)

        # Image quality (0–100)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(0, 100)
        self.quality_spin.setValue(60)
        layout.addRow(QLabel("Image quality (0–100):"), self.quality_spin)

        # DPI threshold
        self.dpi_threshold_spin = QSpinBox()
        self.dpi_threshold_spin.setRange(0, 1200)
        self.dpi_threshold_spin.setValue(100)
        layout.addRow(QLabel("DPI threshold:"), self.dpi_threshold_spin)

        # Target DPI
        self.dpi_target_spin = QSpinBox()
        self.dpi_target_spin.setRange(0, 1200)
        self.dpi_target_spin.setValue(72)
        layout.addRow(QLabel("Target DPI:"), self.dpi_target_spin)

        # Grayscale option
        self.grayscale_check = QCheckBox("Convert images to grayscale")
        layout.addRow(self.grayscale_check)

        # Strip metadata/attachments
        self.remove_metadata_check = QCheckBox("Strip metadata, attachments and thumbnails")
        self.remove_metadata_check.setChecked(True)
        layout.addRow(self.remove_metadata_check)

        # Subset fonts
        self.subset_fonts_check = QCheckBox("Subset fonts")
        self.subset_fonts_check.setChecked(True)
        layout.addRow(self.subset_fonts_check)

        # Remove images
        self.remove_images_check = QCheckBox("Remove all images")
        layout.addRow(self.remove_images_check)

        # Flatten forms
        self.flatten_forms_check = QCheckBox("Flatten form fields")
        self.flatten_forms_check.setChecked(True)
        layout.addRow(self.flatten_forms_check)

        # Remove annotations (leave unchecked by default so Preview signatures are kept)
        self.remove_annotations_check = QCheckBox("Remove annotations (comments, highlights)")
        self.remove_annotations_check.setChecked(False)
        layout.addRow(self.remove_annotations_check)

        # Use Ghostscript checkbox
        self.use_gs_check = QCheckBox("Use Ghostscript for final compression")
        layout.addRow(self.use_gs_check)

        # Ghostscript preset
        self.gs_quality_combo = QComboBox()
        self.gs_quality_combo.addItems(["screen", "ebook", "printer", "prepress", "default"])
        self.gs_quality_combo.setCurrentText("ebook")
        layout.addRow(QLabel("Ghostscript preset:"), self.gs_quality_combo)

        # Remove unreferenced objects (needs pikepdf)
        self.remove_unreferenced_check = QCheckBox("Remove unreferenced objects (requires pikepdf)")
        layout.addRow(self.remove_unreferenced_check)

        # Compress button
        compress_btn = QPushButton("Compress")
        compress_btn.clicked.connect(self._run_compression)
        layout.addRow(compress_btn)

    def _browse_input(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select PDF to compress", str(Path.home()), "PDF files (*.pdf)"
        )
        if filename:
            self.input_edit.setText(filename)

    def _browse_output(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Select output PDF", str(Path.home()), "PDF files (*.pdf)"
        )
        if filename:
            if not filename.lower().endswith(".pdf"):
                filename += ".pdf"
            self.output_edit.setText(filename)

    def _run_compression(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        if not input_path or not output_path:
            QMessageBox.warning(self, "Missing information", "Please specify both input and output files.")
            return

        kwargs = {
            "image_quality": self.quality_spin.value(),
            "dpi_threshold": self.dpi_threshold_spin.value(),
            "dpi_target": self.dpi_target_spin.value(),
            "to_grayscale": self.grayscale_check.isChecked(),
            "remove_metadata": self.remove_metadata_check.isChecked(),
            "subset_fonts": self.subset_fonts_check.isChecked(),
            "remove_images": self.remove_images_check.isChecked(),
            "flatten_forms": self.flatten_forms_check.isChecked(),
            "remove_annotations": self.remove_annotations_check.isChecked(),
            "use_ghostscript": self.use_gs_check.isChecked(),
            "gs_quality": self.gs_quality_combo.currentText(),
            "remove_unreferenced": self.remove_unreferenced_check.isChecked(),
        }
        try:
            compress_pdf(input_path, output_path, **kwargs)
        except Exception as exc:
            QMessageBox.critical(self, "Compression failed", f"An error occurred:\n{exc}")
            return
        QMessageBox.information(self, "Done", f"File saved to:\n{output_path}")

def main() -> int:
    app = QApplication(sys.argv)
    window = CompressorWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())