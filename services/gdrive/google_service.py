from googleapiclient.discovery import build
from google.oauth2 import service_account
import os
from pathlib import Path


from googleapiclient.errors import HttpError

 
from googledrive.models import GoogleDriveFile
from googledrive.models import GoogleDriveSyncState
from typing import Optional, Dict 
from googleapiclient.http import  MediaIoBaseUpload 

import logging

logger = logging.getLogger(__name__)

def conectar_drive():
    SCOPES = [
        "https://www.googleapis.com/auth/drive.readonly"
    ]
    logger.info("obteniendo credenciales")
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
  
    creds = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=SCOPES
    )

    service = build("drive", "v3", credentials=creds)

    return service



    

class GoogleDriveService:
    """Servicio para interactuar con Google Drive API"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    def __init__(self):
        self.credentials = None
        self.service = None
        self._folder_cache = {}  # ✅ AÑADIR CACHÉ: clave -> folder_id
        self._authenticate()
    
    def _authenticate(self):
        """Autentica usando cuenta de servicio"""
        try:
            credentials_path =  os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            self.credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=self.SCOPES
            )
            self.service = build('drive', 'v3', credentials=self.credentials)
            logger.info("? Autenticación con Google Drive exitosa")
        except Exception as e:
            logger.error(f"? Error autenticando con Google Drive: {str(e)}")
            raise
    

    
    def deprec_verify_folder_basic(self, folder_id: str) -> bool:
        """
        Verifica si una carpeta existe en Google Drive.

        Args:
            service: cliente de Google Drive API.
            folder_id: ID de la carpeta.

        Returns:
            bool
        """
        try:
            folder = (
                self.service.files()
                .get(
                    fileId=folder_id,
                    fields="driveId",
                    supportsAllDrives=True
                )
                .execute()
            )
            logger.info(f"✅ FOLDER: {folder}")  
            logger.info(f"✅ Acceso confirmado al folder: {folder_id}")    
            return True

        except HttpError as error:
            logger.error(f"❌ El ID {folder_id} no corresponde a una carpeta")
            if error.resp.status == 404:
                return False

            raise
 
    def verify_folder_exists(self, folder_id: str) -> bool:
        """
        Verifica si una carpeta existe y es accesible
        """
        try:
            # Primero, obtener información básica del archivo/carpeta
            file_info = self.service.files().get(
                fileId=folder_id,
                fields='id, name, mimeType, driveId, parents',
                supportsAllDrives=True
            ).execute()
            
            # Si tiene driveId, está en un Shared Drive
            if 'driveId' in file_info:
                logger.info(f"📁 La carpeta está en Shared Drive ID: {file_info['driveId']}")
                
                # Verificar acceso al Shared Drive
                drive_info = self.service.drives().get(
                    driveId=file_info['driveId'],
                    fields='id, name, capabilities'
                ).execute()
                logger.info(f"✅ Acceso confirmado al Shared Drive: {drive_info.get('name')}")
            
            # Verificar que sea carpeta
            if file_info.get('mimeType') == 'application/vnd.google-apps.folder':
                logger.info(f"✅ Carpeta válida: {file_info.get('name')} (ID: {folder_id})")
                return True
            else:
                logger.error(f"❌ El ID {folder_id} no corresponde a una carpeta")
                return False
                
        except HttpError as error:
            if error.resp.status == 404:
                logger.error(f"❌ Carpeta {folder_id} no encontrada")
                logger.error("🔍 Posibles causas:")
                logger.error("   - La carpeta fue eliminada")
                logger.error(f"   - La cuenta de servicio {self.credentials.service_account_email} no tiene acceso")
                logger.error("   - La carpeta está en un Shared Drive y la cuenta no fue añadida")
                logger.error("   - El ID de carpeta es incorrecto")
                
                # Intentar buscar la carpeta por nombre como alternativa
                logger.info("🔍 Buscando carpetas con nombre similar...")
                results = self.service.files().list(
                    q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                    fields="files(id, name)",
                    pageSize=20,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                
                folders = results.get('files', [])
                for folder in folders:
                    logger.info(f"   - {folder['name']} (ID: {folder['id']})")
                
                return False
                
            elif error.resp.status == 403:
                logger.error(f"🚫 Sin permisos para acceder a la carpeta {folder_id}")
                logger.error("📝 Pasos para agregar la cuenta de servicio al Shared Drive:")
                logger.error(f"   1. Abrir Google Drive")
                logger.error(f"   2. Ir al Shared Drive")
                logger.error(f"   3. Click derecho > Administrar miembros")
                logger.error(f"   4. Agregar: {self.credentials.service_account_email}")
                logger.error(f"   5. Asignar rol mínimo: 'Colaborador'")
                return False
            else:
                logger.error(f"❌ Error verificando carpeta: {error}")
                return False
            
    def create_folder_structure(self, parent_folder_id: str, relative_path: str, use_cache: bool = True) -> str:
        """
        Crea la estructura de carpetas recursivamente con caché
        Retorna el ID de la última carpeta creada
        
        Args:
            parent_folder_id: ID de la carpeta padre
            relative_path: Ruta relativa (ej: "facturasMayo" o "2024/facturas")
            use_cache: Si se debe usar caché (default True)
        """
        # ✅ GENERAR CLAVE DE CACHÉ
        cache_key = f"{parent_folder_id}:{relative_path}"
        
        # ✅ VERIFICAR CACHÉ PRIMERO
        if use_cache and cache_key in self._folder_cache:
            cached_id = self._folder_cache[cache_key]
            logger.info(f"♻️ USANDO CACHÉ: '{relative_path}' -> {cached_id}")
            return cached_id
        
        # PRIMERO: Verificar que el parent_folder_id existe y es accesible
        parent_exists = self.verify_folder_exists(parent_folder_id)
        if not parent_exists:
            logger.warning(f"⚠️ Carpeta padre {parent_folder_id} no existe o no es accesible")
            raise Exception(f"Carpeta padre {parent_folder_id} no existe")
        else:
            logger.info(f"✅ Carpeta padre existe: {parent_folder_id}")  

        if not relative_path:
            return parent_folder_id
    
        path_parts = Path(relative_path).parts
        current_parent = parent_folder_id

        for folder_name in path_parts:
            # 🔍 BÚSQUEDA MÁS PRECISA
            escaped_name = folder_name.replace("'", "\\'")
            query = (
                f"name='{escaped_name}' "
                f"and '{current_parent}' in parents "
                f"and mimeType='application/vnd.google-apps.folder' "
                f"and trashed=false"
            )
            
            try:
                # Buscar carpetas existentes
                results = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='files(id, name, createdTime)',
                    pageSize=10,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                
                folders = results.get('files', [])
                
                # 🎯 IMPORTANTE: Si hay múltiples carpetas con el mismo nombre
                if len(folders) > 1:
                    logger.warning(f"⚠️ Encontradas {len(folders)} carpetas con nombre '{folder_name}'")
                    logger.info("📋 Lista de carpetas duplicadas:")
                    for idx, folder in enumerate(folders, 1):
                        logger.info(f"   {idx}. ID: {folder['id']}, Creada: {folder.get('createdTime', 'N/A')}")
                    
                    # Ordenar por createdTime (más reciente primero)
                    folders.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
                    logger.info(f"✅ Usando carpeta más reciente: {folders[0]['id']}")
                    current_parent = folders[0]['id']
                    
                elif len(folders) == 1:
                    # Situación ideal: exactamente una carpeta
                    logger.info(f"📁 Carpeta existente encontrada: {folder_name} (ID: {folders[0]['id']})")
                    current_parent = folders[0]['id']
                    
                else:
                    # No existe, crear nueva carpeta
                    logger.info(f"📁 Creando carpeta: {folder_name} en padre {current_parent}")
                    
                    # Verificar que el padre sigue existiendo ANTES de crear
                    if not self.verify_folder_exists(current_parent):
                        logger.error(f"❌ El padre {current_parent} desapareció antes de crear {folder_name}")
                        raise Exception(f"Parent folder {current_parent} no longer exists")
                    
                    folder_metadata = {
                        'name': folder_name,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [current_parent]
                    }
                    
                    folder = self.service.files().create(
                        body=folder_metadata,
                        fields='id, name, webViewLink',
                        supportsAllDrives=True
                    ).execute()
                    
                    current_parent = folder.get('id')
                    logger.info(f"✅ Carpeta creada: {folder_name} (ID: {current_parent})")
                    
                    # Pequeña pausa para evitar race conditions
                    import time
                    time.sleep(0.5)

            except HttpError as error:
                logger.error(f"❌ Error creando carpeta {folder_name}: {error}")
                raise
        
        # ✅ GUARDAR EN CACHÉ
        if use_cache:
            self._folder_cache[cache_key] = current_parent
            logger.info(f"💾 CACHÉ GUARDADO: '{relative_path}' -> {current_parent}")
        
      
        return {
                'file_id': current_parent,
                'name': folder_name,
                'size': 0,
                'mime_type': 'application/vnd.google-apps.folder',
                'web_view_link':'', 
                'parent_folder_id':parent_folder_id
            }
    
    def clear_cache(self):
        """✅ Limpia la caché de carpetas"""
        self._folder_cache.clear()
        logger.info("🧹 Caché de carpetas limpiada") 
 
    from django.core.cache import cache
    def get_or_create_user_folder(self, user_id: int, user_email: str) -> str:
        """
        Obtiene o crea la carpeta del usuario en Google Drive
        Retorna el ID de la carpeta
        """
        cache_key = f"gdrive_user_folder_{user_id}"
        folder_id = cache.get(cache_key)
        
        if folder_id:
            return folder_id
        
        # Buscar carpeta existente
        query = f"name='{settings.GOOGLE_DRIVE_CONFIG['USER_FOLDER_PREFIX']}{user_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        
        try:
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                folder_id = folders[0]['id']
                cache.set(cache_key, folder_id, timeout=3600)
                return folder_id
                
            # Crear nueva carpeta
            folder_metadata = {
                'name': f"{settings.GOOGLE_DRIVE_CONFIG['USER_FOLDER_PREFIX']}{user_id}",
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [settings.GOOGLE_DRIVE_CONFIG['PARENT_FOLDER_ID']]
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            cache.set(cache_key, folder_id, timeout=3600)
            
            
            
            return folder_id
            
        except HttpError as error:
            logger.error(f"Error con carpeta de usuario: {error}")
            raise

    def upload_file(self, file_obj, filename: str, parent_folder_id: str, 
                   mime_type: str = None, chunk_size: int = 5 * 1024 * 1024) -> Dict:
        """
        Sube un archivo a Google Drive con soporte para chunks
        Retorna metadata del archivo subido
        """
        try:
            # Preparar metadata
            file_metadata = {
                'name': filename,
                'parents': [parent_folder_id]
            }
            
            # Determinar MIME type
            if not mime_type:
                import mimetypes
                mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            
            # Usar MediaIoBaseUpload para archivos desde memoria
            media = MediaIoBaseUpload(
                file_obj,
                mimetype=mime_type,
                chunksize=chunk_size,
                resumable=True
            )
            
            # Subir archivo
            uploaded_file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, size, mimeType, webViewLink, createdTime',
                supportsAllDrives=True
            ).execute()
            
            logger.info(f"? Archivo subido a Google Drive: {filename} (ID: {uploaded_file.get('id')} parent folder:{parent_folder_id})")
            
            return {
                'file_id': uploaded_file.get('id'),
                'name': uploaded_file.get('name'),
                'size': uploaded_file.get('size'),
                'mime_type': uploaded_file.get('mimeType'),
                'web_view_link': uploaded_file.get('webViewLink'),
                'created_time': uploaded_file.get('createdTime'),
                'parent_folder_id':parent_folder_id
            }
            
        except HttpError as error:
            logger.error(f"? Error subiendo archivo {filename}: {error}")
            raise
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """Obtiene metadata de un archivo"""
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, size, mimeType, webViewLink, parents, createdTime, modifiedTime'
            ).execute()
            return file
        except HttpError:
            return None
    
    def delete_file(self, file_id: str):
        """Mueve el archivo a la papelera (no lo elimina definitivamente)"""
        try:
            # Como no podemos eliminar, lo movemos a la papelera
            file_metadata = {
                'trashed': True  # Mover a papelera
            }
            
            self.service.files().update(
                fileId=file_id,
                body=file_metadata,
                supportsAllDrives=True
            ).execute()
            
            logger.info(f"📦 Archivo movido a papelera: {file_id}")
            return True
            
        except HttpError as error:
            if error.resp.status == 404:
                logger.warning(f"⚠️ Archivo no encontrado: {file_id}")
                return True
            elif error.resp.status == 403:
                logger.error(f"❌ Sin permisos para mover a papelera: {file_id}")
                return False
            logger.error(f"❌ Error moviendo a papelera {file_id}: {error}")
            return False

    def deprec_delete_file(self, file_id: str):
        """Elimina un archivo de Google Drive"""
   
        if not file_id:
                logger.error("❌ file_id vacío")
                return False
        

        # Primero verificar si el archivo existe y obtener información
        try:
            file_metadata = self.service.files().get(
                fileId=file_id,
                  supportsAllDrives=True,
                fields='id, name, trashed, parents, mimeType'
            ).execute()
            
            logger.info(f"📄 Archivo encontrado: {file_metadata.get('name')}")
            logger.info(f"   - ID: {file_metadata.get('id')}")
            logger.info(f"   - En papelera: {file_metadata.get('trashed', False)}")
            logger.info(f"   - MIME: {file_metadata.get('mimeType')}")

            
            file_info = self.service.files().get(
                fileId=file_id,
                supportsAllDrives=True,
                fields='id, name, capabilities, owners, permissions'
            ).execute()
            
            logger.info(f"📄 Archivo: {file_info.get('name')}")
            logger.info(f"🔐 Capabilities: {file_info.get('capabilities', {})}")
            
            # Verificar si tiene permiso de eliminación
            can_delete = file_info.get('capabilities', {}).get('canDelete', False)
            logger.info(f"🗑️ ¿Puede eliminar? {can_delete}")
            
            if not can_delete:
                logger.error("❌ No tiene permisos para eliminar este archivo")
                return False

        except HttpError as error:
            if error.resp.status == 404:
                logger.error(f"❌ Archivo no encontrado con GET: {file_id}")
                # Intentar con supportsAllDrives
                try:
                    file_metadata = self.service.files().get(
                        fileId=file_id,
                        supportsAllDrives=True,
                        fields='id, name'
                    ).execute()
                    logger.info(f"✅ Archivo encontrado con supportsAllDrives: {file_metadata.get('name')}")
                except HttpError as e:
                    logger.error(f"❌ Error con supportsAllDrives: {e}")
                    return False
            else:
                logger.error(f"❌ Error obteniendo archivo {file_id}: {error}")
                return False
 
        try:
             logger.info(f"Eliminando archivo de Drive: {file_id}")
             self.service.files().delete(fileId=file_id, 
                                         supportsAllDrives=True ).execute()
             logger.info(f"✅ Archivo eliminado de Google Drive: {file_id}")
             return True
           
                
        except HttpError as error:
            if error.resp.status == 404:
                logger.warning(f"⚠️ Archivo no encontrado en Google Drive: {file_id}")
                # Considerar como éxito si ya no existe en Drive
                return False
            logger.error(f"❌ Error eliminando archivo {file_id}: {error}")
            return False
        except Exception as error:
            logger.error(f"❌ Error inesperado eliminando {file_id}: {error}")
            return False



    def find_subfolder_by_name(self, folder_name: str, parent_folder_id: Optional[str] = None) -> Optional[Dict]:
        """
        Busca una carpeta por nombre en un directorio específico.
        
        Args:
            folder_name: Nombre de la carpeta a buscar
            parent_folder_id: ID de la carpeta padre (opcional)
            
        Returns:
            Dict con la información de la carpeta si existe, None si no
        """
        try:
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"

            if parent_folder_id:
                query += f" and '{parent_folder_id}' in parents"

            logger.info(f"🔎 consultando: {query}")

            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields="files(id, name, parents)",
                pageSize=10,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                # Si hay múltiples, retornar el primero
                logger.info(f"🔔 existe carpeta con el mismo nombre")
                return files[0]
            return None
            
        except Exception as e:
            logging.error(f"Error al buscar carpeta '{folder_name}': {str(e)}")
            return None
    