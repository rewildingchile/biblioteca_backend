import datetime

from django.utils import timezone
from googleapiclient.errors import HttpError

from googledrive.models import Area
from googledrive.models import GoogleDriveFile
from googledrive.models import GoogleDriveSyncState

import logging

 
logger = logging.getLogger(__name__)


FOLDER_MIME = "application/vnd.google-apps.folder"
import logging
from collections import deque
from datetime import datetime
from typing import Optional

from django.db import transaction
from django.utils import timezone
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Modelos Django (ejemplo)
# from your_app.models import GoogleDriveFile, GoogleDriveSyncState

logger = logging.getLogger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"

import logging
from collections import deque
from datetime import datetime
from typing import Optional

from django.db import transaction
from django.utils import timezone
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# from your_app.models import GoogleDriveFile, GoogleDriveSyncState

logger = logging.getLogger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(HttpError),
    reraise=True,
)
def _execute_with_retry(request):
    return request.execute()

def sync_full(
    service,
    folder_id: str,
    area,
    drive_id: Optional[str] = None,
    sync_started_at: Optional[datetime] = None,
):
    """
    Sincroniza recursivamente (iterativa) un Shared Drive completo.
    Las carpetas/archivos de primer nivel (hijos directos de folder_id)
    tendrán como parent el objeto correspondiente a folder_id.
    """
    if sync_started_at is None:
        sync_started_at = timezone.now()

    # 1. Obtener driveId si no se proporcionó
    if drive_id is None:
        try:
            root_info = _execute_with_retry(
                service.files().get(
                    fileId=folder_id,
                    fields="driveId",
                    supportsAllDrives=True,
                )
            )
            drive_id = root_info.get("driveId")
            if not drive_id:
                raise ValueError(
                    f"El folder_id '{folder_id}' no pertenece a un Shared Drive."
                )
            logger.info(f"Drive ID obtenido: {drive_id}")
        except HttpError as e:
            logger.exception(f"No se pudo obtener driveId para {folder_id}: {e}")
            return

    # 2. Crear/actualizar el objeto raíz (folder_id) en BD
    #    Para obtener metadatos de la raíz (nombre, etc.) si no existen
    try:
        root_metadata = _execute_with_retry(
            service.files().get(
                fileId=folder_id,
                fields="id, name, mimeType, modifiedTime, webViewLink",
                supportsAllDrives=True,
            )
        )
        root_name = root_metadata.get("name", "Root")
        root_mime = root_metadata.get("mimeType", FOLDER_MIME)
        root_modified = root_metadata.get("modifiedTime")
        if root_modified:
            root_modified_dt = datetime.fromisoformat(root_modified.replace("Z", "+00:00"))
        else:
            root_modified_dt = timezone.now()
        root_web_link = root_metadata.get("webViewLink")

        root_obj, root_created = GoogleDriveFile.objects.update_or_create(
            drive_file_id=folder_id,
            defaults={
                "area": area,
                "name": root_name,
                "mime_type": root_mime,
                "parent_drive_file_id": None,  # la raíz no tiene padre
                "drive_web_view_link": root_web_link,
                "last_known_modified_time": root_modified_dt,
                "last_synced_at": timezone.now(),
            },
        )
        logger.info(f"Raíz {folder_id} {'creada' if root_created else 'actualizada'}")
    except HttpError as e:
        logger.exception(f"Error obteniendo metadatos de la raíz {folder_id}: {e}")
        return

    # 3. Cola: cada elemento es (folder_id, parent_db_object)
    #    Iniciamos con los hijos de la raíz, cuyo padre es root_obj
    #    Para ello, primero listamos los elementos directos de la raíz
    #    y los encolamos. La raíz misma no necesita ser recorrida como carpeta
    #    porque ya tenemos su objeto.
    queue = deque()

    # Función auxiliar para encolar carpetas hijas a partir de un folder_id y su padre
    def enqueue_children(folder_id_to_list, parent_db_obj):
        # Determinar query para 'parents'
        if folder_id_to_list == drive_id:
            parents_query = "'root' in parents"
        else:
            parents_query = f"'{folder_id_to_list}' in parents"

        page_token = None
        while True:
            try:
                request = service.files().list(
                    q=f"{parents_query} and trashed=false",
                    driveId=drive_id,
                    corpora="drive",
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink)",
                    pageToken=page_token,
                    pageSize=1000,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                resultados = _execute_with_retry(request)
            except HttpError as e:
                logger.error(f"Error listando {folder_id_to_list}: {e}")
                break

            archivos = resultados.get("files", [])
            for archivo in archivos:
                # Guardamos el archivo y si es carpeta, la añadimos a la cola
                # con el padre recién creado/actualizado
                # (La lógica de guardado y encolado se centraliza más adelante)
                queue.append((archivo, parent_db_obj))

            page_token = resultados.get("nextPageToken")
            if not page_token:
                break

    # Primero encolamos los hijos directos de la raíz
    enqueue_children(folder_id, root_obj)

    processed_file_ids = set()

    # 4. Procesar la cola (BFS)
    while queue:
        archivo, parent_obj = queue.popleft()
        file_id = archivo["id"]
        processed_file_ids.add(file_id)
        nombre = archivo["name"]
        mime = archivo["mimeType"]
        modified_time = archivo.get("modifiedTime")
        web_link = archivo.get("webViewLink")

        if modified_time:
            modified_dt = datetime.fromisoformat(modified_time.replace("Z", "+00:00"))
        else:
            modified_dt = timezone.now()

        try:
            obj, created = GoogleDriveFile.objects.update_or_create(
                drive_file_id=file_id,
                defaults={
                    "area": area,
                    "name": nombre,
                    "mime_type": mime,
                    "parent_drive_file_id": parent_obj if parent_obj else None,
                    "drive_web_view_link": web_link,
                    "last_known_modified_time": modified_dt,
                    "last_synced_at": timezone.now(),
                },
            )
            if created:
                logger.debug(f"Nuevo: {file_id} - {nombre}")
            else:
                logger.debug(f"Actualizado: {file_id} - {nombre}")

            # Si es carpeta,  'enqueue' sus hijos (pero no la carpeta misma)
            if mime == FOLDER_MIME:
                # Usamos el objeto recién creado como padre para los hijos
                enqueue_children(file_id, obj)

        except Exception as e:
            logger.exception(f"Error guardando {file_id} ({nombre}): {e}")

    # 5. Limpieza de archivos que ya no existen en Drive
    with transaction.atomic():
        deleted_count, _ = GoogleDriveFile.objects.filter(
            area=area,
            last_synced_at__lt=sync_started_at,
        ).delete()
        logger.info(f"Registros obsoletos eliminados: {deleted_count}")

        # 6. Guardar startPageToken para sincronización incremental
        try:
            token_data = _execute_with_retry(
                service.changes().getStartPageToken(
                    driveId=drive_id, supportsAllDrives=True
                )
            )
            start_page_token = token_data.get("startPageToken")
            if start_page_token:
                state, created = GoogleDriveSyncState.objects.update_or_create(
                    area=area,
                    defaults={
                        "start_page_token": start_page_token,
                        "last_full_sync_at": timezone.now(),
                    },
                )
                logger.info(f"Token incremental guardado: {start_page_token}")
            else:
                logger.warning("No se recibió startPageToken")
        except HttpError as e:
            logger.error(f"Error obteniendo startPageToken: {e}")

