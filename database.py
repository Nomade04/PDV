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

    # Criar tabela produtos
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

    # Criar tabela movimentacoes
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

    # Criar tabela vendas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vendas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        data_venda TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cliente VARCHAR(100),
        valor_total DECIMAL(10,2)
    )
    """)

    # Criar tabela itens_venda
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

    conexao.commit()
    cursor.close()
    conexao.close()
    print("Banco e tabelas inicializados com sucesso!")
