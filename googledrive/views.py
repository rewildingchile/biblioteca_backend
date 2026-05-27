from django.shortcuts import render
 

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics
from rest_framework import serializers
from django.http import Http404

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfReader
import io


import datetime
from django.utils import timezone

from googleapiclient.discovery import build

import logging

logger = logging.getLogger(__name__)











def procesar_archivo(nombre, mime, contenido):
  
    if mime == "application/pdf":

       
        mensaje = f"PDF: {nombre}\n"
       
        if pdf_es_scan(contenido):
            tipo = "PDF escaneado → requiere OCR"
        else:
            tipo = "PDF nativo → texto directo"

        print("PDF detectado:", nombre,tipo)    

    elif mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        print("WORD:", nombre)
        mensaje = f"WORD: {nombre}\n"
       
    else:

        print("Otro tipo:", nombre)
        mensaje = f"OTRO: {nombre}\n"
        

  
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(mensaje)


from services.gdrive.tasks import sync_full_task
class SyncFullView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
       
        logger.info( f" {logger.name} : llamando->sync_full_task")
        # la vista dispara el proceso Y la tarea pesada corre aparte:

        # delay() retorna un objeto AsyncResult.
        area_id=1
        task = sync_full_task.delay(area_id)
        
        logger.info(f"TAREA CELERY ID: {task.id}")
            
        return Response({
                    "status": 200,
                    "task_id": task.id
                }, status=status.HTTP_200_OK)


from services.gdrive.tasks import sync_changes_task
class SyncChangesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
       
        logger.info( f" {logger.name} : llamando->sync_changes_task")
        # la vista dispara el proceso Y la tarea pesada corre aparte:

        # delay() retorna un objeto AsyncResult.
        area_id=1
        task = sync_changes_task.delay(area_id)
        
        logger.info(f"TAREA CELERY ID: {task.id}")
            
        return Response({
                    "status": 200,
                    "task_id": task.id
                }, status=status.HTTP_200_OK)

from celery.result import AsyncResult
class DriveSyncStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request,task_id):
       
      logger.info( f" {logger.name} : consultando status sincronizacion")
      task_result = AsyncResult(task_id)

      response = {
            "task_id": task_id,
            "status": task_result.status,
            "result": task_result.result
      }

      return Response(response)
    

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from services.gdrive.tree_service import obtener_arbol_area


class DriveTreeView(APIView):

    authentication_classes = [JWTAuthentication]

    permission_classes = [IsAuthenticated]

    def get(self, request, area_id):

        tree = obtener_arbol_area(area_id)

        return Response(tree)    