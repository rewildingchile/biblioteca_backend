from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework_simplejwt.tokens import AccessToken
from datetime import timedelta


from user2factor.models import UserTwoFactor
from user2factor.models import BackupCode

import hashlib


'''
En DRF, un serializer sirve para dos cosas principales:
1) Convertir datos del cliente (JSON, form-data) a objetos Python 
    (y luego a tu modelo si es ModelSerializer).
2) Validar que esos datos sean correctos y completos antes de procesarlos o guardarlos.
“Validar el serializer” significa comprobar que los datos enviados cumplen las reglas 
definidas en el serializer.
'''
class LoginSerializer(serializers.Serializer):
    # comprobacion de datos
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)  #significa que el campo se acepta en la entrada pero no se devuelve en la respuesta JSON

    def validate(self, data): 
        #Aquí se extraen los valores enviados por el usuario (username y password) del diccionario data.
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            raise serializers.ValidationError("Debe ingresar nombre de usuario y contraseña.")

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Credenciales inválidas.")

        if not user.is_active:
            raise serializers.ValidationError("La cuenta está desactivada.")

        # Retornar el usuario autenticado
        data['user'] = user
        return data

class LoginJWTSerializer(serializers.Serializer):
    username = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            raise serializers.ValidationError("Debe ingresar nombre de usuario y contraseña.")

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Credenciales inválidas.")

        if not user.is_active:
            raise serializers.ValidationError("La cuenta está desactivada.")

        # Generar tokens JWT
        refreshTok = RefreshToken.for_user(user)    
        accessTok = refreshTok.access_token

        # refreshTok.set_exp(lifetime=timedelta(minutes=5))
       
        data['user'] = user
        #data['sessionToken']  =str(accessTok)
        data['tokens'] = {
            
            'refresh': str(refreshTok),
            'access': str(accessTok)
        }
        # data['is_temp'] = True
        # data['2fa'] = False
        
        return data
    

    
class LoginJWTTemporalSerializer(serializers.Serializer):
    username = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get('username')
        password = data.get('password')

 
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Credenciales inválidas.")


        print ('--->',user.is_authenticated)

        if not user.is_active:
            raise serializers.ValidationError("La cuenta está desactivada.")
        
      

        ''' No existe registro	Nunca inició enrolamiento
            Existe pero is_2fa_enabled=False	No confirmó
            is_2fa_enabled=True	Debe pedir OTP'''    
        
        data['user']   = user     
        data["status"] = ''
        # Generar token  JWT temporal
        temp_token = AccessToken.for_user(user)    
        temp_token.set_exp(lifetime=timedelta(minutes=5))
        temp_token["is_temp"] = True 
        


        confirmed_device = TOTPDevice.objects.filter(
            user=user,
            confirmed=True
        ).first()

        if not confirmed_device:
            data["status"] = "OTP_SETUP_REQUIRED"
            temp_token["2fa"] = False
        else:
            data["status"] = "OTP_REQUIRED"
            temp_token["2fa"] = True
                  
        data['tokens'] = {
                          'access': str(temp_token)
                         }
        return data
    

from django_otp.plugins.otp_totp.models import TOTPDevice

class VerifyOtpSerializer(serializers.Serializer):
    # define los campos esperados
    codigo = serializers.CharField(max_length=6)
    
    # validador específico del campo 'codigo'
    def validate_codigo(self, value):
         # que sea numerico
         if not value.isdigit():
              raise serializers.ValidationError('el codigo debe ser numerico');
         return value


 

    #validador global del serializer.
    def validate(self,data):
        user = self.context["user"]
        code = data["codigo"]
        # 1️⃣ Intentar verificar con TOTP normal
        device = TOTPDevice.objects.filter(  user = user  ).first()
        if not device:
             raise  serializers.ValidationError("No hay dispositivo 2FA configurado.")

        print ('comprobando device')
        if device and device.verify_token(code):
                data["device"]=device
                return data
        
        print ('comprobando  backup code')
        # 2️⃣ Intentar verificar con backup code
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        backup = BackupCode.objects.filter(
            user=user,
            code_hash=code_hash,
            used=False
        ).first()
        if backup:
            backup.used = True
            backup.save()
            data["method"] = "backup"
            data["backup"] = backup
            data["device"]=device
            return data

        # 3️⃣ Ninguno válido
        raise serializers.ValidationError("Código inválido") 
        
         

      

       
 