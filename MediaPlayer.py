import sys

import qtawesome as qta
from PyQt5.QtCore import QAbstractListModel, Qt, QUrl
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtMultimedia import QMediaPlayer, QMediaPlaylist, QMediaContent
from PyQt5.QtWidgets import QWidget, QMainWindow, QFileDialog, QApplication

from Equalizer import WindowingWidget
from EqualizerTest import Ui_Sliders
from MainWindow import Ui_MainWindow
from Visualizer import *

# Back up the reference to the exceptionhook
sys._excepthook = sys.excepthook


def my_exception_hook(exctype, value, traceback):
    # Print the error and traceback
    print(exctype, value, traceback)
    # Call the normal Exception hook after
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


# Set the exception hook to our wrapping function
sys.excepthook = my_exception_hook


class Slider(Ui_Sliders, QWidget):
    def __init__(self):
        super(Slider, self).__init__()
        self.setupUi(self)


def hhmmss(ms):
    h, r = divmod(ms, 3600000)
    m, r = divmod(r, 60000)
    s, _ = divmod(r, 1000)
    return ("%d:%02d:%02d" % (h, m, s)) if h else ("%d:%02d" % (m, s))


class PlaylistModel(QAbstractListModel):
    def __init__(self, playlist, *args, **kwargs):
        super(PlaylistModel, self).__init__(*args, **kwargs)
        self.playlist = playlist

    def data(self, index, role):
        if role == Qt.DisplayRole:
            media = self.playlist.media(index.row())
            return media.canonicalUrl().fileName()

    def rowCount(self, index):
        return self.playlist.mediaCount()


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)

        self.player = QMediaPlayer()

        self.player.error.connect(self.erroralert)
        self.player.play()
        self.player.stateChanged.connect(self.Set_Icons)
       # self.player.volumeChanged.connect(self.prev_volume)
        # Connect control buttons/slides for media player.
        self.playButton.pressed.connect(self.play_pause)
        self.stopButton.pressed.connect(self.player.stop)
        self.showButton.pressed.connect(self.playlist_toggle)
        self.equalizerButton.pressed.connect(self.ShowEqualizer)
        self.volumeButton.pressed.connect(self.mute)

        self.volumeSlider.valueChanged.connect(self.volumeChanged)
        self.currentVolume = self.volumeSlider.value()
        self.timeSlider.valueChanged.connect(self.player.setPosition)

        # Setup the playlist.
        self.playlist = QMediaPlaylist()
        self.player.setPlaylist(self.playlist)

        self.model = PlaylistModel(self.playlist)
        self.listWidget.setModel(self.model)
        self.playlist.currentIndexChanged.connect(self.playlist_position_changed)
        selection_model = self.listWidget.selectionModel()
        selection_model.selectionChanged.connect(self.playlist_selection_changed)

        self.player.durationChanged.connect(self.update_duration)
        self.player.positionChanged.connect(self.update_position)

        self.actionOpen_File.triggered.connect(self.open_file)
        self.files = []
        self.setAcceptDrops(True)

        self.graphWidget.setBackground((60, 60, 60))
        self.graphWidget.GetViewBox().setMenuEnabled(False)
        self.graphWidget.GetViewBox().setMouseEnabled(x=False, y=False)
        self.graphWidget.setPlotEQ((42, 130, 218))


        self.Visualizer = FFTAnalyser(self.player)
        self.Visualizer.calculated_visual.connect(self.draw)
        self.Visualizer.start()
        self.Equalizer = QWidget()
        self.visdata = np.array([])
        self.show()

    def draw(self, visdata):
        self.visdata = np.array(visdata)
        self.graphWidget.UpdatePlotEQ(self.visdata)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def play_pause(self):
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def Set_Icons(self, state):
        if state == QMediaPlayer.StoppedState:
            self.stopButton.setIcon(
                qta.icon('fa5s.stop-circle', active='fa5s.stop-circle', color='white', color_active='grey'))
            self.playButton.setIcon(qta.icon('fa5s.play-circle', color='white'))
            self.playButton.setToolTip('Play')
        elif state == QMediaPlayer.PlayingState:
            self.playButton.setIcon(qta.icon('fa5s.pause-circle', color='white'))
            self.playButton.setToolTip('Pause')
        elif state == QMediaPlayer.PausedState:
            self.playButton.setIcon(qta.icon('fa5s.play-circle', color='white'))
            self.playButton.setToolTip('Play')

    def playlist_toggle(self):
        if self.listWidget.isHidden():
            self.listWidget.setHidden(False)
            self.listWidget.setProperty("showDropIndicator", True)
            self.showButton.setIcon(qta.icon('fa5s.eye-slash', color='white'))
            self.showButton.setToolTip('Hide Playlist')
        else:
            self.listWidget.setHidden(True)
            self.listWidget.setProperty("showDropIndicator", False)
            self.showButton.setIcon(qta.icon('fa5s.list-ul', color='white'))
            self.showButton.setToolTip('Show Playlist')

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            self.playlist.addMedia(
                QMediaContent(url)
            )

        self.model.layoutChanged.emit()

        # If not playing, seeking to first of newly added + play.
        if self.player.state() != QMediaPlayer.PlayingState:
            i = self.playlist.mediaCount() - len(e.mimeData().urls())
            self.playlist.setCurrentIndex(i)
            self.player.play()

    def open_file(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        path, _ = QFileDialog.getOpenFileName(self, "Open file", "",
                                              "Music Files (*.mp3 *.wav)", options=options)

        if path:
            self.playlist.addMedia(
                QMediaContent(
                    QUrl.fromLocalFile(path)
                )
            )
            self.files.append(QMediaContent(
                QUrl.fromLocalFile(path)
            ))

        self.model.layoutChanged.emit()

    # def contextMenuEvent(self, event):
    # contextMenu = QMenu(self)
    # graph = contextMenu.addAction("Show Graph")

    def update_duration(self, duration):
        print("!", duration)
        print("?", self.player.duration())

        self.timeSlider.setMaximum(duration)

        if duration >= 0:
            self.totalTimeLabel.setText(hhmmss(duration))

    def update_position(self, position):
        if position >= 0:
            self.currentTimeLabel.setText(hhmmss(position))

        self.timeSlider.blockSignals(True)
        self.timeSlider.setValue(position)
        self.timeSlider.blockSignals(False)

    def playlist_selection_changed(self, ix):
        i = ix.indexes()[0].row()
        self.playlist.setCurrentIndex(i)

    def playlist_position_changed(self, i):
        if i > -1:
            ix = self.model.index(i)
            self.listWidget.setCurrentIndex(ix)

    def erroralert(self, *args):
        print(args)

    def ShowEqualizer(self):
        if self.player.currentMedia().canonicalUrl().path() != "":
            self.Equalizer = WindowingWidget(self.player.currentMedia().canonicalUrl().path())
            self.Equalizer.SendPath.connect(self.AddPathToPlaylist)
            self.Equalizer.show()

    def AddPathToPlaylist(self, path):
        if path:
            self.playlist.addMedia(
                QMediaContent(
                    QUrl.fromLocalFile(path)
                )
            )
            self.files.append(path)

        self.model.layoutChanged.emit()

    def volumeChanged(self):
        self.currentVolume = self.volumeSlider.value()
        self.player.setVolume(self.volumeSlider.value())

    def mute(self):
        if self.player.isMuted():
            self.player.setMuted(False)
            self.volumeButton.setIcon(qta.icon('fa5s.volume-up', color='white'))
            self.volumeButton.setToolTip('Mute')
            self.volumeSlider.setEnabled(True)
        else:
            self.player.setMuted(True)
            self.volumeButton.setIcon(qta.icon('fa5s.volume-mute', color='white'))
            self.volumeButton.setToolTip('Unmute')
            self.volumeSlider.setEnabled(False)

    def closeEvent(self, event):
        self.Visualizer.terminate()
        if self.Equalizer.isVisible():
            self.Equalizer.close()


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName("ThePlayer")
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    app.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }")

    window = MainWindow()
    app.exec_()
