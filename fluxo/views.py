# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from .models import *
from django.http import HttpResponse
import hashlib
import json

# Decorators para verificar tipo de instituição
def university_required(function):
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            user_institutions = Institution.objects.filter(admin_users=request.user)
            if user_institutions.filter(type='university').exists():
                return function(request, *args, **kwargs)
        return redirect('access_denied')
    return wrapper

def health_school_required(function):
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            user_institutions = Institution.objects.filter(admin_users=request.user)
            if user_institutions.filter(type='health_school').exists():
                return function(request, *args, **kwargs)
        return redirect('access_denied')
    return wrapper

# --- INTERFACE DA UNIVERSIDADE ---

@login_required
@university_required
def university_dashboard(request):
    university = Institution.objects.filter(admin_users=request.user, type='university').first()
    
    documents = InternshipDocument.objects.filter(university=university).order_by('-created_at')
    
    status_counts = {
        'draft': documents.filter(status='draft').count(),
        'pending_students': documents.filter(status='pending_students').count(),
        'pending_university': documents.filter(status='pending_university').count(),
        'pending_health_school': documents.filter(status='pending_health_school').count(),
        'approved': documents.filter(status='approved').count(),
        'rejected': documents.filter(status='rejected').count(),
    }
    
    return render(request, 'university/dashboard.html', {
        'university': university,
        'documents': documents,
        'status_counts': status_counts
    })

@login_required
@university_required
def create_internship_request(request):
    university = Institution.objects.filter(admin_users=request.user, type='university').first()
    health_schools = Institution.objects.filter(type='health_school')
    students = Student.objects.filter(university=university)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        health_school_id = request.POST.get('health_school')
        student_ids = request.POST.getlist('students')
        file = request.FILES.get('file')
        
        health_school = get_object_or_404(Institution, id=health_school_id, type='health_school')
        
        document = InternshipDocument.objects.create(
            title=title,
            description=description,
            university=university,
            health_school=health_school,
            file=file,
            created_by=request.user,
            status='pending_students'
        )
        
        # Adicionar estudantes como signatários
        for student_id in student_ids:
            student = Student.objects.get(id=student_id, university=university)
            DocumentSigner.objects.create(
                document=document,
                student=student,
                signer_type='student',
                user=student.user
            )
        
        # Adicionar coordenador da universidade como signatário
        DocumentSigner.objects.create(
            document=document,
            signer_type='university_coordinator',
            user=request.user
        )
        
        # Adicionar coordenador da escola de saúde como signatário
        health_school_admin = health_school.admin_users.first()
        if health_school_admin:
            DocumentSigner.objects.create(
                document=document,
                signer_type='health_school_coordinator',
                user=health_school_admin
            )
        
        DocumentStatusHistory.objects.create(
            document=document,
            from_status='draft',
            to_status='pending_students',
            changed_by=request.user,
            notes='Documento criado e enviado para assinatura dos estudantes'
        )
        
        return redirect('university_document_detail', document_id=document.id)
    
    return render(request, 'university/create_request.html', {
        'health_schools': health_schools,
        'students': students
    })

@login_required
@university_required
def university_document_detail(request, document_id):
    university = Institution.objects.filter(admin_users=request.user, type='university').first()
    document = get_object_or_404(InternshipDocument, id=document_id, university=university)
    signers = document.documentsigner_set.all()
    progress = document.get_signature_progress()
    status_history = DocumentStatusHistory.objects.filter(document=document).order_by('-created_at')
    
    return render(request, 'university/document_detail.html', {
        'document': document,
        'signers': signers,
        'progress': progress,
        'status_history': status_history
    })

# --- INTERFACE DA ESCOLA DE SAÚDE ---

@login_required
@health_school_required
def health_school_dashboard(request):
    health_school = Institution.objects.filter(admin_users=request.user, type='health_school').first()
    
    documents = InternshipDocument.objects.filter(health_school=health_school).order_by('-created_at')
    
    status_counts = {
        'pending_health_school': documents.filter(status='pending_health_school').count(),
        'approved': documents.filter(status='approved').count(),
        'rejected': documents.filter(status='rejected').count(),
        'total': documents.count()
    }
    
    return render(request, 'health_school/dashboard.html', {
        'health_school': health_school,
        'documents': documents,
        'status_counts': status_counts
    })

@login_required
@health_school_required
def health_school_document_detail(request, document_id):
    health_school = Institution.objects.filter(admin_users=request.user, type='health_school').first()
    document = get_object_or_404(InternshipDocument, id=document_id, health_school=health_school)
    signers = document.documentsigner_set.all()
    progress = document.get_signature_progress()
    status_history = DocumentStatusHistory.objects.filter(document=document).order_by('-created_at')
    
    # Verificar se usuário atual é signatário
    user_signer = signers.filter(user=request.user).first()
    
    return render(request, 'health_school/document_detail.html', {
        'document': document,
        'signers': signers,
        'progress': progress,
        'status_history': status_history,
        'user_signer': user_signer
    })

