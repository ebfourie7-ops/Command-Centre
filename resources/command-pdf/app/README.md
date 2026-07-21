# Command PDF 1.1.0

A local CommandOS desktop app for reading, converting, editing, and visibly signing PDF documents. PDFs can be opened from the file picker, command line, application menu, or by dragging them onto the window. Conversion includes PDF to DOCX, PDF pages to PNG, office documents and images to PDF, text extraction, and PDF merging.

The document viewer supports touchpad vertical and horizontal scrolling, pinch zoom, Ctrl-scroll zoom, and Shift-scroll horizontal navigation.

## Install

Install or update from **Command Centre → Command Apps**, or use the SourceForge
CommandOS repository:

```bash
sudo pacman -S command-pdf
```

## Development setup

Run `./setup.sh` once, then launch with `./start.sh` or the Command PDF application-menu entry.

Edits and visible signatures are written to a new PDF by default. Visible signatures are image stamps and are not certificate-based cryptographic signatures.
