

from user2factor.models import   BackupCode
from django.contrib import admin
from django.contrib import admin

admin.site.site_header = "Panel de Administración"
admin.site.site_title = "Biblioteca"
admin.site.index_title = "Bienvenidos"
# Register your models here.

 
 
admin.site.register(BackupCode)
