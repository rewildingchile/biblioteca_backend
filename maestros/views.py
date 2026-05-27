from django.shortcuts import render
from django.db.models import Exists, OuterRef
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Centro, Cuenta
 
from .serializers import CentroSerializer, CuentaSerializer
 
#  uso de VISTAS GENERICAS como generics.ListAPIView 
# 1) incluye un 'return Response' automaticamente
 

class PlanDeCuentaListView(generics.ListAPIView):
    queryset = Cuenta.objects.select_related('tipo_cuenta').all().order_by('tipo_cuenta__categoria_cuenta__nombre', 'tipo_cuenta__nombre', 'id')
    serializer_class = CuentaSerializer
    # Define el método de autenticación: en este caso, mediante tokens JWT (JSON Web Tokens).
    # Esto significa que el usuario debe incluir un token válido en el encabezado de la solicitud:
    authentication_classes = [JWTAuthentication] 
    # Indica que solo usuarios autenticados (con token válido) pueden acceder.
    permission_classes = [IsAuthenticated]
