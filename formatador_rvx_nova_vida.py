import streamlit as st
import pandas as pd
import chardet

# # Funções # # 

def corrigir_alinhamento_colunas(caminho_do_arquivo, delimiter=';', encoding='ISO-8859-1'):
    df = pd.read_csv(
        caminho_do_arquivo,
        delimiter=delimiter,
        encoding=encoding,
        header=0,
        index_col=False
    )
    return df

def detectar_delimitador(arquivo, codificacao):
    # Lista de delimitadores comuns para testar
    delimitadores_possiveis = [',', ';', '|', '\t']
    
    with open(arquivo, 'r', encoding=codificacao) as f:
        # Lê as primeiras linhas do arquivo
        linhas = [next(f) for _ in range(20) if len(next(f).strip()) > 0]
        
        if not linhas:
            return None
            
        # Tenta cada delimitador e conta as colunas resultantes
        resultados = {}
        for delim in delimitadores_possiveis:
            # Conta o número de colunas para cada linha usando este delimitador
            num_colunas = [len(linha.strip().split(delim)) for linha in linhas]
            
            # Se o número de colunas é consistente e maior que 1, este pode ser o delimitador correto
            if len(set(num_colunas)) == 1 and num_colunas[0] > 1:
                resultados[delim] = num_colunas[0]
        
        # Se encontrou algum delimitador válido, retorna aquele que resultou no maior número de colunas
        if resultados:
            return max(resultados.items(), key=lambda x: x[1])[0]
            
        # Se nenhum delimitador comum funcionou, tenta o csv.Sniffer
        try:
            dialeto = csv.Sniffer().sniff(''.join(linhas))
            return dialeto.delimiter
        except:
            print(f"Aviso: Não foi possível detectar o delimitador automaticamente para {arquivo}")
            return None

def detectar_codificacao(arquivo):
    with open(arquivo, 'rb') as f:
        amostragem = f.read(10000)
        resultado = chardet.detect(amostragem)
        return resultado['encoding']
    
def identificar_tipo_base(df):
    colunas = set(df.columns.str.lower())
    
    # Colunas características de cada base
    colunas_rvx = {'ddd0', 'numerolinha0', 'whatsapp0'}
    colunas_nova_vida = {'cel1', 'flgwhatscel1', 'flag_de_obito'}
    
    if any(col in colunas for col in colunas_rvx):
        return 'RVX'
    elif any(col in colunas for col in colunas_nova_vida):
        return 'NOVA_VIDA'
    else:
        raise ValueError("Formato de base não reconhecido")

def processar_base_rvx(base):
    base = base.loc[base['obito'] != "S"]
    
    # Formata a coluna 'nascimento'
    base['nascimento'] = base['nascimento'].astype(str).apply(lambda x: f"{x[6:8]}/{x[4:6]}/{x[:4]}")
    
    # Processa telefones com WhatsApp
    for i in range(4):  # 4 números possíveis
        base[f'telefone{i}'] = base.apply(
            lambda x: f"{int(float(x[f'ddd{i}']))}{int(float(x[f'numeroLinha{i}']))}" 
            if x[f'whatsapp{i}'] == 'S' and pd.notna(x[f'ddd{i}']) and pd.notna(x[f'numeroLinha{i}'])
            else '', 
            axis=1
        )
    
    # Seleciona e renomeia colunas para o formato padrão
    base_final = base[['cpf', 'nome', 'nascimento', 'telefone0', 'telefone1', 'telefone2', 'telefone3', 'email0', 'email1']]
    base_final.columns = ['CPF', 'NOME', 'DATA_NASCIMENTO', 'TELEFONE1', 'TELEFONE2', 'TELEFONE3', 'TELEFONE4', 'EMAIL1', 'EMAIL2']
    
    return base_final

def processar_base_nova_vida(base):
    base = base.loc[base['FLAG_DE_OBITO'] != "1"]
    base['NASC'] = base['NASC'].astype(str).apply(lambda x: f"{x[8:]}/{x[5:7]}/{x[:4]}")
    
    # Cria colunas de telefone apenas para números com WhatsApp marcado
    telefones = []
    for i in range(1, 3):
        cel = f'CEL{i}'
        whats = f'FLGWHATSCEL{i}'
        if cel in base.columns and whats in base.columns:
            telefone = base.apply(
                lambda x: str(x[cel]) if x[whats] == 'S' and pd.notna(x[cel]) else '',
                axis=1
            )
            telefones.append(telefone)
    
    # Preenche com vazios se necessário para ter 4 colunas de telefone
    while len(telefones) < 4:
        telefones.append(pd.Series([''] * len(base)))
    
    # Cria DataFrame final no formato padrão
    dados = {
        'CPF': base['CPF'],
        'NOME': base['NOME'],
        'DATA_NASCIMENTO': base['NASC'],
        'TELEFONE1': telefones[0],
        'TELEFONE2': telefones[1],
        'TELEFONE3': telefones[2],
        'TELEFONE4': telefones[3],
        'EMAIL': base['EMAIL1'],
        'EMAIL1': base['EMAIL2'],
        'EMAIL2': base['EMAIL3'],
    }
    
    base_final = pd.DataFrame(dados)
    
    return base_final

def limpar_e_padronizar(df):
    # Padroniza nomes para Title Case
    df['NOME'] = df['NOME'].str.title()
    
    # Remove espaços extras
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].str.strip()
    
    # Garante que telefones sejam strings limpas
    for col in ['TELEFONE1', 'TELEFONE2', 'TELEFONE3', 'TELEFONE4']:
        df[col] = df[col].apply(lambda x: str(int(float(x))) if pd.notna(x) and str(x).replace('.', '', 1).isdigit() else str(x))
        df[col] = df[col].str.replace(r'\D', '', regex=True)
    
    return df


# # Interface Streamlit # #

st.title("Processador de Bases RVX e Nova Vida")

uploaded_file = st.file_uploader("Carregue o arquivo CSV", type="csv")

if uploaded_file is not None:
    base = corrigir_alinhamento_colunas(uploaded_file)       
    tipo_base = identificar_tipo_base(base)
    st.write(f"Tipo de base identificada: {tipo_base}")

    if tipo_base == 'RVX':
        base_processada = processar_base_rvx(base)
    else:
        base_processada = processar_base_nova_vida(base)

    base_final = limpar_e_padronizar(base_processada)

    st.write("Arquivo Processado:")
    st.dataframe(base_final)

    csv = base_final.to_csv(index=False, sep=';').encode('utf-8')
    st.download_button(
        "Baixar CSV Processado",
        data=csv,
        file_name="base_processada.csv",
        mime="text/csv"
    )
