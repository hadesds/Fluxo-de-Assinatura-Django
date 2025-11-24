# Fluxo de Assinatura Digital de Documentos (Django)

Este projeto implementa um sistema web para gerenciar e validar assinaturas digitais em documentos de estágio, focado no fluxo de trabalho entre **Universidades** e **Escolas de Saúde**.

O sistema utiliza o framework Django e Python, com autenticação baseada em funções (`university_required`, `health_school_required`) para controlar o acesso e o fluxo de documentos.

## 🚀 Funcionalidades Principais

* **Autenticação por Função:** Separação de acesso para administradores de Universidades e Escolas de Saúde.
* **Gestão de Documentos:** Envio de documentos de estágio pela Universidade para a Escola de Saúde.
* **Assinatura Digital:** Processo de assinatura digital na interface da Escola de Saúde (requer CPF para autenticação).
* **Auditoria:** Registro de histórico de status e assinaturas digitais completas (Nome, CPF, Hash da Assinatura, Data/Hora).
* **Download:** Permite o download do documento original e do documento assinado.

## ⚙️ Arquitetura do Projeto

O projeto é estruturado em torno da aplicação `fluxo`.

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

* Python 3.x
* Django 5.2.8
* Dependências listadas em `requirements.txt`

### 1. Ambiente Virtual

```bash
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows