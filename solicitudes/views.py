from django.shortcuts import render

# Create your views here.


from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics
from rest_framework import serializers
from django.http import Http404
from backend.constants import ActionType
import datetime
from django.utils import timezone
from .models import UserRequest
from .models import GoogleDriveFile
from solicitudes.models import UserRequest
from maestros.models import Area, UsuarioArea
from services.gdrive.google_service import GoogleDriveService
from django.db import transaction
import logging
# Estos loggers ya están configurados en settings
logger = logging.getLogger("services")



class CancelUserRequest(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
        if not request.user.id:
                    return Response(
                        {"error": "identificacion usuario es requerida"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        user=request.user
        request_id = request.data.get('request_id')
        if not request_id:
            return Response(
                        {"error": "identificacion request user requerida"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
     
        # Verificar que la solicitud existe y pertenece al usuario
        try:
            user_request = UserRequest.objects.get(id=request_id)
            
            # Verificar que la solicitud pertenece al usuario actual
            if user_request.user.id != request.user.id:
                return Response(
                    {"error": "No tienes permiso para cancelar esta solicitud"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Verificar que la solicitud no esté ya anulada
            if user_request.anulado:
                return Response(
                    {"error": "Esta solicitud ya fue anulada anteriormente"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Actualizar el campo anulado
            user_request.anulado = True
            user_request.pendiente = False
            user_request.save(update_fields=['anulado','pendiente'])  # Solo actualiza este campo
            
            return Response({
                "status": 200,
                "success": "Solicitud anulada correctamente",
                "request_id": str(request_id)
            }, status=status.HTTP_200_OK)
            
        except UserRequest.DoesNotExist:
            return Response(
                {"error": "La solicitud no existe"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error al anular la solicitud: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
         
      
         
class DeleteUserRequest(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
        if not request.user.id:
                    return Response(
                        {"error": "identificacion usuario es requerida"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        user=request.user
        request_id = request.data.get('request_id')
        if not request_id:
            return Response(
                        {"error": "identificacion request user requerida"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
     
        # Verificar que la solicitud existe y 1) pertenece al usuario 2) no haya sido ejecutada por el admin 
        try:
            user_request = UserRequest.objects.get(id=request_id, pendiente=True)
 
            area_id = user_request.area_id  # o como sea que obtengas el área

            if not request.user.usuarioarea_set.filter(area_id=area_id, rol_id=1).exists():
                # Verificar que la solicitud pertenece al usuario actual
                if user_request.user.id != request.user.id:
                    return Response(
                        {"error": "No tienes permiso para cancelar esta solicitud"},
                        status=status.HTTP_403_FORBIDDEN
                        )
             
            ''' 
            1) borrar solicitudes.UserRequest
            2) borrar google_drive.GoogleDriveFile
            3) borrar archivo en unidad compartida (si es solicitud.pendiente ==True, 
               folder debe ser la temporal)
            '''
            drive_file_id=user_request.drive_file_id
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

                    try:
                        if user_request:   

                            user_request.delete()    
    
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
                        return Response({
                                            'error': f'solicitud no encontrada {str(e)}'
                                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                     
             
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
             
            #-----------------------------------------------------------------------------------------
            
            return Response({
                "status": 200,
                "success": "Solicitud borrada correctamente",
                "request_id": str(request_id)
            }, status=status.HTTP_200_OK)
            
        except UserRequest.DoesNotExist:
            return Response(
                {"error": "La solicitud no existe o ya fue ejecutada"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error al anular la solicitud: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
         
      
         
class UserRequestFileRename(APIView):
 def post(self, request):
     return Response(
                    {"error": "identificacion usuario es requerida"},
                    status=status.HTTP_400_BAD_REQUEST
                )


class PostUserRequest(APIView):
    authentication_classes = [JWTAuthentication]
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):

        # request.user.id    
        if not request.user.id:
            return Response(
                {"error": "identificacion usuario es requerida"},
                status=status.HTTP_400_BAD_REQUEST
            )
        user=request.user

        area_id = request.data.get('area_id')
        if not area_id:
            return Response(
                        {"error": "identificacion area requerida"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        area = Area.objects.get(id=area_id)

        drive_file_id = request.data.get('drive_file_id')
        if not drive_file_id:
            return Response(
                        {"error": "identificacion archivo  requerida"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        accion_label = request.data.get('accion_label')
        if not accion_label:
            return Response(
                        {"error": "identificacion accion  requerida"},
                        status=status.HTTP_400_BAD_REQUEST
                    )



 
      
        new_name = ''
        if accion_label == ActionType.RENAME.label:
               accion_id = ActionType.RENAME.value
               new_name = request.data.get('new_name')
               if not new_name:
                            return Response(
                                        {"error": "identificacion nuevo nombre es  requerida"},
                                        status=status.HTTP_400_BAD_REQUEST
                                    )
        if accion_label == ActionType.DELETE.label:
               accion_id = ActionType.DELETE.value
                
        googledrivefile=    GoogleDriveFile.objects.get(drive_file_id=drive_file_id)  
        folder_parent=   str(googledrivefile.parent_drive_file_id.drive_file_id)  # Si existe padre
        UserRequest.objects.update_or_create(
            drive_file_id= drive_file_id,
            defaults={
                "area": area,
                "user": user,
                "name":  googledrivefile.name,
                "mime_type": googledrivefile.mime_type ,
                "folder_origin_id": folder_parent,
                "googledrivefile_folder_origin": googledrivefile.parent_drive_file_id,
                "folder_final_id":  folder_parent,
                "googledrivefile_folder_final": googledrivefile.parent_drive_file_id,
                "googledrivefile_drive_file": googledrivefile,
                "drive_web_view_link": googledrivefile.drive_web_view_link  ,
                "last_synced_at": timezone.now(),
                "type_action_request_id": accion_id,
                "new_name": new_name                                                  
            })     
              
        return Response({
                "status": 200,
              
                "success":"solicitud enviada"     
        }, status=status.HTTP_200_OK)
 



class ListUserRequest(APIView):

    authentication_classes = [JWTAuthentication]

    permission_classes = [IsAuthenticated]

    def post(self, request):

        # request.user.id    
        if not request.user.id:
            return Response(
                {"error": "identificacion usuario es requerida"},
                status=status.HTTP_400_BAD_REQUEST
            )

        area_id = request.data.get('area_id')
        try:
            area = Area.objects.get(id=area_id)
            if not area:
                return Response({
                    'error': 'no existe area'
                 }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
                            logger.error(f"error al leer area: {e}")
                            return Response({
                                'error': 'error al leer area'
                            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            usuarioarea = UsuarioArea.objects.filter(area=area, user=request.user).first()
            if not usuarioarea:
                        return Response({
                            'error': 'no existe usuarioarea'
                         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)    
            rol = usuarioarea.rol.id
        except Exception as e:
                            logger.error(f"error UsuarioArea: {e}")
                            return Response({
                                'error': f"error UsuarioArea: {e}"
                            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        f = {
            'pendiente': True,
            'anulado':False
        }  

        ''' 
         Si user pertenece a rol 'manager', puede ver las todas las solicitudes de mi area.
        '''

        if rol != 1:
            f['user'] = request.user.id  # Agregar clave al diccionario correctamente

        f['area_id'] = area_id  #  

        solicitudes = UserRequest.objects.filter(**f)  # Desempaquetar el diccionario con **
        try:
           
            solicitud = solicitudes.first()
            if solicitud:
                lstSolicitudes = ordenar_user_request( f)
            else:   
                lstSolicitudes = []
        except UserRequest.DoesNotExist:
                lstSolicitudes = []        
        return Response({'area':area.nombre, 'solicitudes': lstSolicitudes})    



import json
from datetime import datetime
 
from django.db.models import Subquery, OuterRef, Exists, Q, BooleanField, Value
from django.db.models.functions import Coalesce
from django.db.models import  Value, CharField
from django.db.models import Prefetch
from googledrive.models import GoogleDriveFile
def parse_fecha(fecha_str):
    """Parsear fecha ISO 8601 con manejo de errores"""
    if not fecha_str:
        return datetime.min
    
    try:
        # Si es string, procesarlo
        if isinstance(fecha_str, str):
            return datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
        # Si ya es datetime, devolverlo
        elif isinstance(fecha_str, datetime):
            return fecha_str
        else:
            return datetime.min
    except (ValueError, AttributeError, TypeError):
        return datetime.min

def ordenar_por_fecha(arr):
    return sorted(arr, key=lambda x: parse_fecha(x['last_synced_at']), reverse=True)

def ordenar_user_request(f):
    
    '''
    result = (
    UserRequest.objects
    .filter(**f)
    .values(
        "last_synced_at",
        "id",
        "drive_file_id",
        "name",
        "mime_type",
        "type_action_request",
        "folder_origin_id", 
        "folder_final_id",         
        "pendiente",
    ).order_by('last_synced_at')
    )'''

    # Obtener los UserRequest con relaciones
    user_requests = (
        UserRequest.objects
        .filter(**f)
        .select_related('type_action_request','googledrivefile_folder_origin','googledrivefile_folder_final','user')
        .order_by('last_synced_at')
    )

    # Obtener todos los GoogleDriveFile relacionados de una vez
    drive_files = GoogleDriveFile.objects.filter(
        drive_file_id__in=[ur.drive_file_id for ur in user_requests]
    ).select_related('parent_drive_file_id')

    # Crear un diccionario para acceso rápido
    drive_files_dict = {df.drive_file_id: df for df in drive_files}

    # Construir el resultado
    result = []
    for ur in user_requests:
        drive_file = drive_files_dict.get(ur.drive_file_id)
        result.append({
            'last_synced_at': ur.last_synced_at,
            'id': ur.id,
            'drive_file_id': ur.drive_file_id,
            'name': ur.name,
            'mime_type': ur.mime_type,
            'folder_origin_id': ur.folder_origin_id,
            'folder_final_id': ur.folder_final_id,
            'new_name': ur.new_name,
            'googledrivefile_folder_origin_name': ur.googledrivefile_folder_origin.name if ur.googledrivefile_folder_origin else None,
            'googledrivefile_folder_final_name': ur.googledrivefile_folder_final.name if  ur.googledrivefile_folder_final else None,
            'pendiente': ur.pendiente,
            'type_action_request_id': ur.type_action_request.id if ur.type_action_request else None,
            'type_action_request_nombre': ur.type_action_request.nombre if ur.type_action_request else None,
            'drive_name': drive_file.name if drive_file else None,
            'drive_mime_type': drive_file.mime_type if drive_file else None,
            'parent_name': drive_file.parent_drive_file_id.name if drive_file and drive_file.parent_drive_file_id else None,
            'user_name': str(ur.user.first_name) + " " +  str(ur.user.last_name),
            'area': str(ur.area.nombre) ,
        })
    
    
    # Separar y ordenar
    carpetas = ordenar_por_fecha([x for x in result if 'folder' in x.get('mime_type', '')])
    archivos = ordenar_por_fecha([x for x in result if 'folder' not in x.get('mime_type', '')])

    # Agrupar archivos por carpeta
    archivos_por_carpeta = {}
    for archivo in archivos:
        key = archivo.get('folder_origin_id')
        if key:
            archivos_por_carpeta.setdefault(key, []).append(archivo)

    # Ordenar archivos dentro de cada carpeta
    for key in archivos_por_carpeta:
        archivos_por_carpeta[key] = ordenar_por_fecha(archivos_por_carpeta[key])

    # IDs de carpetas existentes
    drive_ids_carpetas = {c.get('drive_file_id') for c in carpetas if c.get('drive_file_id')}

    # Construir jerarquía
    jerarquia = []

    # Agregar carpetas con hijos
    for carpeta in carpetas:
        carpeta_id = carpeta.get('drive_file_id')
        if carpeta_id:
            jerarquia.append({
                'carpeta': carpeta,
                'children': archivos_por_carpeta.get(carpeta_id, [])
            })

    # Agregar archivos huérfanos
    for archivo in archivos:
        folder_origin = archivo.get('folder_origin_id')
        if folder_origin and folder_origin not in drive_ids_carpetas:
            jerarquia.append({
                'archivo': archivo,
                'children': []
            })

    # ORDENAR TODA LA JERARQUÍA POR last_synced_at
    # Esto asegura que TODOS los elementos (carpetas y archivos) 
    # estén ordenados globalmente por fecha
    def obtener_fecha_objeto(item):
        # Obtener fecha del elemento principal (carpeta o archivo)
        if 'carpeta' in item:
            fecha = item['carpeta'].get('last_synced_at')
        elif 'archivo' in item:
            fecha = item['archivo'].get('last_synced_at')
        else:
            fecha = None
        return parse_fecha(fecha)

    # Ordenar la jerarquía completa por fecha (más reciente primero)
    jerarquia.sort(key=obtener_fecha_objeto, reverse=False)

    return jerarquia

    # Imprimir resultado bonito
    #print(json.dumps(jerarquia, indent=2, default=str, ensure_ascii=False))