import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import json
from datetime import datetime
import pytz
import io

def ler_google_sheet(worksheet_name: str) -> pd.DataFrame:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet=worksheet_name, ttl=300)
    return df

# realocar posteriormente ---
def data_hr_atual():
    # Define o fuso horário GMT-3
    fuso_horario = pytz.timezone("America/Sao_Paulo")
    # Obtém a data e hora atual no fuso horário especificado
    now = datetime.now(fuso_horario)
    # Formata no estilo dd-mm-yyyy hh:mm
    data_hora_atual = now.strftime("%d/%m/%Y %H:%M")
    return data_hora_atual

# Inicializar dados locais se não existirem
def init_local_data():
    """Inicializa os dados locais no session_state"""
    if 'lista_feira_local' not in st.session_state:
        st.session_state.lista_feira_local = pd.DataFrame(columns=[
            'Data/Hora', 'Item', 'Marca', 'Quantidade', 'Tipo', 'Peso/Volume', 'Preço'
        ])
    if 'conexao_online' not in st.session_state:
        st.session_state.conexao_online = True
    if 'sync_pendente' not in st.session_state:
        st.session_state.sync_pendente = False

def connect_to_gsheet(creds_json, spreadsheet_name, sheet_name):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(credentials)
    spreadsheet = client.open(spreadsheet_name)
    
    # Tentar acessar a aba, se não existir, criar
    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        # Criar a aba se não existir
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
        # Se for a aba 'itens', adicionar cabeçalhos
        if sheet_name == 'itens':
            worksheet.append_row(['Data/Hora', 'Item', 'Marca', 'Quantidade', 'Tipo', 'Peso/Volume', 'Preço'])
        return worksheet

CREDENTIALS_FILE = st.secrets['google_credentials2']

# Função para ler os dados com fallback local
def read_data(planilha, aba):
    init_local_data()
    try:
        sheet = connect_to_gsheet(CREDENTIALS_FILE, planilha, aba)
        data = sheet.get_all_values()
        data = pd.DataFrame(data)
        if not data.empty:
            data.columns = data.iloc[0]
            data = data.drop(data.index[0]).reset_index(drop=True)
        st.session_state.conexao_online = True
        return data
    except Exception as e:
        st.session_state.conexao_online = False
        st.warning(f"⚠️ Modo Offline: {e}")
        return st.session_state.lista_feira_local

# Função para adicionar nova linha com fallback local
def add_data(planilha, aba, linha):
    init_local_data()
    try:
        sheet = connect_to_gsheet(CREDENTIALS_FILE, planilha, aba)
        sheet.append_row(linha)
        st.session_state.conexao_online = True
        # Se conseguiu sincronizar online, atualizar dados locais também
        sync_local_data()
    except Exception as e:
        st.session_state.conexao_online = False
        st.session_state.sync_pendente = True
        # Adicionar aos dados locais
        add_to_local_data(linha)
        st.warning(f"⚠️ Item salvo localmente. Sincronização pendente: {e}")

def add_to_local_data(linha):
    """Adiciona item aos dados locais"""
    init_local_data()
    colunas = ['Data/Hora', 'Item', 'Marca', 'Quantidade', 'Tipo', 'Peso/Volume', 'Preço']
    novo_item = pd.DataFrame([linha], columns=colunas)
    st.session_state.lista_feira_local = pd.concat([st.session_state.lista_feira_local, novo_item], ignore_index=True)

def sync_local_data():
    """Sincroniza dados locais com Google Sheets quando possível"""
    init_local_data()
    if st.session_state.sync_pendente and st.session_state.conexao_online:
        try:
            # Tentar sincronizar dados pendentes
            for _, row in st.session_state.lista_feira_local.iterrows():
                linha = row.tolist()
                sheet = connect_to_gsheet(CREDENTIALS_FILE, 'FEIRA', 'itens')
                sheet.append_row(linha)
            st.session_state.sync_pendente = False
            st.success("✅ Dados sincronizados com sucesso!")
        except Exception as e:
            st.error(f"Erro na sincronização: {e}")

