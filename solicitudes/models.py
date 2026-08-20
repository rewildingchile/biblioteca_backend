from django.db import models
import uuid
from django.contrib.auth.models import User
from maestros.models import TypeActionRequest, Area
from googledrive.models import GoogleDriveFile
# EDITORES:
# cada usuario pertenece a un area
# cada area tiene su folder temporal, que debe existir en tabla GoogleDriveFile.
# primero se crea la solicitud, despues se sube a folder temporal

class UserRequest(models.Model):
 
    # id solicitud
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identificador único en tu BD."
    )

    # new, delete, move, rename
    type_action_request =  models.ForeignKey(TypeActionRequest, null=True,on_delete=models.CASCADE)
    name = models.CharField(
            max_length=255,
            null=True,
            help_text="El nombre del archivo o carpeta."
        )
    mime_type = models.CharField(
            max_length=255,
            blank=True,
            null=True,
            help_text="El tipo MIME de Google (application/vnd.google-apps.folder para carpetas)."
        )
   
    #  folder  (Temporal,historial, papelera)
    folder_origin_id = models.CharField(
        max_length=255,
          blank=True,
                    null=True,
        help_text="ID único que Google asigna al archivo o carpeta."
    )
    googledrivefile_folder_origin= models.ForeignKey(
        GoogleDriveFile,
        on_delete=models.CASCADE,
        to_field='drive_file_id',
        db_column='googledrivefile_folder_origin',
        null=True,
        blank=True,
        related_name='folder_origin_id' 
        )

     # archivo original en biblioteca  
    drive_file_id = models.CharField(
        max_length=255,
        unique=True,
         null=True,
        help_text="ID único que Google asigna al archivo o carpeta."
    )
    googledrivefile_drive_file= models.ForeignKey(
        GoogleDriveFile,
        on_delete=models.CASCADE,
        to_field='drive_file_id',
        db_column='googledrivefile_drive_file',
        null=True,
        blank=True,
        related_name='drive_fileid' 
        )
 

    drive_web_view_link = models.URLField(
            max_length=500,
            blank=True,
            null=True,
            help_text="Enlace público para vista/previsualización."
        )

    
    # folder destino en biblioteca
    folder_final_id= models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="carpeta que aloja el archivo"
    )
    
    googledrivefile_folder_final= models.ForeignKey(
        GoogleDriveFile,
        on_delete=models.CASCADE,
        to_field='drive_file_id',
        db_column='googledrivefile_folder_final',
        null=True,
        blank=True,
        related_name='drive_folderfinal' 
        )

    last_synced_at = models.DateTimeField(
        help_text="Marca de tiempo de la última sincronización con Google Drive.",
        null=True,
    )
    # nuevo nombre del archivo en folder destino
    new_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="El nombre del archivo o carpeta."
    )
 
    area = models.ForeignKey(Area, on_delete=models.CASCADE, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    pendiente = models.BooleanField(default=True)
    anulado = models.BooleanField(default=False)