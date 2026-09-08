"""
updater.py — Sistema de Atualização Automática
================================================
Repositório: https://github.com/Nomade04/PDV

Formato de release no GitHub:
  - Crie uma Release com tag: v1.0.0, v1.2.3, etc.
  - Anexe um arquivo chamado "update.zip" com os .py atualizados
  - O sistema compara a versão atual com a mais recente

Estrutura do update.zip:
  update.zip
  ├── interface.py
  ├── clientes.py
  ├── vendas_interface.py
  ├── backup.py
  ├── balanca.py
  ├── relatorios.py
  ├── database.py
  └── versao.txt  (com a nova versão, ex: v1.1.0)

Uso no interface.py (após criar app):
  import updater
  updater.verificar_atualizacao_em_background(app)
"""

# ── Imports padrão ────────────────────────────────────────────────────
import os
import sys
import json
import shutil
import zipfile
import threading
import tempfile
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# ── Imports Tkinter / CustomTkinter ───────────────────────────────────
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

# ═════════════════════════════════════════════════════════════════════
#  CONFIGURAÇÕES
# ═════════════════════════════════════════════════════════════════════

GITHUB_OWNER   = "Nomade04"
GITHUB_REPO    = "PDV"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
ASSET_NAME     = "update.zip"

PASTA_SISTEMA  = os.path.dirname(os.path.abspath(__file__))
VERSAO_FILE    = os.path.join(PASTA_SISTEMA, "versao.txt")
LOG_FILE       = os.path.join(PASTA_SISTEMA, "update_log.txt")
TOKEN_FILE     = os.path.join(PASTA_SISTEMA, "github_token.txt")

COR_PRIMARIA   = "#FFA500"


def _ler_token() -> str:
    """Lê o token do GitHub do arquivo github_token.txt."""
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


# ═════════════════════════════════════════════════════════════════════
#  CONTROLE DE VERSÃO
# ═════════════════════════════════════════════════════════════════════

def ler_versao_atual() -> str:
    """Lê a versão instalada do arquivo versao.txt."""
    try:
        if os.path.exists(VERSAO_FILE):
            with open(VERSAO_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return "v0.0.0"


def salvar_versao(versao: str) -> None:
    """Salva a versão instalada em versao.txt."""
    try:
        with open(VERSAO_FILE, "w", encoding="utf-8") as f:
            f.write(versao.strip())
    except Exception as e:
        _registrar_log(f"Erro ao salvar versao: {e}")


def _versao_para_tupla(v: str) -> tuple:
    """Converte 'v1.2.3' em (1, 2, 3) para comparação numérica."""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)


