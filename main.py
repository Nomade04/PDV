# main.py
from database import inicializar_banco

def main():
    print("Iniciando sistema...")
    inicializar_banco()  # Cria banco e tabelas automaticamente
    print("Banco de dados pronto!")
    # Aqui você pode seguir para a interface ou testes de inserção



if __name__ == "__main__":
    main()
