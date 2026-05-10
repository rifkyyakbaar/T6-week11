"""
Nama  : RIFKY AKBAR UTOMO PUTRA
NIM   : F1D02310149
Kelas : D
"""

import sys
import requests
import os
from PySide6.QtCore import Qt, QRunnable, Slot, QObject, Signal, QThreadPool
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

BASE_URL = "https://api.pahrul.my.id/api/posts"
REQUEST_TIMEOUT = 10


class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(object)
    result = Signal(object)


class RequestWorker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:
            self.signals.error.emit(exc)
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


class PostManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Post Manager")
        self.resize(1000, 650)
        self.thread_pool = QThreadPool()
        self.selected_post_id = None

        self._build_ui()
        self._connect_signals()
        self.load_posts()

    def _build_ui(self):
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Title", "Author", "Status"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        self.refresh_button = QPushButton("Refresh")
        self.add_button = QPushButton("Add Post")
        self.update_button = QPushButton("Update Post")
        self.delete_button = QPushButton("Delete Post")
        self.update_button.setEnabled(False)
        self.delete_button.setEnabled(False)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.table)
        left_layout.addWidget(self.refresh_button)
        left_layout.addWidget(self.add_button)
        left_layout.addWidget(self.update_button)
        left_layout.addWidget(self.delete_button)

        form_group = QGroupBox("Post Form")
        form_layout = QFormLayout()

        self.title_edit = QLineEdit()
        self.body_edit = QPlainTextEdit()
        self.author_edit = QLineEdit()
        self.slug_edit = QLineEdit()
        self.status_combo = QComboBox()
        self.status_combo.addItems(["published", "draft"])

        form_layout.addRow("Title:", self.title_edit)
        form_layout.addRow("Body:", self.body_edit)
        form_layout.addRow("Author:", self.author_edit)
        form_layout.addRow("Slug:", self.slug_edit)
        form_layout.addRow("Status:", self.status_combo)

        form_group.setLayout(form_layout)

        detail_group = QGroupBox("Detail Post / Comments")
        detail_layout = QVBoxLayout()
        self.comments_text = QPlainTextEdit()
        self.comments_text.setReadOnly(True)
        detail_layout.addWidget(self.comments_text)
        detail_group.setLayout(detail_layout)

        right_layout = QVBoxLayout()
        right_layout.addWidget(form_group)
        right_layout.addWidget(detail_group)
        right_layout.addStretch()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: white;")

        main_layout = QHBoxLayout()
        main_layout.addLayout(left_layout, 2)
        main_layout.addLayout(right_layout, 3)

        container = QWidget()
        outer_layout = QVBoxLayout(container)
        outer_layout.addLayout(main_layout)
        outer_layout.addWidget(self.status_label)

        self.setCentralWidget(container)

    def _connect_signals(self):
        self.refresh_button.clicked.connect(self.load_posts)
        self.add_button.clicked.connect(self.create_post)
        self.update_button.clicked.connect(self.update_post)
        self.delete_button.clicked.connect(self.delete_post)
        self.table.itemSelectionChanged.connect(self.on_row_selected)

    def set_status(self, message, error=False):
        self.status_label.setText(message)
        self.status_label.setStyleSheet(
            "color: red;" if error else "color: white;"
        )

    def set_busy(self, busy=True):
        self.refresh_button.setEnabled(not busy)
        self.add_button.setEnabled(not busy)
        self.update_button.setEnabled(not busy and self.selected_post_id is not None)
        self.delete_button.setEnabled(not busy and self.selected_post_id is not None)
        if busy:
            self.set_status("Loading... please wait")

    def _on_worker_finished(self):
        self.set_busy(False)

    def run_in_thread(self, fn, callback, *args, **kwargs):
        worker = RequestWorker(fn, *args, **kwargs)
        worker.signals.result.connect(callback)
        worker.signals.error.connect(self.handle_error)
        worker.signals.finished.connect(self._on_worker_finished)
        self.set_busy(True)
        self.thread_pool.start(worker)

    def handle_error(self, exc):
        message = "Request failed"
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            status_code = exc.response.status_code
            try:
                data = exc.response.json()
                message = data.get("message") or data.get("errors") or str(data)
            except Exception:
                message = exc.response.text or str(exc)
            if status_code == 422:
                message = f"Validation error: {message}"
            else:
                message = f"HTTP {status_code}: {message}"
        elif isinstance(exc, requests.Timeout):
            message = "Timeout: server did not respond"
        elif isinstance(exc, requests.ConnectionError):
            message = "Connection error: unable to reach API"
        else:
            message = str(exc)

        self.set_status(message, error=True)

    def load_posts(self):
        self.run_in_thread(self.api_get_posts, self.on_posts_loaded)

    def on_posts_loaded(self, posts):
        self.table.setRowCount(0)
        
        posts = posts.get("data", posts) if isinstance(posts, dict) else posts

        for post in posts:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(post.get("id") or "")))
            self.table.setItem(row, 1, QTableWidgetItem(str(post.get("title") or "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(post.get("author") or "")))
            self.table.setItem(row, 3, QTableWidgetItem(str(post.get("status") or "")))
            
        self.set_status(f"Loaded {len(posts)} posts")
        self.selected_post_id = None
        self.update_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.comments_text.clear()

    def on_row_selected(self):
        selection = self.table.selectedItems()
        if not selection:
            self.selected_post_id = None
            self.update_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            return

        row = selection[0].row()
        post_id_item = self.table.item(row, 0)
        if not post_id_item:
            return

        try:
            post_id = int(post_id_item.text())
        except ValueError:
            return

        self.selected_post_id = post_id
        self.update_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.run_in_thread(self.api_get_post, self.on_post_detail_loaded, post_id)

    def on_post_detail_loaded(self, data):
        data = data.get("data", data) if isinstance(data, dict) else data

        self.title_edit.setText(str(data.get("title") or ""))
        self.body_edit.setPlainText(str(data.get("body") or ""))
        self.author_edit.setText(str(data.get("author") or ""))
        self.slug_edit.setText(str(data.get("slug") or ""))
        self.status_combo.setCurrentText(str(data.get("status") or "published"))
        
        comments = data.get("comments", [])
        if comments:
            text = "\n\n".join(
                f"{idx+1}. {str(comment.get('name') or '')} ({str(comment.get('email') or '')})\n{str(comment.get('body') or '')}"
                for idx, comment in enumerate(comments)
            )
        else:
            text = "No comments available."
            
        self.comments_text.setPlainText(text)
        self.set_status(f"Loaded details for post {data.get('id')}")

    def create_post(self):
        data = self.collect_form_data()
        if not data:
            return
            
        confirm = QMessageBox.question(
            self,
            "Confirm Add",
            "Are you sure you want to add this new post?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        self.run_in_thread(self.api_create_post, self.on_post_created, data)

    def on_post_created(self, result):
        returned_id = result.get("id")
        self.set_status(f"Post created with ID {returned_id}")
        self.load_posts()

    def update_post(self):
        if self.selected_post_id is None:
            self.set_status("Select a post to update", error=True)
            return
        data = self.collect_form_data()
        if not data:
            return
            
        confirm = QMessageBox.question(
            self,
            "Confirm Update",
            "Are you sure you want to update this post?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        self.run_in_thread(
            self.api_update_post, self.on_post_updated, self.selected_post_id, data
        )

    def on_post_updated(self, result):
        self.set_status("Post updated successfully")
        self.load_posts()

    def delete_post(self):
        if self.selected_post_id is None:
            self.set_status("Select a post to delete", error=True)
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete the selected post?\nThis will also delete comments.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.run_in_thread(
            self.api_delete_post, self.on_post_deleted, self.selected_post_id
        )

    def on_post_deleted(self, result):
        self.set_status("Post deleted successfully")
        self.load_posts()

    def collect_form_data(self):
        title = self.title_edit.text().strip()
        body = self.body_edit.toPlainText().strip()
        author = self.author_edit.text().strip()
        slug = self.slug_edit.text().strip()
        status = self.status_combo.currentText().strip()

        if not title or not body or not author or not slug or not status:
            self.set_status("All form fields are required", error=True)
            return None

        return {"title": title, "body": body, "author": author, "slug": slug, "status": status}

    def api_get_posts(self):
        response = requests.get(BASE_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def api_get_post(self, post_id):
        url = f"{BASE_URL}/{post_id}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def api_create_post(self, data):
        response = requests.post(BASE_URL, json=data, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def api_update_post(self, post_id, data):
        url = f"{BASE_URL}/{post_id}"
        response = requests.put(url, json=data, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def api_delete_post(self, post_id):
        url = f"{BASE_URL}/{post_id}"
        response = requests.delete(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return {"deleted": True}

def main():
    app = QApplication(sys.argv)

    qss_file_name = "style.qss" 
    if os.path.exists(qss_file_name):
        try:
            with open(qss_file_name, "r") as f:
                style = f.read()
                app.setStyleSheet(style) 
                print(f"Style '{qss_file_name}' loaded successfully.")
        except Exception as e:
            print(f"Error loading style: {e}")
    else:
        print(f"style.qss not found in the same directory.")

    window = PostManagerWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()