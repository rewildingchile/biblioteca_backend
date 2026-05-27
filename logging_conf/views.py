from django.http import HttpResponse
import os
from django.conf import settings

def ver_activity_log(request):
    LOG_DIR=os.path.join(os.path.dirname(__file__), "logs")
    log_path = os.path.join(LOG_DIR, 'activity.log')
    with open(log_path, "r",encoding="utf-8") as f:
        contenido = f.read()
    return HttpResponse(f"<pre>{contenido}</pre>")

def ver_importlibromayor_log(request):
    LOG_DIR=os.path.join(os.path.dirname(__file__), "logs")
    log_path = os.path.join(LOG_DIR, 'fails_import_libromayor.log')
    with open(log_path, "r",encoding="utf-8") as f:
        contenido = f.read()
    return HttpResponse(f"<pre>{contenido}</pre>")