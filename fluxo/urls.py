# fluxo_assinatura/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Universidade
    path('university/', views.university_dashboard, name='university_dashboard'),
    path('university/send/', views.university_send_document, name='university_send_document'),
    path('university/document/<int:document_id>/', views.university_view_document, name='university_view_document'),
    
    # Escola de Saúde
    path('health-school/', views.health_school_dashboard, name='health_school_dashboard'),
    path('health-school/document/<int:document_id>/', views.health_school_view_document, name='health_school_view_document'),
    path('health-school/document/<int:document_id>/sign/', views.health_school_sign_document, name='health_school_sign_document'),
    
    # Downloads
    path('document/<int:document_id>/download/original/', views.download_original_document, name='download_original_document'),
    path('document/<int:document_id>/download/signed/', views.download_signed_document, name='download_signed_document'),
]