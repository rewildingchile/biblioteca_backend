from django.shortcuts import render
 

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics
from rest_framework import serializers
from django.http import Http404

from .serializers import GoogleDriveFileDocumentSerializer
from .models import GoogleDriveFileDocument

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfReader
import io


import datetime
from django.utils import timezone

from googleapiclient.discovery import build

import logging

logger = logging.getLogger(__name__)











def procesar_archivo(nombre, mime, contenido):
  
    if mime == "application/pdf":

       
        mensaje = f"PDF: {nombre}\n"
       
        if pdf_es_scan(contenido):
            tipo = "PDF escaneado → requiere OCR"
        else:
            tipo = "PDF nativo → texto directo"

        print("PDF detectado:", nombre,tipo)    

    elif mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        print("WORD:", nombre)
        mensaje = f"WORD: {nombre}\n"
       
    else:

        print("Otro tipo:", nombre)
        mensaje = f"OTRO: {nombre}\n"
        

  
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(mensaje)


from services.gdrive.tasks import sync_full_task
class SyncFullView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
       
        logger.info( f" {logger.name} : llamando->sync_full_task")
        # la vista dispara el proceso Y la tarea pesada corre aparte:

        # delay() retorna un objeto AsyncResult.
        area_id=1
        task = sync_full_task.delay(area_id)
        
        logger.info(f"TAREA CELERY ID: {task.id}")
            
        return Response({
                    "status": 200,
                    "task_id": task.id
                }, status=status.HTTP_200_OK)


from services.gdrive.tasks import sync_changes_task
class SyncChangesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
       
        logger.info( f" {logger.name} : llamando->sync_changes_task")
        # la vista dispara el proceso Y la tarea pesada corre aparte:

        # delay() retorna un objeto AsyncResult.
        area_id=1
        task = sync_changes_task.delay(area_id)
        
        logger.info(f"TAREA CELERY ID: {task.id}")
            
        return Response({
                    "status": 200,
                    "task_id": task.id
                }, status=status.HTTP_200_OK)

from celery.result import AsyncResult
class DriveSyncStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request,task_id):
       
      logger.info( f" {logger.name} : consultando status sincronizacion")
      task_result = AsyncResult(task_id)

      response = {
            "task_id": task_id,
            "status": task_result.status,
            "result": task_result.result
      }

      return Response(response)

class FileDocumentView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        file_id = request.data.get("file_id")
       
        logger.info( f" {logger.name} : consultando datos filedocument")
      
        '''Obtén un GoogleDriveFileDocument cuyo GoogleDriveFile relacionado tenga drive_file_id = "1" 
        y trae ambos objetos en una sola query SQL”.'''

        existe=  GoogleDriveFileDocument.objects.filter(
            file__drive_file_id=file_id
        ).exists()
        if existe:
            try:
                documento=GoogleDriveFileDocument.objects.select_related( "file" ).get(  file__drive_file_id= file_id) 
            except GoogleDriveFileDocument.DoesNotExist:
                                    documento = None

            serializer = GoogleDriveFileDocumentSerializer(
                documento
            )

            return Response(serializer.data)
        else:
            return Response({"status":404})
        

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from services.gdrive.tree_service import obtener_arbol_area
import os

class DriveTreeView(APIView):

    authentication_classes = [JWTAuthentication]

    permission_classes = [IsAuthenticated]

    def get(self, request, area_id):

        tree = obtener_arbol_area(area_id)

        return Response(tree)    
    


    