# --- ASSINATURA ELETRÔNICA ---

@login_required
def sign_document(request, document_id):
    document = get_object_or_404(InternshipDocument, id=document_id)
    signer = get_object_or_404(DocumentSigner, document=document, user=request.user)
    
    if signer.signed_at:
        return JsonResponse({'error': 'Documento já assinado'}, status=400)
    
    if request.method == 'POST':
        # Processar assinatura
        signature_data = {
            'signer_name': request.user.get_full_name() or request.user.username,
            'signer_email': request.user.email,
            'signer_type': signer.signer_type,
            'signing_timestamp': timezone.now().isoformat(),
            'document_hash': document.original_hash,
            'signing_reason': 'Concordo com os termos do documento de estágio',
            'ip_address': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')
        }
        
        signer.signed_at = timezone.now()
        signer.signature_data = json.dumps(signature_data)
        signer.signature_hash = signer.generate_signature_hash()
        signer.ip_address = get_client_ip(request)
        signer.user_agent = request.META.get('HTTP_USER_AGENT', '')
        signer.save()
        
        # Atualizar status do documento baseado no progresso
        update_document_status(document, request.user)
        
        return JsonResponse({'success': True, 'message': 'Documento assinado com sucesso'})
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)

def update_document_status(document, changed_by):
    progress = document.get_signature_progress()
    old_status = document.status
    
    if progress['signed'] == progress['total']:
        new_status = 'approved'
    elif document.status == 'pending_students' and progress['signed'] > 0:
        # Verificar se todos os estudantes assinaram
        student_signers = document.documentsigner_set.filter(signer_type='student')
        signed_students = student_signers.filter(signed_at__isnull=False).count()
        if signed_students == student_signers.count():
            new_status = 'pending_health_school'
        else:
            new_status = document.status
    else:
        new_status = document.status
    
    if old_status != new_status:
        document.status = new_status
        document.save()
        
        DocumentStatusHistory.objects.create(
            document=document,
            from_status=old_status,
            to_status=new_status,
            changed_by=changed_by,
            notes=f'Status alterado devido ao progresso das assinaturas'
        )

@login_required
@health_school_required
def approve_document(request, document_id):
    health_school = Institution.objects.filter(admin_users=request.user, type='health_school').first()
    document = get_object_or_404(InternshipDocument, id=document_id, health_school=health_school)
    
    if request.method == 'POST':
        old_status = document.status
        document.status = 'approved'
        document.save()
        
        DocumentStatusHistory.objects.create(
            document=document,
            from_status=old_status,
            to_status='approved',
            changed_by=request.user,
            notes='Documento aprovado pela Escola de Saúde'
        )
        
        return JsonResponse({'success': True, 'message': 'Documento aprovado com sucesso'})
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)

@login_required
@health_school_required
def reject_document(request, document_id):
    health_school = Institution.objects.filter(admin_users=request.user, type='health_school').first()
    document = get_object_or_404(InternshipDocument, id=document_id, health_school=health_school)
    
    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        old_status = document.status
        document.status = 'rejected'
        document.save()
        
        DocumentStatusHistory.objects.create(
            document=document,
            from_status=old_status,
            to_status='rejected',
            changed_by=request.user,
            notes=f'Documento reprovado: {notes}'
        )
        
        return JsonResponse({'success': True, 'message': 'Documento reprovado'})
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)

def home_redirect(request):
    """Redireciona usuário para o dashboard correto ou página inicial"""
    if not request.user.is_authenticated:
        return render(request, 'home.html')
    
    try:
        # Verificar se é administrador da universidade
        university_institutions = Institution.objects.filter(admin_users=request.user, type='university')
        if university_institutions.exists():
            return redirect('university_dashhomeboard')
        
        # Verificar se é administrador da escola de saúde
        health_school_institutions = Institution.objects.filter(admin_users=request.user, type='health_school')
        if health_school_institutions.exists():
            return redirect('health_school_dashboard')
        
        # Verificar se é estudante
        if Student.objects.filter(user=request.user).exists():
            return redirect('student_dashboard')
        
    except Exception as e:
        # Em caso de erro, redireciona para login
        print(f"Erro no redirecionamento: {e}")
        return render(request, 'home.html')

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@login_required
def student_dashboard(request):
    """Dashboard básico para estudantes"""
    try:
        student = Student.objects.get(user=request.user)
        return render(request, 'student/dashboard.html', {
            'student': student,
        })
    except Student.DoesNotExist:
        messages.error(request, "Acesso permitido apenas para estudantes.")
        return redirect('home')