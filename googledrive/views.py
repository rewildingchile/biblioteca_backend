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
from .models import GoogleDriveFile
from solicitudes.models import UserRequest
from maestros.models import Area

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfReader
import io

import datetime
from django.utils import timezone
from django.db import transaction
from googleapiclient.discovery import build
from maestros.models import UsuarioArea

import base64
import mimetypes

import logging
 
# Estos loggers ya están configurados en settings
 
logger = logging.getLogger("services")










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

    def get(self, request, area_id ,*args, **kwargs):
       
        logger.info( f" {logger.name} : llamando->sync_full_task")
        # la vista dispara el proceso Y la tarea pesada corre aparte:

        # delay() retorna un objeto AsyncResult.
      
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

    def get(self, request, area_id, *args, **kwargs):
       
        logger.info( f" {logger.name} : llamando->sync_changes_task")
        # la vista dispara el proceso Y la tarea pesada corre aparte:

        # delay() retorna un objeto AsyncResult.
         
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
        

 
from services.gdrive.tree_service import obtener_arbol_area, obtener_arbol_subfolder


import os

class DriveTreeView(APIView):

    authentication_classes = [JWTAuthentication]

    permission_classes = [IsAuthenticated]

    def get(self, request, area_id):

        # request.user.id    
        if not request.user.id:
            return Response(
                {"error": "identificacion usuario es requerida"},
                status=status.HTTP_400_BAD_REQUEST
            )
        areas = UsuarioArea.objects.filter(user_id=request.user.id)    
        try:
            logger.info(areas)
            area = areas.first()
            if area:
                tree = obtener_arbol_area(area_id)
            else:   
                tree = []
        except UsuarioArea.DoesNotExist:
                tree = []        
        return Response(tree)    
    
class DriveTreeFolderView(APIView):    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request,folder_id):
        tree = obtener_arbol_subfolder(folder_id)
        return Response(tree)    
    
