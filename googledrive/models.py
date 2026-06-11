from django.db import models

# Create your models here.

class Area(models.Model):
    nombre = models.CharField(max_length=100)
    def __str__(self):
        return self.nombre    
        
import uuid

class GoogleDriveFile(models.Model):
    """
    Modelo para representar archivos y carpetas sincronizados con Google Drive.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identificador único en tu BD."
    )
    area =  models.ForeignKey(Area, null=True,on_delete=models.CASCADE,default=0)
    drive_file_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="ID único que Google asigna al archivo o carpeta."
    )
    name = models.CharField(
        max_length=255,
        help_text="El nombre del archivo o carpeta."
    )
    mime_type = models.CharField(
        max_length=255,
        help_text="El tipo MIME de Google (application/vnd.google-apps.folder para carpetas)."
    )
    parent_drive_file_id = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        to_field='drive_file_id',
        db_column='parent_drive_file_id',
        null=True,
        blank=True,
        related_name='children',
        help_text="ID de la carpeta que lo contiene (para mapear la jerarquía)."
    )
    drive_web_view_link = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Enlace público para vista/previsualización."
    )
    last_known_modified_time = models.DateTimeField(
        help_text="Última fecha de modificación conocida en Drive. Esencial para detectar cambios.",
        null=True,
    )
    last_synced_at = models.DateTimeField(
        help_text="Marca de tiempo de la última sincronización con Google Drive.",
        null=True,
    )

    class Meta:
        verbose_name = "Archivo de Google Drive"
        verbose_name_plural = "Archivos de Google Drive"
        indexes = [
            models.Index(fields=['drive_file_id']),
            models.Index(fields=['parent_drive_file_id']),
            models.Index(fields=['last_known_modified_time']),
        ]

    def __str__(self):
        return f"{self.name} ({self.drive_file_id})"
    

class GoogleDriveSyncState(models.Model):

    area = models.ForeignKey(Area, on_delete=models.CASCADE)
    start_page_token = models.CharField(max_length=255)
    last_full_sync_at = models.DateTimeField(
        null=True,
        blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)


from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
'''en Django ORM hay diferencia entre:
nombre de la columna SQL
nombre del campo del modelo ORM (lo que django puede entender)

GoogleDriveFileDocument.objects.get(file="abc123")
GoogleDriveFileDocument.objects.get(file_id="abc123")

no funciona:
GoogleDriveFileDocument.objects.get(drive_file_id="abc123")
drive_file_id es el nombre fisico de la columna, no del orm
en orm la columna se llama 'file_id'
'''
class GoogleDriveFileDocument(models.Model):

    file = models.OneToOneField(
        GoogleDriveFile,
        on_delete=models.CASCADE,
        related_name="document",
        to_field="drive_file_id",
        db_column="drive_file_id",
        null=True
    )

    text_content = models.TextField(null=True)
    search_vector = SearchVectorField(null=True)

    class Meta:
        indexes = [GinIndex(fields=["search_vector"])]    