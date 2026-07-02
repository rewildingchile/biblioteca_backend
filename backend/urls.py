"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.admin.views.decorators import staff_member_required
from .views import LoginView,LoginJWTView , RefreshTokenView, LoginJWTTemporalView , VerifyOtpView,GenerateBackupCodesView


from googledrive.views import SyncFullView
from googledrive.views import DriveSyncStatusView
from googledrive.views import DriveTreeView, DriveTreeFolderView
from googledrive.views import SyncChangesView 
from googledrive.views import FileDocumentView , FileDocumentContentView
from googledrive.views import FileDocumentDescriptionView,FileDocumentUpload
from googledrive.views import PrepareUploadView, FileDocumentDelete
from googledrive.views import ViewDriveFileView
from googledrive.views import SearchView 

from  .views import M2mTokenView, Test 
from logging_conf.views import ver_activity_log, ver_importlibromayor_log


 
urlpatterns = [
    path('admin/', admin.site.urls),
    path('loginsimple/', LoginView.as_view(), name='login'),
    path('api/v1/login/', LoginJWTView.as_view(), name='login-jwt'),
    path('api/v2/login/', LoginJWTTemporalView.as_view(), name='login-jwt2'),
    path('api/v2/verify-otp/', VerifyOtpView.as_view(), name="verify-otp" ),
    path('api/v1/generatebackupcodes/',GenerateBackupCodesView.as_view(),name="GenerateBackupCodesView"),
    path('api/v1/token/refresh/', RefreshTokenView.as_view(), name='token-refresh'),
    path("api/v1/filedocument/",  FileDocumentView.as_view()),
 
    path('api/v1/drive/syncfull/<int:area_id>/', SyncFullView.as_view()) ,
    path('api/v1/drive/syncchanges/<int:area_id>/', SyncChangesView.as_view()) ,
    path('api/v1/drive/sync/status/<str:task_id>/', DriveSyncStatusView.as_view()),
    path("drive/tree/<int:area_id>/",DriveTreeView.as_view()),
    path("drive/tree/node/<str:folder_id>/",DriveTreeFolderView.as_view()),
    path("api/v1/auth/m2m-token",M2mTokenView.as_view()),
    path("test/",Test.as_view()),
    path("api/v1/filedocument/content/", FileDocumentContentView.as_view()  ),
    path("api/v1/filedocument/description/", FileDocumentDescriptionView.as_view()  ),    
    path("api/v1/upload/",FileDocumentUpload.as_view()),
    path('api/v1/prepare-upload/', PrepareUploadView.as_view(), name='prepare-upload'), 
    path("api/v1/deletefile/",FileDocumentDelete.as_view()),
    path('api/v1/drive/files/<str:file_id>/view/', ViewDriveFileView.as_view(), name='view-drive-file'),
    path('api/v1/search/', SearchView.as_view(), name='view-search'),
]