def _registrar_log(msg: str) -> None:
    """Registra evento no arquivo de log."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════
#  CONSULTA AO GITHUB
# ═════════════════════════════════════════════════════════════════════

def consultar_release_mais_nova(timeout: int = 10) -> Optional[dict]:
    """
    Consulta a API do GitHub e retorna dados da release mais recente.
    Usa token do arquivo github_token.txt se disponível.
    """
    try:
        token = _ler_token()
        headers = {
            "User-Agent": "Mozilla/5.0 MerceariaGodoi-PDV/1.0",
            "Accept":     "application/vnd.github.v3+json",
            "Cache-Control": "no-cache",
        }
        if token:
            headers["Authorization"] = f"token {token}"

        req = urllib.request.Request(GITHUB_API_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dados = json.loads(resp.read().decode("utf-8"))

        tag       = dados.get("tag_name", "")
        nome      = dados.get("name", tag)
        descricao = dados.get("body", "Sem notas de versao.")
        publicado = dados.get("published_at", "")[:10]
        assets    = dados.get("assets", [])

        download_url = None
        for asset in assets:
            if asset.get("name", "").lower() == ASSET_NAME.lower():
                download_url = asset.get("browser_download_url")
                break

        if not tag:
            _registrar_log("GitHub retornou resposta sem tag_name")
            return None

        _registrar_log(f"GitHub consultado com sucesso: release mais nova = {tag}")
        return {
            "tag":          tag,
            "nome":         nome,
            "descricao":    descricao,
            "download_url": download_url,
            "publicado":    publicado,
        }

    except urllib.error.HTTPError as e:
        _registrar_log(f"GitHub HTTP {e.code}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        _registrar_log(f"Sem conexao com GitHub: {e.reason}")
        return None
    except Exception as e:
        _registrar_log(f"Erro ao consultar GitHub: {e}")
        return None


def ha_atualizacao_disponivel() -> Tuple[bool, Optional[dict]]:
    """
    Verifica se há versão mais nova que a instalada.
    Retorna (tem_atualizacao, info_release).
    """
    release = consultar_release_mais_nova()
    if not release:
        return False, None

    atual = _versao_para_tupla(ler_versao_atual())
    nova  = _versao_para_tupla(release["tag"])
    return nova > atual, release


# ═════════════════════════════════════════════════════════════════════
#  DOWNLOAD E APLICAÇÃO
# ═════════════════════════════════════════════════════════════════════

def _baixar_arquivo(url: str, destino: str, callback_progresso=None) -> bool:
    """
    Baixa asset do GitHub. Para repositórios privados, converte a
    browser_download_url para a API URL e usa Accept: application/octet-stream.
    """
    import urllib.parse
    import re

    token = _ler_token()
    _registrar_log(f"Iniciando download: {url[:80]}")

    # Converte browser_download_url → API URL para repos privados
    # De: https://github.com/OWNER/REPO/releases/download/TAG/FILE
    # Para: https://api.github.com/repos/OWNER/REPO/releases/assets/ASSET_ID
    # Alternativa mais simples: usar a URL da API com o asset_id
    url_download = url

    try:
        parsed = urllib.parse.urlparse(url)

        # Se for URL direta do GitHub (browser_download_url), converte para API
        m = re.match(
            r"https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/(.+)",
            url
        )
        if m and token:
            owner, repo, tag, filename = m.groups()
            # Busca o asset_id via API
            api_assets = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
            _registrar_log(f"Buscando asset_id via API: {api_assets}")
            req_info = urllib.request.Request(api_assets, headers={
                "User-Agent": "Mozilla/5.0 MerceariaGodoi-PDV/1.0",
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            })
            with urllib.request.urlopen(req_info, timeout=15) as r:
                release_data = json.loads(r.read().decode("utf-8"))

            asset_id = None
            for asset in release_data.get("assets", []):
                if asset.get("name", "").lower() == filename.lower():
                    asset_id = asset.get("id")
                    break

            if asset_id:
                url_download = f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{asset_id}"
                _registrar_log(f"Usando API URL com asset_id {asset_id}")
            else:
                _registrar_log(f"Asset '{filename}' nao encontrado na release")
                return False

        # Faz o download
        headers = {
            "User-Agent": "Mozilla/5.0 MerceariaGodoi-PDV/1.0",
            "Accept": "application/octet-stream",
        }
        if token and "github" in urllib.parse.urlparse(url_download).netloc:
            headers["Authorization"] = f"token {token}"

        _registrar_log(f"Download via: {url_download[:80]}")
        req = urllib.request.Request(url_download, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            tamanho_total = int(resp.headers.get("Content-Length", 0))
            _registrar_log(f"Resposta OK, tamanho: {tamanho_total} bytes")
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

        _registrar_log(f"Download concluido: {baixado // 1024} KB")
        return True

    except urllib.error.HTTPError as e:
        _registrar_log(f"HTTP {e.code} {e.reason} no download")
        return False
    except Exception as e:
        _registrar_log(f"Excecao no download: {type(e).__name__}: {e}")
        return False


def aplicar_atualizacao(url_zip: str, versao_nova: str,
                         callback_status=None) -> Tuple[bool, str]:
    """
    Baixa o update.zip, faz backup dos arquivos atuais e aplica.
    Retorna (sucesso, mensagem).
    """
    pasta_temp = tempfile.mkdtemp(prefix="pdv_update_")
    try:
        # 1. Download
        if callback_status:
            callback_status("Baixando atualizacao...")
        zip_path = os.path.join(pasta_temp, ASSET_NAME)

        def _prog(p, b, t):
            if callback_status:
                callback_status(f"Baixando... {p}%  ({b // 1024} / {t // 1024} KB)")

        ok = _baixar_arquivo(url_zip, zip_path, callback_progresso=_prog)
        if not ok:
            return False, "Falha no download. Verifique sua conexao."

        # 2. Valida ZIP
        if callback_status:
            callback_status("Validando arquivo...")
        if not zipfile.is_zipfile(zip_path):
            return False, "Arquivo baixado nao e um ZIP valido."

        # 3. Backup dos arquivos que serão substituídos
        if callback_status:
            callback_status("Fazendo backup dos arquivos atuais...")
        pasta_bkp = os.path.join(pasta_temp, "backup_antes_update")
        os.makedirs(pasta_bkp, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            arquivos_no_zip = [
                n for n in zf.namelist()
                if not n.endswith("/") and (n.endswith(".py") or n == "versao.txt")
            ]

        for nome_arq in arquivos_no_zip:
            nome_base = os.path.basename(nome_arq)
            origem = os.path.join(PASTA_SISTEMA, nome_base)
            if os.path.exists(origem):
                shutil.copy2(origem, os.path.join(pasta_bkp, nome_base))

        # 4. Extrai e copia os novos arquivos
        if callback_status:
            callback_status("Aplicando atualizacao...")
        pasta_extraida = os.path.join(pasta_temp, "extraido")
        os.makedirs(pasta_extraida, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(pasta_extraida)

        arquivos_aplicados = []
        for raiz, dirs, arquivos in os.walk(pasta_extraida):
            for arq in arquivos:
                if not (arq.endswith(".py") or arq == "versao.txt"):
                    continue
                src = os.path.join(raiz, arq)
                dst = os.path.join(PASTA_SISTEMA, arq)
                shutil.copy2(src, dst)
                arquivos_aplicados.append(arq)

        if not arquivos_aplicados:
            return False, "O ZIP nao continha arquivos para atualizar."

        # 5. Garante que versao.txt foi atualizado
        salvar_versao(versao_nova)
        _registrar_log(
            f"Atualizacao aplicada: {versao_nova} — "
            f"arquivos: {', '.join(arquivos_aplicados)}"
        )

        lista = "\n  • ".join(arquivos_aplicados)
        return True, f"Arquivos atualizados:\n  • {lista}"

    except Exception as e:
        _registrar_log(f"Erro ao aplicar atualizacao: {e}")
        return False, f"Erro inesperado: {e}"
    finally:
        try:
            shutil.rmtree(pasta_temp, ignore_errors=True)
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════
#  REINÍCIO AUTOMÁTICO
# ═════════════════════════════════════════════════════════════════════

def _reiniciar_sistema() -> None:
    """Relança o processo Python atual e encerra o processo atual."""
    try:
        python = sys.executable
        script = os.path.join(PASTA_SISTEMA, "main.py")
        subprocess.Popen([python, script])
        os._exit(0)
    except Exception as e:
        _registrar_log(f"Erro ao reiniciar: {e}")
        messagebox.showwarning(
            "Reinicio",
            f"Nao foi possivel reiniciar automaticamente:\n{e}\n\n"
            "Feche e abra o sistema manualmente."
        )


def _perguntar_reinicio(root_tk: ctk.CTk, versao_nova: str) -> None:
    """Pergunta ao operador se quer reiniciar agora ou depois."""
    win = ctk.CTkToplevel(root_tk)
    win.title("Reiniciar Sistema")
    win.geometry("420x200")
    win.resizable(False, False)
    win.transient(root_tk)
    win.lift()
    win.focus_force()
    win.after(100, win.grab_set)

    ctk.CTkLabel(
        win, text="Atualizacao Concluida!",
        font=ctk.CTkFont(size=15, weight="bold"),
        text_color="#28a745"
    ).pack(pady=(20, 6))

    ctk.CTkLabel(
        win, text=f"Sistema atualizado para {versao_nova}.",
        text_color="#888888"
    ).pack()

    ctk.CTkLabel(
        win,
        text="Deseja reiniciar agora para aplicar as alteracoes?",
        font=ctk.CTkFont(size=12)
    ).pack(pady=(12, 16))

    frame_bt = ctk.CTkFrame(win, fg_color="transparent")
    frame_bt.pack()

    def reiniciar_agora() -> None:
        win.destroy()
        _reiniciar_sistema()

    def reiniciar_depois() -> None:
        win.destroy()
        messagebox.showinfo(
            "Lembrete",
            "Lembre-se de reiniciar o sistema\n"
            "para que as atualizacoes tenham efeito."
        )

    ctk.CTkButton(
        frame_bt, text="Reiniciar Agora", fg_color="#28a745",
        width=160, command=reiniciar_agora
    ).pack(side="left", padx=10)

    ctk.CTkButton(
        frame_bt, text="Reiniciar Depois", fg_color="#6c757d",
        width=160, command=reiniciar_depois
    ).pack(side="left", padx=10)

    win.bind("<Return>", lambda e: reiniciar_agora())
    win.bind("<Escape>", lambda e: reiniciar_depois())


# ═════════════════════════════════════════════════════════════════════
#  BOTÃO FLUTUANTE
# ═════════════════════════════════════════════════════════════════════

def _criar_botao_flutuante(root_tk: ctk.CTk, release: dict) -> ctk.CTkButton:
    """
    Cria botão discreto no canto inferior direito indicando
    atualização pendente. Ao clicar, reabre o popup.
    """
    btn = ctk.CTkButton(
        root_tk,
        text="Atualizacao disponivel",
        fg_color="#2d89ef",
        hover_color="#1a6fc4",
        text_color="white",
        font=ctk.CTkFont(size=11, weight="bold"),
        width=210,
        height=30,
        corner_radius=6,
    )

    def ao_clicar() -> None:
        _mostrar_popup_atualizacao(root_tk, release, btn_flutuante=btn)

    btn.configure(command=ao_clicar)
    # Canto inferior direito, acima da barra de tarefas
    btn.place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-8)
    return btn


# ═════════════════════════════════════════════════════════════════════
#  POPUP DE ATUALIZAÇÃO
# ═════════════════════════════════════════════════════════════════════

def _mostrar_popup_atualizacao(
    root_tk: ctk.CTk,
    release: dict,
    btn_flutuante: Optional[ctk.CTkButton] = None
) -> None:
    versao_atual = ler_versao_atual()
    versao_nova  = release["tag"]

    win = ctk.CTkToplevel(root_tk)
    win.title("Atualizacao Disponivel")
    win.geometry("520x480")
    win.resizable(False, False)
    win.transient(root_tk)
    win.lift()
    win.focus_force()
    win.after(100, win.grab_set)

    # Cabeçalho
    ctk.CTkLabel(win, text="Nova Atualizacao Disponivel",
                 font=ctk.CTkFont(size=16, weight="bold"),
                 text_color=COR_PRIMARIA).pack(pady=(18, 4))

    frame_v = ctk.CTkFrame(win, fg_color="transparent")
    frame_v.pack(pady=2)
    ctk.CTkLabel(frame_v, text=f"Versao atual: {versao_atual}",
                 text_color="#666666").pack(side="left", padx=8)
    ctk.CTkLabel(frame_v, text="->", text_color="#666666").pack(side="left")
    ctk.CTkLabel(frame_v, text=f" Nova versao: {versao_nova}",
                 text_color="#28a745",
                 font=ctk.CTkFont(weight="bold")).pack(side="left", padx=8)

    ctk.CTkLabel(win, text=f"Publicada em: {release.get('publicado', '')}",
                 text_color="#666666",
                 font=ctk.CTkFont(size=10)).pack(pady=(0, 8))

    # Notas — altura FIXA, sem expand
    ctk.CTkLabel(win, text="Notas da versao:",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 anchor="w").pack(anchor="w", padx=20, pady=(0, 2))

    frame_notas = tk.Frame(win, bg="#1a1a1a", height=140)
    frame_notas.pack(fill="x", padx=20, pady=(0, 6))
    frame_notas.pack_propagate(False)   # mantém altura fixa

    txt_notas = tk.Text(frame_notas, wrap="word",
                        font=("Courier", 9),
                        bg="#1a1a1a", fg="#e0e0e0",
                        relief="flat", padx=6, pady=4)
    sb_notas = tk.Scrollbar(frame_notas, command=txt_notas.yview)
    txt_notas.configure(yscrollcommand=sb_notas.set)
    sb_notas.pack(side="right", fill="y")
    txt_notas.pack(fill="both", expand=True)
    txt_notas.insert("1.0", release.get("descricao") or "Sem notas de versao.")
    txt_notas.configure(state="disabled")

    # Aviso
    ctk.CTkLabel(win,
                 text="⚠  A atualizacao pode levar alguns minutos.",
                 text_color="#cc6600",
                 font=ctk.CTkFont(size=10, weight="bold")).pack(pady=(6, 2))

    # Barra de progresso — oculta inicialmente
    lbl_prog   = ctk.CTkLabel(win, text="", text_color="#555555",
                               font=ctk.CTkFont(size=10))
    barra_prog = ctk.CTkProgressBar(win, width=460)
    barra_prog.set(0)

    # Botões — sempre visíveis na parte inferior
    frame_bt = ctk.CTkFrame(win, fg_color="transparent")
    frame_bt.pack(pady=(10, 16))

    btn_sim = ctk.CTkButton(frame_bt, text="✔  Atualizar Agora",
                             fg_color="#28a745", hover_color="#1e7e34",
                             text_color="white", width=200, height=40,
                             font=ctk.CTkFont(size=13, weight="bold"))
    btn_nao = ctk.CTkButton(frame_bt, text="✖  Agora Nao",
                             fg_color="#6c757d", hover_color="#545b62",
                             text_color="white", width=150, height=40,
                             font=ctk.CTkFont(size=13))
    btn_sim.pack(side="left", padx=12)
    btn_nao.pack(side="left", padx=12)

    # Ações
    def recusar() -> None:
        win.destroy()
        if btn_flutuante is not None:
            try:
                btn_flutuante.place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-8)
            except Exception:
                pass

    def aceitar() -> None:
        url = release.get("download_url")
        if not url:
            messagebox.showerror("Erro",
                "Arquivo de atualizacao nao encontrado na release.\n"
                "Verifique se 'update.zip' foi anexado no GitHub.",
                parent=win)
            return

        btn_sim.configure(state="disabled", text="Atualizando...")
        btn_nao.configure(state="disabled")
        lbl_prog.pack(pady=(2, 0))
        barra_prog.pack(padx=20, pady=(2, 0))
        barra_prog.start()

        def _status(msg: str) -> None:
            try:
                win.after(0, lambda m=msg: lbl_prog.configure(text=m))
            except Exception:
                pass

        def _fazer() -> None:
            sucesso, msg = aplicar_atualizacao(url, versao_nova,
                                                callback_status=_status)
            win.after(0, lambda: _pos_atualizar(sucesso, msg))

        def _pos_atualizar(sucesso: bool, msg: str) -> None:
            barra_prog.stop()
            barra_prog.set(1.0 if sucesso else 0)
            if sucesso:
                win.destroy()
                if btn_flutuante is not None:
                    try:
                        btn_flutuante.place_forget()
                    except Exception:
                        pass
                _perguntar_reinicio(root_tk, versao_nova)
            else:
                lbl_prog.pack_forget()
                barra_prog.pack_forget()
                btn_sim.configure(state="normal", text="✔  Tentar Novamente")
                btn_nao.configure(state="normal")
                messagebox.showerror("Erro na atualizacao",
                    f"Falha ao atualizar:\n\n{msg}", parent=win)

        threading.Thread(target=_fazer, daemon=True).start()

    btn_sim.configure(command=aceitar)
    btn_nao.configure(command=recusar)
    win.bind("<Escape>", lambda e: recusar())
    win.protocol("WM_DELETE_WINDOW", recusar)


# ═════════════════════════════════════════════════════════════════════
#  PONTO DE ENTRADA PÚBLICO
# ═════════════════════════════════════════════════════════════════════

def verificar_atualizacao_em_background(root_tk: ctk.CTk) -> None:
    """
    Verifica atualizações em background sem travar a interface.
    Chamar logo após criar a janela principal (root_tk / app).

    Se houver atualização disponível:
      - Exibe popup perguntando se quer atualizar
      - Se recusar, exibe botão flutuante no canto inferior direito
    """
    def _verificar() -> None:
        try:
            versao_local = ler_versao_atual()
            _registrar_log(f"Verificando atualizacoes... versao local: {versao_local}")
            tem, release = ha_atualizacao_disponivel()
            if tem and release:
                _registrar_log(f"Atualizacao disponivel: {release['tag']} > {versao_local}")
                root_tk.after(500, lambda: _exibir_notificacao(release))
            else:
                _registrar_log(f"Sistema atualizado. Nenhuma versao nova encontrada.")
        except Exception as e:
            _registrar_log(f"Erro ao verificar atualizacao: {e}")

    def _exibir_notificacao(release: dict) -> None:
        try:
            btn_flutuante = _criar_botao_flutuante(root_tk, release)
            _mostrar_popup_atualizacao(
                root_tk, release, btn_flutuante=btn_flutuante
            )
        except Exception as e:
            _registrar_log(f"Erro ao exibir notificacao: {e}")

    t = threading.Thread(target=_verificar, daemon=True, name="UpdateChecker")
    t.start()