def export_to_csv():
    """Exporta os dados atuais para CSV"""
    init_local_data()
    df = get_lista_feira()
    if not df.empty:
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        return csv_buffer.getvalue()
    return None

@st.cache_data(show_spinner=False)
def get_dados_usuarios():
    with st.spinner("Carregando dados..."):
        try:
            return read_data('acessos_siregov', 'usuarios_nivel_acesso')
        except Exception as e:
            return st.error(f"Erro ao carregar dados: {e}")
        

# @st.cache_data(show_spinner=False)
def get_historico_acessos():
    with st.spinner("Carregando dados..."):
        try:
            return read_data('acessos_siregov', 'historico_acessos')
        except Exception as e:
            return st.error(f"Erro ao carregar dados: {e}")
        
def get_nome_usuario(df_usuarios, cpf):
    nome_completo_user = df_usuarios.loc[df_usuarios['CPF'] == cpf]['NOME'].values[0]
    nome = nome_completo_user.split()[0]
    return [nome_completo_user, nome]

def registrar_acesso(cpf, nome):
    try:
        # registrar acesso geral
        dados_novos = [data_hr_atual(), int(cpf), nome]
        add_data('acessos_siregov', 'historico_acessos', dados_novos)
    except Exception as e:
        return st.error(f"Erro ao registrar acesso: {e}")

# Funções para Lista de Feira com fallback local
def get_lista_feira():
    """Recupera a lista de feira atual do Google Sheets ou dados locais"""
    init_local_data()
    with st.spinner("Carregando lista de feira..."):
        try:
            df = read_data('FEIRA', 'itens')
            if st.session_state.conexao_online and not df.empty:
                # Atualizar dados locais com dados online
                st.session_state.lista_feira_local = df
            return df if not df.empty else st.session_state.lista_feira_local
        except Exception as e:
            st.error(f"Erro ao carregar lista de feira: {e}")
            return st.session_state.lista_feira_local

def adicionar_item_feira(item, marca, quantidade, tipo_quantidade, peso_volume, preco):
    """Adiciona um novo item à lista de feira"""
    init_local_data()
    try:
        dados_item = [
            data_hr_atual(),
            item,
            marca,
            quantidade,
            tipo_quantidade,
            peso_volume,
            float(preco)
        ]
        add_data('FEIRA', 'itens', dados_item)
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar item: {e}")
        return False

def calcular_totais_feira(df_feira):
    """Calcula os totais da lista de feira"""
    if df_feira.empty:
        return 0, 0.0
    
    try:
        # Converter colunas para tipos apropriados
        df_feira['Quantidade'] = pd.to_numeric(df_feira['Quantidade'], errors='coerce').fillna(0)
        df_feira['Preço'] = pd.to_numeric(df_feira['Preço'], errors='coerce').fillna(0.0)
        
        total_itens = len(df_feira)
        total_valor = df_feira['Preço'].sum()
        
        return total_itens, total_valor
    except Exception as e:
        st.error(f"Erro ao calcular totais: {e}")
        return 0, 0.0

def limpar_lista_feira():
    """Limpa todos os itens da lista de feira"""
    init_local_data()
    try:
        if st.session_state.conexao_online:
            sheet = connect_to_gsheet(CREDENTIALS_FILE, 'FEIRA', 'itens')
            # Mantém apenas o cabeçalho
            sheet.clear()
            sheet.append_row(['Data/Hora', 'Item', 'Marca', 'Quantidade', 'Tipo', 'Peso/Volume', 'Preço'])
        
        # Limpar dados locais também
        st.session_state.lista_feira_local = pd.DataFrame(columns=[
            'Data/Hora', 'Item', 'Marca', 'Quantidade', 'Tipo', 'Peso/Volume', 'Preço'
        ])
        st.session_state.sync_pendente = False
        return True
    except Exception as e:
        st.error(f"Erro ao limpar lista: {e}")
        return False

def get_connection_status():
    """Retorna o status da conexão"""
    init_local_data()
    return st.session_state.conexao_online, st.session_state.sync_pendente
