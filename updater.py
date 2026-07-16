"""
updater.py — Sistema de Atualização Automática
================================================
Repositório: https://github.com/Nomade04/PDV

Formato de release no GitHub:
  - Crie uma Release no GitHub com tag no formato: v1.0.0, v1.2.3, etc.
  - Anexe um arquivo chamado "update.zip" contendo os arquivos .py atualizados
  - O sistema compara a versão atual com a mais recente e oferece atualização

Estrutura do update.zip:
  update.zip
  ├── interface.py
  ├── clientes.py
  ├── vendas_interface.py
  ├── backup.py
  ├── balanca.py
  ├── relatorios.py
  ├── database.py
  └── ... (qualquer arquivo .py que mudou)

Uso no main.py:
  import updater
  updater.verificar_atualizacao_em_background(root_tk)
"""

import os
import sys
import json
import shutil
import zipfile
import threading
import tempfile
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

# ── Configurações ──────────────────────────────────────────────────────
GITHUB_OWNER    = "Nomade04"
GITHUB_REPO     = "PDV"
GITHUB_API_URL  = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
ASSET_NAME      = "update.zip"   # nome do arquivo anexado na Release

# Pasta onde estão os arquivos .py do sistema
PASTA_SISTEMA   = os.path.dirname(os.path.abspath(__file__))

# Arquivo que guarda a versão instalada atualmente
VERSAO_FILE     = os.path.join(PASTA_SISTEMA, "versao.txt")

# Arquivo de log de atualizações
LOG_FILE        = os.path.join(PASTA_SISTEMA, "update_log.txt")

COR_PRIMARIA    = "#FFA500"
COR_SECUNDARIA  = "#FFD700"


# ══════════════════════════════════════════════════════════════════════
#  CONTROLE DE VERSÃO
# ══════════════════════════════════════════════════════════════════════

