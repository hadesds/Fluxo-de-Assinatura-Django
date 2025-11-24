# Assinatura/urls.py - AJUSTADO
"""
URL configuration for Assinatura project.
...
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views # Importa views de autenticação
from fluxo import views as fluxo_views # Importa views do app fluxo

urlpatterns = [
    path('admin/', admin.site.urls),
    # Rota raiz/home (irá redirecionar para o dashboard apropriado)
    path('', fluxo_views.home_redirect, name='home'),
    # Inclui todas as URLs da aplicação 'fluxo'
    path('', include('fluxo.urls')),
    
    # URLs de Autenticação (Necessário para o botão 'Sair' em base.html)
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]