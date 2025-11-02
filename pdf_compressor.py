"""
pdf_compressor.py

A module for drastically reducing PDF file size using PyMuPDF and (optionally)
Ghostscript or pikepdf.  See citations for details on each technique.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


@dataclass
class CompressionOptions:
    # JPEG quality for recompressing images (0–100).
    image_quality: int = 60
    # Only downsample images whose DPI exceeds this threshold.
    dpi_threshold: int = 100
    # Target DPI for downsampled images.
    dpi_target: int = 72
    # Convert images to grayscale before recompressing.
    to_grayscale: bool = False
    # Strip metadata, thumbnails and attachments.
    remove_metadata: bool = True
    # Subset fonts so only used glyphs are embedded.
    subset_fonts: bool = True
    # Remove all images completely (text and vector only).
    remove_images: bool = False
    # Flatten interactive form fields into static content.
    flatten_forms: bool = True
    # Delete annotations (comments, highlights, etc.).
    remove_annotations: bool = True
    # Run Ghostscript after PyMuPDF.
    use_ghostscript: bool = False
    # Ghostscript quality preset (/screen, /ebook, /printer, /prepress, /default).
    gs_quality: str = "ebook"
    # Use pikepdf to drop unreferenced resources.
    remove_unreferenced: bool = False


class PDFCompressor:
    """Encapsulates PDF compression workflow."""

    def __init__(self, input_path: str | Path, output_path: str | Path,
                 options: Optional[CompressionOptions] = None) -> None:
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.options = options or CompressionOptions()

    def compress(self) -> Path:
        """Execute the compression steps and return the path to the compressed PDF."""
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input PDF '{self.input_path}' does not exist.")

        # Step 1: optimize with PyMuPDF
        tmp_path = self._optimize_with_pymupdf()

        # Step 2: optionally remove unreferenced resources with pikepdf
        if self.options.remove_unreferenced:
            tmp_path = self._cleanup_with_pikepdf(tmp_path)

        # Step 3: optionally run Ghostscript
        if self.options.use_ghostscript:
            tmp_path = self._compress_with_ghostscript(tmp_path)

        # Move temp file to final output
        final_path = self.output_path
        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(tmp_path, final_path)
        return final_path

    def _optimize_with_pymupdf(self) -> Path:
        """Apply PyMuPDF optimizations and return a temporary file path."""
        doc = fitz.open(str(self.input_path))

        # Remove metadata, attachments and thumbnails.
        if self.options.remove_metadata:
            doc.scrub(
                metadata=True,
                xml_metadata=True,
                attached_files=True,
                embedded_files=True,
                thumbnails=True,
                reset_fields=True,
                reset_responses=True,
            )

        # Subset fonts
        if self.options.subset_fonts:
            try:
                doc.subset_fonts()
            except Exception:
                pass

        # Compress images
        if not self.options.remove_images:
            try:
                doc.rewrite_images(
                    dpi_threshold=self.options.dpi_threshold,
                    dpi_target=self.options.dpi_target,
                    quality=self.options.image_quality,
                    lossy=True,
                    lossless=False,
                    bitonal=True,
                    color=True,
                    gray=True,
                    set_to_gray=self.options.to_grayscale,
                )
            except Exception:
                pass

        # Remove images completely
        if self.options.remove_images:
            for page in doc:
                rect = page.rect
                page.add_redact_annot(rect)
                page.apply_redactions(
                    images=fitz.PDF_REDACT_IMAGE_REMOVE,
                    graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                    text=fitz.PDF_REDACT_TEXT_NONE,
                )

        # Flatten forms
        if self.options.flatten_forms:
            try:
                doc.flatten_forms()
            except Exception:
                pass

        # Remove annotations
        if self.options.remove_annotations:
            for page in doc:
                annot = page.first_annot
                while annot:
                    nxt = annot.next
                    page.delete_annot(annot)
                    annot = nxt

        # Save with garbage collection and stream compression
        temp_file = f"{self.output_path.with_suffix('')}_{os.getpid()}_pymupdf.pdf"
        doc.save(
            temp_file,
            garbage=3,       # deduplicate and remove unreferenced objects:contentReference[oaicite:11]{index=11}
            deflate=True,    # apply zlib compression to streams:contentReference[oaicite:12]{index=12}
            use_objstms=True # write objects into compressible streams:contentReference[oaicite:13]{index=13}
        )
        doc.close()
        return Path(temp_file)

    def _cleanup_with_pikepdf(self, input_pdf: Path) -> Path:
        """Use pikepdf to remove unreferenced resources."""
        try:
            import pikepdf
        except ImportError:
            raise RuntimeError("pikepdf is not installed (set remove_unreferenced=False or install pikepdf).")

        output_path = f"{self.output_path.with_suffix('')}_{os.getpid()}_pikepdf.pdf"
        with pikepdf.open(str(input_pdf)) as pdf:
            pdf.remove_unreferenced_resources()  # drop objects never referenced by page content:contentReference[oaicite:14]{index=14}
            pdf.save(str(output_path))
        os.remove(input_pdf)
        return Path(output_path)

    def _compress_with_ghostscript(self, input_pdf: Path) -> Path:
        """Run Ghostscript with a selected preset to compress the PDF further."""
        # Locate Ghostscript executable (gs on Unix, gswin64c/gswin32c on Windows)
        for candidate in ("gs", "gswin64c", "gswin64c.exe", "gswin32c.exe"):
            if shutil.which(candidate):
                gs_cmd = candidate
                break
        else:
            raise RuntimeError("Ghostscript not found; install it or set use_ghostscript=False.")

        quality = self.options.gs_quality.lower()
        presets = {"screen", "ebook", "printer", "prepress", "default"}
        if quality not in presets:
            raise ValueError(f"Invalid Ghostscript quality preset: {quality}")

        output_path = f"{self.output_path.with_suffix('')}_{os.getpid()}_gs_{quality}.pdf"
        args = [
            gs_cmd,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS=/{quality}",  # choose preset:contentReference[oaicite:15]{index=15}
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={output_path}",
            str(input_pdf),
        ]
        result = subprocess.run(args, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"Ghostscript failed: {result.stderr.decode(errors='ignore')}")
        os.remove(input_pdf)
        return Path(output_path)


def compress_pdf(input_path: str | Path,
                 output_path: str | Path,
                 **kwargs) -> Path:
    """
    Convenience function to compress a PDF.

    Parameters
    ----------
    input_path : str or Path
        Path of the input PDF.
    output_path : str or Path
        Where to write the compressed PDF.
    **kwargs
        Overrides for CompressionOptions (e.g., image_quality=50).

    Returns
    -------
    Path
        Path to the compressed PDF.
    """
    options = CompressionOptions(**kwargs)
    compressor = PDFCompressor(input_path, output_path, options)
    return compressor.compress()
