from django.db import models
from django.contrib.auth.models import User

 

class UserProxy(User):
    class Meta:
        proxy = True
        permissions = [
            ("ver_cta_remuneraciones", "Puede ver cta remuneraciones")
        ]
        
class Rol(models.Model):
    nombre = models.CharField(max_length=100)
    def __str__(self):
        return self.nombre   
  
class TypeActionRequest(models.Model):
    nombre = models.CharField(max_length=100)
    def __str__(self):
        return self.nombre  

class Area(models.Model):
    nombre = models.CharField(max_length=100)
    biblioteca_folder_id = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="folder id google"
    )
    temporal_folder_id = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="folder id google"
    )
    def __str__(self):
        return self.nombre    
    
class UsuarioArea(models.Model):
    area = models.ForeignKey(Area, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rol = models.ForeignKey(Rol,on_delete=models.CASCADE, null=True)
    class Meta:
        unique_together = ('area', 'user')

    def __str__(self):
        return f"{self.area} - {self.user}"  # Cambiar 'centro' por 'area'