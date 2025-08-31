import base64
import io
import json
import mimetypes
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from PIL import Image
import streamlit as st
from dotenv import load_dotenv

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


@dataclass
class ExtractedProduct:
    source_file: str
    marca_nome: Optional[str]
    marca: Optional[str]
    produto: Optional[str]
    preco_brl: Optional[float]
    preco_brl_texto: Optional[str]
    condicoes: List[Dict[str, Any]]


INSTRUCTIONS_PT = (
    """
Você é um assistente especializado em leitura de ofertas em imagens (banners, folhetos, posts).
Extraia todos os produtos distintos que aparecem na imagem e retorne apenas JSON conforme o schema.

Regras:
- Para cada produto, identifique: "marca_nome" (Marca + Nome do Produto), "marca" (se visível), "produto" (nome/modelo),
  "preco_brl" (como número, em reais; use ponto decimal), e "preco_brl_texto" (captura textual como aparece na imagem, ex: "R$ 29,90").
- Em "condicoes", liste itens com {"tipo": "desconto|data|outro", "valor": "texto"}.
- Se houver múltiplos produtos e preços, associe o preço correto a cada produto.
- Se faltar alguma informação, deixe o campo como string vazia ou omita a subchave opcional; nunca invente.
- Não adicione comentários nem texto fora do JSON. Retorne SOMENTE o JSON.

Schema JSON alvo:
{
  "products": [
    {
      "marca_nome": "string",
      "marca": "string opcional",
      "produto": "string opcional",
      "preco_brl": 0.0,
      "preco_brl_texto": "string opcional",
      "condicoes": [
        {"tipo": "desconto|data|outro", "valor": "string"}
      ]
    }
  ]
}
"""
).strip()


def encode_image_to_data_url(image_bytes: bytes, filename: str) -> Tuple[str, str]:
    mime, _ = mimetypes.guess_type(filename)
    if not mime:
        mime = "image/jpeg"
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}", mime


def image_file_to_bytes(file_like) -> bytes:
    # Streamlit's UploadedFile supports .read(); local files we open via PIL and save to bytes
    data = file_like.read()
    if data is not None and len(data) > 0:
        return data
    # Fallback (should rarely happen): try PIL conversion
    file_like.seek(0)
    img = Image.open(file_like)
    buf = io.BytesIO()
    img.save(buf, format=img.format or "JPEG")
    return buf.getvalue()


def pil_image_to_bytes(img: Image.Image, format_hint: Optional[str] = None) -> bytes:
    buf = io.BytesIO()
    fmt = format_hint or img.format or "JPEG"
    img.save(buf, format=fmt)
    return buf.getvalue()


