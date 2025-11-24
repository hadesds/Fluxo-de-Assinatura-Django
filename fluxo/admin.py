from django.contrib import admin
from .models import Institution, InternshipDocument, DigitalSignature, DocumentHistory

# --- 1. Instituições (Universidade/Escola de Saúde) ---

@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    """Configuração para o modelo Institution."""
    list_display = ('name', 'type', 'cnpj', 'created_at')
    list_filter = ('type',)
    search_fields = ('name', 'cnpj')
    filter_horizontal = ('admin_users',) # Permite adicionar múltiplos usuários facilmente

# --- 2. Assinaturas Digitais (Inline para Documento) ---

class DigitalSignatureInline(admin.TabularInline):
    """Define como as assinaturas aparecem dentro do formulário do Documento."""
    model = DigitalSignature
    extra = 0
    fields = ('signer_name', 'signer_type', 'signed_at', 'signer_cpf', 'signature_hash')
    readonly_fields = ('signer_name', 'signer_type', 'signed_at', 'signer_cpf', 'signature_hash', 'ip_address', 'user_agent', 'signature_data')

# --- 3. Histórico do Documento (Inline para Documento) ---

class DocumentHistoryInline(admin.TabularInline):
    """Define como o histórico aparece dentro do formulário do Documento."""
    model = DocumentHistory
    extra = 0
    fields = ('action', 'performed_by', 'created_at', 'notes')
    readonly_fields = ('action', 'performed_by', 'created_at', 'notes')
    can_delete = False
    ordering = ('-created_at',)


# --- 4. Documento de Estágio ---

@admin.register(InternshipDocument)
class InternshipDocumentAdmin(admin.ModelAdmin):
    """Configuração para o modelo InternshipDocument."""
    list_display = ('title', 'university', 'health_school', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'university', 'health_school')
    search_fields = ('title', 'description')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Informações Básicas', {
            'fields': ('title', 'description', 'created_by')
        }),
        ('Fluxo e Instituições', {
            'fields': ('university', 'health_school', 'status')
        }),
        ('Arquivos e Integridade', {
            'fields': ('original_file', 'original_hash', 'signed_file')
        }),
        ('Detalhes do Estágio', {
            'fields': ('num_students', 'student_info')
        }),
    )
    
    readonly_fields = ('original_hash',)
    
    inlines = [
        DigitalSignatureInline,
        DocumentHistoryInline,
    ]