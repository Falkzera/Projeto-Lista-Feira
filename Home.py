import streamlit as st
import pandas as pd
from src.google_sheets_api import (
    get_lista_feira, 
    adicionar_item_feira, 
    calcular_totais_feira, 
    limpar_lista_feira,
    get_connection_status,
    export_to_csv,
    sync_local_data
)

# Configuração da página para mobile
st.set_page_config(
    page_title="Lista de Feira",
    page_icon="🛒",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Título principal
st.title("🛒 Lista de Feira")

# Status de conexão
conexao_online, sync_pendente = get_connection_status()
if conexao_online:
    if sync_pendente:
        st.info("🔄 Online - Sincronização pendente")
        if st.button("🔄 Tentar Sincronizar", key="sync_btn"):
            sync_local_data()
            st.rerun()
    else:
        st.success("✅ Online - Dados sincronizados")
else:
    st.warning("⚠️ Modo Offline - Dados salvos localmente")

st.markdown("---")

# Seção de resumo no topo (mobile-first)
df_feira = get_lista_feira()
total_itens, total_valor = calcular_totais_feira(df_feira)

col1, col2 = st.columns(2)
with col1:
    st.metric("📦 Total de Itens", total_itens)
with col2:
    st.metric("💰 Valor Total", f"R$ {total_valor:.2f}")

st.markdown("---")

# Formulário para adicionar itens
st.header("➕ Adicionar Novo Item")

with st.form("adicionar_item", clear_on_submit=True):
    # Linha 1: Item e Marca
    col1, col2 = st.columns([2, 1])
    with col1:
        item = st.text_input("Item *", placeholder="Ex: Arroz, Feijão, Leite...")
    with col2:
        marca = st.text_input("Marca", placeholder="Ex: Tio João...")
    
    # Linha 2: Quantidade, Tipo e Preço
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        quantidade = st.number_input("Quantidade *", min_value=0.1, step=0.1, format="%.1f")
    with col2:
        tipo_quantidade = st.selectbox("Tipo *", ["Unidade", "Pacote", "Kg", "Litro"])
    with col3:
        preco = st.number_input("Preço (R$) *", min_value=0.01, step=0.01, format="%.2f")
    
    # Linha 3: Peso/Volume
    peso_volume = st.text_input("Peso/Volume", placeholder="Ex: 1kg, 500ml, 2L...")
    
    # Botão de submit
    submitted = st.form_submit_button("🛒 Adicionar à Lista", use_container_width=True, type="primary")
    
    if submitted:
        if item and quantidade and preco:
            if adicionar_item_feira(item, marca, quantidade, tipo_quantidade, peso_volume, preco):
                st.success("✅ Item adicionado com sucesso!")
                st.rerun()
        else:
            st.error("❌ Preencha todos os campos obrigatórios (*)")

st.markdown("---")

# Lista atual
st.header("📋 Minha Lista Atual")

if not df_feira.empty:
    # Para mobile, vamos mostrar os dados de forma mais compacta
    for index, row in df_feira.iterrows():
        with st.container():
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.write(f"**{row['Item']}**")
                if pd.notna(row['Marca']) and row['Marca']:
                    st.caption(f"Marca: {row['Marca']}")
                if pd.notna(row['Peso/Volume']) and row['Peso/Volume']:
                    st.caption(f"Peso/Vol: {row['Peso/Volume']}")
            
            with col2:
                st.write(f"**{row['Quantidade']:.1f}** {row['Tipo']}")
                st.caption(f"Adicionado: {row['Data/Hora']}")
            
            with col3:
                st.write(f"**R$ {row['Preço']:.2f}**")
                st.caption(f"Total: R$ {(row['Quantidade'] * row['Preço']):.2f}")
            
            st.divider()
else:
    st.info("📝 Sua lista está vazia. Adicione itens usando o formulário acima.")

st.markdown("---")

# Botões de ação
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🔄 Atualizar Lista", use_container_width=True):
        st.rerun()

with col2:
    # Botão de download CSV
    csv_data = export_to_csv()
    if csv_data:
        st.download_button(
            label="📥 Baixar CSV",
            data=csv_data,
            file_name=f"lista_feira_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.button("📥 Baixar CSV", disabled=True, use_container_width=True, help="Lista vazia")

with col3:
    if st.button("🗑️ Limpar Lista", use_container_width=True, type="secondary"):
        if st.session_state.get('confirmar_limpeza', False):
            if limpar_lista_feira():
                st.success("✅ Lista limpa com sucesso!")
                st.session_state['confirmar_limpeza'] = False
                st.rerun()
        else:
            st.session_state['confirmar_limpeza'] = True
            st.warning("⚠️ Clique novamente para confirmar")

# Botão de cancelar limpeza
if st.session_state.get('confirmar_limpeza', False):
    if st.button("❌ Cancelar Limpeza", use_container_width=True):
        st.session_state['confirmar_limpeza'] = False
        st.rerun()

st.markdown("---")

# Dica para uso mobile
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 20px;'>
        📱 <strong>Dica Mobile:</strong> Use este app no mercado para controlar seus gastos em tempo real!<br>
        💡 Adicione itens conforme pega no mercado e acompanhe o valor total.
    </div>
    """, 
    unsafe_allow_html=True
)

# Auto-refresh a cada 30 segundos se houver itens (opcional para mobile)
if not df_feira.empty:
    import time
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    # Aumentei o tempo para 60 segundos para economizar dados mobile
    if time.time() - st.session_state.last_refresh > 60:
        st.session_state.last_refresh = time.time()
        st.rerun()