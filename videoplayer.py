from PyQt6.QtGui import QIcon, QFont, QAction
from PyQt6.QtCore import Qt, QUrl, QSize
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QPushButton, QSlider, QStyle, QVBoxLayout, QWidget, QStatusBar,
    QLabel, QMenu, QWidgetAction, QHBoxLayout as QHBox, QVBoxLayout as QVBox
)
from PyQt6.QtCore import pyqtSignal, QPoint, QPointF


class ClickableSlider(QSlider):
    """QSlider, реагирующий на клик по треку – сразу переходит к позиции."""

    def mousePressEvent(self, event):  # noqa: N802  – PyQt naming
        if event.button() == Qt.MouseButton.LeftButton:
            if self.orientation() == Qt.Orientation.Horizontal:
                # получаем позицию клика относительно слайдера
                pos_x = event.position().x() if hasattr(event, "position") else event.x()
                new_val = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(pos_x), self.width())
                self.setValue(new_val)
                event.accept()
                # Эмитируем обычное поведение – полезно для внешних обработчиков
                self.sliderMoved.emit(new_val)
        super().mousePressEvent(event)


class VideoPlayer(QWidget):

    def __init__(self, parent=None):
        super(VideoPlayer, self).__init__(parent)

        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()

        btnSize = QSize(16, 16)
        videoWidget = QVideoWidget()

        backButton = QPushButton("Назад")
        backButton.setToolTip("Закрыть плеер")
        backButton.setStatusTip("Закрыть плеер")
        backButton.setFixedHeight(24)
        backButton.setIconSize(btnSize)
        backButton.setFont(QFont("Noto Sans", 8))
        backButton.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowLeft))

        # Применяем стиль для плеера
        self.apply_styles()
        backButton.clicked.connect(self.close)

        self.playButton = QPushButton()
        self.playButton.setEnabled(False)
        self.playButton.setFixedHeight(24)
        self.playButton.setIconSize(btnSize)
        self.playButton.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.playButton.clicked.connect(self.play)

        self.positionSlider = ClickableSlider(Qt.Orientation.Horizontal)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.sliderMoved.connect(self.setPosition)

        # Иконка динамика
        volume_icon = QLabel()
        volume_icon.setPixmap(QIcon("icons/dinamic.svg").pixmap(16, 16))

        self.volumeSlider = QSlider(Qt.Orientation.Horizontal)
        self.volumeSlider.setRange(0, 100)
        self.volumeSlider.setValue(100)
        self.volumeSlider.setFixedWidth(100)
        self.volumeSlider.valueChanged.connect(self.setVolume)

        # Кнопка скорости
        self.speedButton = QPushButton("1x")
        self.speedButton.setFixedHeight(24)
        self.speedButton.clicked.connect(self.showSpeedMenu)

        self.statusBar = QStatusBar()
        self.statusBar.setFont(QFont("Noto Sans", 7))
        self.statusBar.setFixedHeight(14)

        controlLayout = QHBoxLayout()
        controlLayout.setContentsMargins(0, 0, 0, 0)
        controlLayout.addWidget(backButton)
        controlLayout.addWidget(self.playButton)
        controlLayout.addWidget(self.positionSlider)
        controlLayout.addWidget(volume_icon)
        controlLayout.addWidget(self.volumeSlider)
        controlLayout.addWidget(self.speedButton)

        layout = QVBoxLayout()
        layout.addWidget(videoWidget)
        layout.addLayout(controlLayout)
        layout.addWidget(self.statusBar)

        self.setLayout(layout)

        self.mediaPlayer.setVideoOutput(videoWidget)
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        self.mediaPlayer.playbackStateChanged.connect(self.mediaStateChanged)
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.errorChanged.connect(self.handleError)

        self.audioOutput.volumeChanged.connect(self.volumeChanged)

    # Метод abrir больше не нужен (загрузка из главного окна), оставим на случай ручного теста
    def abrir(self):
        pass  # Не используется

    def play(self):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()

    def mediaStateChanged(self, state):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.playButton.setIcon(
                    self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.playButton.setIcon(
                    self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def positionChanged(self, position):
        self.positionSlider.setValue(position)

    def durationChanged(self, duration):
        self.positionSlider.setRange(0, duration)

    def setPosition(self, position):
        self.mediaPlayer.setPosition(position)

    def setVolume(self, volume):
        self.audioOutput.setVolume(volume / 100)

    def volumeChanged(self, volume):
        self.volumeSlider.setValue(int(volume * 100))

    def handleError(self):
        self.playButton.setEnabled(False)
        self.statusBar.showMessage("Ошибка: " + self.mediaPlayer.errorString())

    def setSource(self, url: QUrl):
        """Устанавливает источник видео и активирует кнопку воспроизведения."""
        self.mediaPlayer.setSource(url)
        self.playButton.setEnabled(True)

    def set_video_data(self, data: dict):
        """Получает словарь с данными о видео и выводит краткую информацию."""
        info = f"{data.get('title', '')} | {data.get('resolution', '')} | {data.get('duration', '')}"
        self.statusBar.showMessage(info)

    def apply_styles(self):
        """Применяет современную тему оформления к элементам плеера."""
        self.setStyleSheet("""
            QWidget {
                background-color: #202124;
                color: #e8eaed;
            }

            QPushButton {
                background-color: #1a73e8;
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
            }

            QPushButton:hover {
                background-color: #1669c1;
            }

            QSlider::groove:horizontal {
                height: 6px;
                background: #5f6368;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background: #ffffff;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }

            QStatusBar {
                background: #303134;
                border-top: 1px solid #5f6368;
            }
        """)

    # ---------- Управление скоростью ----------

    def updateSpeed(self, rate: float):
        """Устанавливает скорость и обновляет текст на кнопке."""
        rate = max(0.25, min(rate, 2.0))
        self.mediaPlayer.setPlaybackRate(rate)
        # Формат без лишних нулей
        self.speedButton.setText(f"{rate:g}x")

    def showSpeedMenu(self):
        """Показывает компактное меню управления скоростью поверх кнопки."""
        current_rate = self.mediaPlayer.playbackRate() or 1.0

        menu = QMenu(self)
        # Полупрозрачный фон (фрост-эффект)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(32, 34, 36, 180); /* тёмный с прозрачностью */
                border: 1px solid #5f6368;
            }
            QMenu::item {
                color: #e8eaed;
                padding: 4px 16px;
            }
            QMenu::item:selected {
                background-color: rgba(95, 99, 104, 120);
            }
        """)

        # ---- Виджет со слайдером ----
        w = QWidget()
        vbox = QVBox(w)
        vbox.setContentsMargins(8, 8, 8, 8)

        lbl = QLabel(f"{current_rate:g}x")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(lbl)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(25, 200)  # 0.25–2.0x
        slider.setValue(int(current_rate * 100))

        def on_slider(val: int):
            rate = val / 100.0
            self.updateSpeed(rate)
            lbl.setText(f"{rate:g}x")

        slider.valueChanged.connect(on_slider)
        vbox.addWidget(slider)

        wa = QWidgetAction(menu)
        wa.setDefaultWidget(w)
        menu.addAction(wa)

        menu.addSeparator()

        # ---- Пресеты ----
        presets = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

        for r in presets:
            act = QAction(f"{r:g}x", menu)
            if abs(r - current_rate) < 0.001:
                act.setCheckable(True)
                act.setChecked(True)

            def make_handler(val: float):
                def _handler():
                    self.updateSpeed(val)
                    slider.setValue(int(val * 100))
                    lbl.setText(f"{val:g}x")
                return _handler

            act.triggered.connect(make_handler(r))
            menu.addAction(act)

        # ---- Показываем меню, но не даём ему выйти за пределы экрана плеера ----
        global_pos = self.speedButton.mapToGlobal(self.speedButton.rect().bottomLeft())

        menu_size = menu.sizeHint()

        # Геометрия окна плеера в глобальных координатах
        win_geo = self.frameGeometry()
        win_top_left = self.mapToGlobal(self.rect().topLeft())
        win_rect_global = win_geo.translated(win_top_left - win_geo.topLeft())

        x = global_pos.x()
        y = global_pos.y()

        if x + menu_size.width() > win_rect_global.right():
            x = win_rect_global.right() - menu_size.width()
        if y + menu_size.height() > win_rect_global.bottom():
            # если не помещается снизу, показываем выше кнопки
            y = self.speedButton.mapToGlobal(self.speedButton.rect().topLeft()).y() - menu_size.height()
            if y < win_rect_global.top():
                y = win_rect_global.top()

        menu.popup(QPoint(x, y))

# ----- SpeedDialog класс больше не нужен; удалён -----

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True)
    player = VideoPlayer()
    player.setWindowTitle("Видеоплеер")
    player.resize(900, 600)
    player.show()
    sys.exit(app.exec())