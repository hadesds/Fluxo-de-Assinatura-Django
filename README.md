# Fluxo de Assinatura Digital de Documentos (Django)

Este projeto implementa um sistema web para gerenciar e validar assinaturas digitais em documentos de estágio, focado no fluxo de trabalho entre **Universidades** e **Escolas de Saúde**.

O sistema utiliza o framework Django e Python, com autenticação baseada em funções (`university_required`, `health_school_required`) para controlar o acesso e o fluxo de documentos.

## 🚀 Funcionalidades Principais

* **Autenticação por Função:** Separação de acesso para administradores de Universidades e Escolas de Saúde.
* **Gestão de Documentos:** Envio de documentos de estágio pela Universidade para a Escola de Saúde.
* **Assinatura Visual e Precisa:** A Escola de Saúde pode visualizar o PDF no navegador (via PDF.js) e **clicar na área exata** onde o carimbo da assinatura deve ser aplicado.
* **Carimbo Digital com QR Code:** O backend gera e insere um carimbo com o nome do signatário, CPF, data/hora e um QR Code de validação.
* **Autenticação por Função:** Controle de acesso estrito para administradores de Universidades e Escolas de Saúde.
* **Auditoria Completa:** Registro de histórico de status e assinaturas digitais com dados de IP/User Agent.
* **Downloads:** Permite o download do documento original e do documento assinado/carimbado.

## ⚙️ Arquitetura do Processo de Assinatura

O processo de assinatura é dividido entre Frontend e Backend:

| Etapa | Tecnologia | Descrição |
| :--- | :--- | :--- |
| **Frontend** | HTML, JavaScript, **PDF.js** | Renderiza o PDF em um elemento `<canvas>`. Ao clicar, calcula e envia as coordenadas (X, Y) exatas para o servidor. |
| **Backend** | Python, **PyPDF2**, **ReportLab**, **qrcode** | Recebe as coordenadas, gera um PDF de carimbo (com texto e QR Code) usando ReportLab, e mescla esse carimbo na primeira página do PDF original usando PyPDF2. |

### Modelos Chave (`fluxo/models.py`)

| Modelo | Descrição | Relacionamentos Chave |
| :--- | :--- | :--- |
| **Institution** | Representa Universidades ou Escolas de Saúde. | `admin_users` (ManyToMany com `User`) |
| **InternshipDocument** | O documento central no fluxo de trabalho. | `university`, `health_school`, `created_by` |
| **DigitalSignature** | Registra cada assinatura digital aplicada a um documento. | `document`, `signer` |
| **DocumentHistory** | Log de todas as ações importantes (criação, envio, assinatura, rejeição). | `document`, `performed_by` |

### Fluxo de Trabalho (`fluxo/views.py` e `fluxo/urls.py`)

1.  **Universidade:**
    * Acessa o Dashboard (`/university/`).
    * Cria e envia um novo documento (rota `/university/send/`).
    * Visualiza o status do documento (`/university/document/<id>/`).
2.  **Escola de Saúde:**
    * Acessa o Dashboard (rota `/health-school/`).
    * Visualiza o documento pendente (`/health-school/document/<id>/`).
    * **Assina** o documento (`/health-school/document/<id>/sign/`).
3.  **Downloads:** Documentos podem ser baixados como **Original** ou **Assinado** (após a conclusão do fluxo de assinatura).

## 💻 Configuração e Instalação

### Pré-requisitos

* Python 3.10+ (Recomendado)
* Git (Opcional, para clonagem)
* Django 5.2.8
* Dependências listadas em `requirements.txt`
* **Dependências de Sistema** (Crucial para compilar `Pillow` e `ReportLab`)

### 2. Instalar Dependências de Sistema

Devido à natureza das bibliotecas de PDF e imagem, são necessários pacotes de desenvolvimento do sistema operacional (OS headers).

### 2. Ambiente Virtual

```bash
python -m venv venv
source venv/bin/activate ou venv\Scripts\activate no Windows

#### 🐧 Para Arch Linux (seu ambiente):

```bash
sudo pacman -S --needed zlib libjpeg libtiff libwebp lcms2