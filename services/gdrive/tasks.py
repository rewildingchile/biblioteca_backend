from celery import shared_task
from services.gdrive.google_service import conectar_drive
from services.gdrive.sync_service import sync_full
from services.gdrive.sync_service import sync_changes
 

from googledrive.models import   Area
import logging

logger = logging.getLogger(__name__)
# bind=True da acceso al contexto de Celery
@shared_task(bind=True) 
def sync_full_task(self,area_id):
        logger.info( f" {logger.name} --> Iniciando tarea fulldrive_task")
        service = conectar_drive()
     
        FOLDER_IDS = {
                1: "1fQmuOcRH4E5KEM2S3NXQSJwVK_1U02zD",
                2: "16j0klxJnQspJ1mvafpnMaRx7Xd1SRIDO",
        }

        folder_id = FOLDER_IDS.get(area_id)

        if not folder_id:
                raise ValueError(f"Área no soportada: {area_id}")

        area = Area.objects.get(id=area_id)
        try:
                sync_full( service, folder_id, area )
        except Exception:
                logger.exception("Error en celery")        

@shared_task(bind=True) 
def sync_changes_task(self,area_id):
        logger.info( f" {logger.name} --> Iniciando tarea changesdrive_task")
        service = conectar_drive()
     
        folder_id = "1fQmuOcRH4E5KEM2S3NXQSJwVK_1U02zD"
        area = Area.objects.get(id=area_id)
        try:
                sync_changes( service, folder_id, area )
        except Exception:
                logger.exception("Error en celery")        


  