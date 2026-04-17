import mysql.connector


def criar_conexao():
    return mysql.connector.connect(
        host="localhost",
        user="pdv",
        password="1234"
    )


def inicializar_banco():
    conexao = criar_conexao()
    cursor = conexao.cursor()

    # Criar banco
    cursor.execute("CREATE DATABASE IF NOT EXISTS sistema_vendas")
    cursor.execute("USE sistema_vendas")

    # Criar tabela produtos (NÃO ALTERAR)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        codigo VARCHAR(50) UNIQUE,
        nome VARCHAR(100) NOT NULL,
        custo DECIMAL(10,2) DEFAULT 0.00,
        lucro_percentual DECIMAL(5,2) DEFAULT 0.00,
        preco_sugerido DECIMAL(10,2) 
            GENERATED ALWAYS AS (custo + (custo * lucro_percentual / 100)) STORED,
        preco_venda DECIMAL(10,2) DEFAULT 0.00,
        estoque_minimo INT DEFAULT 0,
        estoque_inicial INT DEFAULT 0,
        fracionado BOOLEAN DEFAULT FALSE,
        cod_balanca VARCHAR(20),
        validade_dias INT,
        tipo_medida ENUM('peso','unidade') DEFAULT 'unidade',
        observacao TEXT
    )
    """)

    # Criar tabela movimentacoes (NÃO ALTERAR)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movimentacoes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        produto_id INT NOT NULL,
        tipo ENUM('entrada','saida') NOT NULL,
        quantidade DECIMAL(10,3) NOT NULL,
        data_movimentacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        motivo VARCHAR(100),
        validade DATE,
        FOREIGN KEY (produto_id) REFERENCES produtos(id)
    )
    """)

    # Criar tabela vendas (NÃO ALTERAR)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vendas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        data_venda TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cliente VARCHAR(100),
        valor_total DECIMAL(10,2)
    )
    """)

    # Criar tabela itens_venda (NÃO ALTERAR)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS itens_venda (
        id INT AUTO_INCREMENT PRIMARY KEY,
        venda_id INT NOT NULL,
        produto_id INT NOT NULL,
        quantidade INT NOT NULL,
        preco_unitario DECIMAL(10,2),
        subtotal DECIMAL(10,2),
        FOREIGN KEY (venda_id) REFERENCES vendas(id),
        FOREIGN KEY (produto_id) REFERENCES produtos(id)
    )
    """)

    # --- Novas tabelas sugeridas (adicionadas sem alterar as existentes) ---

    # Usuários (necessário antes de caixas que referencia usuario_id)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE,
        nome VARCHAR(100),
        senha_hash VARCHAR(255),
        nivel_acesso VARCHAR(50),
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Clientes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        documento VARCHAR(50),
        telefone VARCHAR(30),
        email VARCHAR(100),
        endereco TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Formas de pagamento
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS formas_pagamento (
        id SMALLINT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(50) NOT NULL,
        ativo BOOLEAN DEFAULT TRUE
    )
    """)

    # Pagamentos por venda
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pagamentos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        venda_id INT NOT NULL,
        forma_id SMALLINT NOT NULL,
        valor DECIMAL(12,2) NOT NULL,
        troco DECIMAL(12,2) DEFAULT 0.00,
        referencia VARCHAR(100),
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (venda_id) REFERENCES vendas(id) ON DELETE CASCADE,
        FOREIGN KEY (forma_id) REFERENCES formas_pagamento(id)
    )
    """)

    # Caixas (sessões de caixa)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS caixas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(100),
        usuario_id INT,
        saldo_inicial DECIMAL(12,2) DEFAULT 0.00,
        aberto BOOLEAN DEFAULT TRUE,
        aberto_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fechado_em TIMESTAMP NULL,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    )
    """)

    # Movimentos de estoque detalhados (com referência a venda/operação)
    # Observação: já existe 'movimentacoes'; esta tabela é opcional para histórico mais detalhado.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS estoque_movimentos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        produto_id INT NOT NULL,
        tipo ENUM('saida','entrada','ajuste') NOT NULL,
        quantidade DECIMAL(12,6) NOT NULL,
        referencia_tipo VARCHAR(50),
        referencia_id INT,
        motivo VARCHAR(100),
        data_movimentacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (produto_id) REFERENCES produtos(id)
    )
    """)

    # Logs de vendas / auditoria (estornos, alterações)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS venda_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        venda_id INT NOT NULL,
        acao VARCHAR(50) NOT NULL,
        detalhes TEXT,
        usuario_id INT,
        data_log TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (venda_id) REFERENCES vendas(id) ON DELETE CASCADE,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    )
    """)

    # Índices e dados iniciais mínimos (não alteram tabelas existentes)
    # Inserir formas de pagamento padrão se não existirem
    cursor.execute("""
    INSERT IGNORE INTO formas_pagamento (id, nome, ativo) VALUES
      (1, 'Dinheiro', TRUE),
      (2, 'PIX', TRUE),
      (3, 'Cartão Crédito', TRUE),
      (4, 'Cartão Débito', TRUE),
      (5, 'Cheque', TRUE)
    """)

    conexao.commit()
    cursor.close()
    conexao.close()




