# -*- coding: utf-8 -*-
"""
Qt Signal classes for thread-safe GUI updates
"""
import time
from typing import Any, Callable, Optional

from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition
from PySide6.QtWidgets import QWidget, QMessageBox
from PySide6.QtGui import QIcon


class SignThread(QThread):
    """
    GUI signal thread for thread-safe updates
    
    This class provides a way to safely update GUI elements from background threads
    by using Qt's signal-slot mechanism.
    """
    
    def __new__(cls, parent: QWidget, func: Callable, *types: type):
        """
        Create new SignThread instance with dynamic signal
        
        :param parent: Parent widget
        :param func: Function to bind to signal
        :param types: Signal parameter types
        """
        # Define signal dynamically based on types
        cls._update_signal = Signal(*types, name=func.__name__)
        return super().__new__(cls)
    
    def __init__(self, parent: QWidget, func: Callable, *types: type):
        """
        Initialize SignThread
        
        :param parent: Parent widget
        :param func: Function to bind to signal
        :param types: Signal parameter types (for documentation)
        """
        super().__init__(parent)
        self._update_signal.connect(func)
    
    def send(self, *args: Any) -> None:
        """
        Send signal to GUI thread
        
        :param args: Signal arguments matching the defined types
        """
        self._update_signal.emit(*args)


class QuestionSignal(QThread):
    """
    Signal thread for asynchronous user questions
    
    This class allows showing question dialogs from background threads
    and waiting for user responses in a thread-safe manner.
    """
    
    # Signal for asking question: (title, message, buttons, default_button)
    question_asked = Signal(str, str, QMessageBox.StandardButtons, QMessageBox.StandardButton)
    
    def __init__(self, parent: QWidget):
        """
        Initialize QuestionSignal
        
        :param parent: Parent widget
        """
        super().__init__(parent)
        self.question_asked.connect(self._show_question_dialog)
        self.parent_widget = parent
        
        # Thread synchronization
        self._mutex = QMutex()
        self._condition = QWaitCondition()
        self._response: Optional[int] = None
        self._response_received = False
    
    def send(
        self, 
        title: str, 
        message: str,
        buttons: QMessageBox.StandardButtons = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes
    ) -> int:
        """
        Send question signal and wait for response
        
        :param title: Dialog title
        :param message: Dialog message
        :param buttons: Available buttons
        :param default_button: Default button
        :return: User's button choice
        """
        self._mutex.lock()
        self._response = None
        self._response_received = False
        self._mutex.unlock()
        
        # Emit signal to show dialog in main thread
        self.question_asked.emit(title, message, buttons, default_button)
        
        # Wait for response using condition variable (more efficient than busy waiting)
        self._mutex.lock()
        while not self._response_received:
            # Wait with timeout to avoid deadlock
            self._condition.wait(self._mutex, 100)  # 100ms timeout
        response = self._response
        self._mutex.unlock()
        
        return response if response is not None else QMessageBox.StandardButton.Cancel
    
    def _show_question_dialog(
        self, 
        title: str, 
        message: str, 
        buttons: QMessageBox.StandardButtons,
        default_button: QMessageBox.StandardButton
    ) -> None:
        """
        Show question dialog in main thread
        
        :param title: Dialog title
        :param message: Dialog message  
        :param buttons: Available buttons
        :param default_button: Default button
        """
        from PySide6.QtCore import Qt
        
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        # Try to get icon from parent widget
        try:
            msg_box.setWindowIcon(self.parent_widget.windowIcon())
        except AttributeError:
            pass
            
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(buttons)
        msg_box.setDefaultButton(default_button)
        msg_box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        
        # Show dialog and store result
        result = msg_box.exec()
        
        # Signal that response is ready
        self._mutex.lock()
        self._response = result
        self._response_received = True
        self._condition.wakeAll()
        self._mutex.unlock()
