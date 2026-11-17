"""
JARVIS Notification Service
Provides desktop notifications on Windows.
"""

import logging
import threading

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends Windows desktop notifications."""

    def __init__(self):
        self._available = False
        self._check_availability()

    def _check_availability(self):
        """Check if notification library is available."""
        try:
            import winotify
            self._available = True
            logger.info("Notification service: winotify available")
        except ImportError:
            logger.warning("winotify not installed. Notifications will be logged only.")

    def notify(self, title: str, message: str, duration: int = 5):
        """Send a desktop notification (non-blocking)."""
        def _send():
            try:
                if self._available:
                    from winotify import Notification, audio
                    toast = Notification(
                        app_id="JARVIS",
                        title=title,
                        msg=message,
                        duration="short" if duration <= 5 else "long"
                    )
                    toast.set_audio(audio.Default, loop=False)
                    toast.show()
                else:
                    logger.info(f"[NOTIFICATION] {title}: {message}")
            except Exception as e:
                logger.error(f"Notification error: {e}")
                logger.info(f"[NOTIFICATION] {title}: {message}")

        thread = threading.Thread(target=_send, daemon=True)
        thread.start()

    def notify_success(self, message: str):
        """Send a success notification."""
        self.notify("JARVIS", f"✓ {message}")

    def notify_error(self, message: str):
        """Send an error notification."""
        self.notify("JARVIS - Error", f"✗ {message}")

    def notify_info(self, message: str):
        """Send an info notification."""
        self.notify("JARVIS", f"ℹ {message}")
