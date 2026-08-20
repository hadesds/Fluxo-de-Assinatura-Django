"""
URL configuration for Assinatura project.
...
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views # Importa views de autenticação
from fluxo import views as fluxo_views # Importa views do app fluxo
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', fluxo_views.home_redirect, name='home'),
    path('', include('fluxo.urls')),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