def ler_versao_atual() -> str:
    """Lê a versão instalada do arquivo versao.txt."""
    try:
        if os.path.exists(VERSAO_FILE):
            with open(VERSAO_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return "v0.0.0"


def salvar_versao(versao: str):
    """Salva a versão instalada."""
    try:
        with open(VERSAO_FILE, "w", encoding="utf-8") as f:
            f.write(versao.strip())
    except Exception as e:
        print(f"[updater] Erro ao salvar versao: {e}")


def _versao_para_tupla(v: str) -> tuple:
    """Converte 'v1.2.3' em (1, 2, 3) para comparação."""
    try:
        partes = v.lstrip("v").split(".")
        return tuple(int(x) for x in partes)
    except Exception:
        return (0, 0, 0)


def _registrar_log(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════
#  CONSULTA AO GITHUB
# ══════════════════════════════════════════════════════════════════════

def consultar_release_mais_nova(timeout=10) -> dict | None:
    """
    Consulta a API do GitHub e retorna informações da release mais recente.
    Retorna None se não houver conexão ou release.

    Retorno:
      {
        "tag":         "v1.2.0",
        "nome":        "Versão 1.2.0 - Correções e melhorias",
        "descricao":   "...",
        "download_url": "https://...",
        "publicado":   "2025-01-15"
      }
    """
    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={
                "User-Agent": "MerceariaGodoi-PDV-Updater/1.0",
                "Accept":     "application/vnd.github.v3+json"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dados = json.loads(resp.read().decode("utf-8"))

        tag        = dados.get("tag_name", "")
        nome       = dados.get("name", tag)
        descricao  = dados.get("body", "Sem notas de versão.")
        publicado  = dados.get("published_at", "")[:10]
        assets     = dados.get("assets", [])

        # Procura o arquivo update.zip nos assets
        download_url = None
        for asset in assets:
            if asset.get("name", "").lower() == ASSET_NAME.lower():
                download_url = asset.get("browser_download_url")
                break

        if not tag:
            return None

        return {
            "tag":          tag,
            "nome":         nome,
            "descricao":    descricao,
            "download_url": download_url,
            "publicado":    publicado
        }

    except urllib.error.URLError:
        return None   # sem conexão
    except Exception as e:
        _registrar_log(f"Erro ao consultar GitHub: {e}")
        return None


def ha_atualizacao_disponivel() -> tuple[bool, dict | None]:
    """
    Verifica se há versão mais nova que a instalada.
    Retorna (tem_atualizacao, info_release).
    """
    release = consultar_release_mais_nova()
    if not release:
        return False, None

    versao_atual  = ler_versao_atual()
    versao_nova   = release["tag"]

    atual_tupla = _versao_para_tupla(versao_atual)
    nova_tupla  = _versao_para_tupla(versao_nova)

    return nova_tupla > atual_tupla, release


# ══════════════════════════════════════════════════════════════════════
#  DOWNLOAD E APLICAÇÃO
# ══════════════════════════════════════════════════════════════════════

def _baixar_arquivo(url: str, destino: str, callback_progresso=None) -> bool:
    """Baixa um arquivo com reporte de progresso."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MerceariaGodoi-PDV-Updater/1.0"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            tamanho_total = int(resp.headers.get("Content-Length", 0))
            baixado = 0
            with open(destino, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    baixado += len(chunk)
                    if callback_progresso and tamanho_total > 0:
                        pct = int(baixado / tamanho_total * 100)
                        callback_progresso(pct, baixado, tamanho_total)
        return True
    except Exception as e:
        _registrar_log(f"Erro no download: {e}")
        return False


def aplicar_atualizacao(url_zip: str, versao_nova: str,
                         callback_status=None) -> tuple[bool, str]:
    """
    Baixa o update.zip, faz backup dos arquivos atuais e aplica a atualização.
    Retorna (sucesso, mensagem).
    """
    pasta_temp = tempfile.mkdtemp(prefix="pdv_update_")

    try:
        # 1. Download
        if callback_status: callback_status("Baixando atualização...")
        zip_path = os.path.join(pasta_temp, ASSET_NAME)
        ok = _baixar_arquivo(
            url_zip, zip_path,
            callback_progresso=lambda p, b, t:
                callback_status(f"Baixando... {p}%  ({b//1024} / {t//1024} KB)")
                if callback_status else None
        )
        if not ok:
            return False, "Falha no download. Verifique sua conexão."

        # 2. Valida ZIP
        if callback_status: callback_status("Validando arquivo...")
        if not zipfile.is_zipfile(zip_path):
            return False, "Arquivo baixado não é um ZIP válido."

        # 3. Backup dos arquivos que serão substituídos
        if callback_status: callback_status("Fazendo backup dos arquivos atuais...")
        pasta_bkp = os.path.join(pasta_temp, "backup_antes_update")
        os.makedirs(pasta_bkp, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            arquivos_no_zip = [
                n for n in zf.namelist()
                if not n.endswith("/") and n.endswith(".py")
            ]

        for nome_arq in arquivos_no_zip:
            nome_base = os.path.basename(nome_arq)
            origem = os.path.join(PASTA_SISTEMA, nome_base)
            if os.path.exists(origem):
                shutil.copy2(origem, os.path.join(pasta_bkp, nome_base))

        # 4. Extrai e copia os novos arquivos
        if callback_status: callback_status("Aplicando atualização...")
        pasta_extraida = os.path.join(pasta_temp, "extraido")
        os.makedirs(pasta_extraida, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(pasta_extraida)

        # Copia apenas arquivos .py para a pasta do sistema
        arquivos_aplicados = []
        for raiz, dirs, arquivos in os.walk(pasta_extraida):
            for arq in arquivos:
                if not arq.endswith(".py"):
                    continue
                src = os.path.join(raiz, arq)
                dst = os.path.join(PASTA_SISTEMA, arq)
                shutil.copy2(src, dst)
                arquivos_aplicados.append(arq)

        if not arquivos_aplicados:
            return False, "O ZIP não continha arquivos .py para atualizar."

        # 5. Atualiza versão
        salvar_versao(versao_nova)
        _registrar_log(f"Atualização aplicada: {versao_nova} — arquivos: {', '.join(arquivos_aplicados)}")

        lista = "\n  • ".join(arquivos_aplicados)
        return True, f"Arquivos atualizados:\n  • {lista}"

    except Exception as e:
        _registrar_log(f"Erro ao aplicar atualização: {e}")
        return False, f"Erro inesperado: {e}"
    finally:
        try: shutil.rmtree(pasta_temp, ignore_errors=True)
        except Exception: pass


# ══════════════════════════════════════════════════════════════════════
#  JANELA DE ATUALIZAÇÃO
# ══════════════════════════════════════════════════════════════════════

def _mostrar_popup_atualizacao(root_tk, release: dict,
                                btn_flutuante=None):
    """
    Mostra popup com detalhes da atualização disponível.
    Se aceitar, baixa e aplica. Se recusar, mantém botão flutuante visível.
    """
    versao_atual = ler_versao_atual()
    versao_nova  = release["tag"]

    win = ctk.CTkToplevel(root_tk)
    win.title("Atualização Disponível")
    win.geometry("520x400")
    win.resizable(False, False)
    win.transient(root_tk)
    win.lift()
    win.focus_force()
    win.after(100, win.grab_set)

    # Cabeçalho
    ctk.CTkLabel(win, text="🔄  Nova Atualização Disponível",
                 font=ctk.CTkFont(size=16, weight="bold"),
                 text_color=COR_PRIMARIA).pack(pady=(20,4))

    frame_versoes = ctk.CTkFrame(win, fg_color="transparent")
    frame_versoes.pack(pady=4)
    ctk.CTkLabel(frame_versoes, text=f"Versão atual:  {versao_atual}",
                 text_color="#888888").pack(side="left", padx=16)
    ctk.CTkLabel(frame_versoes, text="→", text_color="#888888").pack(side="left")
    ctk.CTkLabel(frame_versoes, text=f"  Nova versão:  {versao_nova}",
                 text_color="#28a745", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=16)

    ctk.CTkLabel(win, text=f"Publicada em: {release.get('publicado','')}",
                 text_color="#888888", font=ctk.CTkFont(size=11)).pack()

    ctk.CTkLabel(win, text="Notas da versão:",
                 font=ctk.CTkFont(size=12, weight="bold"),
                 anchor="w").pack(anchor="w", padx=20, pady=(12,2))

    frame_notas = ctk.CTkFrame(win)
    frame_notas.pack(fill="both", expand=True, padx=20, pady=(0,8))
    txt_notas = tk.Text(frame_notas, height=8, wrap="word",
                        font=("Courier", 9), bg="#2b2b2b", fg="#dddddd",
                        relief="flat", padx=6, pady=6)
    sb_notas = tk.Scrollbar(frame_notas, command=txt_notas.yview)
    txt_notas.configure(yscrollcommand=sb_notas.set)
    sb_notas.pack(side="right", fill="y")
    txt_notas.pack(fill="both", expand=True)
    descricao = release.get("descricao") or "Sem notas de versão."
    txt_notas.insert("1.0", descricao)
    txt_notas.configure(state="disabled")

    ctk.CTkLabel(win,
                 text="⚠  A atualização pode levar alguns minutos. O sistema continuará aberto.",
                 text_color="#ffcc44", font=ctk.CTkFont(size=10)).pack(pady=(0,6))

    # Barra de progresso (oculta inicialmente)
    frame_prog = ctk.CTkFrame(win, fg_color="transparent")
    frame_prog.pack(fill="x", padx=20, pady=(0,4))
    barra_prog = ctk.CTkProgressBar(frame_prog, width=460)
    barra_prog.set(0)
    lbl_prog = ctk.CTkLabel(frame_prog, text="", text_color="#888888",
                             font=ctk.CTkFont(size=10))

    # Botões
    frame_bt = ctk.CTkFrame(win, fg_color="transparent")
    frame_bt.pack(pady=(0,16))
    btn_sim = ctk.CTkButton(frame_bt, text="✔  Atualizar Agora",
                             fg_color="#28a745", width=180)
    btn_nao = ctk.CTkButton(frame_bt, text="✖  Agora Não",
                             fg_color="#6c757d", width=140)
    btn_sim.pack(side="left", padx=10)
    btn_nao.pack(side="left", padx=10)

    def recusar():
        win.destroy()
        # Mantém botão flutuante visível
        if btn_flutuante:
            try: btn_flutuante.place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-8)
            except Exception: pass

    def aceitar():
        url = release.get("download_url")
        if not url:
            messagebox.showerror("Erro",
                "Arquivo de atualização não encontrado na release.\n"
                "Verifique se o arquivo 'update.zip' foi anexado à release no GitHub.",
                parent=win)
            return

        btn_sim.configure(state="disabled", text="Atualizando...")
        btn_nao.configure(state="disabled")
        barra_prog.pack(fill="x", pady=(0,2))
        lbl_prog.pack()
        barra_prog.start()

        def _status(msg):
            try:
                win.after(0, lambda m=msg: lbl_prog.configure(text=m))
            except Exception:
                pass

        def _fazer():
            sucesso, msg = aplicar_atualizacao(url, versao_nova, callback_status=_status)
            win.after(0, lambda: _pos_atualizar(sucesso, msg))

        def _pos_atualizar(sucesso, msg):
            barra_prog.stop(); barra_prog.set(1.0 if sucesso else 0)
            if sucesso:
                win.destroy()
                if btn_flutuante:
                    try: btn_flutuante.place_forget()
                    except Exception: pass
                messagebox.showinfo(
                    "Atualização concluída",
                    f"✅ Sistema atualizado para {versao_nova}!\n\n"
                    f"{msg}\n\n"
                    "Reinicie o sistema para que as alterações tenham efeito."
                )
            else:
                barra_prog.pack_forget(); lbl_prog.pack_forget()
                btn_sim.configure(state="normal", text="✔  Tentar Novamente")
                btn_nao.configure(state="normal")
                messagebox.showerror("Erro na atualização",
                    f"❌ Falha ao atualizar:\n\n{msg}", parent=win)

        threading.Thread(target=_fazer, daemon=True).start()

    btn_sim.configure(command=aceitar)
    btn_nao.configure(command=recusar)
    win.bind("<Escape>", lambda e: recusar())
    win.protocol("WM_DELETE_WINDOW", recusar)


# ══════════════════════════════════════════════════════════════════════
#  BOTÃO FLUTUANTE "Atualização disponível"
# ══════════════════════════════════════════════════════════════════════

def _criar_botao_flutuante(root_tk, release: dict) -> ctk.CTkButton:
    """
    Cria um botão discreto no canto inferior direito da tela
    que fica visível quando há atualização pendente.
    """
    btn = ctk.CTkButton(
        root_tk,
        text="🔄 Atualização disponível",
        fg_color="#2d89ef",
        hover_color="#1a6fc4",
        text_color="white",
        font=ctk.CTkFont(size=11, weight="bold"),
        width=200,
        height=30,
        corner_radius=6,
    )

    def ao_clicar():
        _mostrar_popup_atualizacao(root_tk, release, btn_flutuante=btn)

    btn.configure(command=ao_clicar)
    # Posiciona no canto inferior direito, sem cobrir o menu lateral
    btn.place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-8)
    return btn


# ══════════════════════════════════════════════════════════════════════
#  PONTO DE ENTRADA — verificar em background
# ══════════════════════════════════════════════════════════════════════

def verificar_atualizacao_em_background(root_tk):
    """
    Verifica atualizações em background sem travar a interface.
    Chamar logo após criar a janela principal (root_tk).

    Se houver atualização:
      - Exibe popup perguntando se quer atualizar
      - Se recusar, exibe botão flutuante no canto da tela
    """
    def _verificar():
        try:
            tem, release = ha_atualizacao_disponivel()
            if tem and release:
                versao_nova = release["tag"]
                _registrar_log(f"Atualização disponível: {versao_nova}")
                # Executa na thread principal do Tk
                root_tk.after(500, lambda: _exibir_notificacao(release))
        except Exception as e:
            _registrar_log(f"Erro ao verificar atualização: {e}")

    def _exibir_notificacao(release):
        try:
            btn_flutuante = _criar_botao_flutuante(root_tk, release)
            _mostrar_popup_atualizacao(root_tk, release, btn_flutuante=btn_flutuante)
        except Exception as e:
            _registrar_log(f"Erro ao exibir notificação: {e}")

    t = threading.Thread(target=_verificar, daemon=True, name="UpdateChecker")
    t.start()