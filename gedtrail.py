import sys
import os
import platform

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QFrame, QScrollArea, QFileDialog, 
                            QMessageBox, QSizePolicy, QGridLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData, QPoint
from PyQt5.QtGui import QPixmap, QIcon, QCursor, QDrag, QPainter


class ThumbnailWidget(QWidget):
    removeRequested = pyqtSignal(int)
    clicked = pyqtSignal(int)
    rearrangeRequested = pyqtSignal(int, int)  # source_index, target_index

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.dragStartPosition = None
        self.setFixedSize(150, 180)
        self.setAcceptDrops(True)
        
        # Styles
        self.normal_style = "background: transparent;"
        self.hover_style = "background: #f0f0f0; border: 1px dashed #aaa;"
        self.drag_over_style = "background: #e0e0ff; border: 2px dashed #666;"
        self.setStyleSheet(self.normal_style)
        
        # Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Image container
        self.image_container = QWidget()
        self.image_container.setFixedSize(150, 150)
        self.image_container.setStyleSheet("background: transparent;")
        
        # Image label
        self.image_label = QLabel(self.image_container)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setGeometry(0, 0, 150, 150)
        
        # Close button
        self.close_button = QPushButton("✕", self.image_container)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 0, 0, 150);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 200);
            }
        """)
        self.close_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.close_button.move(125, 5)
        self.close_button.hide()
        self.close_button.clicked.connect(self.on_remove_clicked)
        
        self.layout.addWidget(self.image_container)
        
        # Page number label
        self.page_label = QLabel(f"Page {index+1}")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet("font-weight: bold;")
        self.layout.addWidget(self.page_label)

    def on_remove_clicked(self):
        """Handle click on the remove button"""
        self.removeRequested.emit(self.index)

    def enterEvent(self, event):
        if self.image_label.pixmap() and not self.image_label.pixmap().isNull():
            self.close_button.show()
            self.setStyleSheet(self.hover_style)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.close_button.hide()
        self.setStyleSheet(self.normal_style)
        super().leaveEvent(event)
        
    def set_image(self, pixmap):
        if pixmap.isNull():
            self.image_label.clear()
        else:
            self.image_label.setPixmap(pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.image_label.pixmap() and not self.image_label.pixmap().isNull():
            if self.close_button.geometry().contains(event.pos()):
                return
            self.dragStartPosition = event.pos()
            self.clicked.emit(self.index)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self.dragStartPosition is None:
            return
            
        if (event.pos() - self.dragStartPosition).manhattanLength() < QApplication.startDragDistance():
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData("application/x-thumbnail", str(self.index).encode())
        drag.setMimeData(mime_data)
        
        drag_pixmap = QPixmap(self.size())
        drag_pixmap.fill(Qt.transparent)
        painter = QPainter(drag_pixmap)
        painter.setOpacity(0.7)
        self.render(painter)
        painter.end()
        
        drag.setPixmap(drag_pixmap)
        drag.setHotSpot(event.pos() - self.rect().topLeft())
        
        self.setStyleSheet("background: #f8f8f8; border: 1px dashed #888;")
        
        if drag.exec_(Qt.MoveAction) == Qt.MoveAction:
            self.setStyleSheet(self.normal_style)
        self.dragStartPosition = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-thumbnail"):
            event.acceptProposedAction()
            self.setStyleSheet(self.drag_over_style)

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.normal_style)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-thumbnail"):
            event.setDropAction(Qt.MoveAction)
            source_index = int(event.mimeData().data("application/x-thumbnail").data().decode())
            target_index = self.index
            
            if source_index != target_index:
                drop_pos = event.pos()
                center = self.rect().center()
                
                if drop_pos.x() < center.x():
                    self.rearrangeRequested.emit(source_index, target_index)
                else:
                    self.rearrangeRequested.emit(source_index, target_index + 1)
            
            self.setStyleSheet(self.normal_style)
            event.accept()

class ScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GED SaaS - Document Scanner")
        self.setGeometry(100, 100, 1000, 800)
        
        # Initialize scanner
        self.scanner = None
        self.scanned_images = []
        self.thumbnails = []  # Will store created thumbnail widgets
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Preview area
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet("background: white; border: 1px solid #ddd;")
        self.preview_layout = QVBoxLayout(self.preview_frame)
        self.preview_label = QLabel("Preview will appear here")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("font-size: 16px; color: #888;")
        self.preview_layout.addWidget(self.preview_label)
        layout.addWidget(self.preview_frame, 1)
        
        # Title label
        title = QLabel("Scanned Document Preview")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                padding: 10px; 
                qproperty-alignment: 'AlignCenter';
            }
        """)
        layout.addWidget(title)
        # Thumbnail area with scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("background-color: #f9f9f9; border: none;")

        self.thumbnail_container = QWidget()
        self.thumbnail_layout = QHBoxLayout(self.thumbnail_container)
        self.thumbnail_layout.setSizeConstraint(QHBoxLayout.SetMinAndMaxSize)
        self.thumbnail_layout.setSpacing(15)
        self.thumbnail_layout.setContentsMargins(15, 15, 15, 15)
        self.thumbnail_container.setMinimumHeight(150)
        
        self.scroll_area.setWidget(self.thumbnail_container)
        layout.addWidget(self.preview_frame, 1)  # Preview area (keep existing)
        layout.addWidget(title)                 # Title (keep existing)
        layout.addWidget(self.scroll_area, 1)   # Thumbnail area - increased space
        
        # Button area
        button_area = QWidget()
        button_layout = QHBoxLayout(button_area)
        button_layout.setSpacing(20)
        
        # Upload button
        self.upload_btn = QPushButton("Upload")
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px 28px;
                font-size: 16px;
                border-radius: 4px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.upload_btn.clicked.connect(self.upload_document)
        button_layout.addWidget(self.upload_btn)
        
        # Scan button
        self.scan_btn = QPushButton("Scan")
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #008CBA;
                color: white;
                border: none;
                padding: 12px 28px;
                font-size: 16px;
                border-radius: 4px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #007B9E;
            }
            QPushButton:pressed {
                background-color: #006688;
            }
        """)
        self.scan_btn.clicked.connect(self.scan_document)
        button_layout.addWidget(self.scan_btn)
        
        layout.addWidget(button_area)
        
        # Status bar
        self.statusBar().showMessage("Ready to scan or upload documents")
     

    def add_thumbnail(self, pixmap):
        """Add a new thumbnail widget for an image"""
        index = len(self.thumbnails)
        thumbnail = ThumbnailWidget(index, self.thumbnail_container)
        thumbnail.set_image(pixmap)
        thumbnail.removeRequested.connect(self.remove_image)
        thumbnail.clicked.connect(self.show_preview)
        thumbnail.rearrangeRequested.connect(self.rearrange_thumbnails)
        
        self.thumbnails.append(thumbnail)
        self.thumbnail_layout.addWidget(thumbnail)
        
        if index == 0:
            self.show_preview(0)

    def rearrange_thumbnails(self, source_index, target_index):
        """Handle thumbnail reordering after drag and drop"""
        # Ensure target_index is within bounds
        target_index = max(0, min(target_index, len(self.thumbnails) - 1))
        
        if source_index == target_index:
            return
            
        widget = self.thumbnails.pop(source_index)
        self.thumbnail_layout.removeWidget(widget)
        
        
        self.thumbnails.insert(target_index, widget)
        self.thumbnail_layout.insertWidget(target_index, widget)
        
        # Update all indices
        for i, thumb in enumerate(self.thumbnails):
            thumb.index = i
            thumb.page_label.setText(f"Page {i+1}")
        
        # Update preview if showing moved image
        if hasattr(self, 'current_preview') and self.current_preview.isVisible():
            current_pixmap = self.current_preview.pixmap()
            thumbnail_pixmap = widget.image_label.pixmap()
            if current_pixmap and thumbnail_pixmap and current_pixmap.cacheKey() == thumbnail_pixmap.cacheKey():
                self.show_preview(target_index)
        
        self.update_status(f"Moved page {source_index+1} to position {target_index+1}")

    def show_preview(self, index):  
        """Show the preview in the main area"""
        if 0 <= index < len(self.thumbnails):
            thumbnail = self.thumbnails[index]
            if thumbnail.image_label.pixmap() and not thumbnail.image_label.pixmap().isNull():
                self.preview_label.hide()
                if not hasattr(self, 'current_preview'):
                    self.current_preview = QLabel(self.preview_frame)
                    self.current_preview.setAlignment(Qt.AlignCenter)
                    self.preview_layout.addWidget(self.current_preview)
                
                preview_pixmap = thumbnail.image_label.pixmap().scaled(
                    self.preview_frame.width()-40,
                    self.preview_frame.height()-40,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.current_preview.setPixmap(preview_pixmap)
                self.current_preview.show()
                
 
    def update_status(self, message):
        self.statusBar().showMessage(message)
        
    def upload_document(self):
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Document(s)", "", 
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff);;All Files (*)", 
            options=options)
            
        if files:
            for file in files:
                pixmap = QPixmap(file)
                if not pixmap.isNull():
                    self.add_thumbnail(pixmap)
            self.update_status(f"Uploaded {len(files)} document(s)")
            
    import platform

    def scan_document(self):
        try:
            if platform.system() == 'Linux':
                import sane
                sane.init()
                devices = sane.get_devices()
                if not devices:
                    raise Exception("No scanner devices found.")
                scanner = sane.open(devices[0][0])
                scanner.start()
                im = scanner.snap()
                # Convert to QPixmap and add
                pixmap = QPixmap.fromImage(ImageQt.ImageQt(im))
                self.add_thumbnail(pixmap)
                scanner.close()
                sane.exit()

            elif platform.system() == 'Windows':
                try:
                    from twain import SourceManager
                    
                    # Initialize TWAIN
                    sm = SourceManager(0)
                    scanners = sm.source_list
                    if not scanners:
                        raise Exception("No TWAIN-compatible scanners found.\n"
                                    "1. Check scanner is powered on\n"
                                    "2. Install manufacturer's TWAIN driver\n"
                                    "3. Try a different USB port")

                    # For multiple scanners, let user select
                    if len(scanners) > 1:
                        scanner_idx = self._show_scanner_dialog(scanners)  # Implement this
                    else:
                        scanner_idx = 0

                    scanner = sm.open_source(scanner_idx)
                    scanner.request_acquire(0, True)
                    
                    # Set scan parameters (optional)
                    try:
                        scanner.set_capability(
                            twain.ICAP_XRESOLUTION, 
                            twain.TWTY_FIX32, 
                            300  # 300 DPI
                        )
                    except:
                        pass  # Skip if scanner doesn't support this

                    image = scanner.xfer_image_native()
                    if image:
                        temp_file = "scan_temp.jpg"
                        image.save(temp_file)
                        pixmap = QPixmap(temp_file)
                        if not pixmap.isNull():
                            self.add_thumbnail(pixmap)
                        else:
                            raise Exception("Failed to load scanned image")
                    else:
                        raise Exception("Scanning was cancelled or failed")
                        
                except Exception as e:
                    QMessageBox.critical(
                        self, 
                        "Scan Error", 
                        f"TWAIN Error:\n{str(e)}\n\n"
                        "Troubleshooting:\n"
                        "1. Reinstall scanner drivers\n"
                        "2. Try another USB port\n"
                        "3. Check manufacturer's website for TWAIN updates"
                    )
                finally:
                    if 'scanner' in locals():
                        scanner.destroy()
                    if 'sm' in locals():
                        sm.destroy()

            else:
                QMessageBox.critical(self, "Unsupported OS", "Scanning is only supported on Windows and Linux.")

        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"An error occurred during scanning:\n{e}")

            
    def remove_image(self, index):
        if 0 <= index < len(self.thumbnails):
            # Clear the preview if it's showing this image
            if (hasattr(self, 'current_preview')) and self.current_preview.isVisible():
                current_pixmap = self.current_preview.pixmap()
                thumbnail_pixmap = self.thumbnails[index].image_label.pixmap()
                if current_pixmap and thumbnail_pixmap and current_pixmap.cacheKey() == thumbnail_pixmap.cacheKey():
                    self.current_preview.hide()
                    self.preview_label.show()
            
            # Remove the thumbnail widget
            thumbnail = self.thumbnails.pop(index)
            self.thumbnail_layout.removeWidget(thumbnail)
            thumbnail.setParent(None)
            thumbnail.deleteLater()
            
            # Update indices for remaining thumbnails
            for i, thumb in enumerate(self.thumbnails):
                thumb.index = i
                thumb.page_label.setText(f"Page {i+1}")
            
            # Remove temporary file if it exists
            temp_file = f"scan_temp_{index+1}.png"
            if temp_file in self.scanned_images and os.path.exists(temp_file):
                os.remove(temp_file)
                self.scanned_images.remove(temp_file)
            
            self.update_status(f"Removed document")
            
    def closeEvent(self, event):
        # Clean up temporary files when closing
        for img in self.scanned_images:
            if os.path.exists(img):
                os.remove(img)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern style
    window = ScannerApp()
    window.show()
    sys.exit(app.exec_())
