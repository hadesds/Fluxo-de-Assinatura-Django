from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import hashlib
import json
from datetime import datetime

class Institution(models.Model):
    """Instituição - Universidade ou Escola de Saúde"""
    INSTITUTION_TYPES = [
        ('university', 'Universidade'),
        ('health_school', 'Escola de Saúde Pública')
    ]
    
    name = models.CharField(max_length=200, verbose_name="Nome")
    type = models.CharField(max_length=20, choices=INSTITUTION_TYPES, verbose_name="Tipo")
    cnpj = models.CharField(max_length=18, unique=True, verbose_name="CNPJ")
    admin_users = models.ManyToManyField(User, related_name='administered_institutions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Instituição"
        verbose_name_plural = "Instituições"
    
    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class InternshipDocument(models.Model):
    """Documento de Estágio"""
    STATUS_CHOICES = [
        ('pending_health_school', 'Aguardando Escola de Saúde'),
        ('signed_health_school', 'Assinado pela Escola de Saúde'),
        ('completed', 'Processo Concluído'),
        ('rejected', 'Rejeitado')
    ]
    
    # Informações básicas
    title = models.CharField(max_length=300, verbose_name="Título")
    description = models.TextField(verbose_name="Descrição")
    
    # Instituições envolvidas
    university = models.ForeignKey(
        Institution, 
        on_delete=models.CASCADE, 
        related_name='sent_documents',
        limit_choices_to={'type': 'university'},
        verbose_name="Universidade Remetente"
    )
    health_school = models.ForeignKey(
        Institution, 
        on_delete=models.CASCADE, 
        related_name='received_documents',
        limit_choices_to={'type': 'health_school'},
        verbose_name="Escola de Saúde Destinatária"
    )
    
    # Arquivo original
    original_file = models.FileField(
        upload_to='documents/original/%Y/%m/',
        verbose_name="Arquivo Original (PDF)"
    )
    original_hash = models.CharField(max_length=64, blank=True, verbose_name="Hash SHA-256 do Original")
    
    # Arquivo assinado
    signed_file = models.FileField(
        upload_to='documents/signed/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Arquivo Assinado (PDF)"
    )
    
    # Status e controle
    status = models.CharField(
        max_length=30, 
        choices=STATUS_CHOICES, 
        default='pending_health_school',
        verbose_name="Status"
    )
    
    # Metadados
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Criado por")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    # Informações sobre estudantes
    num_students = models.IntegerField(default=0, verbose_name="Número de Estudantes")
    student_info = models.TextField(blank=True, verbose_name="Informações dos Estudantes (JSON)")
    
    class Meta:
        verbose_name = "Documento de Estágio"
        verbose_name_plural = "Documentos de Estágio"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    def calculate_hash(self, file_field):
        """Calcula o hash SHA-256 de um arquivo"""
        if file_field:
            file_field.seek(0)
            file_content = file_field.read()
            return hashlib.sha256(file_content).hexdigest()
        return None
    
    def save(self, *args, **kwargs):
        # Calcular hash do arquivo original na primeira vez
        if self.original_file and not self.original_hash:
            self.original_hash = self.calculate_hash(self.original_file)
        super().save(*args, **kwargs)


class DigitalSignature(models.Model):
    """Assinatura Digital"""
    SIGNER_TYPES = [
        ('university', 'Representante da Universidade'),
        ('health_school', 'Representante da Escola de Saúde')
    ]
    
    # Relacionamentos
    document = models.ForeignKey(
        InternshipDocument, 
        on_delete=models.CASCADE, 
        related_name='signatures',
        verbose_name="Documento"
    )
    signer = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Signatário")
    signer_type = models.CharField(max_length=20, choices=SIGNER_TYPES, verbose_name="Tipo de Signatário")
    
    # Dados da assinatura
    signature_data = models.TextField(verbose_name="Dados da Assinatura (JSON)")
    signature_hash = models.CharField(max_length=64, verbose_name="Hash da Assinatura")
    certificate_data = models.TextField(blank=True, verbose_name="Dados do Certificado Digital")
    
    # Metadados de auditoria
    signed_at = models.DateTimeField(default=timezone.now, verbose_name="Assinado em")
    ip_address = models.GenericIPAddressField(verbose_name="Endereço IP")
    user_agent = models.TextField(verbose_name="User Agent")
    
    # Informações do signatário
    signer_name = models.CharField(max_length=200, verbose_name="Nome do Signatário")
    signer_email = models.EmailField(verbose_name="Email do Signatário")
    signer_cpf = models.CharField(max_length=14, verbose_name="CPF do Signatário")
    
    class Meta:
        verbose_name = "Assinatura Digital"
        verbose_name_plural = "Assinaturas Digitais"
        ordering = ['-signed_at']
    
    def __str__(self):
        return f"Assinatura de {self.signer_name} em {self.document.title}"
    
    def generate_signature_hash(self):
        """Gera o hash da assinatura baseado nos dados"""
        data = {
            'document_hash': self.document.original_hash,
            'signer_email': self.signer_email,
            'signer_cpf': self.signer_cpf,
            'signed_at': self.signed_at.isoformat(),
            'signature_data': self.signature_data
        }
        signature_string = json.dumps(data, sort_keys=True)
        return hashlib.sha256(signature_string.encode()).hexdigest()


class DocumentHistory(models.Model):
    """Histórico de mudanças do documento"""
    ACTION_TYPES = [
        ('created', 'Documento Criado'),
        ('sent', 'Documento Enviado'),
        ('signed', 'Documento Assinado'),
        ('rejected', 'Documento Rejeitado'),
        ('completed', 'Processo Concluído')
    ]
    
    document = models.ForeignKey(
        InternshipDocument, 
        on_delete=models.CASCADE, 
        related_name='history',
        verbose_name="Documento"
    )
    action = models.CharField(max_length=20, choices=ACTION_TYPES, verbose_name="Ação")
    performed_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Realizado por")
    notes = models.TextField(blank=True, verbose_name="Observações")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data/Hora")
    
    class Meta:
        verbose_name = "Histórico do Documento"
        verbose_name_plural = "Históricos dos Documentos"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.document.title}"