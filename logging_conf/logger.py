import logging
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
import os
import queue


# Crear carpeta de logs
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Cola para logging asíncrono
log_queue = queue.Queue()

# Handler que escribe en disco con rotación
file_handler = RotatingFileHandler(
    filename=os.path.join(LOG_DIR, "activity.log"),
    maxBytes=5*1024*1024,  # 5 MB
    backupCount=3
)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
file_handler.setFormatter(formatter)

# QueueHandler: envía logs a la cola
queue_handler = QueueHandler(log_queue)

# Logger principal de actividad
activity_logger = logging.getLogger("activity")
activity_logger.setLevel(logging.INFO)
activity_logger.addHandler(queue_handler)  # escribe en cola

# Listener que consume la cola y escribe en el RotatingFileHandler
listener = QueueListener(log_queue, file_handler)
listener.start()