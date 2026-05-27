from googleapiclient.discovery import build
from google.oauth2 import service_account
import os
import logging

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly"
]
 

def conectar_drive():

    logger.info("obteniendo credenciales")
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    creds = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=SCOPES
    )

    service = build("drive", "v3", credentials=creds)

    return service
