import sys
import os
import sqlite3
import subprocess
import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QListView, QMessageBox,
    QApplication, QFileDialog, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QStyle, QMenu, QStyledItemDelegate, QAbstractItemView,
    QComboBox, QProgressBar, QDialog
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QVariant, QModelIndex, QUrl, QSize, QEvent, QRect, QRectF, QThread, pyqtSignal, QObject
from PyQt6.QtGui import (
    QDesktopServices, QIcon, QPixmap, QImage, QAction, QPainter, QColor, QPainterPath, QFontMetrics
)
from videoplayer import VideoPlayer

class Video:
    def __init__(self, title, duration, resolution, file_path, thumbnail: QPixmap | None = None):
        self.title = title
        self.duration = duration
        self.resolution = resolution
        self.file_path = file_path
        self.thumbnail = thumbnail


class VideoTableModel(QAbstractTableModel):
    def __init__(self, videos):
        super().__init__()
        self.videos = videos
        # Иконка ▶ для списка
        self.play_icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.videos)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1  # только название

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> QVariant:
        video = self.videos[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return video.title
        if role == Qt.ItemDataRole.DecorationRole and index.column() == 0:
            return self.play_icon
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> QVariant:
        return None  # скрываем заголовки


class VideoLibraryApp(QMainWindow):
    # ---------- Служебные методы ----------
    def _refresh_table(self, videos):
        """Совместимость: перенаправляем на обновление списка превью."""
        self._refresh_list(videos)

    def _refresh_list(self, videos):
        """Обновляет QListWidget превью."""
        self.list_widget.clear()
        self.displayed_videos = list(videos)
        for video in videos:
            pixmap = video.thumbnail or QPixmap()
            if pixmap.isNull():
                icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
            else:
                icon = QIcon(pixmap.scaled(160, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            item = QListWidgetItem(icon, f"{video.title}\n{video.duration}")
            item.setData(Qt.ItemDataRole.UserRole, video)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setSizeHint(QSize(160, 150))
            self.list_widget.addItem(item)
    def open_selected_video(self, item):
        """Открывает видеоплеер для выбранного видео из QListWidget."""
        video: Video | None = item.data(Qt.ItemDataRole.UserRole)
        if video is None:
            return
        player = VideoPlayer()
        player.setWindowTitle(video.title)
        player.setSource(QUrl.fromLocalFile(video.file_path))
        player.resize(900, 600)

        # Передача метаданных
        video_data = {
            "title": video.title,
            "duration": video.duration,
            "resolution": video.resolution,
            "file_path": video.file_path,
        }
        player.set_video_data(video_data)

        # Сохраняем ссылку, иначе окно закроется сразу после выхода из функции
        self.open_players.append(player)
        player.show()
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Видеотека")
        # применяем глобальный стиль
        self.apply_styles()
        self.video_library = []
        # Храним ссылки на открытые видеоплееры, чтобы они не уничтожались сборщиком
        self.open_players: list[VideoPlayer] = []

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # ---------- Новый макет ----------
        main_layout = QHBoxLayout()
        self.central_widget.setLayout(main_layout)

        # Левая панель с кнопками
        sidebar = QVBoxLayout()
        sidebar.setSpacing(12)  # разделение между кнопками
        main_layout.addLayout(sidebar, 0)

        # Правая панель с поиском и таблицей
        right_panel = QVBoxLayout()
        main_layout.addLayout(right_panel, 1)

        # Кнопки
        add_button = QPushButton("Добавить")
        add_button.setIcon(QIcon("icons/add.svg"))
        add_button.clicked.connect(self.add_video)
        delete_button = QPushButton("Удалить")
        delete_button.setIcon(QIcon("icons/delete.svg"))
        delete_button.clicked.connect(self.delete_selected_videos)

        convert_button = QPushButton("Конвертировать")
        convert_button.setIcon(QIcon("icons/reverse.svg"))
        convert_button.clicked.connect(self.convert_selected_video)

        # Выравниваем текст и иконки по левому краю
        for btn in (add_button, delete_button, convert_button):
            btn.setStyleSheet("text-align: left; padding-left: 8px;")

        sidebar.addWidget(add_button)
        sidebar.addWidget(delete_button)
        sidebar.addWidget(convert_button)
        sidebar.addStretch()

        # Поиск
        self.search_line_edit = QLineEdit()
        self.search_line_edit.setPlaceholderText("Поиск видео")
        self.search_line_edit.textChanged.connect(self.filter_videos)
        right_panel.addWidget(self.search_line_edit)

        # Список превью
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListView.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(160, 90))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListView.Movement.Static)
        self.list_widget.setSpacing(10)
        # Разрешаем множественное выделение (Ctrl, Shift, рамкой)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setMouseTracking(True)
        self.list_widget.itemDoubleClicked.connect(self.open_selected_video)
        # Контекстное меню ПКМ
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        # Снятие выделения по клику в пустой области
        self.list_widget.viewport().installEventFilter(self)
        # Кастомный делегат для рисования текста с разным стилем
        self.list_widget.setItemDelegate(VideoItemDelegate(self.list_widget))
        right_panel.addWidget(self.list_widget)

        # Отдельный список отображаемых видео (для фильтрации)
        self.displayed_videos: list[Video] = []

        # Поля ввода для метаданных больше не нужны в новом дизайне, но оставим их скрытыми для авто-заполнения
        self.line_edit_title = QLineEdit()
        self.line_edit_duration = QLineEdit()
        self.line_edit_resolution = QLineEdit()
        for w in (self.line_edit_title, self.line_edit_duration, self.line_edit_resolution):
            w.hide()

        self.create_database()
        self.load_videos_from_database()

    def create_widgets(self):
        label_title = QLabel("Название:")
        self.line_edit_title = QLineEdit()
        label_duration = QLabel("Продолжительность:")
        self.line_edit_duration = QLineEdit()
        label_resolution = QLabel("Разрешение:")
        self.line_edit_resolution = QLineEdit()

        add_button = QPushButton("Добавить")
        add_button.clicked.connect(self.add_video)

        delete_button = QPushButton("Удалить")
        delete_button.clicked.connect(self.delete_selected_video)

        search_label = QLabel("Поиск:")
        self.search_line_edit = QLineEdit()
        self.search_line_edit.textChanged.connect(self.filter_videos)

        self.layout.addWidget(label_title)
        self.layout.addWidget(self.line_edit_title)
        self.layout.addWidget(label_duration)
        self.layout.addWidget(self.line_edit_duration)
        self.layout.addWidget(label_resolution)
        self.layout.addWidget(self.line_edit_resolution)
        self.layout.addWidget(add_button)
        self.layout.addWidget(delete_button)
        self.layout.addWidget(search_label)
        self.layout.addWidget(self.search_line_edit)

        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_view.doubleClicked.connect(self.open_selected_video)

    def create_database(self):
        connection = sqlite3.connect("video_library.db")
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                duration TEXT,
                resolution TEXT,
                file_path TEXT
            )
        """)

        connection.commit()
        connection.close()

    def load_videos_from_database(self):
        connection = sqlite3.connect("video_library.db")
        cursor = connection.cursor()

        cursor.execute("SELECT title, duration, resolution, file_path FROM videos")
        rows = cursor.fetchall()

        for row in rows:
            title, duration, resolution, file_path = row
            thumbnail = self.get_video_thumbnail(file_path)
            video = Video(title, duration, resolution, file_path, thumbnail)
            self.video_library.append(video)

        self._refresh_table(self.video_library)

        connection.close()

    def add_video(self):
        """Открывает диалог выбора файлов и добавляет выбранные видео в коллекцию."""
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilters(["Видеофайлы (*.mp4 *.avi *.mkv *.flv *.ts *.mts)"])
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)

        if file_dialog.exec() == QFileDialog.DialogCode.Accepted:
            file_paths = file_dialog.selectedFiles()
            for file_path in file_paths:
                # Если пользователь заполнил поля – используем их, иначе определяем заголовок по имени файла
                title = self.line_edit_title.text() or os.path.splitext(os.path.basename(file_path))[0]
                # Метаданные
                metadata_duration, metadata_resolution = self.get_video_info(file_path)

                duration = self.line_edit_duration.text() or metadata_duration or "-"
                resolution = self.line_edit_resolution.text() or metadata_resolution or "-"

                thumbnail = self.get_video_thumbnail(file_path)
                video = Video(title, duration, resolution, file_path, thumbnail)
                self.video_library.append(video)
                self.save_video_to_database(video)

            # Обновляем список
            self._refresh_table(self.video_library)

        # Очищаем поля ввода
        self.line_edit_title.clear()
        self.line_edit_duration.clear()
        self.line_edit_resolution.clear()

    def save_video_to_database(self, video):
        connection = sqlite3.connect("video_library.db")
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO videos (title, duration, resolution, file_path)
            VALUES (?, ?, ?, ?)
        """, (video.title, video.duration, video.resolution, video.file_path))

        connection.commit()
        connection.close()

    def delete_selected_videos(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
        videos = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items if item.data(Qt.ItemDataRole.UserRole)]
        if not videos:
            return

        # Подтверждение с количеством
        count = len(videos)
        names_preview = ", ".join(v.title for v in videos[:3])
        if count > 3:
            names_preview += " …"
        msg = f"Вы уверены, что хотите удалить выбранные {count} видео?\n{names_preview}"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Удалить видео")
        box.setText(msg)
        yes_btn = box.addButton("Да", QMessageBox.ButtonRole.YesRole)
        no_btn = box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_btn)
        box.exec()

        if box.clickedButton() == yes_btn:
            for video in videos:
                if video in self.video_library:
                    self.video_library.remove(video)
                self.delete_video_from_database(video)
            self._refresh_table(self.video_library)

    def convert_selected_video(self):
        selected_items = self.list_widget.selectedItems()
        if len(selected_items) == 1:
            video: Video | None = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if video:
                self.convert_video(video)
        else:
            QMessageBox.information(self, "Конвертировать", "Выберите одно видео для конвертации.")

    # ---- Event filter для очистки выделения ----
    def eventFilter(self, obj, event):
        if obj is self.list_widget.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            index = self.list_widget.indexAt(event.pos())
            if not index.isValid():
                self.list_widget.clearSelection()
        return super().eventFilter(obj, event)

    def delete_video_from_database(self, video):
        connection = sqlite3.connect("video_library.db")
        cursor = connection.cursor()

        cursor.execute("DELETE FROM videos WHERE file_path = ?", (video.file_path,))

        connection.commit()
        connection.close()

    def filter_videos(self):
        search_text = self.search_line_edit.text().lower()
        filtered_videos = [v for v in self.video_library if search_text in v.title.lower()]
        self._refresh_table(filtered_videos)

    # Переименовали дублирующий метод, чтобы не перекрывать основной open_selected_video
    def open_video_with_os(self, index):
        video = self.video_library[index.row()]
        QDesktopServices.openUrl(QUrl.fromLocalFile(video.file_path))

    def apply_styles(self):
        """Применяет современную цветовую схему к виджетам приложения."""
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', sans-serif;
                font-size: 12pt;
                background-color: #1a1a1a;
                color: #f0f0f0;
            }

            /* Кнопки */
            QPushButton {
                background-color: #3d3d3d;
                border: 2px solid #5a5a5a;
                border-radius: 6px;
                padding: 6px 12px;
            }

            QPushButton:hover {
                background-color: #5c5c5c;
            }

            /* Поле поиска */
            QLineEdit {
                background: #3d3d3d;
                border: 2px solid #5a5a5a;
                border-radius: 6px;
                padding: 6px;
                color: #f0f0f0;
            }

            /* Таблица как список */
            QListWidget {
                background: #1a1a1a;
                outline: none;
            }

            QListWidget::item {
                border-radius: 6px;
            }

            QListWidget::item:hover {
                background: #333333;
                border-radius: 6px;
            }

            QListWidget::item:selected {
                background: #505050;
                border-radius: 6px;
            }

            /* Контекстное меню */
            QMenu {
                background-color: #1a1a1a;
                color: #f0f0f0;
            }

            QMenu::item {
                padding: 6px 24px 6px 24px;
            }

            QMenu::item:selected {
                background-color: #404040;
            }
        """)

    # ---------- Метаданные видео ----------
    @staticmethod
    def get_video_info(file_path: str) -> tuple[str | None, str | None]:
        """Возвращает (длительность «MM:SS», разрешение «ШxВ») или (None, None) при ошибке.
        Использует OpenCV, без зависимости от ffmpeg/ffprobe."""
        try:
            import cv2  # pylint: disable=import-error

            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return None, None

            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            duration_sec = frame_count / fps if fps else None

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()

            duration_str = None
            if duration_sec is not None:
                m, s = divmod(int(duration_sec + 0.5), 60)
                h, m = divmod(m, 60)
                duration_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

            resolution_str = f"{width}x{height}" if width and height else None
            return duration_str, resolution_str
        except Exception:
            return None, None

    @staticmethod
    def get_video_thumbnail(file_path: str, seek_sec: float = 1.0) -> QPixmap | None:
        """Возвращает QPixmap с кадром-превью (через OpenCV) или None при ошибке."""
        try:
            import cv2  # pylint: disable=import-error

            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return None

            # Переходим к нужному времени, если возможно
            cap.set(cv2.CAP_PROP_POS_MSEC, seek_sec * 1000)
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return None

            # OpenCV возвращает BGR; преобразуем в RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(image)
            return pixmap
        except Exception:
            return None

    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if item is None:
            return
        video: Video | None = item.data(Qt.ItemDataRole.UserRole)
        if video is None:
            return

        menu = QMenu(self)
        selected_items = self.list_widget.selectedItems()

        single_selection = len(selected_items) == 1

        if single_selection:
            action_convert = QAction("Конвертировать", self)
            action_properties = QAction("Свойства", self)
            menu.addAction(action_convert)
            menu.addAction(action_properties)
            action_properties.triggered.connect(lambda _: self.show_properties(video))
            action_convert.triggered.connect(lambda _: self.convert_video(video))

        action_delete = QAction("Удалить", self)
        if single_selection and menu.actions():
            menu.addSeparator()
        menu.addAction(action_delete)
        action_delete.triggered.connect(lambda _: self.delete_selected_videos())

        global_pos = self.list_widget.mapToGlobal(pos)
        menu.exec(global_pos)

    def delete_video_with_confirmation(self, video: 'Video'):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Удалить видео")
        box.setText(f"Вы уверены, что хотите удалить видео '{video.title}'?")
        yes_btn = box.addButton("Да", QMessageBox.ButtonRole.YesRole)
        no_btn = box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no_btn)
        box.exec()

        if box.clickedButton() == yes_btn:
            if video in self.video_library:
                self.video_library.remove(video)
            self.delete_video_from_database(video)
            self._refresh_table(self.video_library)

    def convert_video(self, video: 'Video'):
        """Открывает диалог конвертации выбранного видео."""
        dlg = ConvertDialog(video, self)
        dlg.exec()

    def show_properties(self, video: 'Video'):
        """Показывает диалог со свойствами файла, похожий на проводник."""
        try:
            file_path = video.file_path
            stat = os.stat(file_path)
            size_bytes = stat.st_size
            size_mb = size_bytes / (1024 * 1024)
            created_ts = stat.st_ctime
            created_dt = datetime.datetime.fromtimestamp(created_ts)

            fmt = os.path.splitext(file_path)[1].lstrip('.').upper() or "—"

            text = (
                f"Имя: {os.path.basename(file_path)}\n"
                f"Расположение: {os.path.dirname(file_path)}\n"
                f"Размер: {size_mb:.2f} МБ ({size_bytes} байт)\n"
                f"Длительность: {video.duration}\n"
                f"Разрешение: {video.resolution}\n"
                f"Формат: {fmt}\n"
                f"Дата создания: {created_dt.strftime('%d.%m.%Y %H:%M:%S')}"
            )

            QMessageBox.information(self, "Свойства видео", text)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось получить свойства файла.\n{e}")


class VideoItemDelegate(QStyledItemDelegate):
    """Рисуем в элементе: превью, жирный заголовок и обычную длительность."""

    def paint(self, painter: QPainter, option, index):
        video = index.data(Qt.ItemDataRole.UserRole)
        icon: QIcon | None = index.data(Qt.ItemDataRole.DecorationRole)

        painter.save()

        # Подсветка выбора / hover с закруглением
        radius = 6
        path = QPainterPath()
        rect = option.rect.adjusted(1, 1, -1, -1)
        path.addRoundedRect(QRectF(rect), radius, radius)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillPath(path, QColor("#505050"))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillPath(path, QColor("#333333"))

        # Превью (иконка)
        if icon is not None:
            icon_rect = QRect(rect.x() + (rect.width() - 160) // 2, rect.y(), 160, 90)
            icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)

        text_y = rect.y() + 95
        text_width = rect.width()

        # Заголовок жирным с обрезкой по ширине
        bold_font = option.font
        bold_font.setBold(True)
        painter.setFont(bold_font)
        fm = QFontMetrics(bold_font)
        elided_title = fm.elidedText(video.title, Qt.TextElideMode.ElideRight, text_width - 4)
        painter.setPen(option.palette.text().color())
        painter.drawText(QRect(rect.x(), text_y, text_width, 20), Qt.AlignmentFlag.AlignHCenter, elided_title)

        # Длительность обычным
        normal_font = option.font
        normal_font.setBold(False)
        painter.setFont(normal_font)
        painter.drawText(QRect(rect.x(), text_y + 22, text_width, 20), Qt.AlignmentFlag.AlignHCenter, video.duration)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(160, 150)


# ---------- Конвертация видео ----------


class CVConvertWorker(QObject):
    """Конвертирует видео средствами OpenCV: читаем кадры и записываем заново с нужным кодеком."""

    progressChanged = pyqtSignal(int, float)  # проценты, ETA (сек)
    finished = pyqtSignal(bool, str)  # успех, путь выходного файла

    _FORMAT_FOURCC = {
        "mp4": "mp4v",
        "avi": "XVID",
        "mkv": "X264",  # может не работать – зависит от сборки OpenCV
        "mov": "mp4v",
        "webm": "VP90",  # поддержка ограничена
        "mpg": "PIM1",
    }

    def __init__(self, input_path: str, output_path: str):
        super().__init__()
        self._in = input_path
        self._out = output_path

    def run(self):  # noqa: C901 – сложная, но линейная логика
        import cv2  # pylint: disable=import-error
        import time, os

        cap = cv2.VideoCapture(self._in)
        if not cap.isOpened():
            self.finished.emit(False, self._out)
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        # Определяем fourcc
        ext = os.path.splitext(self._out)[1].lstrip('.').lower()
        fourcc_str = self._FORMAT_FOURCC.get(ext, "XVID")
        writer = cv2.VideoWriter(self._out, cv2.VideoWriter_fourcc(*fourcc_str), fps, (width, height))

        if not writer.isOpened():
            # Попытка fallback
            writer = cv2.VideoWriter(self._out, cv2.VideoWriter_fourcc(*"XVID"), fps, (width, height))
            if not writer.isOpened():
                cap.release()
                self.finished.emit(False, self._out)
                return

        processed = 0
        start_ts = time.time()
        update_each = max(int(fps // 2), 1)  # обновлять ~2 раза в секунду

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)
            processed += 1

            if total_frames and processed % update_each == 0:
                percent = int(processed / total_frames * 100)
                eta = ((total_frames - processed) / fps) if fps else 0.0
                self.progressChanged.emit(percent, eta)

        cap.release()
        writer.release()

        self.progressChanged.emit(100, 0.0)
        self.finished.emit(True, self._out)


class ConvertDialog(QDialog):
    """Диалог выбора формата и отображения прогресса конвертации."""

    _FORMATS = ["mp4", "avi", "mkv", "mov", "webm", "mpg"]

    def __init__(self, video: 'Video', parent=None):
        super().__init__(parent)
        self._video = video
        self.setWindowTitle("Конвертация видео")
        self.setModal(True)

        layout = QVBoxLayout(self)

        cur_fmt = os.path.splitext(video.file_path)[1].lstrip('.').lower()
        layout.addWidget(QLabel(f"Текущий формат: {cur_fmt.upper() or '—'}"))

        self.combo = QComboBox()
        for fmt in self._FORMATS:
            self.combo.addItem(fmt.upper(), fmt)
        if cur_fmt in self._FORMATS:
            # Ставим ближайший отличный от текущего формат по умолчанию
            self.combo.setCurrentIndex((self._FORMATS.index(cur_fmt) + 1) % len(self._FORMATS))
        layout.addWidget(self.combo)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.label_eta = QLabel()
        self.label_eta.setVisible(False)
        layout.addWidget(self.label_eta)

        self.btn_convert = QPushButton("Конвертировать")
        self.btn_convert.clicked.connect(self._on_convert_clicked)
        layout.addWidget(self.btn_convert)

        self._thread: QThread | None = None
        self._worker: CVConvertWorker | None = None

    # ---------- Внутреннее ----------

    @staticmethod
    def _duration_to_sec(duration: str | None) -> float | None:
        """Конвертирует строку вида HH:MM:SS или MM:SS в секунды."""
        if not duration:
            return None
        parts = duration.split(':')
        try:
            if len(parts) == 3:
                h, m, s = parts
            elif len(parts) == 2:
                h = 0
                m, s = parts
            else:
                return None
            return int(h) * 3600 + int(m) * 60 + int(float(s))
        except ValueError:
            return None

    def _on_convert_clicked(self):
        fmt = self.combo.currentData()
        base = os.path.splitext(self._video.file_path)[0]
        default_target = f"{base}_conv.{fmt}"

        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить как",
            default_target,
            f"{fmt.upper()} (*.{fmt})",
        )
        if not target_path:
            return
        if not target_path.lower().endswith(f".{fmt}"):
            target_path += f".{fmt}"

        # Запускаем прогресс
        self.progress.setVisible(True)
        self.label_eta.setVisible(True)
        self.btn_convert.setEnabled(False)
        self.combo.setEnabled(False)

        total_sec = self._duration_to_sec(self._video.duration)

        self._worker = CVConvertWorker(self._video.file_path, target_path)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progressChanged.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_progress(self, percent: int, eta: float):
        self.progress.setValue(percent)
        if eta:
            mins, secs = divmod(int(eta), 60)
            self.label_eta.setText(f"Оставшееся время: {mins:02d}:{secs:02d}")

    def _on_finished(self, success: bool, output_path: str):
        if success:
            QMessageBox.information(self, "Конвертация завершена", f"Файл сохранён:\n{output_path}")
        else:
            QMessageBox.warning(self, "Ошибка", "Конвертация не удалась. Проверьте наличие ffmpeg.")
        self.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoLibraryApp()
    window.resize(900, 600)
    window.show()
    sys.exit(app.exec())