def sync_full_old(
    service,
    folder_id,
    area,
    parent_obj=None,
    is_root=True,
    sync_started_at=None
):
    """
    Recorre recursivamente una carpeta de Google Drive
    y guarda archivos/carpetas en BD.
    """
    logger.info(f"sincronizando full {folder_id}")
    
    # timestamp único para TODA la sincronización
    if sync_started_at is None:
        sync_started_at = timezone.now()

    page_token = None

    while True:

        resultados = service.files().list(

            q=f"'{folder_id}' in parents and trashed=false",

            fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink)",

            pageToken=page_token,

            supportsAllDrives=True,

            includeItemsFromAllDrives=True,

            corpora="allDrives"

        ).execute()

        archivos = resultados.get("files", [])

        for archivo in archivos:
         try:
            file_id = archivo["id"]
            nombre = archivo["name"]
            mime = archivo["mimeType"]
            modified_time = archivo.get("modifiedTime")
            web_link = archivo.get("webViewLink")

            # convertir fecha ISO Google -> datetime
            if modified_time:

                modified_dt = datetime.datetime.fromisoformat(
                    modified_time.replace("Z", "+00:00")
                )

            else:

                modified_dt = timezone.now()

            
            logger.info(f"Procesando files : { file_id}, {area}")
                
            obj, created = GoogleDriveFile.objects.update_or_create(

                    drive_file_id=file_id,
                   
                    defaults={

                        "area": area,

                        "name": nombre,

                        "mime_type": mime,

                        "parent_drive_file_id": parent_obj if parent_obj else None,

                        "drive_web_view_link": web_link,

                        "last_known_modified_time": modified_dt,

                        "last_synced_at": timezone.now(),

                    }

                )
           

            # recursion
            if mime == FOLDER_MIME:

                sync_full(

                    service=service,

                    folder_id=file_id,

                    area=area,

                    parent_obj=obj,
                    
                    is_root=False,

                    sync_started_at=sync_started_at

                )
         except Exception as e:
                    logger.exception(
                    f"Error procesando "
                    f"file={archivo}"
                    )
        
        page_token = resultados.get("nextPageToken")

        if not page_token:
            break

    # SOLO la raíz realiza limpieza y token
    if is_root:

        logger.info(
            "Eliminando registros obsoletos"
        )

        # eliminar archivos que ya no existen
        # __lt : less than
        GoogleDriveFile.objects.filter(

            area=area,

            last_synced_at__lt=sync_started_at 

        ).delete()

        logger.info(
            "Obteniendo driveId"
        )

        # obtener driveId REAL desde folder_id
        root_info = service.files().get(

            fileId=folder_id,

            fields="driveId",

            supportsAllDrives=True

        ).execute()

        drive_id = root_info["driveId"]

        logger.info(
            f"drive_id={drive_id}"
        )

        logger.info(
            "Solicitando startPageToken"
        )

        token_data = (

            service.changes()

            .getStartPageToken(

                driveId=drive_id,

                supportsAllDrives=True

            )

            .execute()
        )

        start_page_token = (
            token_data["startPageToken"]
        )

        GoogleDriveSyncState.objects.update_or_create(

            area=area,

            defaults={

                "start_page_token":
                    start_page_token,

                "last_full_sync_at":
                    timezone.now()
            }
        )

        logger.info(
            f"Token inicial guardado: "
            f"{start_page_token}"
        )



