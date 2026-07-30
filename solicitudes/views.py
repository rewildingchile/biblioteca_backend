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
from .models import UserRequest

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
        # Diccionario con comillas 
        f = {
            'area': area_id,
            'pendiente': True
        }  
        if request.user.id != 2:
            f['user'] = request.user.id  # Agregar clave al diccionario correctamente


        solicitudes = UserRequest.objects.filter(**f)  # Desempaquetar el diccionario con **
        try:
           
            solicitud = solicitudes.first()
            if solicitud:
                lstSolicitudes = ordenar_user_request( f)
            else:   
                lstSolicitudes = []
        except UserRequest.DoesNotExist:
                lstSolicitudes = []        
        return Response(lstSolicitudes)    



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
        .select_related('type_action_request')
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
            'pendiente': ur.pendiente,
            'type_action_request_nombre': ur.type_action_request.nombre if ur.type_action_request else None,
            'drive_name': drive_file.name if drive_file else None,
            'drive_mime_type': drive_file.mime_type if drive_file else None,
            'parent_name': drive_file.parent_drive_file_id.name if drive_file and drive_file.parent_drive_file_id else None,
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