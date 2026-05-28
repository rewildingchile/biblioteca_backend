from collections import defaultdict

from googledrive.models import GoogleDriveFile

FOLDER_MIME = "application/vnd.google-apps.folder"


def obtener_arbol_area(area_id):

    archivos = ( 
    GoogleDriveFile.objects
    .filter(area_id=area_id)
    .select_related("document")
    .values(
        "id",
        "drive_file_id",
        "name",
        "mime_type",
        "parent_id",
        "drive_web_view_link",
        "last_known_modified_time",
        # campos relacionados
        "document__text_content",      
    ))
     
    nodes = {}

    children_map = defaultdict(list)

    roots = []

    # crear nodos
    for item in archivos:

        node = {

            "id": str(item["id"]),

            "drive_file_id": item["drive_file_id"],

            "name": item["name"],

            "mime_type": item["mime_type"],

            "is_folder": (
                item["mime_type"] == FOLDER_MIME
            ),

            "web_view_link": item["drive_web_view_link"],

            "modified_time": item[
                "last_known_modified_time"
            ],
            "text_content": item[
                            "document__text_content"
                        ],
            "parent_id":item["parent_id"]             ,
            "children": []

        }

        nodes[item["drive_file_id"]] = node

        parent = item["parent_id"]

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