def extract_products_from_image(client, model: str, image_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    data_url, _ = encode_image_to_data_url(image_bytes, filename)

    messages = [
        {
            "role": "system",
            "content": INSTRUCTIONS_PT,
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Extraia os produtos desta imagem e retorne apenas o JSON."},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=messages,
    )
    content = response.choices[0].message.content
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        # Try to salvage basic JSON object from text
        content_stripped = content.strip()
        start = content_stripped.find("{")
        end = content_stripped.rfind("}")
        if start != -1 and end != -1:
            payload = json.loads(content_stripped[start : end + 1])
        else:
            payload = {"products": []}

    products = payload.get("products", []) or []
    normalized: List[Dict[str, Any]] = []
    for p in products:
        # Normalize fields and types
        marca_nome = p.get("marca_nome") or p.get("marca+nome") or p.get("nome") or ""
        marca = p.get("marca") or ""
        produto = p.get("produto") or ""
        preco_brl_val = p.get("preco_brl")
        preco_brl_texto = p.get("preco_brl_texto") or p.get("preco_texto") or ""
        try:
            preco_brl = float(preco_brl_val) if preco_brl_val is not None else None
        except Exception:
            # Attempt to parse from text like "R$ 29,90"
            preco_str = str(preco_brl_val or preco_brl_texto or "").replace("R$", "").replace(" ", "")
            preco_str = preco_str.replace(".", "").replace(",", ".")
            try:
                preco_brl = float(preco_str)
            except Exception:
                preco_brl = None

        condicoes = p.get("condicoes") or []
        if isinstance(condicoes, dict):
            condicoes = [condicoes]
        if not isinstance(condicoes, list):
            condicoes = []

        normalized.append(
            {
                "marca_nome": marca_nome,
                "marca": marca,
                "produto": produto,
                "preco_brl": preco_brl,
                "preco_brl_texto": preco_brl_texto,
                "condicoes": condicoes,
            }
        )

    return normalized


def build_dataframe(rows: List[Tuple[str, Dict[str, Any]]]) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    for filename, product in rows:
        condicoes = product.get("condicoes") or []
        if isinstance(condicoes, list):
            condicoes_str = "; ".join(
                [
                    f"{(c.get('tipo') or 'outro')}: {c.get('valor') or ''}"
                    for c in condicoes
                    if isinstance(c, dict)
                ]
            )
        else:
            condicoes_str = str(condicoes)

        records.append(
            {
                "arquivo": filename,
                "marca_nome": product.get("marca_nome"),
                "marca": product.get("marca"),
                "produto": product.get("produto"),
                "preco_brl": product.get("preco_brl"),
                "preco_brl_texto": product.get("preco_brl_texto"),
                "condicoes": condicoes_str,
            }
        )

    df = pd.DataFrame.from_records(records)
    # Order columns
    desired = [
        "arquivo",
        "marca_nome",
        "marca",
        "produto",
        "preco_brl",
        "preco_brl_texto",
        "condicoes",
    ]
    df = df[[c for c in desired if c in df.columns]]
    return df


def get_openai_client(api_key: Optional[str]):
    if OpenAI is None:
        raise RuntimeError("Pacote openai não está instalado. Verifique requirements.txt e instale as dependências.")
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Chave da OpenAI ausente. Informe a chave na UI ou via variável de ambiente OPENAI_API_KEY.")
    return OpenAI(api_key=key)


def list_sample_images(sample_dir: str) -> List[str]:
    paths: List[str] = []
    if not os.path.isdir(sample_dir):
        return paths
    for name in os.listdir(sample_dir):
        lower = name.lower()
        if lower.endswith((".jpg", ".jpeg", ".png")):
            paths.append(os.path.join(sample_dir, name))
    paths.sort()
    return paths


def main() -> None:
    # Carrega variáveis do .env se existir
    try:
        load_dotenv(override=False)
    except Exception:
        pass

    st.set_page_config(page_title="Leitor de Ofertas - Lothus AI", layout="wide")
    st.title("Leitor de Ofertas com LLM (Streamlit)")
    st.caption("Extração de Marca+Produto, Preço (BRL) e Condições a partir de imagens.")

    with st.sidebar:
        st.header("Configuração")
        # Campo para chave da OpenAI (com valor padrão vindo de env/secrets)
        default_key = os.getenv("OPENAI_API_KEY", "")
        if not default_key:
            try:
                default_key = st.secrets["OPENAI_API_KEY"]  # type: ignore[index]
            except Exception:
                default_key = ""
        api_key = st.text_input("OpenAI API Key", value=default_key, type="password")

        model = st.selectbox(
            "Modelo",
            options=["gpt-4o-mini", "gpt-4o", "gpt-5"],
            index=0,
            help="Modelos com visão. 'gpt-4o-mini' é mais econômico.",
        )

    st.subheader("Fonte de Imagens")
    col1, col2 = st.columns(2)
    uploaded_files = col1.file_uploader(
        "Envie imagens (JPG/PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True
    )

    sample_dir = os.path.join(os.getcwd(), "sample-data")
    sample_paths = list_sample_images(sample_dir)
    use_samples = False
    if col2.button("Carregar amostras da pasta ./sample-data"):
        use_samples = True

    images_to_process: List[Tuple[str, bytes]] = []
    preview_columns = st.columns(4)
    col_idx = 0

    if uploaded_files:
        st.write(f"Imagens enviadas: {len(uploaded_files)}")
        for up in uploaded_files:
            up_bytes = up.read()
            up.seek(0)
            images_to_process.append((up.name, up_bytes))
            try:
                img = Image.open(io.BytesIO(up_bytes))
                with preview_columns[col_idx % 4]:
                    st.image(img, caption=up.name, use_column_width=True)
            except Exception:
                pass
            col_idx += 1

    if use_samples and sample_paths:
        st.write(f"Amostras localizadas: {len(sample_paths)}")
        for path in sample_paths:
            try:
                img = Image.open(path)
                img_bytes = pil_image_to_bytes(img)
                images_to_process.append((os.path.basename(path), img_bytes))
                with preview_columns[col_idx % 4]:
                    st.image(img, caption=os.path.basename(path), use_column_width=True)
            except Exception:
                continue
            col_idx += 1

    st.divider()
    run = st.button("Extrair dados com LLM", type="primary", use_container_width=True)

    if run:
        if not images_to_process:
            st.warning("Envie imagens ou carregue amostras para continuar.")
            st.stop()
        try:
            client = get_openai_client(api_key)
        except Exception as e:
            st.error(str(e))
            st.stop()

        progress = st.progress(0.0, text="Processando imagens...")
        collected: List[Tuple[str, Dict[str, Any]]] = []

        for idx, (filename, img_bytes) in enumerate(images_to_process, start=1):
            try:
                products = extract_products_from_image(client, model, img_bytes, filename)
                for p in products:
                    collected.append((filename, p))
            except Exception as ex:
                st.error(f"Falha ao processar {filename}: {ex}")
            progress.progress(idx / max(len(images_to_process), 1), text=f"Processado {idx}/{len(images_to_process)}")

        if not collected:
            st.info("Nenhum produto encontrado nas imagens enviadas.")
            st.stop()

        df = build_dataframe(collected)
        st.subheader("Resultados")
        st.dataframe(df, use_container_width=True)

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Baixar CSV",
            data=csv_bytes,
            file_name="ofertas_extraidas.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()


