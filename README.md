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

A UI permite upload de imagens (não há mais opção de carregar amostras locais).

## Notas

- Modelo utilizado: `gpt-5-nano`.
- Saída normalizada inclui: `marca_nome`, `marca`, `produto`, `preco_brl`, `preco_brl_texto`, `condicoes`.

## Autenticação da OpenAI

Você pode informar a chave da OpenAI pela UI (sidebar) ou via `.env`/variáveis de ambiente/`secrets`.