import logging
from django.utils import timezone
from django.db import transaction
from googleapiclient.errors import HttpError
 

logger = logging.getLogger(__name__)

@transaction.atomic
def sync_changes(service, folder_id, area):
    # 1. Obtener o crear el estado de sincronización
    state, _ = GoogleDriveSyncState.objects.get_or_create(area=area)
    token = state.start_page_token
    sync_time = timezone.now()
    logger.info(f"sync_time {sync_time}")

    # 2. Obtener driveId de la carpeta raíz
    root_info = service.files().get(
        fileId=folder_id,
        fields="driveId",
        supportsAllDrives=True
    ).execute()
    logger.info(f"******* AQUI ******")
    logger.info(f"FOLDER: {root_info}")  
    drive_id = root_info["driveId"]

    # 3. Bucle de paginación sobre cambios
    while token:
        try:
            resultados = service.changes().list(
                pageToken=token,
                driveId=drive_id,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                includeRemoved=True,
                restrictToMyDrive=False,
                fields=(
                    "nextPageToken,"
                    "newStartPageToken,"
                    "changes("
                        "fileId,"
                        "removed,"
                        "file("
                            "id,"
                            "name,"
                            "mimeType,"
                            "modifiedTime,"
                            "webViewLink,"
                            "parents,"
                            "trashed"
                        ")"
                    ")"
                )
            ).execute()
            logger.info(f"Cantidad cambios: {len(resultados.get('changes', []))}")

        except HttpError as e:
            if e.resp.status == 410:  # token expirado
                logger.warning("Google Drive pageToken expirado. Solicitando nuevo token mediante sync_full.")
                sync_full(service=service, folder_id=folder_id, area=area)
                return
            raise

        # 4. Procesar cada cambio
        for cambio in resultados.get("changes", []):
            try:
                file_id = cambio.get("fileId")
                if not file_id:
                    logger.warning(f"Cambio sin fileId: {cambio}")
                    continue

                # Eliminado o en papelera
                if cambio.get("removed") or (cambio.get("file") and cambio["file"].get("trashed")):
                    GoogleDriveFile.objects.filter(drive_file_id=file_id).delete()
                    continue

                file_data = cambio.get("file")
                if not file_data:
                    continue

                # Obtener padre (si existe)
                parents = file_data.get("parents", [])
                parent_drive_id = parents[0] if parents else None
                parent_obj = None
                if parent_drive_id:
                    parent_obj = GoogleDriveFile.objects.filter(drive_file_id=parent_drive_id).first()

                # update_or_create
                # Nota: si el campo parent es una clave foránea, asignar parent_obj (instancia) es correcto.
                # Si es un campo entero (IntegerField) usar parent_obj.pk si parent_obj else None.
                GoogleDriveFile.objects.update_or_create(
                    drive_file_id=file_id,
                    defaults={
                        "area": area,
                        "name": file_data.get("name"),
                        "mime_type": file_data.get("mimeType"),
                        "parent_drive_file_id": parent_obj,  # Django ORM acepta instancia para ForeignKey
                        "drive_web_view_link": file_data.get("webViewLink"),
                        "last_synced_at": sync_time,
                    }
                )
            except Exception:
                logger.exception(f"Error procesando cambio file_id={file_id}")

        # 5. Avanzar al siguiente token
        token = resultados.get("nextPageToken")
        if token:
            continue

        # 6. Actualizar el token final (newStartPageToken)
        new_token = resultados.get("newStartPageToken")
        if new_token:
            state.start_page_token = new_token
            state.save(update_fields=["start_page_token"])
            logger.info(f"Token actualizado: {new_token}")
        else:
            # Si no viene newStartPageToken, lo solicitamos explícitamente
            logger.warning("No se recibió newStartPageToken, obteniendo token actual desde la API.")
            token_resp = service.changes().getStartPageToken().execute()
            state.start_page_token = token_resp.get("startPageToken")
            state.save()
        break

    logger.info(f"sync_changeXXX completado area={area.id}")


