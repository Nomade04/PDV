"""
backup.py — Backup e Recuperação do Banco de Dados
=====================================================
ATENÇÃO: Este módulo manipula o banco de dados inteiro.
Toda operação de recuperação é irreversível sem um backup prévio.

Funcionalidades:
  - Backup automático a cada 30 minutos em background (thread)
  - Seleção de pasta de destino (disco local, pendrive, rede)
  - Exportação imediata (backup forçado)
  - Recuperação a partir de arquivo .sql com confirmação dupla
  - Tela integrada no frame_main do PDV
"""

import os
import threading
import subprocess
import shutil
import gzip
import time
import json
from datetime import datetime
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

# ── Configuração do banco (mesmo do interface.py) ──────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "user":     "pdv",
    "password": "1234",
    "database": "sistema_vendas"
}

# ── Arquivo de configuração de backup ─────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup_config.json")
INTERVALO_MINUTOS = 30   # backup automático a cada N minutos
MAX_BACKUPS_AUTO  = 48   # manter os últimos N backups automáticos (~24h)

COR_PRIMARIA  = "#FFA500"
COR_SECUNDARIA = "#FFD700"


# ══════════════════════════════════════════════════════════════════════
#  CONFIGURAÇÃO PERSISTENTE
# ══════════════════════════════════════════════════════════════════════

