from .logger import activity_logger
def log_activity(user=None, action="", request=None, data=None):
    msg = {
        "user": str(user) if user else "Anonymous",
        "action": action,
        "path": request.path if request else "",
        "method": request.method if request else "",
        "data": data,
    }
    activity_logger.info(msg)