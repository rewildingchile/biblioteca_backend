from django.db import models
from django.contrib.auth.models import User

 

class UserProxy(User):
    class Meta:
        proxy = True
        permissions = [
            ("ver_cta_remuneraciones", "Puede ver cta remuneraciones")
        ]
        
 
  
class Action(models.Model):
    nombre = models.CharField(max_length=100)
    def __str__(self):
        return self.nombre  
