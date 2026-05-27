from django.db import models
from django.contrib.auth.models import User

 

class UserProxy(User):
    class Meta:
        proxy = True
        permissions = [
            ("ver_cta_remuneraciones", "Puede ver cta remuneraciones")
        ]
        
from django.db import models
  