class FileDocumentContentView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
            
        file_id = request.data.get('file_id')
        content = request.data.get('content')
        
        if not file_id or not content:
            return Response(
                {"error": "file_id y content son requeridos"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            obj, created = GoogleDriveFileDocument.objects.update_or_create(
                file_id=file_id,
                defaults={
                    "text_content": content,
                },
            )
            if created:
                logger.debug(f"Nuevo: {file_id}  ")
            else:
                logger.debug(f"Actualizado: {file_id}  ")

           

        except Exception as e:
            logger.exception(f"Error guardando {file_id} : {e}")


        return Response({
                "status": 200,
                "message": "hola!",
                
            }, status=status.HTTP_200_OK)
    
# views.py

class PrepareUploadView(APIView):
    """
    Endpoint para preparar la estructura de carpetas ANTES de subir archivos
    Esto evita crear la misma carpeta múltiples veces
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        folder_id = request.data.get('folder_id')
        relative_path = request.data.get('relative_path', '')
        
        if not folder_id:
            return Response(
                {'error': 'Se requiere folder_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            google_drive = GoogleDriveService()  # Singleton
            
            if relative_path:
                final_folder_id = google_drive.create_folder_structure(
                    folder_id, 
                    relative_path
                )
            else:
                final_folder_id = folder_id
            
            return Response({
                'success': True,
                'folder_id': final_folder_id,
                'relative_path': relative_path
            })
            
        except Exception as e:
            logger.error(f"Error preparando carpeta: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

from services.gdrive.google_service import GoogleDriveService
class FileDocumentUpload(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    MAX_FILE_SIZE = 100 * 1024 * 1024
    ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.xls', 
                          '.xlsx', '.txt', '.zip', '.mp4', '.mp3', '.ppt', '.pptx']
    
    def post(self, request):
        """
        Sube archivo directamente a Google Drive
        """
        # ✅ SINGLETON - misma instancia para todos los requests
        google_drive = GoogleDriveService()  # ¡Siempre devuelve la misma instancia!
        
        # Validar archivo
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'error': 'No se proporcionó ningún archivo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar tamaño
        if uploaded_file.size > self.MAX_FILE_SIZE:
            return Response(
                {'error': f'El archivo excede el tamaño máximo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar extensión
        from pathlib import Path
        file_extension = Path(uploaded_file.name).suffix.lower()
        if file_extension not in self.ALLOWED_EXTENSIONS:
            return Response(
                {'error': f'Tipo de archivo no permitido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        relative_path = request.POST.get('relativePath', '')
        folder_id = request.POST.get('folder_id')
        
        if not folder_id:
            return Response(
                {'error': 'Se requiere folder_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # ✅ Esto ahora es thread-safe y con caché
            if relative_path:
                final_parent_id = google_drive.create_folder_structure(
                    folder_id, 
                    relative_path
                )
            else:
                final_parent_id = folder_id
            
            # Subir archivo
            import io
            file_obj = io.BytesIO(uploaded_file.read())
            
            drive_file = google_drive.upload_file(
                file_obj=file_obj,
                filename=uploaded_file.name,
                parent_folder_id=final_parent_id,
                mime_type=uploaded_file.content_type,
                chunk_size=10 * 1024 * 1024
            )
            
            return Response({
                'success': True,
                'message': 'Archivo subido exitosamente',
                'file': {
                    'name': drive_file['name'],
                    'size': drive_file['size'],
                    'web_link': drive_file['web_view_link'],
                    'drive_id': drive_file['file_id']
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error en upload: {str(e)}", exc_info=True)
            return Response({
                'error': f'Error al subir archivo: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class deprec_FileDocumentUpload(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB (Google Drive gratis permite hasta 5TB)
    ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.xls', 
                          '.xlsx', '.txt', '.zip', '.mp4', '.mp3', '.ppt', '.pptx']
    

    
    def post(self, request):
        """
        Sube archivo directamente a Google Drive
        """

        # Inicializar servicio (singleton)
        google_drive = GoogleDriveService()

        # Validar archivo
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'error': 'No se proporcionó ningún archivo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar tamaño
        if uploaded_file.size > self.MAX_FILE_SIZE:
            return Response(
                {'error': f'El archivo excede el tamaño máximo de {self.MAX_FILE_SIZE // (1024*1024)} MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar extensión
        from pathlib import Path
        file_extension = Path(uploaded_file.name).suffix.lower()
        if file_extension not in self.ALLOWED_EXTENSIONS:
            return Response(
                {'error': f'Tipo de archivo no permitido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        relative_path = request.POST.get('relativePath', '')
        
        try:
            # 1. Obtener o crear carpeta del usuario
            folder_id =  request.POST.get('folder_id')
            """ user_folder_id = google_drive.get_or_create_user_folder(
                request.user.id, 
                request.user.email
            ) """
            # 2. Crear estructura de carpetas si es necesario
            if relative_path:
                print(f"📁 CREAR NUEVA CARPETA")
                final_parent_id = google_drive.create_folder_structure(
                    folder_id, 
                    relative_path
                )
            else:
                final_parent_id = folder_id
            
            # 3. Preparar el archivo para subida
            # Convertir Django UploadedFile a un objeto file-like
            file_obj = io.BytesIO(uploaded_file.read())
            
            # 4. Subir a Google Drive
            drive_file = google_drive.upload_file(
                file_obj=file_obj,
                filename=uploaded_file.name,
                parent_folder_id=final_parent_id,
                mime_type=uploaded_file.content_type,
                chunk_size=10 * 1024 * 1024  # 10 MB chunks
            )
            
            # 5. Guardar referencia en tu base de datos local
            '''user_file = UserFile.objects.create(
                user=request.user,
                google_drive_file_id=drive_file['file_id'],
                original_filename=uploaded_file.name,
                file_size=uploaded_file.size,
                relative_path=relative_path,
                mime_type=uploaded_file.content_type,
                web_view_link=drive_file['web_view_link'],
                uploaded_at=datetime.now()
            )'''
            
            return Response({
                'success': True,
                'message': 'Archivo subido exitosamente a Google Drive',
                'file': {
                    #'id': user_file.id,
                    'name': drive_file['name'],
                    'size': drive_file['size'],
                    'web_link': drive_file['web_view_link'],
                    'drive_id': drive_file['file_id']
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error en upload: {str(e)}")
            return Response({
                'error': f'Error al subir archivo: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