def sync_changes_old(service,folder_id,  area):

    state = GoogleDriveSyncState.objects.get(area=area)

    token = state.start_page_token

    sync_time = timezone.now()
    logger.info(f"sync_time {sync_time}")


    root_info = service.files().get(

        fileId=folder_id,

        fields="driveId",

        supportsAllDrives=True

    ).execute()

    drive_id = root_info["driveId"]


    while token:
        try:
            resultados = service.changes().list(

                pageToken=token,

                driveId=drive_id,

                supportsAllDrives=True,

                includeItemsFromAllDrives=True,

                includeRemoved=True,

                restrictToMyDrive=False,

                fields=(
                    "nextPageToken,"
                    "newStartPageToken,"
                    "changes("
                        "fileId,"
                        "removed,"
                        "file("
                            "id,"
                            "name,"
                            "mimeType,"
                            "modifiedTime,"
                            "webViewLink,"
                            "parents,"
                            "trashed"
                        ")"
                    ")"
                )

            ).execute()
           
            logger.info(resultados)
        except HttpError as e:
            #token expirado
            if e.resp.status == 410:

                logger.warning(
                    "Google Drive pageToken expirado. "
                    "Solicitando nuevo token."
                )

                # IMPORTANTE:
                # reconciliación completa

                sync_full(
                    service=service,
                    folder_id=folder_id,
                    area=area
                )

                return

            raise
        
        logger.info(
            f"Cantidad cambios: "
            f"{len(resultados.get('changes', []))}"
        )     
        for cambio in resultados.get("changes", []):
         try:
          
            logger.info(
                f"Cambio detectado: "
                f"{cambio}"
            )
            file_id = cambio.get("fileId")

            if not file_id:

                logger.warning(
                    f"Cambio sin fileId: {cambio}"
                )

                continue
          
            # eliminado
            if cambio.get("removed"):

                GoogleDriveFile.objects.filter(
                    drive_file_id=file_id
                ).delete()

                continue

            file_data = cambio.get("file")

            if not file_data:
                continue

            # papelera
            if file_data.get("trashed"):
                GoogleDriveFile.objects.filter(
                    drive_file_id=file_id
                ).delete()

                continue
             
            '''
            parents puede venir vacío cuando:
                se mueve archivo
                se elimina parent
                permisos insuficientes
                Shared Drives
            '''
            parents = file_data.get("parents", [])
            parent_drive_id = parents[0] if parents else None
            parent_obj = None

            if parent_drive_id:
                parent_obj = GoogleDriveFile.objects.filter(
                    drive_file_id=parent_drive_id
                ).first()

            GoogleDriveFile.objects.update_or_create(

                drive_file_id=file_id,

                defaults={

                    "area": area,

                    "name": file_data.get("name"),

                    "mime_type": file_data.get("mimeType"),

                    "parent_drive_file_id": parent_obj,

                    "drive_web_view_link":
                        file_data.get("webViewLink"),

                    "last_synced_at": sync_time,
                }
            )
         except Exception:

                logger.exception(
                    f"Error procesando "
                    f"cambio file_id={file_id}"
                )
        token = resultados.get("nextPageToken")

        if token:
            continue

        # último token válido    
        new_token = resultados.get("newStartPageToken")

        if new_token:

                state.start_page_token = new_token
                state.save(update_fields=["start_page_token"])
                logger.info(
                    f"Token actualizado: "
                    f"{new_token}"
                )

        break        
    
    logger.info(
        f"sync_changes completado "
        f"area={area.id}"
    )