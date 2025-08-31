# Lothus AI Reader – Streamlit

Aplicação Streamlit para extrair de imagens (banners/folhetos/posts):

- Marca + Nome do Produto
- Preço (BRL)
- Condições (desconto/data)

Usa LLM com visão para detectar múltiplos produtos por imagem, exibir tabela e exportar CSV.

## Requisitos

- Python 3.10+
- Chave da OpenAI (`OPENAI_API_KEY`)

## Instalação

```bash
pip install -r requirements.txt
```

## Execução

```bash
# Opção A: usar .env (recomendado)
cp .env .env.local  # opcional, ou edite diretamente .env
echo "OPENAI_API_KEY=seu_token_aqui" >> .env

# Opção B: variável de ambiente
export OPENAI_API_KEY=seu_token_aqui

streamlit run app.py
```

A UI permite upload de imagens ou uso das amostras em `./sample-data`.

## Notas

- Modelos sugeridos: `gpt-4o-mini` (econômico) e `gpt-4o`.
- Saída normalizada inclui: `marca_nome`, `marca`, `produto`, `preco_brl`, `preco_brl_texto`, `condicoes`.

## Controle de acesso (allowlist de e-mails)

Para restringir o uso a e-mails específicos no deploy público (ex.: [Streamlit Cloud](https://share.streamlit.io/)):

- Defina `ALLOWED_EMAILS` como lista no `secrets.toml`:

```toml
ALLOWED_EMAILS = [
  "email1@dominio.com",
  "email2@dominio.com"
]
```

Ou como string separada por vírgulas (env):

```bash
export ALLOWED_EMAILS="email1@dominio.com,email2@dominio.com"
```

Localmente, se precisar simular um usuário:

```bash
export STREAMLIT_USER_EMAIL="seu.email@dominio.com"
```

Obs.: E-mails não ficam expostos no código; use secrets/env no provedor.
