from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from .serializers import LoginSerializer
from .serializers import LoginJWTSerializer
from .serializers import LoginJWTTemporalSerializer
from .serializers import VerifyOtpSerializer

from django.contrib.auth.models import User, Group
from django.http import JsonResponse
 
import logging
import os

logger = logging.getLogger(__name__)

  

class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
         
            return Response({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
     
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class LoginJWTView(APIView):
    def post(self, request):
        serializer = LoginJWTSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = serializer.validated_data['tokens']
            #sessionToken = serializer.validated_data['sessionToken']


            
       
           
            return Response({
                "status": 200,
                "message": "OK",
                "payload":{
                #"sessionToken": sessionToken,
                "tokens": tokens,
                "info": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "nombres": user.first_name,
                    "apellido1": user.last_name,
                    "flag":'true',
                                      
                }
                },
               
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RefreshTokenView(APIView):
    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response({
                "status": 400,
                "message": "Debe enviar el token de actualización (refresh)."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Intentar validar y crear nuevo access token
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)

            return Response({
                "status": 200,
                "message": "Nuevo token generado correctamente.",
                "payload": {
                    "access": new_access_token
                }
            }, status=status.HTTP_200_OK)

        except TokenError as e:
            return Response({
                "status": 401,
                "message": "Token inválido o expirado.",
                "error": str(e)
            }, status=status.HTTP_401_UNAUTHORIZED)

from django_otp.plugins.otp_totp.models import TOTPDevice
class LoginJWTTemporalView(APIView):
    def post(self, request):
        serializer = LoginJWTTemporalSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user = serializer.validated_data['user']
            tokens = serializer.validated_data['tokens']
            status = serializer.validated_data['status']

            ''' TOTPDevice: 📱 Un dispositivo autenticador basado en TOTP
                (Google Authenticator, Microsoft Authenticator, Authy, etc.)'''
            device = TOTPDevice.objects.filter(user=user ).first()
            if not device:
                device = TOTPDevice.objects.create(user=user,
                                                   name='Authenticator',
                                                   confirmed=False)
                '''
                Genera un secret aleatorio
                Lo guarda en device.key
                Ese secret sirve para:
                        Generar el QR
                        Validar códigos OTP
                '''

           

            response_data = {
                "status": status,
                "payload": {
                    "tokens": tokens,
                    
                }
            }    
              
            if not device.confirmed:
                     response_data["payload"]["qr"] = device.config_url
            
            return Response(response_data)
 
'''
  🔐  

    Validar device.verify_token(code)
    Marcar device.confirmed = True si es primer uso
    Emitir JWT final + refresh
    Marcar 2fa=True
    '''

from rest_framework.permissions import IsAuthenticated
class VerifyOtpView(APIView):
   
    permission_classes = [IsAuthenticated]
    def post(self, request):
     
     
        
        serializer = VerifyOtpSerializer(
                        data=request.data,
                        context={"user":request.user.id})
        if serializer.is_valid():
            user = request.user
            device = serializer.validated_data["device"]
            # confirmar dispositivo  si es primer uso
            if not device.confirmed:
                device.confirmed = True
                device.save()

            # emitir JWT definitivo
            refresh = RefreshToken.for_user(user)
            print(refresh["exp"])
            access = refresh.access_token
            access["2fa"] = True
            access["is_temp"]= False
 

            from django.db.models import Exists, OuterRef
        

            modifica_presupuestos=False
            is_admin = user.groups.filter(name__iexact="Admin").exists()
            if is_admin:
                    modifica_presupuestos=True    

         
             
            logger.info("login exitoso")

            return Response({
                  "status":200,
           
                  "payload": {
                  "tokens": {
                    "refresh": str(refresh),
                    "access": str(access),
                   },
                     "info": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "nombres": user.first_name,
                    "apellido1": user.last_name,
                    "is_admin":is_admin,
                    "modifica_presupuestos": modifica_presupuestos,
                             
                }
                }
            })    
        # ❌ Si no es válido
        
        logger.error("credenciales no validas")
        return Response(serializer.errors, status=400)
    

from rest_framework.views import APIView
from rest_framework.response import Response
from user2factor.models import BackupCode
from rest_framework.permissions import IsAuthenticated     
class GenerateBackupCodesView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):

       
        user = request.user

        print ('--->',user.is_authenticated)
        
        # 1️⃣ Verificar que el usuario esté autenticado
        if not user.is_authenticated:
            return Response(
                {"detail": "No autenticado"},
                status=status.HTTP_401_UNAUTHORIZED
            )
      

        # 2️⃣ Verificar que la cuenta esté activa
        if not user.is_active:
            return Response(
                {"detail": "Cuenta desactivada"},
                status=status.HTTP_403_FORBIDDEN
            )

        # 3️⃣ Verificar que el usuario tenga TOTPDevice confirmado
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
        if not device:
            return Response(
                {"detail": "No tiene dispositivo 2FA confirmado"},
                status=status.HTTP_403_FORBIDDEN
            )

        BackupCode.objects.filter(user=user).delete()

        codes = generate_single_backup_code(user)

        return Response({
            "backup_codes": codes
        })
    
import secrets
import hashlib


def generate_backup_codes(user, total=8):
    codes = []

    for _ in range(total):
        code = str(secrets.randbelow(10**6)).zfill(6)

        BackupCode.objects.create(
            user=user,
            code_hash=hashlib.sha256(code.encode()).hexdigest()
        )

        codes.append(code)

    return codes  


import secrets
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.conf import settings

def generate_single_backup_code(user):
    # Borrar códigos antiguos
    BackupCode.objects.filter(user=user).delete()

    # Generar un único código de 6 dígitos
    code = str(secrets.randbelow(10**6)).zfill(6)

    # Guardar hash en la base de datos
    BackupCode.objects.create(
        user=user,
        code_hash=hashlib.sha256(code.encode()).hexdigest()
    )
    # Crear el correo
    
    import requests
    from django.http import JsonResponse
    from django.conf import settings

 

    url = "https://api.brevo.com/v3/smtp/email"

    payload = {
        "sender": {
            "name": "Admin Rewilding Chile",
            "email": "admin@rewildingchile.org"
        },
        "to": [
            {
                "email": user.email,
                "name": str( user.first_name)+ " " + str( user.last_name)  
            }
        ],
        "subject": "tu codigo de acceso para presupuestos",
        "htmlContent": f"""
        <html>
        <body>
        <p>Este es tu codigo y no lo compartas con nadie</p>
        <p>codigo temporal: {code}</p>
        </body>
        </html>
        """
    }
    #"api-key": settings.BREVO_API_KEY,
    headers = {
        "accept": "application/json",
        "api-key": os.getenv("BREVO_API_KEY"),
        "content-type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    return "ok"
     
class Test(APIView):
    def get(self,request):
            return Response({
                "status": 200,
                "message": "hola!",
                
            }, status=status.HTTP_200_OK)
class M2mTokenView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):        
        try:

            client_id = request.data.get("client_id")
            client_secret = request.data.get("client_secret")
            if (  client_id != settings.M2M_CLIENT_ID or  client_secret != settings.M2M_CLIENT_SECRET  ):
                return Response(
                    {"error": "Credenciales inválidas"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            # Intentar validar y crear nuevo access token
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)

            return Response({
                "status": 200,
                "message": "Nuevo token generado correctamente.",
                "payload": {
                    "access": new_access_token
                }
            }, status=status.HTTP_200_OK)

        except TokenError as e:
            return Response({
                "status": 401,
                "message": "Token inválido o expirado.",
                "error": str(e)
            }, status=status.HTTP_401_UNAUTHORIZED)