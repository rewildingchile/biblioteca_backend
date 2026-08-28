from collections import defaultdict

from googledrive.models import GoogleDriveFile
from solicitudes.models import UserRequest

FOLDER_MIME = "application/vnd.google-apps.folder"
import logging
logger = logging.getLogger(__name__)


from collections import defaultdict
 

# Constante para el MIME type de carpetas de Google Drive
FOLDER_MIME = 'application/vnd.google-apps.folder'
from collections import defaultdict
 

# Constante para el MIME type de carpetas de Google Drive
FOLDER_MIME = 'application/vnd.google-apps.folder'

def obtener_arbol_subfolder(folder_id):
    """
    Obtiene todos los objetos (archivos y carpetas) hijos de un folder_id dado,
    incluyendo todos los niveles de profundidad (recursivo).
    
    Args:
        folder_id (str): El ID de Google Drive del folder padre
        
    Returns:
        list: Lista de nodos raíz con toda la estructura de árbol
    """
    
    def obtener_hijos(parent_id):
        """
        Función recursiva para obtener todos los hijos de un folder.
        """
        # Obtener hijos directos del parent_id
        hijos = (
            GoogleDriveFile.objects
            .filter(parent_drive_file_id__drive_file_id=parent_id)
            .select_related("document")
            .values(
                "id",
                "drive_file_id",
                "name",
                "mime_type",
                "parent_drive_file_id",
                "drive_web_view_link",
                "last_known_modified_time",
                "document__text_content",
                "document__description",
            )
        )
        
        resultado = []
        for item in hijos:
            is_folder = item["mime_type"] == FOLDER_MIME
            
            node = {
                "id": str(item["id"]),
                "drive_file_id": item["drive_file_id"],
                "name": item["name"],
                "mime_type": item["mime_type"],
                "size": item["size"],
                "is_folder": is_folder,
                "web_view_link": item["drive_web_view_link"],
                "modified_time": item["last_known_modified_time"].isoformat() if item["last_known_modified_time"] else None,
                "text_content": item.get("document__text_content"),
                "description": item.get("document__description"),
                "parent_drive_file_id": item["parent_drive_file_id"],
                "children": []
            }
            
            # Si es carpeta, obtener sus hijos recursivamente
            if is_folder:
                node["children"] = obtener_hijos(item["drive_file_id"])
            
            resultado.append(node)
        
        return resultado
    
    # Verificar que el folder_id existe
    try:
        root = GoogleDriveFile.objects.get(drive_file_id=folder_id)
    except GoogleDriveFile.DoesNotExist:
        logger.error(f"No se encontró el folder con drive_file_id: {folder_id}")
        return []
    
    # Si el root no es una carpeta, retornar vacío
    if root.mime_type != FOLDER_MIME:
        logger.warning(f"El drive_file_id {folder_id} no es una carpeta")
        return []
    
    # Construir el árbol completo empezando desde la raíz
    root_node = {
        "id": str(root.id),
        "drive_file_id": root.drive_file_id,
        "name": root.name,
        "mime_type": root.mime_type,
        "is_folder": True,
        "web_view_link": root.drive_web_view_link,
        "modified_time": root.last_known_modified_time.isoformat() if root.last_known_modified_time else None,
        "text_content": None,
        "description": None,
        "parent_drive_file_id": None,
        "children": obtener_hijos(folder_id)
    }
    
    return [root_node]

from rest_framework import status
from rest_framework.response import Response
from django.db.models import Subquery, OuterRef, Exists, Q, BooleanField, Value
from django.db.models.functions import Coalesce
from maestros.models import Area, UsuarioArea
from solicitudes.models import UserRequest
from django.contrib.auth.models import User
def obtener_arbol_area(area_id,user_id):
    try:
            area = Area.objects.get(id=area_id)
            user = User.objects.get(id=user_id)
            usuarioarea = UsuarioArea.objects.filter(area=area, user=user).first()
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
            f['user'] = user_id   


    user_request_exists = UserRequest.objects.filter(
            folder_final_id=OuterRef('drive_file_id'),
            **f
        )



    '''user_request_exists = UserRequest.objects.filter(
            folder_final_id=OuterRef('drive_file_id'),
            pendiente=True
        )'''
    
    archivos = ( 
    GoogleDriveFile.objects
    .filter(area_id=area_id, hidden=False)
    .select_related("document")
    .annotate(
                # Columna virtual booleana: True si existe UserRequest que cumpla condiciones
                user_request=Coalesce(
                    Exists(
                        user_request_exists.filter(
                            # Solo para carpetas
                            Q(folder_final_id=OuterRef('drive_file_id')) &
                            Q(pendiente=True)
                        )
                    ),
                    Value(False),
                    output_field=BooleanField()
                ),
              
    )
    .values(
        "id",
        "drive_file_id",
        "name",
        "mime_type",
        "size",
        "parent_drive_file_id",
        "drive_web_view_link",
        "last_known_modified_time",
        "user_request",  # Campo virtual booleano
        # campos relacionados
        "document__text_content",    
        "document__description",       
    ))
     
    nodes = {}

    children_map = defaultdict(list)

    roots = []

    # crear nodos
    for item in archivos:
        user_request_value = item["user_request"] if item["user_request"] else False
                
        node = {

            "id": str(item["id"]),

            "drive_file_id": item["drive_file_id"],

            "name": item["name"],

            "mime_type": item["mime_type"],

            "size": item["size"],

            "is_folder": (
                item["mime_type"] == FOLDER_MIME
            ),
            #"user_request": user_request_value,
            #"web_view_link": item["drive_web_view_link"],

            #"modified_time": item[
            #    "last_known_modified_time"
            #],
            #"text_content": item[
            #                "document__text_content"
            #            ],
            # "description": item[
             #               "document__description"
             #           ],            
            "parent_drive_file_id":item["parent_drive_file_id"]             ,
            "children": []

        }

        nodes[item["drive_file_id"]] = node

        parent = item["parent_drive_file_id"]

        if parent:

            children_map[parent].append(node)

        else:

            roots.append(node)

    # unir hijos
    for drive_id, node in nodes.items():

        node["children"] = children_map.get(
            drive_id,
            []
        )
   
    return roots