from services.gdrive.search import buscar_tokens,search_google_drive_files_ranked,GoogleDriveSearchService    
class  SearchView (APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
        tokens = request.data.get('tokens')
        #result = buscar_tokens(tokens)
        result=search_google_drive_files_ranked(tokens)
        #result = GoogleDriveSearchService.execute_as_json_ready(tokens)
        return  result   
    
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
                logger.info(f"Nuevo: {file_id}  ")
            else:
                logger.info(f"Actualizado: {file_id}  ")

           

        except Exception as e:
            logger.exception(f"Error guardando {file_id} : {e}")


        return Response({
                "status": 200,
                "message": "hola!",
                
            }, status=status.HTTP_200_OK)
    
class FileDocumentDescriptionView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
            
        file_id = request.data.get('file_id')
        description = request.data.get('description')
        
        if not file_id or not description:
            return Response(
                {"error": "file_id y descrip son requeridos"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            obj, created = GoogleDriveFileDocument.objects.update_or_create(
                file_id=file_id,
                defaults={
                    "description": description,
                },
            )
            if created:
                logger.info(f"Nuevo: {file_id}  ")
            else:
                logger.info(f"Actualizado: {file_id}  ")

           

        except Exception as e:
            logger.exception(f"Error guardando {file_id} : {e}")


        return Response({
                "status": 200,
                "message": "hola!",
                
            }, status=status.HTTP_200_OK)
    
class PrepareUploadView(APIView):
    """
    Endpoint para preparar la estructura de carpetas ANTES de subir archivos
    Esto evita crear la misma carpeta múltiples veces
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user=request.user
      
        
        relative_path                = request.data.get('relative_path', '')
        area_id                      = request.data.get('area_id')
        folder_destino_selec_by_user = ""

        # folder_id: (en que folder se prepara esta carpeta)
        folder_id  = request.data.get('folder_id')
        folder_destino_en_biblioteca= folder_id

        if not folder_id:
            return Response(
                {'error': 'Se requiere folder_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        area = Area.objects.get(id=area_id)
        upload_granted = True
       
       

        if user.id == 4:
             upload_granted=False 
        
                 


        #------------------------------------------
        # si no tiene permiso de Manager
        # folder_id: será la carpeta temporal
        if upload_granted is False:
                folder_id = area.temporal_folder_id 
        #-------------------------------------------
        
        try:
            google_drive = GoogleDriveService() 




            
            if relative_path:
                existing_folder = google_drive.find_subfolder_by_name(relative_path, folder_id)
                        
                if existing_folder:
                                # Si existe, crear un nombre con timestamp
                                from datetime import datetime
                                timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
                                new_folder_name = f"{relative_path}_{timestamp}"
                                
                                # Crear la carpeta con el nuevo nombre
                                obj = google_drive.create_folder_structure(
                                    folder_id,
                                    new_folder_name
                                )
                                folder_container_id = obj['file_id']
                            
                else:
                                
                                #------------------------------------------------
                                obj = google_drive.create_folder_structure(
                                    folder_id, 
                                    relative_path
                                )
                                folder_container_id=obj['file_id']
                                #-----------------------------------------------
            else:
                folder_container_id = folder_id

            parent_obj = GoogleDriveFile.objects.filter(drive_file_id=obj["parent_folder_id"]).first() 
            d={
                        "area": area,
                        "name": obj['name'],
                        "mime_type": obj['mime_type'],
                        "parent_drive_file_id": parent_obj,  # Django ORM acepta instancia para ForeignKey
                        "drive_web_view_link": obj['web_view_link']  ,
                        "last_synced_at": timezone.now(),
                       
            }
            if upload_granted == False:
                 d['hidden']=True
                 
            GoogleDriveFile.objects.update_or_create(
                    drive_file_id=folder_container_id,
                    defaults=d)


            data_response={
                                        'success': True,
                                        'folder_id': folder_container_id,
                                        'relative_path': relative_path
            }
           
            if upload_granted is False:
                try:
                    folder_destino_selec_by_user=folder_id
                    data_response['folder_destino_selec_by_user']=folder_destino_selec_by_user
                    googledrivefile_folder_origin= GoogleDriveFile.objects.get(drive_file_id=folder_id) 
                    googledrivefile_folder_final= GoogleDriveFile.objects.get(drive_file_id=folder_destino_en_biblioteca) 

                    googledrivefile_drive_file=    GoogleDriveFile.objects.get(drive_file_id=obj["file_id"]) 
                    UserRequest.objects.update_or_create(
                                        drive_file_id=obj['file_id'],
                                        defaults={
                                            "area": area,
                                            "user": user,
                                            "name":  obj['name'],
                                            "mime_type": obj['mime_type'] ,
                                            "folder_origin_id": folder_id,
                                            "googledrivefile_folder_origin": googledrivefile_folder_origin,
                                            "folder_final_id":  folder_destino_en_biblioteca,
                                            "googledrivefile_folder_final":  googledrivefile_folder_final, 
                                            "googledrivefile_drive_file":googledrivefile_drive_file,
                                            "drive_web_view_link": obj['web_view_link']   ,
                                            "last_synced_at": timezone.now(),
                                            "type_action_request_id": 1 
                
                                    })    
                except Exception as e:
                            logger.error(f"Error registro USERREQUEST: {folder_id} no existe en googledrivefile {str(e)}")
                            return Response(
                                {'error': str(e)},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR
                            )

            
            return Response(data_response)
            
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
        user    = request.user
        area_id = request.data.get('area_id')
        relative_path   = request.POST.get('relativePath', '')
        folder_id       = request.POST.get('folder_id')

        area    = Area.objects.get(id=area_id)
        
        upload_granted = True
        
        if user.id == 4:
             upload_granted=False
             folder_destino_selec_by_user = request.data.get('folder_destino_selec_by_user')
             if not folder_destino_selec_by_user:
                    # se trata de un file (no folder)
                    folder_destino_selec_by_user = folder_id
                    folder_id = area.temporal_folder_id
            
 
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
            
            # .read() Lee todo el contenido del archivo y devuelve bytes
            # io.BytesIO(...) Crea un archivo virtual en memoria con esos bytes

            drive_file = google_drive.upload_file(
                file_obj=file_obj,
                filename=uploaded_file.name,
                parent_folder_id=final_parent_id,
                mime_type=uploaded_file.content_type,
                chunk_size=10 * 1024 * 1024
            )

        except Exception as e:
            logger.error(f"Error en upload: {str(e)}", exc_info=True)
            return Response({
                'error': f'Error al subir archivo: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
        try:
                parent_obj = None
                if final_parent_id:
                    parent_obj = GoogleDriveFile.objects.filter(drive_file_id=drive_file["parent_folder_id"]).first()
                logger.info(f"parent obj: {parent_obj}")

                

                if upload_granted:
                    GoogleDriveFile.objects.update_or_create(
                        drive_file_id=drive_file['file_id'],
                        defaults={
                            "area": area,
                            "user": user,
                            "name": drive_file['name'],
                            "mime_type": drive_file['mime_type'] ,
                            "parent_drive_file_id": parent_obj,  # Django ORM acepta instancia para ForeignKey
                            "drive_web_view_link": drive_file['web_view_link']  ,
                            "last_synced_at": timezone.now(),
                            
                    })
                else:


                    GoogleDriveFile.objects.update_or_create(
                                            drive_file_id=drive_file['file_id'],
                                            defaults={
                                                "area": area,
                                                "user": user,
                                                "name": drive_file['name'],
                                                "mime_type": drive_file['mime_type'] ,
                                                "parent_drive_file_id": parent_obj,  # Django ORM acepta instancia para ForeignKey
                                                "drive_web_view_link": drive_file['web_view_link']  ,
                                                "last_synced_at": timezone.now(),
                                                "hidden":True
                    })    
                    googledrivefile_drive_file=    GoogleDriveFile.objects.get(drive_file_id=drive_file['file_id']) 
                    googledrivefile_folder_final =  GoogleDriveFile.objects.get(drive_file_id=folder_destino_selec_by_user) 
                    UserRequest.objects.update_or_create(
                        drive_file_id=drive_file['file_id'],
                        defaults={
                            "area": area,
                            "user": user,
                            "name": drive_file['name'],
                            "mime_type": drive_file['mime_type'] ,
                            "folder_origin_id": final_parent_id,
                            "folder_final_id":  folder_destino_selec_by_user,  # Django ORM acepta instancia para ForeignKey
                            "googledrivefile_folder_final": googledrivefile_folder_final,
                            "drive_web_view_link": drive_file['web_view_link']  ,
                            "last_synced_at": timezone.now(),
                            "type_action_request_id": 1,
                            "googledrivefile_drive_file": googledrivefile_drive_file

                    })       


                data_response = {
                                'success': True,
                                'message': 'Archivo subido exitosamente',
                                'file': {
                                    'name': drive_file['name'],
                                    'size': drive_file['size'],
                                    'web_link': drive_file['web_view_link'],
                                    'drive_id': drive_file['file_id']
                                }
                }
                

                             
        except Exception as e:
                logger.error(f"Error grabando registro GoogleDriveFile: {e}")    
                return Response({
                'error': f'Error grabando registro file: {str(e)}'
                } , status=status.HTTP_500_INTERNAL_SERVER_ERROR)  
          
        return Response(data_response, status=status.HTTP_201_CREATED)
            


class old_FileDocumentUpload(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    MAX_FILE_SIZE = 100 * 1024 * 1024
    ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.xls', 
                          '.xlsx', '.txt', '.zip', '.mp4', '.mp3', '.ppt', '.pptx']
    
    def post(self, request):
        """
        Sube archivo directamente a Google Drive
        payload:
        file: (binary)
        folder_id: 1KvNiZ9Kc7HkN_1BafHvgm5FD6ZmNlt76
        area_id: 2
        """
        user=request.user
        area_id=request.data.get('area_id')
        area = Area.objects.get(id=area_id)
        folder_id = request.POST.get('folder_id')
        if not folder_id:
            return Response(
                {'error': 'Se requiere folder_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

      

       
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
        
        
        try:

            '''
                    Si el usuario es editor:
                    revisar sus permisos
            
                    sino tiene permisos, se crea registro UserRequest

                    folder_id pasa a ser el ID_CARPETA_TEMPORAL del area del usuario.  
            '''    
            upload_granted = True

            area  = Area.objects.get(id=area_id)
            

            
            if relative_path:
                    final_parent_id = google_drive.create_folder_structure(
                        folder_id, 
                        relative_path
                    )
                
            
            # Subir archivo
            import io
            file_obj = io.BytesIO(uploaded_file.read()) 
            
            # .read() Lee todo el contenido del archivo y devuelve bytes
            # io.BytesIO(...) Crea un archivo virtual en memoria con esos bytes

            drive_file = google_drive.upload_file(
                file_obj=file_obj,
                filename=uploaded_file.name,
                parent_folder_id=final_parent_id,
                mime_type=uploaded_file.content_type,
                chunk_size=10 * 1024 * 1024
            )

        except Exception as e:
            logger.error(f"Error en upload: {str(e)}", exc_info=True)
            return Response({
                'error': f'Error al subir archivo: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
        try:
                parent_obj = None
                if final_parent_id:
                        parent_obj = GoogleDriveFile.objects.filter(drive_file_id=drive_file["parent_folder_id"]).first()
                logger.info(f"parent obj: {parent_obj}")    

                if upload_granted:

                    GoogleDriveFile.objects.update_or_create(
                        drive_file_id=drive_file['file_id'],
                        defaults={
                            "area": area,
                            "user": user,
                            "name": drive_file['name'],
                            "mime_type": drive_file['mime_type'] ,
                            "parent_drive_file_id": parent_obj,  # Django ORM acepta instancia para ForeignKey
                            "drive_web_view_link": drive_file['web_view_link']  ,
                            "last_synced_at": timezone.now(),
                    })
                else:
                    UserRequest.objects.update_or_create(
                        drive_file_id=drive_file['file_id'],
                        defaults={
                            "area": area,
                            "user": user,
                            "name": drive_file['name'],
                            "mime_type": drive_file['mime_type'] ,
                            "folder_origin_id": final_parent_id,
                            "folder_final_id":  folder_id,  # Django ORM acepta instancia para ForeignKey
                            "drive_web_view_link": drive_file['web_view_link']  ,
                            "last_synced_at": timezone.now(),
                            "type_action_request_id": 1

                    })

        except Exception as e:
                logger.error(f"Error grabando registro GoogleDriveFile: {e}")    
                return Response({
                'error': f'Error grabando registro file: {str(e)}'
                } , status=status.HTTP_500_INTERNAL_SERVER_ERROR)  
          
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
            

class FileDocumentDelete(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self,request):
        drive_file_id = request.data.get('drive_file_id')
        
      
        if not  drive_file_id:
             return Response({
                  'error':'drive_file_id requerido',
                  'detail':'proporcione drive_file_id del archivo a eliminar'
             },status=status.HTTP_400_BAD_REQUEST)
      
        # Verificar si existe en BD antes de eliminar
        try:
            file_record = GoogleDriveFile.objects.filter(drive_file_id=drive_file_id).first()
            if not file_record:
                return Response({
                    'error': f'Archivo con ID {drive_file_id} no encontrado en la base de datos',
                    'detail': 'Verifique que el ID sea correcto'
                }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
                logger.error(f"Error verificando archivo en BD (file id: {drive_file_id} ): {e}")
                return Response({
                    'error': 'Error verificando el archivo en la base de datos (file id: '+str(drive_file_id)+' )'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        google_drive = GoogleDriveService() 
        try:
            if not google_drive.delete_file(drive_file_id):
                return Response({
                    'error': 'No se pudo eliminar el archivo de Google Drive',
                    'detail': 'El archivo id:'+str(drive_file_id)+' podría no existir en Google Drive o no tener permisos'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Error en Google Drive: {e}")
            return Response({
                'error': f'Error en Google Drive: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
        # Eliminar de la base de datos
        try:
              
            with transaction.atomic():
                deleted_count, _ = GoogleDriveFile.objects.filter(
                    drive_file_id=drive_file_id
                ).delete()
                
                if deleted_count == 0:
                    logger.warning(f"No se encontró archivo para eliminar: {drive_file_id}")
                    return Response({
                        'warning': 'El archivo no existía en la base de datos'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                logger.info(f"✅ Archivo eliminado de BD:  ({drive_file_id})")
                
                # ✅ RETORNAR 200 OK, NO 500
                return Response({
                    'success': True,
                    'message': f'Archivo eliminado exitosamente',
                     
                    'drive_file_id': drive_file_id,
                    'deleted_count': deleted_count
                }, status=status.HTTP_200_OK)  # ✅ Código 200 para éxito
                
        except Exception as e:
            logger.error(f"Error en base de datos: {e}")
            return Response({
                'error': f'Error en base de datos: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        except Exception as e:
            logger.error(f"Error en base de datos: {e}")
            # Nota: En este punto el archivo ya se eliminó de Google Drive
            # pero falló la BD, necesitas manejar esta inconsistencia
            return Response({
                'error': 'Error en base de datos, pero el archivo fue eliminado de Google Drive',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ViewDriveFileView(APIView):
    """
    Obtiene un archivo de Google Drive para visualización
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, file_id):
        try:
            google_drive = GoogleDriveService()
            
            # Obtener metadata del archivo
            file_metadata = google_drive.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size',
                supportsAllDrives=True
            ).execute()
            
            # Verificar que sea PDF
            if file_metadata.get('mimeType') != 'application/pdf':
                return Response(
                    {'error': 'El archivo no es un PDF'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Descargar el archivo
            request_download = google_drive.service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            )
            
            # Leer el contenido
            file_content = request_download.execute()
            
            # Convertir a base64 para enviar al frontend
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            
            return Response({
                'success': True,
                'file': {
                    'id': file_metadata.get('id'),
                    'name': file_metadata.get('name'),
                    'mime_type': file_metadata.get('mimeType'),
                    'size': file_metadata.get('size'),
                    'content': file_base64,
                    'content_type': 'application/pdf'
                }
            })
            
        except Exception as e:
            logger.error(f"Error obteniendo archivo {file_id}: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



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
