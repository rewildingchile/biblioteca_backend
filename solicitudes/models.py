from django.db import models
import uuid
from django.contrib.auth.models import User
from maestros.models import Action
# primero se crea la solicitud, despues se sube a folder temporal

class UserRequest(models.Model):
 
    # id solicitud
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identificador único en tu BD."
    )

    # new, delete, move
    accion =  models.ForeignKey(Action, null=True,on_delete=models.CASCADE,default=0)
    
    # archivo existente en biblioteca (usado por 'delete', 'move').
    drive_file_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="ID único que Google asigna al archivo o carpeta."
    )
    # nuevo archivo subido a a temp (usado por 'new')
    temp_file_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="ID único que Google asigna al archivo o carpeta."
    )
    # para 'new', 'move'
    destination_drive_parent_drive_file_id = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        to_field='drive_file_id',
        db_column='parent_drive_file_id',
        null=True,
        blank=True,
        related_name='children',
        help_text="ID de la carpeta que lo contiene (para mapear la jerarquía)."
    )

    # para 'rename' 
    new_name = models.CharField(
        max_length=255,
        help_text="El nombre del archivo o carpeta."
    )
 
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)