# =========================================================
# PAINEL DE GESTÃO - MERCHAN PDV
# KoboToolbox + Streamlit + Folium + Base de Lojas + SLA
# =========================================================

# =========================================================
# 1. IMPORTAÇÃO DE BIBLIOTECAS
# =========================================================

from geopy.distance import geodesic
from io import BytesIO
from streamlit_autorefresh import st_autorefresh
from streamlit.components.v1 import html
import base64
import folium
import math
import pandas as pd
import requests
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import os


# =========================================================
# 2. CONFIGURAÇÕES DO KOBO E ARQUIVOS LOCAIS
# =========================================================

TOKEN = st.secrets["KOBO_TOKEN"]
ASSET_ID = "aQVpdCVPTPEkJxiWie4CqN"
URL = f"https://kf.kobotoolbox.org/api/v2/assets/{ASSET_ID}/data.json"
HEADERS = {"Authorization": f"Token {TOKEN}"}
ARQUIVO_LOJAS = "lojas.csv"
LOGO = "logo_merchan_pdv.jpeg.jpeg"


# =========================================================
# 3. CAMPOS TÉCNICOS DO FORMULÁRIO KOBO
# =========================================================

CAMPO_LOJA = "sel_loja"
CAMPO_GPS = "geo_localizacao"
CAMPO_STATUS = "loja_abastecida"


# =========================================================
# 4. CONFIGURAÇÃO DA PÁGINA
# =========================================================

st.set_page_config(
    page_title="Painel de Gestão - Merchan PDV",
    layout="wide"
)

# Atualização automática a cada 30 minutos.
st_autorefresh(interval=1800000, key="refresh")

# Botão para atualização manual.
if st.button("🔄 Atualizar agora"):
    st.cache_data.clear()
    st.rerun()


# =========================================================
# 5. IDENTIDADE VISUAL / CSS
# =========================================================

