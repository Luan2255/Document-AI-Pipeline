<!-- Project overview, architecture, setup instructions, and API reference. -->
# Document AI Pipeline

API modular para receber imagens e PDFs, reconhecer texto com OCR, extrair informações com um modelo de linguagem e persistir resultados validados em PostgreSQL.

## Problema

Documentos recebidos em PDF ou imagem frequentemente contêm informações que precisam ser digitadas e integradas manualmente. Esta API automatiza a ingestão e a extração, retornando campos consistentes em JSON.

## Arquitetura

```text
Cliente -> FastAPI -> validação -> arquivo temporário -> OCR -> API LLM
                                                       -> Pydantic -> PostgreSQL
```

- `app/api`: rotas HTTP e conversão de erros em respostas da API.
- `app/core`: configurações por variáveis de ambiente e logging sem conteúdo documental.
- `app/db`: engine, sessões e modelos SQLAlchemy.
- `app/schemas`: contratos de entrada e dados extraídos validados com Pydantic.
- `app/services`: validação de arquivos, OCR, integração OpenAI-compatible e orquestração.
- `tests`: testes unitários e de integração da API.

## Pipeline

1. `POST /documents` recebe JPG, PNG ou PDF e verifica extensão, MIME, assinatura e tamanho.
2. O arquivo fica em armazenamento temporário durante o processamento; ele é removido ao final, inclusive em caso de erro.
3. PyMuPDF tenta extrair texto nativo de PDFs. Páginas sem texto aproveitável e imagens passam por Tesseract OCR.
4. O texto é enviado a uma API compatível com OpenAI, que retorna os campos estruturados.
5. Pydantic valida e normaliza a resposta antes da persistência.
6. SQLAlchemy grava o documento, os dados extraídos e um registro de processamento sem armazenar texto OCR, conteúdo pessoal ou credenciais.

## Tecnologias

Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy 2, PostgreSQL, PyMuPDF, Tesseract, Pillow, API LLM OpenAI-compatible, Docker Compose e Pytest.

## Instalação e configuração

Requisitos: Docker com Docker Compose. Para execução local, instale Python 3.12 e Tesseract com os pacotes de idioma português e inglês.

```bash
cp .env.example .env
```

Edite `.env`, substitua `POSTGRES_PASSWORD` e configure `LLM_API_KEY`, `LLM_BASE_URL` e `LLM_MODEL` para seu provedor OpenAI-compatible. A chave nunca é incluída no código nem na imagem. Para desenvolvimento local fora do Docker, configure `DATABASE_URL` para um PostgreSQL acessível com a mesma senha e instale o projeto:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Para executar a aplicação e o PostgreSQL em containers:

```bash
docker compose up --build
```

Documentação interativa: <http://localhost:8000/docs>. `GET /health` verifica a conectividade com o banco. Sem configurar um provedor LLM, o serviço inicia, mas `POST /documents` retorna HTTP 503.

## Exemplo de entrada

```bash
curl -X POST http://localhost:8000/documents \
  -F 'file=@documento.pdf;type=application/pdf'
```

## Exemplo de saída

```json
{
  "id": 1,
  "status": "completed",
  "created_at": "2025-01-15T12:30:00Z",
  "extracted_data": {
    "document_type": "identity_document",
    "name": "Maria Silva",
    "cpf": "123.456.789-00",
    "rg": null,
    "birth_date": "1990-05-10",
    "phone": null,
    "email": null,
    "address": null,
    "city": null,
    "state": null
  }
}
```

## Endpoints

- `POST /documents`: processa um arquivo multipart e retorna o resultado extraído.
- `GET /documents`: lista resultados paginados, sem retornar texto OCR.
- `GET /documents/{id}`: obtém o resultado de um documento.
- `DELETE /documents/{id}`: apaga o documento e os dados associados.
- `GET /health`: verifica se a API consegue acessar o banco.

## Banco de dados

- `documents`: metadados, status e data de criação; o arquivo original não é persistido.
- `extracted_data`: campos estruturados com relacionamento um-para-um.
- `processing_logs`: status, duração e código de erro, sem dados pessoais ou texto extraído.

As tabelas são criadas automaticamente ao iniciar a aplicação. Em produção, substitua essa inicialização por migrações versionadas.

## Testes

```bash
pip install -e '.[dev]'
pytest
```

Os testes usam SQLite isolado, substituem os serviços externos e não precisam de credenciais, banco PostgreSQL ou binário Tesseract.

## Limitações

- A qualidade do OCR depende da resolução, orientação e legibilidade do documento.
- PDFs limitados a 20 páginas e uploads limitados a 15 MiB por padrão.
- O modelo LLM pode produzir informações incorretas; a validação de esquema não confirma a veracidade dos dados.
- A integração do modelo requer uma API OpenAI-compatible configurada.
- Não há autenticação, autorização, antivírus ou limitação de requisições nesta versão.
- Dados extraídos contêm informações pessoais: proteja a rede, o banco e os backups, e defina políticas de retenção adequadas.

## Melhorias futuras

- Autenticação, autorização, rate limiting e cotas por cliente.
- Migrações Alembic, políticas de retenção e exclusão automática de dados.
- Fila assíncrona para documentos maiores e processamento em segundo plano.
- Métricas, tracing e auditoria com controles de acesso.
- Validação de CPF e datas e suporte a esquemas de extração configuráveis.