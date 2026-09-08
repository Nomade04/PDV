# main.py


from database import inicializar_banco
from interface import iniciar_interface
import backup as _backup_mod


def main():
    print("Iniciando sistema...")
    inicializar_banco()
    print("Banco de dados pronto!")

    # Inicia backup automático em background (a cada 30 minutos)
    _backup_mod.iniciar_backup_automatico()
    print("Backup automático iniciado!")

    # Inicia interface gráfica
    iniciar_interface()


if __name__ == "__main__":
    main()
