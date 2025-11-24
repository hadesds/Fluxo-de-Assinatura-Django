# fluxo/views.py - Versão Final com Carimbo PDF
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.contrib import messages
from django.core.files.base import ContentFile

from .models import Institution, InternshipDocument, DigitalSignature, DocumentHistory
import hashlib
import json
import os 

# --- IMPORTS PARA MANIPULAÇÃO DE PDF E QR CODE ---
import io
import qrcode
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
# Nota: ReportLab usa pontos (pt). A4 = (595.2755905511812, 841.8897637795277)
from PyPDF2 import PdfReader, PdfWriter, Transformation

# --- UTILITIES ---
# ... (get_client_ip, university_required, health_school_required, e dashboards)
# Funções inalteradas

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

# --- INTERFACE DA UNIVERSIDADE (Views simplificadas/mantidas) ---

@login_required
@university_required
def university_dashboard(request):
    """Dashboard principal da Universidade (usa university/dashboard.html)."""
    university = get_object_or_404(Institution, admin_users=request.user, type='university')
    
    documents = InternshipDocument.objects.filter(university=university).order_by('-created_at')
    
    status_counts = {
        'pending': documents.filter(status='pending_health_school').count(),
        'signed': documents.filter(status='signed_health_school').count(),
        'completed': documents.filter(status='completed').count(),
        'total': documents.count(),
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
    university = get_object_or_404(Institution, admin_users=request.user, type='university')
    health_schools = Institution.objects.filter(type='health_school')
    
    # Placeholder
    students = []
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        health_school_id = request.POST.get('health_school')
        num_students = int(request.POST.get('num_students', 0))
        file = request.FILES.get('file')
        
        health_school = get_object_or_404(Institution, id=health_school_id, type='health_school')
        
        # Criação do Documento
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
        DocumentHistory.objects.create(
            document=document,
            action='sent',
            performed_by=request.user,
            notes='Documento enviado para assinatura da Escola de Saúde'
        )
        
        # Cria a DigitalSignature para o remetente (Universidade)
        DigitalSignature.objects.create(
            document=document,
            signer=request.user,
            signer_type='university',
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
    
    return render(request, 'university/create_request.html', {
        'university': university,
        'health_schools': health_schools,
        'students': students
    })

@login_required
@university_required
def university_view_document(request, document_id):
    """Detalhes de um documento na visão da Universidade (usa university/view_document.html)."""
    university = get_object_or_404(Institution, admin_users=request.user, type='university')
    document = get_object_or_404(InternshipDocument, id=document_id, university=university)
    
    signatures = document.signatures.all() 
    history = document.history.all() 
    
    return render(request, 'university/view_document.html', {
        'document': document,
        'university': university,
        'signatures': signatures,
        'history': history,
    })

# --- INTERFACE DA ESCOLA DE SAÚDE (Views simplificadas/mantidas) ---

@login_required
@health_school_required
def health_school_dashboard(request):
    """Dashboard principal da Escola de Saúde."""
    messages.info(request, "Dashboard da Escola de Saúde não possui template no escopo.")
    return redirect('home')

@login_required
@health_school_required
def health_school_view_document(request, document_id):
    """Detalhes de um documento na visão da Escola de Saúde (usa health_school/view_document.html)."""
    health_school = get_object_or_404(Institution, admin_users=request.user, type='health_school')
    document = get_object_or_404(InternshipDocument, id=document_id, health_school=health_school)
    
    signatures = document.signatures.all() 
    history = document.history.all() 
    
    return render(request, 'health_school/view_document.html', {
        'document': document,
        'health_school': health_school,
        'signatures': signatures,
        'history': history,
    })

# --- MÓDULO DE MANIPULAÇÃO DE PDF ---

def create_signature_stamp_pdf(signature_info, position_x, position_y, signature_hash):
    """Cria um PDF de uma página com o carimbo da assinatura e QR Code."""
    buffer = io.BytesIO()
    
    # Tamanho da página (usando A4)
    p_width, p_height = A4 
    
    # Cria o objeto ReportLab Canvas
    c = canvas.Canvas(buffer, pagesize=A4)

    # --- Configurações de Posição ---
    # Convertendo as coordenadas de pixel (canvas) para pontos (pt)
    # Assumimos uma proporção aproximada do A4 (largura de 595.275 pt)
    # E que a coordenada Y já está invertida (origem inferior esquerda)
    
    # Fator de escala SIMPLIFICADO para conversão de pixel para ponto
    # Nota: Em um sistema real, o fator de escala deve ser calculado dinamicamente
    # baseado nas dimensões reais do PDF e da tela do cliente.
    # Usaremos um fator arbitrário de 0.7 para que o carimbo não seja muito grande.
    SCALE_FACTOR = 0.7 
    
    # Posição X e Y (em pontos)
    # Usamos position_x (pixel) * SCALE_FACTOR
    # Usamos position_y (pixel) * SCALE_FACTOR
    x_pt = float(position_x) * SCALE_FACTOR
    y_pt = float(position_y) * SCALE_FACTOR
    
    # Garante que o carimbo fique dentro dos limites da página
    x_pt = min(x_pt, p_width - 200) 
    y_pt = max(y_pt, 50) 
    
    # --- 1. Carimbo de Texto da Assinatura ---
    c.setFont("Helvetica-Bold", 8)
    
    # Texto do carimbo
    text = c.beginText(x_pt + 60, y_pt + 40)
    text.setFont("Helvetica-Bold", 8)
    text.setFillColorRGB(0.1, 0.1, 0.1)
    
    text.textLine(f"ASSINADO DIGITALMENTE ({signature_info['signer_type'].upper()})")
    text.setFont("Helvetica", 7)
    text.textLine(f"Nome: {signature_info['signer_name']}")
    text.textLine(f"CPF: {signature_info['signer_cpf']}")
    text.textLine(f"Data: {signature_info['signing_timestamp'][:19].replace('T', ' ')} (UTC)")
    text.textLine(f"Hash: {signature_hash[:25]}...")
    text.textLine(f"Doc Hash: {signature_info['document_hash'][:25]}...")
    
    c.drawText(text)
    
    # Borda do carimbo
    c.rect(x_pt, y_pt, 220, 50, stroke=1, fill=0)

    # --- 2. QR Code ---
    try:
        qr_data = f"HASH:{signature_hash}|DOC:{signature_info['document_hash']}|ID:{signature_info['document_id']}"
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=3, border=1)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        
        # Salva o QR Code em um buffer para o ReportLab
        qr_buffer = io.BytesIO()
        img_qr.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        
        # Desenha o QR Code ao lado do texto
        c.drawImage(ImageReader(qr_buffer), x_pt + 5, y_pt + 5, width=40, height=40)
        
    except Exception as e:
        # Em caso de falha no QR Code, apenas registra o erro e prossegue
        print(f"Erro ao gerar QR Code: {e}")
        
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def apply_signature_to_pdf(document, signature_info, signature_hash, position_x, position_y):
    """
    Mescla o PDF do carimbo (overlay) com a primeira página do PDF original.
    Retorna o conteúdo binário do PDF assinado.
    """
    try:
        # 1. Cria o carimbo PDF
        stamp_pdf_buffer = create_signature_stamp_pdf(signature_info, position_x, position_y, signature_hash)
        stamp_reader = PdfReader(stamp_pdf_buffer)
        stamp_page = stamp_reader.pages[0]
        
        # 2. Carrega o PDF original
        document.original_file.seek(0)
        original_reader = PdfReader(document.original_file)
        writer = PdfWriter()
        
        # 3. Mescla o carimbo na primeira página
        if original_reader.pages:
            first_page = original_reader.pages[0]
            
            # Use a largura e altura da página original para alinhamento se necessário
            # Aqui, apenas adicionamos o carimbo como overlay
            first_page.merge_page(stamp_page)
            writer.add_page(first_page)
            
            # Adiciona as páginas restantes
            for page_num in range(1, len(original_reader.pages)):
                writer.add_page(original_reader.pages[page_num])

        # 4. Salva o novo PDF mesclado em um buffer
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        
        return output_buffer.read()
        
    except Exception as e:
        print(f"Erro no apply_signature_to_pdf: {e}")
        return None


# --- ATUALIZAÇÃO DA VIEW health_school_sign_document ---

@login_required
@health_school_required
def health_school_sign_document(request, document_id):
    """Exibe o formulário de assinatura e processa o POST (usa health_school/sign_document.html)."""
    health_school = get_object_or_404(Institution, admin_users=request.user, type='health_school')
    document = get_object_or_404(InternshipDocument, id=document_id, health_school=health_school)

    if DigitalSignature.objects.filter(
        document=document, 
        signer=request.user, 
        signer_type='health_school'
    ).exists():
        messages.info(request, "Este documento já foi assinado por você.")
        return redirect('health_school_view_document', document_id=document.id)

    if request.method == 'POST':
        signer_cpf = request.POST.get('signer_cpf')
        
        # OBTENÇÃO DA POSIÇÃO DA ASSINATURA NO PDF (Coordenadas em Pixel da Tela)
        signature_x = request.POST.get('signature_x') 
        signature_y = request.POST.get('signature_y')
        
        if not signer_cpf or not signature_x or not signature_y:
            messages.error(request, "O CPF e a posição de assinatura são obrigatórios.")
            return redirect('health_school_sign_document', document_id=document.id)
            
        # 1. Cria a DigitalSignature (temporariamente para obter o hash de auditoria)
        # O Hash da Assinatura depende de todos os dados, incluindo a hora exata.
        temp_signature = DigitalSignature(
            document=document,
            signer=request.user,
            signer_type='health_school',
            # Usar data e hora exata AGORA para o hash
            signed_at=timezone.now(), 
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            signer_name=request.user.get_full_name() or request.user.username,
            signer_email=request.user.email,
            signer_cpf=signer_cpf
        )

        # Prepara dados completos para o carimbo e o registro final
        signature_info = {
            'document_id': document.id,
            'signer_name': temp_signature.signer_name,
            'signer_email': temp_signature.signer_email,
            'signer_cpf': temp_signature.signer_cpf,
            'signer_type': 'health_school',
            'signing_timestamp': temp_signature.signed_at.isoformat(),
            'document_hash': document.original_hash,
            'position_x': signature_x,
            'position_y': signature_y
        }
        
        # Garante que o campo signature_data (que alimenta o hash) esteja preenchido
        temp_signature.signature_data = json.dumps(signature_info)
        
        # Gera o Hash da Assinatura
        signature_hash = temp_signature.generate_signature_hash() #
        
        # --- NOVO: APLICAÇÃO DO CARIMBO AO PDF ---
        signed_pdf_content = apply_signature_to_pdf(
            document, 
            signature_info, 
            signature_hash, 
            signature_x, 
            signature_y
        )

        if signed_pdf_content is None:
             messages.error(request, "Falha ao gerar o documento assinado digitalmente. Verifique as dependências PDF.")
             return redirect('health_school_sign_document', document_id=document.id)

        # 2. Atualiza e salva a DigitalSignature
        temp_signature.signature_hash = signature_hash
        temp_signature.signature_data = json.dumps(signature_info) # Salva a posição
        temp_signature.save() # Salva o registro no banco
        
        # 3. Salva o novo arquivo PDF assinado no modelo InternshipDocument
        document.signed_file.save(
            name=f'signed_{document.id}_{temp_signature.signer_name.replace(" ", "_")}.pdf',
            content=ContentFile(signed_pdf_content)
        )
        document.status = 'signed_health_school' #
        document.save()
        
        # 4. Adiciona o histórico
        DocumentHistory.objects.create(
            document=document,
            action='signed',
            performed_by=request.user,
            notes=f'Documento assinado digitalmente na posição X:{signature_x}, Y:{signature_y}'
        )
        
        messages.success(request, f'Documento "{document.title}" assinado com sucesso! Enviado de volta para a universidade.')
        return redirect('health_school_view_document', document_id=document.id)
    
    # GET request
    return render(request, 'health_school/sign_document.html', {
        'document': document,
        'health_school': health_school,
        'user': request.user
    })

# --- DOWNLOADS E REDIRECIONAMENTO (inalteradas) ---
# ...
@login_required
def download_document(request, document_id, file_type):
    """Função auxiliar para downloads."""
    document = get_object_or_404(InternshipDocument, id=document_id)
    
    is_authorized = document.university.admin_users.filter(id=request.user.id).exists() or \
                    document.health_school.admin_users.filter(id=request.user.id).exists()
    
    if not is_authorized:
        messages.error(request, "Você não tem permissão para acessar este documento.")
        return redirect('home')

    if file_type == 'original':
        file_field = document.original_file
        filename = f"{document.title.replace(' ', '_')}_ORIGINAL.pdf"
    elif file_type == 'signed':
        file_field = document.signed_file
        filename = f"{document.title.replace(' ', '_')}_ASSINADO.pdf"
    else:
        return HttpResponse("Tipo de arquivo inválido", status=400)

    if not file_field:
        messages.error(request, f"Arquivo {file_type} não encontrado para este documento.")
        return redirect(request.META.get('HTTP_REFERER', 'home'))

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

def home_redirect(request):
    """Redireciona usuário para o dashboard correto ou página inicial (usa base.html)."""
    if not request.user.is_authenticated:
        return render(request, 'home.html') 
    
    if Institution.objects.filter(admin_users=request.user, type='university').exists():
        return redirect('university_dashboard')
    
    if Institution.objects.filter(admin_users=request.user, type='health_school').exists():
        return redirect('health_school_dashboard')
    
    messages.info(request, "Seu perfil não tem um dashboard associado.")
    return redirect('admin:index')