# main.py
from database import inicializar_banco
from interface import iniciar_interface


def main():
    print("Iniciando sistema...")
    inicializar_banco()  # Cria banco e tabelas automaticamente
    print("Banco de dados pronto!")
    # Aqui você pode seguir para a interface ou testes de inserção

    # Inicia interface gráfica
    iniciar_interface()


if __name__ == "__main__":
    main()
