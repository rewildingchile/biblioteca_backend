 
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
# Register your models here.
from  .models import TypeActionRequest

from maestros.models import   Area,UsuarioArea  , Rol
admin.site.register(TypeActionRequest)
try:
    admin.site.unregister(Area)
except admin.sites.NotRegistered:
    pass


class RolAdmin(admin.ModelAdmin):
    search_fields = ['nombre']  
    list_display = ('id', 'nombre')
    ordering = ['nombre']   

admin.site.register(Rol, RolAdmin) 
 
class AreaAdmin(admin.ModelAdmin):
    search_fields = ['nombre']  
    list_display = ('id', 'nombre')
    ordering = ['nombre']   

admin.site.register(Area, AreaAdmin)

class UsuarioAreaInline(admin.TabularInline):
    model = UsuarioArea
    extra = 1
    autocomplete_fields = ['area']
 

class CustomUserAdmin(UserAdmin):
    inlines = [UsuarioAreaInline]


# Reemplazamos el admin original de User
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)