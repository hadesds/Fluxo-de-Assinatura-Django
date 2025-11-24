from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.contrib import messages
from .models import Institution, InternshipDocument, DigitalSignature, DocumentHistory
import json
import os 

# --- UTILITIES ---

def get_client_ip(request):
    """Obtém o endereço IP do cliente (utility necessária para DigitalSignature)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def university_required(function):
    """Decorator para exigir que o usuário seja administrador de uma Universidade."""
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and \
           Institution.objects.filter(admin_users=request.user, type='university').exists():
            return function(request, *args, **kwargs)
        messages.error(request, "Acesso não autorizado para a Universidade.")
        return redirect('home')
    return wrapper

def health_school_required(function):
    """Decorator para exigir que o usuário seja administrador de uma Escola de Saúde."""
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and \
           Institution.objects.filter(admin_users=request.user, type='health_school').exists():
            return function(request, *args, **kwargs)
        messages.error(request, "Acesso não autorizado para a Escola de Saúde.")
        return redirect('home')
    return wrapper

# --- 1. INTERFACE DA UNIVERSIDADE ---

@login_required
@university_required
def university_dashboard(request):
    """Dashboard principal da Universidade (usa university/dashboard.html)."""
    #
    university = get_object_or_404(Institution, admin_users=request.user, type='university')
    
    #
    documents = InternshipDocument.objects.filter(university=university).order_by('-created_at')
    
    # Mapeamento dos STATUS_CHOICES de models.py para as chaves do template university/dashboard.html
    status_counts = {
        'pending': documents.filter(status='pending_health_school').count(), # Aguardando Assinatura
        'signed': documents.filter(status='signed_health_school').count(),   # Assinados
        'completed': documents.filter(status='completed').count(),         # Concluídos
        'total': documents.count(),                                         # Total
    }
    
    return render(request, 'university/dashboard.html', {
        'university': university,
        'documents': documents,
        'status_counts': status_counts
    })

@login_required
@university_required
def university_send_document(request):
    """View para criar e enviar um novo documento de estágio."""
    #
    university = get_object_or_404(Institution, admin_users=request.user, type='university')
    #
    health_schools = Institution.objects.filter(type='health_school')
    
    # Estudantes
    students = []
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        health_school_id = request.POST.get('health_school')
        num_students = int(request.POST.get('num_students', 0))
        file = request.FILES.get('file')
        
        #
        health_school = get_object_or_404(Institution, id=health_school_id, type='health_school')
        
        # Criação do Documento
        #
        document = InternshipDocument.objects.create(
            title=title,
            description=description,
            university=university,
            health_school=health_school,
            original_file=file,
            created_by=request.user,
            status='pending_health_school', 
            num_students=num_students,
            student_info=json.dumps({'num_students': num_students})
        )
        
        # Adicionar o histórico de criação
        #
        DocumentHistory.objects.create(
            document=document,
            action='sent',
            performed_by=request.user,
            notes='Documento enviado para assinatura da Escola de Saúde'
        )
        
        # Cria a DigitalSignature para o remetente (Universidade)
        #
        DigitalSignature.objects.create(
            document=document,
            signer=request.user,
            signer_type='university', #
            signature_data=json.dumps({'notes': 'Enviado/Assinado pela Universidade'}),
            signature_hash=document.original_hash[:64] if document.original_hash else 'NOHASH',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            signer_name=request.user.get_full_name() or request.user.username,
            signer_email=request.user.email,
            signer_cpf='000.000.000-00'
        )

        messages.success(request, f'Documento "{document.title}" enviado com sucesso.')
        return redirect('university_view_document', document_id=document.id)
    
    # GET request renderiza o template
    return render(request, 'university/create_request.html', {
        'university': university,
        'health_schools': health_schools,
        'students': students
    })

@login_required
@university_required
def university_view_document(request, document_id):
    """Detalhes de um documento na visão da Universidade (usa university/view_document.html)."""
    #
    university = get_object_or_404(Institution, admin_users=request.user, type='university')
    #
    document = get_object_or_404(InternshipDocument, id=document_id, university=university)
    
    #
    signatures = document.signatures.all()
    #
    history = document.history.all()
    
    return render(request, 'university/view_document.html', {
        'document': document,
        'university': university,
        'signatures': signatures,
        'history': history,
    })

# --- 2. INTERFACE DA ESCOLA DE SAÚDE ---

@login_required
@health_school_required
def health_school_dashboard(request):
    """Dashboard principal da Escola de Saúde. (Falta template)"""
    messages.info(request, "Dashboard da Escola de Saúde não possui template no escopo.")
    return redirect('home')

@login_required
@health_school_required
def health_school_view_document(request, document_id):
    """Detalhes de um documento na visão da Escola de Saúde (usa health_school/view_document.html)."""
    #
    health_school = get_object_or_404(Institution, admin_users=request.user, type='health_school')
    #
    document = get_object_or_404(InternshipDocument, id=document_id, health_school=health_school)
    
    #
    signatures = document.signatures.all() # DigitalSignature
    #
    history = document.history.all()       # DocumentHistory
    
    return render(request, 'health_school/view_document.html', {
        'document': document,
        'health_school': health_school,
        'signatures': signatures,
        'history': history,
    })

@login_required
@health_school_required
def health_school_sign_document(request, document_id):
    """Exibe o formulário de assinatura e processa o POST (usa health_school/sign_document.html)."""
    #
    health_school = get_object_or_404(Institution, admin_users=request.user, type='health_school')
    #
    document = get_object_or_404(InternshipDocument, id=document_id, health_school=health_school)

    # Verifica se já está assinado pela Escola de Saúde (pelo usuário atual)
    if DigitalSignature.objects.filter(document=document, signer=request.user, signer_type='health_school').exists():
        messages.info(request, "Este documento já foi assinado por você.")
        return redirect('health_school_view_document', document_id=document.id)

    if request.method == 'POST':
        signer_cpf = request.POST.get('signer_cpf')
        
        if not signer_cpf:
            messages.error(request, "O CPF é obrigatório para a assinatura digital.")
            return redirect('health_school_sign_document', document_id=document.id)
            
        # 1. Prepara dados da assinatura
        signature_data = {
            'signer_name': request.user.get_full_name() or request.user.username,
            'signer_email': request.user.email,
            'signer_type': 'health_school',
            'signing_timestamp': timezone.now().isoformat(),
            'document_hash': document.original_hash,
            'signing_reason': 'Assinatura digital pela Escola de Saúde',
        }
        
        # 2. Cria o objeto DigitalSignature
        signature = DigitalSignature.objects.create(
            document=document,
            signer=request.user,
            signer_type='health_school',
            signature_data=json.dumps(signature_data),
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            signer_name=request.user.get_full_name() or request.user.username,
            signer_email=request.user.email,
            signer_cpf=signer_cpf
        )
        
        # 3. Gera o hash da assinatura e salva
        signature.signature_hash = signature.generate_signature_hash()
        signature.save()
        
        # 4. Atualiza o status do documento para 'signed_health_school'
        document.status = 'signed_health_school'
        document.save()
        
        # 5. Adiciona o histórico
        DocumentHistory.objects.create(
            document=document,
            action='signed',
            performed_by=request.user,
            notes='Documento assinado digitalmente pela Escola de Saúde'
        )
        
        messages.success(request, f'Documento "{document.title}" assinado com sucesso! Enviado de volta para a universidade.')
        return redirect('health_school_view_document', document_id=document.id)
    
    # GET request - Renderiza o template de assinatura
    return render(request, 'health_school/sign_document.html', {
        'document': document,
        'health_school': health_school,
        'user': request.user
    })


# --- 3. DOWNLOADS ---

@login_required
def download_document(request, document_id, file_type):
    """Função auxiliar para downloads."""
    #
    document = get_object_or_404(InternshipDocument, id=document_id)
    
    # Verifica permissão: Usuário deve ser da University ou Health School envolvida
    is_authorized = document.university.admin_users.filter(id=request.user.id).exists() or \
                    document.health_school.admin_users.filter(id=request.user.id).exists()
    
    if not is_authorized:
        messages.error(request, "Você não tem permissão para acessar este documento.")
        return redirect('home')

    if file_type == 'original':
        file_field = document.original_file #
        filename = f"{document.title.replace(' ', '_')}_ORIGINAL.pdf"
    elif file_type == 'signed':
        file_field = document.signed_file #
        filename = f"{document.title.replace(' ', '_')}_ASSINADO.pdf"
    else:
        return HttpResponse("Tipo de arquivo inválido", status=400)

    if not file_field:
        messages.error(request, f"Arquivo {file_type} não encontrado para este documento.")
        return redirect(request.META.get('HTTP_REFERER', 'home'))

    # Serve o arquivo do FileField
    # A leitura direta de file_field.read() é usada aqui para simular o download
    response = HttpResponse(file_field.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
def download_original_document(request, document_id):
    """Faz o download do arquivo original."""
    return download_document(request, document_id, 'original')

@login_required
def download_signed_document(request, document_id):
    """Faz o download do arquivo assinado."""
    return download_document(request, document_id, 'signed')


# --- 4. REDIRECIONAMENTO ---

def home_redirect(request):
    """Redireciona usuário para o dashboard correto ou página inicial (usa base.html)."""
    if not request.user.is_authenticated:
        return render(request, 'home.html') 
    
    #
    if Institution.objects.filter(admin_users=request.user, type='university').exists():
        return redirect('university_dashboard')
    
    #
    if Institution.objects.filter(admin_users=request.user, type='health_school').exists():
        return redirect('health_school_dashboard')
    
    # Usuário logado sem papel definido
    messages.info(request, "Seu perfil não tem um dashboard associado.")
    return redirect('admin:index')