def _carregar_config():
    """Carrega configuração salva em JSON."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"pasta_backup": ""}

def _salvar_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[backup] Erro ao salvar config: {e}")


# ══════════════════════════════════════════════════════════════════════
#  LÓGICA DE BACKUP / RESTAURAÇÃO
# ══════════════════════════════════════════════════════════════════════

def _encontrar_mysqldump():
    """
    Tenta localizar o executável mysqldump no sistema.
    Procura no PATH e em locais comuns do Windows/Linux.
    """
    # Tenta pelo PATH primeiro
    dump = shutil.which("mysqldump")
    if dump:
        return dump

    # Locais comuns no Windows
    candidatos_win = [
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
        r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysqldump.exe",
        r"C:\Program Files (x86)\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
        r"C:\xampp\mysql\bin\mysqldump.exe",
        r"C:\wamp64\bin\mysql\mysql8.0\bin\mysqldump.exe",
        r"C:\laragon\bin\mysql\mysql-8.0\bin\mysqldump.exe",
    ]
    for c in candidatos_win:
        if os.path.isfile(c):
            return c

    return None

def _encontrar_mysql():
    """Localiza o executável mysql (cliente) para restauração."""
    cli = shutil.which("mysql")
    if cli:
        return cli
    candidatos_win = [
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
        r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysql.exe",
        r"C:\Program Files (x86)\MySQL\MySQL Server 8.0\bin\mysql.exe",
        r"C:\xampp\mysql\bin\mysql.exe",
        r"C:\wamp64\bin\mysql\mysql8.0\bin\mysql.exe",
        r"C:\laragon\bin\mysql\mysql-8.0\bin\mysql.exe",
    ]
    for c in candidatos_win:
        if os.path.isfile(c):
            return c
    return None


def executar_backup(pasta_destino: str, prefixo: str = "auto") -> tuple[bool, str]:
    """
    Executa mysqldump e salva o resultado comprimido (.sql.gz) na pasta destino.

    Retorna (sucesso: bool, mensagem: str)
    NUNCA lança exceção — sempre retorna o resultado.
    """
    if not pasta_destino or not os.path.isdir(pasta_destino):
        return False, f"Pasta de backup invalida ou nao encontrada: '{pasta_destino}'"

    mysqldump = _encontrar_mysqldump()
    if not mysqldump:
        return False, (
            "mysqldump nao encontrado.\n"
            "Verifique se o MySQL esta instalado e se o mysqldump esta no PATH.\n"
            "Caminhos verificados: PATH do sistema e locais comuns do Windows."
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"backup_{prefixo}_{timestamp}.sql.gz"
    caminho_arquivo = os.path.join(pasta_destino, nome_arquivo)

    cmd = [
        mysqldump,
        f"--host={DB_CONFIG['host']}",
        f"--user={DB_CONFIG['user']}",
        f"--password={DB_CONFIG['password']}",
        "--single-transaction",     # consistência sem travar tabelas
        "--routines",               # inclui procedures/functions
        "--triggers",               # inclui triggers
        "--add-drop-table",         # facilita restauração limpa
        "--complete-insert",        # inserts completos (mais seguro)
        "--set-gtid-purged=OFF",    # evita erro em alguns ambientes
        DB_CONFIG["database"]
    ]

    try:
        resultado = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120   # 2 minutos de timeout
        )

        if resultado.returncode != 0:
            erro = resultado.stderr.decode("utf-8", errors="replace")
            # Ignora avisos não fatais do mysqldump
            linhas_erro = [l for l in erro.splitlines()
                           if l.strip() and "Warning" not in l and "warning" not in l]
            if linhas_erro:
                return False, f"mysqldump retornou erro:\n{chr(10).join(linhas_erro[:5])}"

        sql_bytes = resultado.stdout
        if len(sql_bytes) < 100:
            return False, "mysqldump gerou arquivo vazio. Verifique a conexao com o banco."

        # Comprime com gzip
        with gzip.open(caminho_arquivo, "wb") as f:
            f.write(sql_bytes)

        tamanho_kb = os.path.getsize(caminho_arquivo) // 1024
        return True, caminho_arquivo

    except subprocess.TimeoutExpired:
        return False, "Timeout: mysqldump demorou mais de 2 minutos. Verifique a conexao."
    except FileNotFoundError:
        return False, f"Executavel nao encontrado: {mysqldump}"
    except Exception as e:
        return False, f"Erro inesperado no backup: {e}"


def _limpar_backups_antigos(pasta: str):
    """Remove backups automáticos mais antigos, mantendo os últimos MAX_BACKUPS_AUTO."""
    try:
        arquivos = sorted([
            os.path.join(pasta, f) for f in os.listdir(pasta)
            if f.startswith("backup_auto_") and f.endswith(".sql.gz")
        ], key=os.path.getmtime)
        while len(arquivos) > MAX_BACKUPS_AUTO:
            os.remove(arquivos.pop(0))
    except Exception:
        pass


def restaurar_backup(caminho_sql_gz: str,
                     callback_progresso=None) -> tuple[bool, str]:
    """
    Restaura o banco a partir de um arquivo .sql.gz.

    ATENÇÃO: Esta operação substitui TODOS os dados atuais.
    Retorna (sucesso: bool, mensagem: str).
    """
    if not os.path.isfile(caminho_sql_gz):
        return False, f"Arquivo nao encontrado: '{caminho_sql_gz}'"

    mysql = _encontrar_mysql()
    if not mysql:
        return False, (
            "Cliente mysql nao encontrado.\n"
            "Verifique se o MySQL esta instalado e acessivel pelo PATH."
        )

    if callback_progresso:
        callback_progresso("Descomprimindo arquivo de backup...")

    try:
        with gzip.open(caminho_sql_gz, "rb") as f:
            sql_bytes = f.read()
    except Exception as e:
        return False, f"Erro ao descomprimir arquivo: {e}"

    if callback_progresso:
        callback_progresso("Restaurando banco de dados...")

    cmd = [
        mysql,
        f"--host={DB_CONFIG['host']}",
        f"--user={DB_CONFIG['user']}",
        f"--password={DB_CONFIG['password']}",
        DB_CONFIG["database"]
    ]

    try:
        resultado = subprocess.run(
            cmd,
            input=sql_bytes,
            capture_output=True,
            timeout=300   # 5 minutos
        )

        if resultado.returncode != 0:
            erro = resultado.stderr.decode("utf-8", errors="replace")
            linhas_erro = [l for l in erro.splitlines()
                           if l.strip() and "Warning" not in l]
            if linhas_erro:
                return False, f"Erro na restauracao:\n{chr(10).join(linhas_erro[:8])}"

        return True, "Banco de dados restaurado com sucesso!"

    except subprocess.TimeoutExpired:
        return False, "Timeout: restauracao demorou mais de 5 minutos."
    except Exception as e:
        return False, f"Erro inesperado na restauracao: {e}"


# ══════════════════════════════════════════════════════════════════════
#  THREAD DE BACKUP AUTOMÁTICO
# ══════════════════════════════════════════════════════════════════════

class BackupAutomatico:
    """Thread daemon que executa backup a cada INTERVALO_MINUTOS minutos."""

    def __init__(self):
        self._thread  = None
        self._parar   = threading.Event()
        self._cfg     = _carregar_config()
        self._ultimo  = None    # datetime do último backup bem-sucedido
        self._log     = []      # histórico dos últimos backups
        self._lock    = threading.Lock()

    def iniciar(self):
        if self._thread and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="BackupAuto")
        self._thread.start()
        print(f"[backup] Thread de backup iniciada (intervalo: {INTERVALO_MINUTOS} min)")

    def parar(self):
        self._parar.set()

    def recarregar_config(self):
        with self._lock:
            self._cfg = _carregar_config()

    def get_ultimo(self):
        return self._ultimo

    def get_log(self):
        with self._lock:
            return list(self._log)

    def _loop(self):
        # Aguarda 2 minutos na primeira vez (deixa o sistema inicializar)
        self._parar.wait(120)
        while not self._parar.is_set():
            self._executar_agora(prefixo="auto")
            self._parar.wait(INTERVALO_MINUTOS * 60)

    def _executar_agora(self, prefixo="auto"):
        with self._lock:
            pasta = self._cfg.get("pasta_backup", "")

        if not pasta or not os.path.isdir(pasta):
            self._registrar_log(False, "Pasta de backup nao configurada ou inacessivel")
            return

        sucesso, msg = executar_backup(pasta, prefixo=prefixo)
        self._registrar_log(sucesso, msg if not sucesso else os.path.basename(msg))

        if sucesso and prefixo == "auto":
            _limpar_backups_antigos(pasta)
            self._ultimo = datetime.now()

    def _registrar_log(self, sucesso, msg):
        with self._lock:
            entrada = {
                "hora":    datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "sucesso": sucesso,
                "msg":     msg
            }
            self._log.insert(0, entrada)
            if len(self._log) > 100:
                self._log = self._log[:100]


# Instância global — criada uma vez e reutilizada
_backup_auto = BackupAutomatico()

def iniciar_backup_automatico():
    """Chamar no main.py após inicializar o banco."""
    _backup_auto.iniciar()

def parar_backup_automatico():
    """Chamar ao fechar o aplicativo."""
    _backup_auto.parar()


# ══════════════════════════════════════════════════════════════════════
#  TELA DE RECUPERAÇÃO (integrada no frame_main)
# ══════════════════════════════════════════════════════════════════════

def _construir_tela_backup(container, parent_win):
    _backup_auto.recarregar_config()
    cfg = _carregar_config()
    pasta_atual = {"v": cfg.get("pasta_backup", "")}

    # ── layout ──────────────────────────────────────────────────────
    frame_header = ctk.CTkFrame(container)
    frame_header.pack(fill="x", padx=10, pady=(10,4))

    frame_pasta = ctk.CTkFrame(container)
    frame_pasta.pack(fill="x", padx=10, pady=4)

    frame_acoes = ctk.CTkFrame(container)
    frame_acoes.pack(fill="x", padx=10, pady=4)

    frame_status = ctk.CTkFrame(container)
    frame_status.pack(fill="x", padx=10, pady=4)

    frame_log = ctk.CTkFrame(container)
    frame_log.pack(fill="both", expand=True, padx=10, pady=(4,10))

    # ── cabeçalho ───────────────────────────────────────────────────
    ctk.CTkLabel(frame_header, text="Backup e Recuperação",
                 font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=8)
    ctk.CTkLabel(frame_header,
                 text=f"Backup automático a cada {INTERVALO_MINUTOS} minutos",
                 text_color="#888888").pack(side="left", padx=16)

    # ── pasta de destino ─────────────────────────────────────────────
    ctk.CTkLabel(frame_pasta, text="Pasta de backup:", width=130, anchor="w").pack(side="left", padx=(8,4))
    lbl_pasta = ctk.CTkLabel(frame_pasta,
                              text=pasta_atual["v"] or "(nao configurada)",
                              text_color=COR_PRIMARIA if pasta_atual["v"] else "#ff6666",
                              wraplength=500, anchor="w")
    lbl_pasta.pack(side="left", padx=4, fill="x", expand=True)

    def selecionar_pasta():
        inicial = pasta_atual["v"] if pasta_atual["v"] and os.path.isdir(pasta_atual["v"]) else "/"
        pasta = filedialog.askdirectory(
            title="Selecionar pasta de backup",
            initialdir=inicial,
            parent=parent_win
        )
        if not pasta:
            return
        pasta_atual["v"] = pasta
        cfg2 = _carregar_config()
        cfg2["pasta_backup"] = pasta
        _salvar_config(cfg2)
        _backup_auto.recarregar_config()
        lbl_pasta.configure(text=pasta, text_color=COR_PRIMARIA)
        atualizar_status()
        messagebox.showinfo("Pasta configurada",
                            f"Pasta de backup definida:\n{pasta}\n\n"
                            "O backup automático já usará este local.")

    ctk.CTkButton(frame_pasta, text="📁 Selecionar Pasta", fg_color="#2d89ef",
                  width=160, command=selecionar_pasta).pack(side="right", padx=8)

    # ── botões de ação ───────────────────────────────────────────────
    ctk.CTkLabel(frame_acoes, text="Ações:", width=130, anchor="w",
                 font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(8,4))

    def exportar_agora():
        pasta = pasta_atual["v"]
        if not pasta or not os.path.isdir(pasta):
            messagebox.showwarning("Aviso",
                "Configure a pasta de backup antes de exportar.\n"
                "Clique em 'Selecionar Pasta'.")
            return

        btn_exportar.configure(state="disabled", text="Aguarde...")
        container.update_idletasks()

        def _fazer():
            sucesso, msg = executar_backup(pasta, prefixo="manual")
            container.after(0, lambda: _pos_exportar(sucesso, msg))

        def _pos_exportar(sucesso, msg):
            btn_exportar.configure(state="normal", text="⬇ Exportar Agora")
            if sucesso:
                nome = os.path.basename(msg)
                tamanho = os.path.getsize(msg) // 1024
                messagebox.showinfo("Backup realizado",
                    f"Backup exportado com sucesso!\n\n"
                    f"Arquivo: {nome}\n"
                    f"Tamanho: {tamanho} KB\n"
                    f"Local: {pasta}")
                _backup_auto._registrar_log(True, nome)
            else:
                messagebox.showerror("Erro no backup", msg)
                _backup_auto._registrar_log(False, msg)
            atualizar_log()
            atualizar_status()

        threading.Thread(target=_fazer, daemon=True).start()

    def recuperar():
        # Aviso duplo — MUITO IMPORTANTE
        if not messagebox.askyesno(
            "⚠ ATENÇÃO — RECUPERAÇÃO",
            "ATENÇÃO!\n\n"
            "A recuperação irá SUBSTITUIR COMPLETAMENTE o banco de dados atual.\n"
            "Todos os dados existentes serão perdidos e substituídos\n"
            "pelo conteúdo do arquivo de backup selecionado.\n\n"
            "Esta operação É IRREVERSÍVEL sem um backup prévio.\n\n"
            "Deseja continuar?",
            icon="warning"
        ):
            return

        # Segunda confirmação
        if not messagebox.askyesno(
            "⚠ CONFIRMAÇÃO FINAL",
            "CONFIRMAÇÃO FINAL:\n\n"
            "Você tem certeza ABSOLUTA que deseja restaurar o banco?\n\n"
            "Recomendamos fazer um backup AGORA antes de continuar.\n\n"
            "Clique SIM apenas se tiver certeza.",
            icon="warning"
        ):
            return

        # Selecionar arquivo
        arquivo = filedialog.askopenfilename(
            title="Selecionar arquivo de backup (.sql.gz)",
            filetypes=[("Backup SQL comprimido", "*.sql.gz"),
                       ("Arquivo SQL", "*.sql"),
                       ("Todos os arquivos", "*.*")],
            parent=parent_win
        )
        if not arquivo:
            return

        # Verifica extensão
        if not (arquivo.endswith(".sql.gz") or arquivo.endswith(".sql")):
            messagebox.showwarning("Arquivo inválido",
                "Selecione um arquivo .sql.gz gerado por este sistema.")
            return

        # Se for .sql puro (não comprimido), envolve em gz temporário
        arquivo_gz = arquivo
        arquivo_temp = None
        if arquivo.endswith(".sql") and not arquivo.endswith(".sql.gz"):
            import gzip, tempfile
            arquivo_temp = arquivo + ".gz_tmp"
            try:
                with open(arquivo, "rb") as fin, gzip.open(arquivo_temp, "wb") as fout:
                    fout.write(fin.read())
                arquivo_gz = arquivo_temp
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao preparar arquivo:\n{e}")
                return

        btn_recuperar.configure(state="disabled", text="Restaurando...")
        lbl_progresso = ctk.CTkLabel(frame_status, text="Iniciando restauração...",
                                      text_color="#ffcc44")
        lbl_progresso.pack(side="left", padx=8)
        container.update_idletasks()

        def _fazer():
            def _prog(msg):
                container.after(0, lambda m=msg: lbl_progresso.configure(text=m))
            sucesso, msg = restaurar_backup(arquivo_gz, callback_progresso=_prog)
            if arquivo_temp and os.path.exists(arquivo_temp):
                try: os.remove(arquivo_temp)
                except: pass
            container.after(0, lambda: _pos_recuperar(sucesso, msg, lbl_progresso))

        def _pos_recuperar(sucesso, msg, lbl_prog):
            btn_recuperar.configure(state="normal", text="🔄 Recuperar")
            try: lbl_prog.destroy()
            except: pass
            if sucesso:
                messagebox.showinfo("Restauração concluída",
                    "✅ Banco de dados restaurado com sucesso!\n\n"
                    "O sistema continuará funcionando com os dados recuperados.\n"
                    "Reinicie o sistema para garantir consistência.")
            else:
                messagebox.showerror("Erro na restauração",
                    f"❌ Falha ao restaurar:\n\n{msg}\n\n"
                    "O banco pode estar inconsistente.\n"
                    "Tente novamente ou contate o suporte.")
            atualizar_status()

        threading.Thread(target=_fazer, daemon=True).start()

    btn_exportar = ctk.CTkButton(frame_acoes, text="⬇ Exportar Agora",
                                  fg_color="#28a745", width=160, command=exportar_agora)
    btn_exportar.pack(side="left", padx=6)

    btn_recuperar = ctk.CTkButton(frame_acoes, text="🔄 Recuperar",
                                   fg_color="#d9534f", width=140, command=recuperar)
    btn_recuperar.pack(side="left", padx=6)

    ctk.CTkButton(frame_acoes, text="↺ Atualizar Log",
                  fg_color="#6c757d", width=130,
                  command=lambda: (atualizar_log(), atualizar_status())).pack(side="left", padx=6)

    # ── status ───────────────────────────────────────────────────────
    lbl_ultimo_backup = ctk.CTkLabel(frame_status, text="Último backup: —",
                                      text_color="#888888")
    lbl_ultimo_backup.pack(side="left", padx=8)

    lbl_proximo = ctk.CTkLabel(frame_status, text="",
                                text_color="#888888")
    lbl_proximo.pack(side="left", padx=16)

    def atualizar_status():
        ultimo = _backup_auto.get_ultimo()
        if ultimo:
            lbl_ultimo_backup.configure(
                text=f"Último backup automático: {ultimo.strftime('%d/%m/%Y %H:%M:%S')}",
                text_color="#28a745")
            prox = INTERVALO_MINUTOS - int((datetime.now() - ultimo).total_seconds() / 60)
            prox = max(0, prox)
            lbl_proximo.configure(text=f"Próximo em: ~{prox} min")
        else:
            lbl_ultimo_backup.configure(
                text="Nenhum backup automático realizado ainda",
                text_color="#888888")
            lbl_proximo.configure(text="")

    # ── log de backups ───────────────────────────────────────────────
    ctk.CTkLabel(frame_log, text="Histórico de backups:",
                 font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=8, pady=(6,2))

    frame_tree = tk.Frame(frame_log)
    frame_tree.pack(fill="both", expand=True, padx=8, pady=(0,8))

    cols = ("hora","status","arquivo")
    tree_log = ttk.Treeview(frame_tree, columns=cols, show="headings", height=12)
    tree_log.heading("hora",    text="Data/Hora")
    tree_log.heading("status",  text="Status")
    tree_log.heading("arquivo", text="Arquivo / Mensagem")
    tree_log.column("hora",    width=160)
    tree_log.column("status",  width=80,  anchor="center")
    tree_log.column("arquivo", width=500)
    sb_log = ttk.Scrollbar(frame_tree, orient="vertical", command=tree_log.yview)
    tree_log.configure(yscrollcommand=sb_log.set)
    sb_log.pack(side="right", fill="y")
    tree_log.pack(fill="both", expand=True)
    tree_log.tag_configure("ok",   foreground="#28a745")
    tree_log.tag_configure("erro", foreground="#d9534f")

    def atualizar_log():
        for i in tree_log.get_children(): tree_log.delete(i)
        for entrada in _backup_auto.get_log():
            status = "✔ OK" if entrada["sucesso"] else "✘ ERRO"
            tag    = "ok"   if entrada["sucesso"] else "erro"
            tree_log.insert("", tk.END,
                            values=(entrada["hora"], status, entrada["msg"]),
                            tags=(tag,))

    atualizar_status()
    atualizar_log()

    # Atualiza status a cada 60s enquanto a tela estiver visível
    def _loop_status():
        try:
            if container.winfo_exists():
                atualizar_status()
                container.after(60000, _loop_status)
        except Exception:
            pass
    container.after(60000, _loop_status)


def mostrar_backup_inline(frame_main, show_frame_in_main_fn):
    """Abre a tela de backup dentro do frame_main do PDV."""
    parent_win = frame_main.winfo_toplevel()
    frame_bkp = ctk.CTkFrame(frame_main)
    _construir_tela_backup(frame_bkp, parent_win)
    show_frame_in_main_fn(frame_bkp)