st.markdown("""
<style>
.main { background-color: #f5f7fb; }

h1, h2, h3 { color: #1E2A78; }

section[data-testid="stSidebar"] { background-color: #1E2A78; }

section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: white !important;
}

/* ===== FILTROS SIDEBAR ===== */
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] select,
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background-color: white !important;
    color: black !important;
}

section[data-testid="stSidebar"] div[data-baseweb="select"] * { color: black !important; }
section[data-testid="stSidebar"] input::placeholder { color: #555 !important; }
div[role="listbox"] * { color: black !important; }

/* ===== BOTÕES ===== */
.stButton > button,
.stDownloadButton > button {
    background-color: #60A5FA !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.5rem 1rem !important;
    font-weight: bold !important;
    transition: 0.3s !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
    background-color: #1D4ED8 !important;
    color: white !important;
    border: none !important;
}

/* ===== CARDS ===== */
.metric-card {
    background: white;
    border-radius: 15px;
    padding: 18px;
    border-left: 8px solid #F8E826;
    box-shadow: 0px 2px 8px rgba(0,0,0,0.08);
    height: 115px;
}
.metric-card h4 {
    color: #1E2A78;
    margin: 0;
    font-size: 15px;
}
.metric-card h2 {
    color: #111827;
    margin: 8px 0 0 0;
    font-size: 28px;
}

/* ===== TABELA HTML ===== */
table {
    width: 100%;
    border-collapse: collapse;
    font-family: Arial;
    background: white;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0px 2px 8px rgba(0,0,0,0.08);
}
th {
    padding: 14px;
    background-color: #1E2A78;
    color: white;
    text-align: center;
    font-size: 14px;
}
td {
    padding: 14px;
    text-align: center;
    vertical-align: middle;
    border-bottom: 1px solid #E5E7EB;
}
.status-ok { color: #0F766E; font-weight: bold; }
.status-alerta { color: #DC2626; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


# =========================================================
# 6. TOPO DO PAINEL
# =========================================================

col_logo, col_titulo = st.columns([1, 5])

with col_logo:
    try:
        st.image(LOGO, width=140)
    except Exception:
        st.warning("Logo não encontrada.")

with col_titulo:
    st.title("Painel de Gestão - Merchan PDV")
    st.markdown("### Monitoramento de promotores, visitas, fotos, localização e SLA de atendimento")


# =========================================================
# 7. FUNÇÕES DE CARREGAMENTO
# =========================================================

@st.cache_data(ttl=30)
def carregar_dados_kobo():
    """Consulta a API do Kobo e retorna as submissões em DataFrame."""
    resposta = requests.get(URL, headers=HEADERS)

    if resposta.status_code != 200:
        st.error(f"Erro ao acessar API Kobo: {resposta.status_code}")
        st.write(resposta.text)
        return pd.DataFrame()

    dados = resposta.json()

    if isinstance(dados, dict) and "results" in dados:
        resultados = dados["results"]
    elif isinstance(dados, list):
        resultados = dados
    else:
        st.error("Formato de retorno da API não reconhecido.")
        st.write(dados)
        return pd.DataFrame()

    return pd.json_normalize(resultados) if resultados else pd.DataFrame()


@st.cache_data(ttl=30)
def carregar_lojas():
    """Carrega a base mestre de lojas do arquivo lojas.csv."""
    try:
        df_lojas = pd.read_csv(ARQUIVO_LOJAS, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df_lojas = pd.read_csv(ARQUIVO_LOJAS, encoding="latin1")
    except FileNotFoundError:
        st.error(f"Arquivo {ARQUIVO_LOJAS} não encontrado na pasta do projeto.")
        return pd.DataFrame()

    colunas_numericas = [
        "latitude_loja",
        "longitude_loja",
        "raio_metros",
        "frequencia_mensal_prevista",
        "intervalo_minimo_retorno_dias"
    ]

    for coluna in colunas_numericas:
        if coluna in df_lojas.columns:
            df_lojas[coluna] = pd.to_numeric(df_lojas[coluna], errors="coerce")

    if "status" in df_lojas.columns:
        df_lojas = df_lojas[
            df_lojas["status"].astype(str).str.lower() == "ativo"
        ]

    return df_lojas


# =========================================================
# 8. FUNÇÕES UTILITÁRIAS
# =========================================================

@st.cache_data(show_spinner=False)
def imagem_base64(url):
    """Baixa imagem protegida do Kobo e converte para Base64."""
    if not url:
        return None

    try:
        resposta = requests.get(url, headers=HEADERS)

        if resposta.status_code == 200:
            return base64.b64encode(resposta.content).decode("utf-8")

        return None

    except Exception:
        return None


def nome_bonito(valor):
    """Converte texto técnico em texto amigável."""
    if pd.isna(valor):
        return ""

    return str(valor).replace("_", " ").title()


def obter_lat_long(row):
    """Extrai latitude e longitude do campo GPS do Kobo."""
    try:
        geo = row.get(CAMPO_GPS)

        if isinstance(geo, list):
            return float(geo[0]), float(geo[1])

        if isinstance(geo, str):
            partes = geo.split()
            return float(partes[0]), float(partes[1])

        geo_padrao = row.get("_geolocation")

        if isinstance(geo_padrao, list):
            return float(geo_padrao[0]), float(geo_padrao[1])

        return None, None

    except Exception:
        return None, None


def extrair_fotos(row):
    """Separa as fotos em fachada, antes e depois."""
    fachada = ""
    antes = ""
    depois = ""

    attachments = row.get("_attachments", [])

    if isinstance(attachments, list):
        for foto in attachments:
            url = foto.get("download_small_url") or foto.get("download_url")
            campo = foto.get("question_xpath", "").lower()

            if not url:
                continue

            if "fachada" in campo or "frente" in campo:
                fachada = url
            elif "antes" in campo:
                antes = url
            elif "depois" in campo:
                depois = url

    return fachada, antes, depois


def img_html(url, largura=120):
    """Cria HTML de imagem usando Base64."""
    if not url:
        return ""

    img64 = imagem_base64(url)

    if not img64:
        return ""

    return f'''
    <img src="data:image/jpeg;base64,{img64}" width="{largura}"
    style="border-radius:8px;border:1px solid #ddd;">
    '''


def gerar_excel(df_exportar):
    """Gera arquivo Excel em memória para download."""
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_exportar.to_excel(writer, index=False, sheet_name="Visitas")

    return output.getvalue()


def formatar_data(valor):
    """Formata data em dd/mm/aaaa."""
    if pd.isna(valor):
        return ""

    return pd.to_datetime(valor).strftime("%d/%m/%Y")


def formatar_hora(valor):
    """Formata hora em HH:MM."""
    if pd.isna(valor):
        return ""

    return pd.to_datetime(valor).strftime("%H:%M")


def calcular_duracao(inicio, fim):
    """Calcula duração entre start e end em HH:MM."""
    if pd.isna(inicio) or pd.isna(fim):
        return ""

    duracao = fim - inicio
    minutos = int(duracao.total_seconds() // 60)

    if minutos < 0:
        return ""

    horas = minutos // 60
    mins = minutos % 60

    return f"{horas:02d}:{mins:02d}"


# =========================================================
# 9. FUNÇÕES PARA RELATÓRIO PDF
# =========================================================

def obter_valor_linha(row, campos_possiveis):
    for campo in campos_possiveis:
        valor = row.get(campo, "")

        if pd.notna(valor) and str(valor).strip() != "":
            return valor

    return ""


def baixar_imagem_bytes(url):
    if not url:
        return None

    try:
        resposta = requests.get(url, headers=HEADERS)

        if resposta.status_code == 200:
            return BytesIO(resposta.content)

        return None

    except Exception:
        return None


def desenhar_imagem_pdf(c, url, x, y, largura, altura):
    imagem_bytes = baixar_imagem_bytes(url)

    if imagem_bytes is None:
        c.setFont("Helvetica", 8)
        c.drawString(x, y + altura / 2, "Imagem nao disponivel")
        return

    try:
        img = ImageReader(imagem_bytes)

        c.drawImage(
            img,
            x,
            y,
            width=largura,
            height=altura,
            preserveAspectRatio=True,
            anchor="c"
        )

    except Exception:
        c.setFont("Helvetica", 8)
        c.drawString(x, y + altura / 2, "Erro ao carregar imagem")


def gerar_pdf_visitas(df_relatorio):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    largura_pagina, altura_pagina = A4

    for _, row in df_relatorio.iterrows():

        loja_oficial = row.get("nome_loja_oficial", "")
        data_visita = formatar_data(row.get("start"))

        latitude = row.get("latitude_visita", "")
        longitude = row.get("longitude_visita", "")

        if pd.notna(latitude):
            latitude = round(float(latitude), 6)

        if pd.notna(longitude):
            longitude = round(float(longitude), 6)

        loja_abastecida = nome_bonito(row.get(CAMPO_STATUS, ""))

        nota = obter_valor_linha(
            row,
            [
                "txt_motivo_nao_abastecida",
                "motivo_nao_abastecida",
                "txt_observacoes",
                "observacao",
                "observacoes",
                "ANOTACOES_GERAIS"
            ]
        )

        fachada, antes, depois = extrair_fotos(row)

        margem_x = 2 * cm
        y = altura_pagina - 2 * cm

        if os.path.exists(LOGO):
            try:
                c.drawImage(
                    LOGO,
                    margem_x,
                    y - 1.3 * cm,
                    width=3.2 * cm,
                    height=1.3 * cm,
                    preserveAspectRatio=True,
                    mask="auto"
                )
            except Exception:
                pass

        c.setFillColor(colors.HexColor("#1E2A78"))
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(largura_pagina / 2, y - 0.4 * cm, "Ficha de Visita de Loja")

        c.setStrokeColor(colors.HexColor("#1E2A78"))
        c.line(margem_x, y - 1.7 * cm, largura_pagina - margem_x, y - 1.7 * cm)

        y = y - 2.5 * cm

        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margem_x, y, "Dados de Coleta:")

        y -= 0.7 * cm

        dados = [
            ("Data da Visita", data_visita),
            ("Loja", loja_oficial),
            ("Latitude", str(latitude)),
            ("Longitude", str(longitude)),
            ("Loja Abastecida", loja_abastecida),
            ("Nota", str(nota))
        ]

        for rotulo, valor in dados:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(margem_x, y, f"{rotulo}:")
            c.setFont("Helvetica", 9)
            c.drawString(margem_x + 4 * cm, y, valor[:95])
            y -= 0.55 * cm

        y -= 0.4 * cm

        c.setFont("Helvetica-Bold", 12)
        c.drawString(margem_x, y, "Registros Fotograficos:")

        y -= 0.8 * cm

        largura_foto = 15.5 * cm
        altura_foto = 4.4 * cm

        fotos = [
            ("Foto da fachada", fachada),
            ("Foto antes do abastecimento", antes),
            ("Foto depois do abastecimento", depois)
        ]

        for titulo, url in fotos:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(margem_x, y, titulo)

            y -= 0.25 * cm

            desenhar_imagem_pdf(c, url, margem_x, y - altura_foto, largura_foto, altura_foto)

            y -= altura_foto + 0.6 * cm

        c.setFont("Helvetica", 8)
        c.setFillColor(colors.gray)
        c.drawCentredString(
            largura_pagina / 2,
            1 * cm,
            "Relatorio gerado automaticamente pelo Painel de Gestao - Merchan PDV"
        )

        c.showPage()

    c.save()
    buffer.seek(0)

    return buffer.getvalue()


# =========================================================
# 10. FUNÇÕES DE GEOLOCALIZAÇÃO / ANTIFRAUDE
# =========================================================

def encontrar_loja_mais_proxima(lat_visita, lon_visita, df_lojas):
    menor_distancia = None
    loja_mais_proxima = None

    for _, loja in df_lojas.iterrows():
        lat_loja = loja["latitude_loja"]
        lon_loja = loja["longitude_loja"]

        if pd.isna(lat_loja) or pd.isna(lon_loja):
            continue

        distancia = geodesic((lat_visita, lon_visita), (lat_loja, lon_loja)).meters

        if menor_distancia is None or distancia < menor_distancia:
            menor_distancia = distancia
            loja_mais_proxima = loja

    return loja_mais_proxima, menor_distancia


def enriquecer_visitas_com_lojas(df_visitas, df_lojas):
    registros = []

    for _, row in df_visitas.iterrows():
        latitude, longitude = obter_lat_long(row)

        if latitude is None or longitude is None or df_lojas.empty:
            registros.append({
                "latitude_visita": latitude,
                "longitude_visita": longitude,
                "id_loja_oficial": "",
                "nome_loja_oficial": "",
                "distancia_metros": None,
                "raio_metros": None,
                "status_gps": "Sem GPS"
            })
            continue

        loja_proxima, distancia = encontrar_loja_mais_proxima(latitude, longitude, df_lojas)

        if loja_proxima is None or distancia is None:
            registros.append({
                "latitude_visita": latitude,
                "longitude_visita": longitude,
                "id_loja_oficial": "",
                "nome_loja_oficial": "",
                "distancia_metros": None,
                "raio_metros": None,
                "status_gps": "Sem loja cadastrada"
            })
            continue

        raio = loja_proxima["raio_metros"]
        distancia = round(distancia, 1)
        status_gps = "Dentro do raio" if distancia <= raio else "Fora do raio"

        registros.append({
            "latitude_visita": latitude,
            "longitude_visita": longitude,
            "id_loja_oficial": loja_proxima["id_loja"],
            "nome_loja_oficial": loja_proxima["nome_loja"],
            "distancia_metros": distancia,
            "raio_metros": raio,
            "status_gps": status_gps
        })

    return pd.concat([df_visitas.reset_index(drop=True), pd.DataFrame(registros)], axis=1)


# =========================================================
# 11. FUNÇÕES DE SLA / FREQUÊNCIA DE ATENDIMENTO
# =========================================================

def calcular_sla_lojas(df_lojas, df_visitas_filtrado, data_inicio, data_fim, dias_periodo):
    linhas = []

    for _, loja in df_lojas.iterrows():
        id_loja = loja["id_loja"]
        visitas_loja = df_visitas_filtrado[df_visitas_filtrado["id_loja_oficial"] == id_loja]

        realizado = len(visitas_loja)
        frequencia = loja.get("frequencia_mensal_prevista", 0)
        intervalo = loja.get("intervalo_minimo_retorno_dias", 0)

        previsto = math.ceil((frequencia / 30) * dias_periodo) if frequencia and dias_periodo > 0 else 0

        if previsto == 0 and frequencia > 0:
            previsto = 1

        if realizado > 0:
            ultima_visita = visitas_loja["data_visita"].max()
            dias_sem_atendimento = (data_fim - ultima_visita).days
        else:
            ultima_visita = None
            dias_sem_atendimento = None

        if realizado == 0:
            status_sla = "Não atendida"
        elif realizado < previsto:
            status_sla = "Fora do prazo"
        elif intervalo and dias_sem_atendimento is not None and dias_sem_atendimento > intervalo:
            status_sla = "Fora do prazo"
        else:
            status_sla = "Dentro do prazo"

        indice_atendimento = 0 if previsto == 0 else min(realizado / previsto, 1)

        linhas.append({
            "id_loja": id_loja,
            "Rede": loja.get("rede", ""),
            "Loja Oficial": loja.get("nome_loja", ""),
            "Cidade": loja.get("cidade", ""),
            "Bairro": loja.get("bairro", ""),
            "Frequência Mensal Prevista": frequencia,
            "Intervalo Mínimo Retorno Dias": intervalo,
            "Visitas Previstas no Período": previsto,
            "Visitas Realizadas": realizado,
            "Última Visita": "" if ultima_visita is None else ultima_visita.strftime("%d/%m/%Y"),
            "Dias Sem Atendimento": "" if dias_sem_atendimento is None else dias_sem_atendimento,
            "Status Atendimento": status_sla,
            "Índice Atendimento": round(indice_atendimento * 100, 1)
        })

    return pd.DataFrame(linhas)


# =========================================================
# 12. CARREGAMENTO PRINCIPAL
# =========================================================

df = carregar_dados_kobo()
df_lojas = carregar_lojas()

if df.empty:
    st.warning("Nenhuma visita encontrada no Kobo.")
    st.stop()

if df_lojas.empty:
    st.warning("Base de lojas vazia ou não encontrada.")
    st.stop()

# Tratamento de datas vindas do Kobo.
# AJUSTE PRINCIPAL:
# A data de referência do sistema passa a ser a DATA do campo start.
df["start"] = pd.to_datetime(df.get("start"), errors="coerce")
df["end"] = pd.to_datetime(df.get("end"), errors="coerce")
df["data_visita"] = df["start"].dt.date

# Enriquecimento das visitas com loja oficial, distância e status GPS.
df = enriquecer_visitas_com_lojas(df, df_lojas)


# =========================================================
# 13. FILTROS LATERAIS
# =========================================================

st.sidebar.header("Filtros")

# =========================================================
# INTERVALO DE DATAS
# =========================================================

data_min = df["data_visita"].dropna().min()
data_max = df["data_visita"].dropna().max()

intervalo_datas = st.sidebar.date_input(
    "Período da visita",
    value=(data_min, data_max),
    min_value=data_min,
    max_value=data_max,
    format="DD/MM/YYYY"
)

# =========================================================
# BASE TEMPORÁRIA PARA FILTROS ANINHADOS
# =========================================================

df_filtros = df.copy()

if isinstance(intervalo_datas, tuple) and len(intervalo_datas) == 2:

    data_inicio_filtro, data_fim_filtro = intervalo_datas

    df_filtros = df_filtros[
        (df_filtros["data_visita"] >= data_inicio_filtro) &
        (df_filtros["data_visita"] <= data_fim_filtro)
    ]

else:
    data_inicio_filtro = data_min
    data_fim_filtro = data_max

# =========================================================
# FILTRO - LOJA INFORMADA PELO PROMOTOR
# =========================================================

lojas_disponiveis = sorted(df_filtros[CAMPO_LOJA].dropna().unique())

lojas_selecionadas = st.sidebar.multiselect(
    "Loja informada pelo promotor",
    lojas_disponiveis,
    format_func=lambda x: nome_bonito(x)
)

if lojas_selecionadas:
    df_filtros = df_filtros[df_filtros[CAMPO_LOJA].isin(lojas_selecionadas)]

# =========================================================
# FILTRO - STATUS GPS
# =========================================================

status_gps_lista = sorted(df_filtros["status_gps"].dropna().unique())

status_gps_selecionados = st.sidebar.multiselect("Status GPS", status_gps_lista)

if status_gps_selecionados:
    df_filtros = df_filtros[df_filtros["status_gps"].isin(status_gps_selecionados)]

# =========================================================
# FILTRO - LOJA ABASTECIDA
# =========================================================

abastecida_lista = sorted(df_filtros[CAMPO_STATUS].dropna().unique())

abastecida_selecionados = st.sidebar.multiselect(
    "Loja abastecida",
    abastecida_lista,
    format_func=lambda x: nome_bonito(x)
)

if abastecida_selecionados:
    df_filtros = df_filtros[df_filtros[CAMPO_STATUS].isin(abastecida_selecionados)]

# =========================================================
# FILTRO INDEPENDENTE - LOJAS CADASTRADAS
# =========================================================

lojas_cadastradas = sorted(df_lojas["nome_loja"].dropna().unique())

lojas_cadastradas_selecionadas = st.sidebar.multiselect(
    "Lojas cadastradas",
    lojas_cadastradas
)

# =========================================================
# DATAFRAME FINAL FILTRADO
# =========================================================

df_filtrado = df_filtros.copy()

if lojas_cadastradas_selecionadas:
    df_filtrado = df_filtrado[
        df_filtrado["nome_loja_oficial"].isin(lojas_cadastradas_selecionadas)
    ]

# =========================================================
# PERÍODO PARA SLA
# =========================================================

data_inicio = data_inicio_filtro
data_fim = data_fim_filtro
dias_periodo = (data_fim - data_inicio).days + 1

# =========================================================
# SLA DAS LOJAS
# =========================================================

df_sla = calcular_sla_lojas(
    df_lojas,
    df_filtrado,
    data_inicio,
    data_fim,
    dias_periodo
)

# =========================================================
# BOTÃO DE RELATÓRIO PDF
# =========================================================

st.sidebar.markdown("---")

if st.sidebar.button("📄 Preparar PDF das visitas filtradas"):

    with st.spinner("Gerando PDF das visitas filtradas..."):
        st.session_state["pdf_visitas"] = gerar_pdf_visitas(df_filtrado)

if "pdf_visitas" in st.session_state:

    st.sidebar.download_button(
        label="⬇️ Baixar PDF",
        data=st.session_state["pdf_visitas"],
        file_name="fichas_visitas_lojas.pdf",
        mime="application/pdf"
    )


# =========================================================
# 14. INDICADORES EXECUTIVOS
# =========================================================

total_visitas = len(df_filtrado)
visitas_dentro_raio = len(df_filtrado[df_filtrado["status_gps"] == "Dentro do raio"])
visitas_fora_raio = len(df_filtrado[df_filtrado["status_gps"] == "Fora do raio"])

total_lojas = len(df_lojas)
lojas_atendidas = df_filtrado["id_loja_oficial"].nunique()
lojas_nao_atendidas = total_lojas - lojas_atendidas

cobertura_lojas = 0

if total_lojas > 0:
    cobertura_lojas = round((lojas_atendidas / total_lojas) * 100, 1)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(f'<div class="metric-card"><h4>Total de Visitas</h4><h2>{total_visitas}</h2></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card"><h4>Dentro do Raio</h4><h2>{visitas_dentro_raio}</h2></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card"><h4>Fora do Raio</h4><h2>{visitas_fora_raio}</h2></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-card"><h4>Lojas Não Atendidas</h4><h2>{lojas_nao_atendidas}</h2></div>', unsafe_allow_html=True)
with col5:
    st.markdown(f'<div class="metric-card"><h4>Cobertura de Lojas</h4><h2>{cobertura_lojas}%</h2></div>', unsafe_allow_html=True)

st.markdown("")


# =========================================================
# 15. MAPA COM VALIDAÇÃO GEOGRÁFICA
# =========================================================

mapa = folium.Map(location=[-8.0476, -34.8770], zoom_start=11)

for _, loja in df_lojas.iterrows():

    id_loja = loja["id_loja"]
    nome_loja = loja["nome_loja"]

    visitas_loja = df_filtrado[df_filtrado["id_loja_oficial"] == id_loja]

    if len(visitas_loja) == 0:
        cor_loja = "#111827"
        texto_status = "Não atendida no período"
    else:
        cor_loja = "#1E2A78"
        texto_status = "Atendida no período"

    folium.Circle(
        location=[float(loja["latitude_loja"]), float(loja["longitude_loja"])],
        radius=int(loja["raio_metros"]),
        color=cor_loja,
        fill=True,
        fill_opacity=0.18,
        popup=f"""
        <b>{nome_loja}</b><br>
        Status: {texto_status}<br>
        Raio: {int(loja["raio_metros"])} m
        """
    ).add_to(mapa)

for _, row in df_filtrado.iterrows():

    latitude = row.get("latitude_visita")
    longitude = row.get("longitude_visita")

    if pd.isna(latitude) or pd.isna(longitude):
        continue

    loja = nome_bonito(row.get(CAMPO_LOJA, ""))
    usuario = row.get("username", "")

    data = formatar_data(row.get("start"))
    hora_inicio = formatar_hora(row.get("start"))
    hora_fim = formatar_hora(row.get("end"))
    duracao = calcular_duracao(row.get("start"), row.get("end"))

    status = nome_bonito(row.get(CAMPO_STATUS, ""))

    nome_loja_oficial = row.get("nome_loja_oficial", "")
    distancia = row.get("distancia_metros", "")
    raio_loja = row.get("raio_metros", "")
    status_gps = row.get("status_gps", "")

    cor_marcador = "green" if status_gps == "Dentro do raio" else "red"

    fachada, antes, depois = extrair_fotos(row)

    fotos_popup = f'''
    <p><b>Fachada</b></p>{img_html(fachada, 250)}
    <p><b>Gôndola Antes</b></p>{img_html(antes, 250)}
    <p><b>Gôndola Depois</b></p>{img_html(depois, 250)}
    '''

    popup_html = f'''
    <div style="width:340px">
        <h3>{loja}</h3>
        <p><b>Promotor:</b> {usuario}</p>
        <p><b>Data:</b> {data}</p>
        <p><b>Início:</b> {hora_inicio}</p>
        <p><b>Fim:</b> {hora_fim}</p>
        <p><b>Duração:</b> {duracao}</p>
        <p><b>Loja abastecida:</b> {status}</p>
        <hr>
        <p><b>Loja oficial mais próxima:</b> {nome_loja_oficial}</p>
        <p><b>Distância:</b> {distancia} m</p>
        <p><b>Raio permitido:</b> {raio_loja} m</p>
        <p><b>Status GPS:</b> {status_gps}</p>
        <hr>
        {fotos_popup}
    </div>
    '''

    folium.Marker(
        location=[float(latitude), float(longitude)],
        popup=folium.Popup(popup_html, max_width=400),
        tooltip=f"{loja} - {status_gps}",
        icon=folium.Icon(color=cor_marcador, icon="map-marker")
    ).add_to(mapa)

    loja_match = df_lojas[df_lojas["id_loja"] == row.get("id_loja_oficial")]

    if not loja_match.empty:
        loja_oficial = loja_match.iloc[0]

        folium.Circle(
            location=[
                float(loja_oficial["latitude_loja"]),
                float(loja_oficial["longitude_loja"])
            ],
            radius=int(loja_oficial["raio_metros"]),
            color=cor_marcador,
            fill=True,
            fill_opacity=0.15,
            popup=f"Raio permitido - {loja_oficial['nome_loja']}"
        ).add_to(mapa)

mapa.save("mapa_visitas.html")

with open("mapa_visitas.html", "r", encoding="utf-8") as f:
    mapa_html = f.read()

html(mapa_html, height=650)


# =========================================================
# 16. TABELA VISUAL COM FOTOS
# =========================================================

st.markdown("---")
st.subheader("Visitas Realizadas")

linhas_excel = []

tabela_html = """
<table style="
width:100%;
border-collapse:collapse;
font-family:Arial;
background:white;
border-radius:12px;
overflow:hidden;
box-shadow:0px 2px 8px rgba(0,0,0,0.08);
">

<tr style="
background-color:#1E2A78;
color:white;
text-align:center;
font-size:14px;
">

    <th style="padding:14px;">Loja Informada</th>
    <th style="padding:14px;">Loja Oficial</th>
    <th style="padding:14px;">Status GPS</th>
    <th style="padding:14px;">Distância</th>
    <th style="padding:14px;">Data</th>
    <th style="padding:14px;">Hora Início</th>
    <th style="padding:14px;">Hora Fim</th>
    <th style="padding:14px;">Duração</th>
    <th style="padding:14px;">Foto Fachada</th>
    <th style="padding:14px;">Foto Antes</th>
    <th style="padding:14px;">Foto Depois</th>
    <th style="padding:14px;">Abastecida</th>
    <th style="padding:14px;">Promotor</th>

</tr>
"""

for _, row in df_filtrado.iterrows():

    loja = nome_bonito(row.get(CAMPO_LOJA, ""))
    loja_oficial = row.get("nome_loja_oficial", "")
    status_gps = row.get("status_gps", "")
    distancia = row.get("distancia_metros", "")

    if distancia != "" and pd.notna(distancia):
        distancia = int(round(distancia))

    data = formatar_data(row.get("start"))
    hora_inicio = formatar_hora(row.get("start"))
    hora_fim = formatar_hora(row.get("end"))
    duracao = calcular_duracao(row.get("start"), row.get("end"))

    usuario = row.get("username", "")
    status = nome_bonito(row.get(CAMPO_STATUS, ""))

    fachada, antes, depois = extrair_fotos(row)

    classe_status_gps = "status-ok" if status_gps == "Dentro do raio" else "status-alerta"
    classe_abastecida = "status-ok" if status.lower() == "sim" else "status-alerta"

    tabela_html += f"""
    <tr style="
    border-bottom:1px solid #E5E7EB;
    text-align:center;
    ">

        <td style="padding:14px;font-weight:500;">{loja}</td>
        <td style="padding:14px;">{loja_oficial}</td>
        <td style="padding:14px;" class="{classe_status_gps}">{status_gps}</td>
        <td style="padding:14px;">{distancia} m</td>
        <td style="padding:14px;">{data}</td>
        <td style="padding:14px;">{hora_inicio}</td>
        <td style="padding:14px;">{hora_fim}</td>
        <td style="padding:14px;font-weight:bold;color:#1E2A78;">{duracao}</td>
        <td style="padding:14px;text-align:center;">{img_html(fachada, 110)}</td>
        <td style="padding:14px;text-align:center;">{img_html(antes, 110)}</td>
        <td style="padding:14px;text-align:center;">{img_html(depois, 110)}</td>
        <td style="padding:14px;" class="{classe_abastecida}">{status}</td>
        <td style="padding:14px;">{usuario}</td>

    </tr>
    """

    linhas_excel.append({
        "Loja Informada": loja,
        "Loja Oficial": loja_oficial,
        "Status GPS": status_gps,
        "Distância (m)": distancia,
        "Data": data,
        "Hora Início": hora_inicio,
        "Hora Fim": hora_fim,
        "Duração": duracao,
        "Foto Fachada": fachada,
        "Foto Antes": antes,
        "Foto Depois": depois,
        "Loja Foi Abastecida": status,
        "Promotor": usuario
    })

tabela_html += "</table>"

html(tabela_html, height=600, scrolling=True)


# =========================================================
# 17. DOWNLOAD EXCEL
# =========================================================

df_excel = pd.DataFrame(linhas_excel)
arquivo_excel = gerar_excel(df_excel)

col1, col2, col3 = st.columns([8, 1, 1])

with col3:
    st.download_button(
        label="📥 Baixar Excel",
        data=arquivo_excel,
        file_name="visitas_merchan_pdv.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# =========================================================
# 18. TABELA ANALÍTICA ORDENÁVEL
# =========================================================

st.markdown("---")

with st.expander("📊 Tabela Analítica", expanded=False):

    df_analitico = pd.DataFrame(linhas_excel)

    estilo_analitico = (
        df_analitico.style
        .set_properties(**{
            "text-align": "center",
            "font-weight": "normal"
        })
        .set_table_styles([
            {
                "selector": "th",
                "props": [
                    ("text-align", "center"),
                    ("font-weight", "bold"),
                    ("color", "black"),
                    ("background-color", "#F3F4F6")
                ]
            },
            {
                "selector": "td",
                "props": [
                    ("text-align", "center"),
                    ("font-weight", "normal")
                ]
            }
        ])
    )

    st.dataframe(
        estilo_analitico,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 19. SLA DAS LOJAS
# =========================================================

st.markdown("---")

with st.expander("📌 SLA de Atendimento das Lojas", expanded=False):

    st.markdown(
        f"Período considerado: **{data_inicio.strftime('%d/%m/%Y')}** até **{data_fim.strftime('%d/%m/%Y')}**"
    )

    df_sla_exibicao = df_sla.copy()

    df_sla_exibicao["Índice Atendimento"] = (
        df_sla_exibicao["Índice Atendimento"].astype(str) + "%"
    )

    estilo_sla = (
        df_sla_exibicao.style
        .set_properties(**{
            "text-align": "center",
            "font-weight": "normal"
        })
        .set_table_styles([
            {
                "selector": "th",
                "props": [
                    ("text-align", "center"),
                    ("font-weight", "bold"),
                    ("color", "black"),
                    ("background-color", "#F3F4F6")
                ]
            },
            {
                "selector": "td",
                "props": [
                    ("text-align", "center"),
                    ("font-weight", "normal")
                ]
            }
        ])
    )

    st.dataframe(
        estilo_sla,
        use_container_width=True,
        hide_index=True
    )
st.markdown("### Desenvolvido by Reinaldo 🚀")