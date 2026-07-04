"""
clientes.py — Módulo de Clientes e Vendas a Prazo
===================================================
Funcionalidades:
  - Cadastro/edição de clientes
  - Listagem com busca em tempo real
  - Visualização de compras a prazo por cliente
  - Botão "Ver Venda" em cada linha para visualizar itens
  - Pagamento de dívidas (múltiplas formas, duplo Enter, dívida restante)
  - Botão "Cobrar": gera nota sem quitar (PDF ou impressa)
  - Gerar nota de pagamento de vendas já pagas
  - Auto-abrir seleção de cliente ao digitar em "A Prazo" na finalização
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from datetime import datetime
import unicodedata
import os
import tempfile
import subprocess

DB_CONFIG = {
    "host": "localhost",
    "user": "pdv",
    "password": "1234",
    "database": "sistema_vendas"
}

COR_PRIMARIA   = "#FFA500"
COR_SECUNDARIA = "#FFD700"

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def normalizar(texto):
    texto = str(texto).upper()
    return unicodedata.normalize("NFD", texto).encode("ascii","ignore").decode("ascii")

def _colunas_existentes(cur, tabela):
    cur.execute("""
        SELECT COLUMN_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
    """, (DB_CONFIG["database"], tabela))
    return {r[0] for r in cur.fetchall()}


# ══════════════════════════════════════════════════════════════════════
#  GARANTIR TABELAS
# ══════════════════════════════════════════════════════════════════════

def garantir_tabelas():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id        INT AUTO_INCREMENT PRIMARY KEY,
                nome      VARCHAR(120) NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        todas_colunas = [
            ("ativo",          "BOOLEAN       DEFAULT TRUE"),
            ("telefone",       "VARCHAR(30)   DEFAULT ''"),
            ("cpf",            "VARCHAR(20)   DEFAULT NULL"),
            ("email",          "VARCHAR(100)  DEFAULT NULL"),
            ("endereco",       "TEXT          DEFAULT NULL"),
            ("limite_credito", "DECIMAL(12,2) DEFAULT 0.00"),
        ]
        cols_atuais = _colunas_existentes(cur, "clientes")
        for col, definicao in todas_colunas:
            if col not in cols_atuais:
                cur.execute(f"ALTER TABLE clientes ADD COLUMN {col} {definicao}")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS vendas_prazo (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                cliente_id  INT NOT NULL,
                venda_id    INT NOT NULL,
                valor_total DECIMAL(12,2) NOT NULL,
                valor_pago  DECIMAL(12,2) DEFAULT 0.00,
                status      ENUM('aberto','pago','parcial') DEFAULT 'aberto',
                criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cliente_id) REFERENCES clientes(id),
                FOREIGN KEY (venda_id)   REFERENCES vendas(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pagamentos_prazo (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                venda_prazo_id  INT NOT NULL,
                valor           DECIMAL(12,2) NOT NULL,
                forma_pagamento VARCHAR(50) DEFAULT 'Dinheiro',
                troco           DECIMAL(12,2) DEFAULT 0.00,
                data_pagamento  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (venda_prazo_id) REFERENCES vendas_prazo(id) ON DELETE CASCADE
            )
        """)
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f"[clientes] Erro ao criar/atualizar tabelas: {e}")


# ══════════════════════════════════════════════════════════════════════
#  IMPRESSÃO E PDF
# ══════════════════════════════════════════════════════════════════════

COLS = 48

def _l(c="-"): return c * COLS

def _c2(e, d, w=COLS):
    sp = w - len(e) - len(d)
    return e + " " * max(sp, 1) + d

def _txt(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii","ignore").decode("ascii")
    return s.encode("cp850", errors="replace")

def _centro(texto):
    t = unicodedata.normalize("NFD", str(texto)).encode("ascii","ignore").decode("ascii")
    return t.center(COLS)

def _cabecalho_conta(buf, cliente_nome, forma):
    ESC=b'\x1b'; GS=b'\x1d'
    INIT=ESC+b'@'
    BOLD_ON=ESC+b'E\x01'; BOLD_OFF=ESC+b'E\x00'
    AC=ESC+b'a\x01'; AL=ESC+b'a\x00'
    DBL_ON=GS+b'!\x11'; DBL_OFF=GS+b'!\x00'
    now = datetime.now()
    buf += INIT
    buf += AC + DBL_ON + BOLD_ON + _txt("Mercearia Godoi\n") + DBL_OFF + BOLD_OFF
    buf += AC
    buf += _txt(_centro("Rua: Antonia Rosa de Melo Bolanho, 40") + "\n")
    buf += _txt(_centro("Jd. Nova Biritiba - Biritiba Mirim - SP") + "\n")
    buf += _txt(_centro("Telefone: (11) 97147-4599") + "\n")
    buf += _txt(_l() + "\n")
    buf += BOLD_ON + _txt(_centro("RECIBO DE PAGAMENTO") + "\n") + BOLD_OFF
    buf += _txt(_l() + "\n")
    buf += AL
    buf += _txt(f"Cliente : {cliente_nome[:38]}\n")
    buf += _txt(f"Data    : {now.strftime('%d/%m/%Y %H:%M:%S')}\n")
    buf += _txt(f"Forma   : {forma[:38]}\n")
    buf += _txt(_l() + "\n")
    return buf, ESC+b'E\x01', ESC+b'E\x00', AL, AC, now

def _cabecalho_cobranca(buf, cliente_nome):
    ESC=b'\x1b'; GS=b'\x1d'
    INIT=ESC+b'@'
    BOLD_ON=ESC+b'E\x01'; BOLD_OFF=ESC+b'E\x00'
    AC=ESC+b'a\x01'; AL=ESC+b'a\x00'
    DBL_ON=GS+b'!\x11'; DBL_OFF=GS+b'!\x00'
    now = datetime.now()
    buf += INIT
    buf += AC + DBL_ON + BOLD_ON + _txt("Mercearia Godoi\n") + DBL_OFF + BOLD_OFF
    buf += AC
    buf += _txt(_centro("Rua: Antonia Rosa de Melo Bolanho, 40") + "\n")
    buf += _txt(_centro("Jd. Nova Biritiba - Biritiba Mirim - SP") + "\n")
    buf += _txt(_centro("Telefone: (11) 97147-4599") + "\n")
    buf += _txt(_l() + "\n")
    buf += BOLD_ON + _txt(_centro("NOTA DE COBRANCA") + "\n") + BOLD_OFF
    buf += _txt(_l() + "\n")
    buf += AL
    buf += _txt(f"Cliente : {cliente_nome[:38]}\n")
    buf += _txt(f"Data    : {now.strftime('%d/%m/%Y %H:%M:%S')}\n")
    buf += _txt(_l() + "\n")
    return buf, ESC+b'E\x01', ESC+b'E\x00', AL, AC, now

def _rodape_conta(buf, total_conta, total_recebido, troco, restante, BOLD_ON, BOLD_OFF):
    ESC=b'\x1b'; GS=b'\x1d'
    CUT=GS+b'V\x41\x03'; AC=ESC+b'a\x01'
    buf += _txt(_l() + "\n")
    buf += BOLD_ON + _txt(_c2("TOTAL DA CONTA",  f"R$ {total_conta:.2f}") + "\n") + BOLD_OFF
    buf += BOLD_ON + _txt(_c2("VALOR RECEBIDO",  f"R$ {total_recebido:.2f}") + "\n") + BOLD_OFF
    buf += BOLD_ON + _txt(_c2("TROCO",            f"R$ {troco:.2f}") + "\n") + BOLD_OFF
    if restante > 0.001:
        buf += BOLD_ON + _txt(_c2("DIVIDA RESTANTE", f"R$ {restante:.2f}") + "\n") + BOLD_OFF
    buf += _txt(_l() + "\n")
    buf += AC + _txt("Obrigado pela preferencia!\n")
    buf += _txt(_l("=") + "\n")
    buf += b'\n' * 4 + CUT
    return buf

def _rodape_cobranca(buf, total_cobrar, BOLD_ON, BOLD_OFF):
    ESC=b'\x1b'; GS=b'\x1d'
    CUT=GS+b'V\x41\x03'; AC=ESC+b'a\x01'
    buf += _txt(_l() + "\n")
    buf += BOLD_ON + _txt(_c2("TOTAL A PAGAR", f"R$ {total_cobrar:.2f}") + "\n") + BOLD_OFF
    buf += _txt(_l() + "\n")
    buf += AC + _txt("Mercearia Godoi - Aguardamos seu pagamento\n")
    buf += _txt(_l("=") + "\n")
    buf += b'\n' * 4 + CUT
    return buf

def _montar_nota_resumida(cliente_nome, a_pagar, total_conta, total_recebido, troco, restante, forma):
    buf = bytearray()
    buf, BOLD_ON, BOLD_OFF, AL, AC, now = _cabecalho_conta(buf, cliente_nome, forma)
    buf += BOLD_ON + _txt(_c2("VENDA  DATA/HORA", "VALOR") + "\n") + BOLD_OFF
    buf += _txt(_l() + "\n")
    for d in a_pagar:
        vp_id, v_id, total, pago_ant, saldo, criado, status = d
        try: dt_s = criado.strftime("%d/%m/%Y %H:%M") if isinstance(criado, datetime) else str(criado)[:16]
        except: dt_s = str(criado)[:16]
        linha = f"#{v_id:<5} {dt_s}"
        buf += _txt(_c2(linha, f"R$ {float(saldo):.2f}") + "\n")
    buf = _rodape_conta(buf, total_conta, total_recebido, troco, restante, BOLD_ON, BOLD_OFF)
    return bytes(buf)

def _montar_nota_detalhada(cliente_nome, a_pagar, total_conta, total_recebido, troco, restante, forma):
    buf = bytearray()
    buf, BOLD_ON, BOLD_OFF, AL, AC, now = _cabecalho_conta(buf, cliente_nome, forma)
    for d in a_pagar:
        vp_id, v_id, total, pago_ant, saldo, criado, status = d
        try: dt_s = criado.strftime("%d/%m/%Y %H:%M") if isinstance(criado, datetime) else str(criado)[:16]
        except: dt_s = str(criado)[:16]
        buf += BOLD_ON + _txt(f"Venda #{v_id}  {dt_s}\n") + BOLD_OFF
        buf += _txt(_l("-") + "\n")
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                SELECT p.nome, iv.quantidade, iv.preco_unitario, iv.subtotal
                FROM itens_venda iv LEFT JOIN produtos p ON p.id=iv.produto_id
                WHERE iv.venda_id=%s ORDER BY iv.id
            """, (v_id,))
            itens = cur.fetchall(); cur.close(); conn.close()
        except: itens = []
        for it in itens:
            nome_p = (it[0] or "?")[:COLS]
            try: qtd_f = float(it[1])
            except: qtd_f = 0.0
            try: pu = float(it[2])
            except: pu = 0.0
            try: sub = float(it[3])
            except: sub = qtd_f*pu
            qtd_s = f"{qtd_f:.3f}".rstrip("0").rstrip(".") if not qtd_f.is_integer() else str(int(qtd_f))
            buf += _txt(nome_p + "\n")
            buf += _txt(f"  {qtd_s} x{pu:>7.2f} ={sub:>8.2f}\n")
        buf += _txt(_c2(f"  Total venda #{v_id}", f"R$ {float(saldo):.2f}") + "\n")
        buf += _txt(_l() + "\n")
    buf = _rodape_conta(buf, total_conta, total_recebido, troco, restante, BOLD_ON, BOLD_OFF)
    return bytes(buf)

def _montar_cobranca_resumida(cliente_nome, a_cobrar, total_cobrar):
    buf = bytearray()
    buf, BOLD_ON, BOLD_OFF, AL, AC, now = _cabecalho_cobranca(buf, cliente_nome)
    buf += BOLD_ON + _txt(_c2("VENDA  DATA/HORA", "SALDO") + "\n") + BOLD_OFF
    buf += _txt(_l() + "\n")
    for d in a_cobrar:
        vp_id, v_id, total, pago_ant, saldo, criado, status = d
        try: dt_s = criado.strftime("%d/%m/%Y %H:%M") if isinstance(criado, datetime) else str(criado)[:16]
        except: dt_s = str(criado)[:16]
        buf += _txt(_c2(f"#{v_id:<5} {dt_s}", f"R$ {float(saldo):.2f}") + "\n")
    buf = _rodape_cobranca(buf, total_cobrar, BOLD_ON, BOLD_OFF)
    return bytes(buf)

def _montar_cobranca_detalhada(cliente_nome, a_cobrar, total_cobrar):
    buf = bytearray()
    buf, BOLD_ON, BOLD_OFF, AL, AC, now = _cabecalho_cobranca(buf, cliente_nome)
    for d in a_cobrar:
        vp_id, v_id, total, pago_ant, saldo, criado, status = d
        try: dt_s = criado.strftime("%d/%m/%Y %H:%M") if isinstance(criado, datetime) else str(criado)[:16]
        except: dt_s = str(criado)[:16]
        buf += BOLD_ON + _txt(f"Venda #{v_id}  {dt_s}\n") + BOLD_OFF
        buf += _txt(_l("-") + "\n")
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                SELECT p.nome, iv.quantidade, iv.preco_unitario, iv.subtotal
                FROM itens_venda iv LEFT JOIN produtos p ON p.id=iv.produto_id
                WHERE iv.venda_id=%s ORDER BY iv.id
            """, (v_id,))
            itens = cur.fetchall(); cur.close(); conn.close()
        except: itens = []
        for it in itens:
            nome_p = (it[0] or "?")[:COLS]
            try: qtd_f = float(it[1])
            except: qtd_f = 0.0
            try: pu = float(it[2])
            except: pu = 0.0
            try: sub = float(it[3])
            except: sub = qtd_f*pu
            qtd_s = f"{qtd_f:.3f}".rstrip("0").rstrip(".") if not qtd_f.is_integer() else str(int(qtd_f))
            buf += _txt(nome_p + "\n")
            buf += _txt(f"  {qtd_s} x{pu:>7.2f} ={sub:>8.2f}\n")
        buf += _txt(_c2(f"  Saldo venda #{v_id}", f"R$ {float(saldo):.2f}") + "\n")
        buf += _txt(_l() + "\n")
    buf = _rodape_cobranca(buf, total_cobrar, BOLD_ON, BOLD_OFF)
    return bytes(buf)

def _imprimir_bytes(dados_bytes):
    try:
        import win32print
    except ImportError:
        messagebox.showwarning("Impressao", "pywin32 nao instalado.\npip install pywin32"); return
    NOME_IMP = "EPSON TM-T20X"
    try:
        imps = [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        nome_imp = next((p for p in imps if NOME_IMP.upper() in p.upper()),
                        win32print.GetDefaultPrinter())
        hp = win32print.OpenPrinter(nome_imp)
        try:
            hj = win32print.StartDocPrinter(hp, 1, ("Nota Conta", None, "RAW"))
            try:
                win32print.StartPagePrinter(hp)
                win32print.WritePrinter(hp, dados_bytes)
                win32print.EndPagePrinter(hp)
            finally: win32print.EndDocPrinter(hp)
        finally: win32print.ClosePrinter(hp)
    except Exception as e:
        messagebox.showwarning("Impressao", f"Erro ao imprimir:\n{e}")

def _gerar_pdf(linhas_texto, nome_arquivo="nota"):
    try:
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        try:
            import subprocess, sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            from reportlab.pdfgen import canvas as rl_canvas
        except Exception:
            messagebox.showwarning("PDF", "Instale reportlab:\npip install reportlab"); return
    FONT="Courier"; FS=7; LH=FS+2; W=226.77; M=10
    altura = max(LH*(len(linhas_texto)+6)+M*2, 200)
    caminho = os.path.join(tempfile.gettempdir(),
                           f"{nome_arquivo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    c = rl_canvas.Canvas(caminho, pagesize=(W, altura))
    c.setFont(FONT, FS)
    y = altura - M - LH
    for ln in linhas_texto:
        ln_s = unicodedata.normalize("NFD", str(ln)).encode("ascii","ignore").decode("ascii")
        c.drawString(M, y, ln_s[:COLS])
        y -= LH
        if y < M:
            c.showPage(); c.setFont(FONT, FS); y = altura - M - LH
    c.save()
    try: os.startfile(caminho)
    except: subprocess.Popen(["start", caminho], shell=True)


def _centro_txt(texto):
    t = unicodedata.normalize("NFD", str(texto)).encode("ascii","ignore").decode("ascii")
    return t.center(COLS)


# ── Funções que montam listas de strings puras (sem ESC/POS) para PDF ──

def _montar_linhas_cabecalho_conta(cliente_nome, forma):
    now = datetime.now()
    linhas = [
        _centro_txt("Mercearia Godoi"),
        _centro_txt("Rua: Antonia Rosa de Melo Bolanho, 40"),
        _centro_txt("Jd. Nova Biritiba - Biritiba Mirim - SP"),
        _centro_txt("Telefone: (11) 97147-4599"),
        _l(), _centro_txt("RECIBO DE PAGAMENTO"), _l(),
        f"Cliente : {cliente_nome[:38]}",
        f"Data    : {now.strftime('%d/%m/%Y %H:%M:%S')}",
        f"Forma   : {forma[:38]}", _l(),
    ]
    return linhas


def _montar_linhas_cabecalho_cobranca(cliente_nome):
    now = datetime.now()
    linhas = [
        _centro_txt("Mercearia Godoi"),
        _centro_txt("Rua: Antonia Rosa de Melo Bolanho, 40"),
        _centro_txt("Jd. Nova Biritiba - Biritiba Mirim - SP"),
        _centro_txt("Telefone: (11) 97147-4599"),
        _l(), _centro_txt("NOTA DE COBRANCA"), _l(),
        f"Cliente : {cliente_nome[:38]}",
        f"Data    : {now.strftime('%d/%m/%Y %H:%M:%S')}",
        _l(),
    ]
    return linhas


def _montar_linhas_resumida(cliente_nome, a_pagar, total_conta,
                             total_recebido, troco, restante, forma):
    linhas = _montar_linhas_cabecalho_conta(cliente_nome, forma)
    linhas += [_c2("VENDA  DATA/HORA", "VALOR"), _l()]
    for d in a_pagar:
        vp_id, v_id, total, pago_ant, saldo, criado, status = d
        try: dt_s = criado.strftime("%d/%m/%Y %H:%M") if isinstance(criado, datetime) else str(criado)[:16]
        except: dt_s = str(criado)[:16]
        linhas.append(_c2(f"#{v_id:<5} {dt_s}", f"R$ {float(saldo):.2f}"))
    linhas += [
        _l(),
        _c2("TOTAL DA CONTA",  f"R$ {total_conta:.2f}"),
        _c2("VALOR RECEBIDO",  f"R$ {total_recebido:.2f}"),
        _c2("TROCO",           f"R$ {troco:.2f}"),
    ]
    if restante > 0.001:
        linhas.append(_c2("DIVIDA RESTANTE", f"R$ {restante:.2f}"))
    linhas += [_l(), _centro_txt("Obrigado pela preferencia!"), _l("=")]
    return linhas


def _montar_linhas_detalhada(cliente_nome, a_pagar, total_conta,
                              total_recebido, troco, restante, forma):
    linhas = _montar_linhas_cabecalho_conta(cliente_nome, forma)
    for d in a_pagar:
        vp_id, v_id, total, pago_ant, saldo, criado, status = d
        try: dt_s = criado.strftime("%d/%m/%Y %H:%M") if isinstance(criado, datetime) else str(criado)[:16]
        except: dt_s = str(criado)[:16]
        linhas += [f"Venda #{v_id}  {dt_s}", _l("-")]
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""SELECT p.nome, iv.quantidade, iv.preco_unitario, iv.subtotal
                FROM itens_venda iv LEFT JOIN produtos p ON p.id=iv.produto_id
                WHERE iv.venda_id=%s ORDER BY iv.id""", (v_id,))
            itens = cur.fetchall(); cur.close(); conn.close()
        except: itens = []
        for it in itens:
            np_ = unicodedata.normalize("NFD", str(it[0] or "?")).encode("ascii","ignore").decode("ascii")[:COLS]
            try: qf = float(it[1])
            except: qf = 0.0
            try: pu = float(it[2])
            except: pu = 0.0
            try: sb = float(it[3])
            except: sb = qf*pu
            qs = f"{qf:.3f}".rstrip("0").rstrip(".") if not qf.is_integer() else str(int(qf))
            linhas += [np_, f"  {qs} x{pu:>7.2f} ={sb:>8.2f}"]
        linhas += [_c2(f"  Total venda #{v_id}", f"R$ {float(saldo):.2f}"), _l()]
    linhas += [
        _c2("TOTAL DA CONTA",  f"R$ {total_conta:.2f}"),
        _c2("VALOR RECEBIDO",  f"R$ {total_recebido:.2f}"),
        _c2("TROCO",           f"R$ {troco:.2f}"),
    ]
    if restante > 0.001:
        linhas.append(_c2("DIVIDA RESTANTE", f"R$ {restante:.2f}"))
    linhas += [_l(), _centro_txt("Obrigado pela preferencia!"), _l("=")]
    return linhas


def _montar_linhas_cobranca_resumida(cliente_nome, a_cobrar, total_cobrar):
    linhas = _montar_linhas_cabecalho_cobranca(cliente_nome)
    linhas += [_c2("VENDA  DATA/HORA", "SALDO"), _l()]
    for d in a_cobrar:
        vp_id, v_id, total, pago_ant, saldo, criado, status = d
        try: dt_s = criado.strftime("%d/%m/%Y %H:%M") if isinstance(criado, datetime) else str(criado)[:16]
        except: dt_s = str(criado)[:16]
        linhas.append(_c2(f"#{v_id:<5} {dt_s}", f"R$ {float(saldo):.2f}"))
    linhas += [_l(), _c2("TOTAL A PAGAR", f"R$ {total_cobrar:.2f}"),
               _l(), _centro_txt("Mercearia Godoi - Aguardamos seu pagamento"), _l("=")]
    return linhas


def _montar_linhas_cobranca_detalhada(cliente_nome, a_cobrar, total_cobrar):
    linhas = _montar_linhas_cabecalho_cobranca(cliente_nome)
    for d in a_cobrar:
        vp_id, v_id, total, pago_ant, saldo, criado, status = d
        try: dt_s = criado.strftime("%d/%m/%Y %H:%M") if isinstance(criado, datetime) else str(criado)[:16]
        except: dt_s = str(criado)[:16]
        linhas += [f"Venda #{v_id}  {dt_s}", _l("-")]
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""SELECT p.nome, iv.quantidade, iv.preco_unitario, iv.subtotal
                FROM itens_venda iv LEFT JOIN produtos p ON p.id=iv.produto_id
                WHERE iv.venda_id=%s ORDER BY iv.id""", (v_id,))
            itens = cur.fetchall(); cur.close(); conn.close()
        except: itens = []
        for it in itens:
            np_ = unicodedata.normalize("NFD", str(it[0] or "?")).encode("ascii","ignore").decode("ascii")[:COLS]
            try: qf = float(it[1])
            except: qf = 0.0
            try: pu = float(it[2])
            except: pu = 0.0
            try: sb = float(it[3])
            except: sb = qf*pu
            qs = f"{qf:.3f}".rstrip("0").rstrip(".") if not qf.is_integer() else str(int(qf))
            linhas += [np_, f"  {qs} x{pu:>7.2f} ={sb:>8.2f}"]
        linhas += [_c2(f"  Saldo venda #{v_id}", f"R$ {float(saldo):.2f}"), _l()]
    linhas += [_c2("TOTAL A PAGAR", f"R$ {total_cobrar:.2f}"),
               _l(), _centro_txt("Mercearia Godoi - Aguardamos seu pagamento"), _l("=")]
    return linhas


# ══════════════════════════════════════════════════════════════════════
#  POPUP FORMATO: impressa ou PDF
# ══════════════════════════════════════════════════════════════════════

def _popup_formato_cobranca(parent_win, cliente_nome, a_cobrar, total_cobrar, tipo):
    win = ctk.CTkToplevel(parent_win)
    win.title("Formato da Nota")
    win.geometry("360x160")
    win.transient(parent_win); win.lift(); win.focus_force()
    win.after(100, win.grab_set); win.resizable(False, False)
    ctk.CTkLabel(win, text="Gerar nota de cobranca como:",
                 font=ctk.CTkFont(size=13)).pack(pady=(20,12))
    frame_bt = ctk.CTkFrame(win, fg_color="transparent"); frame_bt.pack()

    def fazer(formato):
        win.destroy()
        if tipo == "resumida":
            linhas = _montar_linhas_cobranca_resumida(cliente_nome, a_cobrar, total_cobrar)
            dados  = _montar_cobranca_resumida(cliente_nome, a_cobrar, total_cobrar)
        else:
            linhas = _montar_linhas_cobranca_detalhada(cliente_nome, a_cobrar, total_cobrar)
            dados  = _montar_cobranca_detalhada(cliente_nome, a_cobrar, total_cobrar)
        if formato == "impressa":
            _imprimir_bytes(dados)
        else:
            _gerar_pdf(linhas, nome_arquivo="cobranca")

    ctk.CTkButton(frame_bt, text="Impressa",  fg_color=COR_PRIMARIA, width=110,
                  command=lambda: fazer("impressa")).pack(side="left", padx=6)
    ctk.CTkButton(frame_bt, text="PDF",       fg_color="#2d89ef",   width=110,
                  command=lambda: fazer("pdf")).pack(side="left", padx=6)
    ctk.CTkButton(frame_bt, text="Cancelar",  fg_color="#6c757d",   width=100,
                  command=win.destroy).pack(side="left", padx=6)
    win.bind("<Escape>", lambda e: win.destroy())


# ══════════════════════════════════════════════════════════════════════
#  JANELAS DE AÇÃO
# ══════════════════════════════════════════════════════════════════════

def perguntar_e_imprimir_nota(parent_win, cliente_nome, a_pagar,
                               total_conta, total_recebido, troco, restante, forma):
    win = ctk.CTkToplevel(parent_win)
    win.title("Imprimir Nota")
    win.geometry("480x200")
    win.transient(parent_win); win.lift(); win.focus_force()
    win.after(100, win.grab_set); win.resizable(False, False)

    ctk.CTkLabel(win, text="Deseja imprimir nota do pagamento?",
                 font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(16,4))
    ctk.CTkLabel(win, text="Escolha o tipo e o formato:",
                 text_color="#888888").pack(pady=(0,10))

    frame_bt = ctk.CTkFrame(win, fg_color="transparent")
    frame_bt.pack()

    def impr(tipo, formato):
        win.destroy()
        if tipo == "resumida":
            linhas = _montar_linhas_resumida(cliente_nome, a_pagar, total_conta,
                                              total_recebido, troco, restante, forma)
            dados  = _montar_nota_resumida(cliente_nome, a_pagar, total_conta,
                                            total_recebido, troco, restante, forma)
        else:
            linhas = _montar_linhas_detalhada(cliente_nome, a_pagar, total_conta,
                                               total_recebido, troco, restante, forma)
            dados  = _montar_nota_detalhada(cliente_nome, a_pagar, total_conta,
                                             total_recebido, troco, restante, forma)
        if formato == "pdf":
            _gerar_pdf(linhas, nome_arquivo="recibo")
        else:
            _imprimir_bytes(dados)

    # Linha 1: Impressora
    ctk.CTkLabel(frame_bt, text="Impressora:", width=90, anchor="w").grid(row=0, column=0, padx=6, pady=4)
    ctk.CTkButton(frame_bt, text="Resumida",  fg_color="#2d89ef",    width=110,
                  command=lambda: impr("resumida","impressora")).grid(row=0, column=1, padx=4, pady=4)
    ctk.CTkButton(frame_bt, text="Detalhada", fg_color=COR_PRIMARIA, width=110,
                  command=lambda: impr("detalhada","impressora")).grid(row=0, column=2, padx=4, pady=4)

    # Linha 2: PDF
    ctk.CTkLabel(frame_bt, text="PDF:", width=90, anchor="w").grid(row=1, column=0, padx=6, pady=4)
    ctk.CTkButton(frame_bt, text="Resumida",  fg_color="#17a2b8",    width=110,
                  command=lambda: impr("resumida","pdf")).grid(row=1, column=1, padx=4, pady=4)
    ctk.CTkButton(frame_bt, text="Detalhada", fg_color="#138496",    width=110,
                  command=lambda: impr("detalhada","pdf")).grid(row=1, column=2, padx=4, pady=4)

    # Não imprimir
    ctk.CTkButton(frame_bt, text="Nao imprimir (ESC)", fg_color="#6c757d", width=240,
                  command=win.destroy).grid(row=2, column=0, columnspan=3, pady=(8,4))

    win.bind("<Return>", lambda e: impr("resumida","impressora"))
    win.bind("<Escape>", lambda e: win.destroy())


def abrir_cadastro_cliente(parent, cliente_id=None, on_salvo=None):
    parent_win = parent.winfo_toplevel()
    dados = {}
    if cliente_id:
        try:
            conn = get_connection(); cur = conn.cursor()
            cols = _colunas_existentes(cur, "clientes")
            sel = ", ".join([
                "nome",
                "telefone"       if "telefone"       in cols else "'' AS telefone",
                "cpf"            if "cpf"            in cols else "NULL AS cpf",
                "email"          if "email"          in cols else "NULL AS email",
                "endereco"       if "endereco"       in cols else "NULL AS endereco",
                "limite_credito" if "limite_credito" in cols else "0 AS limite_credito",
            ])
            cur.execute(f"SELECT {sel} FROM clientes WHERE id=%s", (cliente_id,))
            row = cur.fetchone(); cur.close(); conn.close()
            if row:
                dados = {"nome":row[0],"telefone":row[1] or "","cpf":row[2] or "",
                         "email":row[3] or "","endereco":row[4] or "","limite":float(row[5] or 0)}
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar cliente:\n{e}"); return

    win = ctk.CTkToplevel(parent_win)
    win.title("Editar Cliente" if cliente_id else "Novo Cliente")
    win.geometry("480x420"); win.transient(parent_win); win.lift(); win.focus_force()
    win.after(100, win.grab_set); win.resizable(False, False)
    ctk.CTkLabel(win, text="Editar Cliente" if cliente_id else "Novo Cliente",
                 font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(14,8), padx=16, anchor="w")

    def campo(label, obrigatorio=False):
        fr = ctk.CTkFrame(win, fg_color="transparent"); fr.pack(fill="x", padx=16, pady=3)
        ctk.CTkLabel(fr, text=label+(" *" if obrigatorio else ""), width=140, anchor="w").pack(side="left")
        ent = ctk.CTkEntry(fr, width=280); ent.pack(side="left"); return ent

    ent_nome=campo("Nome completo",True); ent_telefone=campo("Telefone",True)
    ent_cpf=campo("CPF"); ent_email=campo("E-mail")
    ent_endereco=campo("Endereco"); ent_limite=campo("Limite de credito (R$)")
    if dados:
        ent_nome.insert(0,dados.get("nome","")); ent_telefone.insert(0,dados.get("telefone",""))
        ent_cpf.insert(0,dados.get("cpf","")); ent_email.insert(0,dados.get("email",""))
        ent_endereco.insert(0,dados.get("endereco","")); ent_limite.insert(0,f"{dados.get('limite',0):.2f}")
    ctk.CTkLabel(win, text="* Campos obrigatorios", text_color="#888888",
                 font=ctk.CTkFont(size=10)).pack(anchor="w", padx=16, pady=(4,0))
    frame_bt = ctk.CTkFrame(win, fg_color="transparent"); frame_bt.pack(fill="x", padx=16, pady=(10,14))

    def salvar():
        nome=ent_nome.get().strip(); telefone=ent_telefone.get().strip()
        if not nome: messagebox.showwarning("Aviso","Nome e obrigatorio."); ent_nome.focus_set(); return
        if not telefone: messagebox.showwarning("Aviso","Telefone e obrigatorio."); ent_telefone.focus_set(); return
        cpf=ent_cpf.get().strip() or None; email=ent_email.get().strip() or None
        endereco=ent_endereco.get().strip() or None
        try: limite=float(ent_limite.get().strip().replace(",",".") or "0")
        except: limite=0.0
        try:
            conn=get_connection(); cur=conn.cursor()
            cols=_colunas_existentes(cur,"clientes")
            if cliente_id:
                sets=["nome=%s","telefone=%s"]; vals=[nome,telefone]
                if "cpf"            in cols: sets.append("cpf=%s");            vals.append(cpf)
                if "email"          in cols: sets.append("email=%s");          vals.append(email)
                if "endereco"       in cols: sets.append("endereco=%s");       vals.append(endereco)
                if "limite_credito" in cols: sets.append("limite_credito=%s"); vals.append(limite)
                vals.append(cliente_id)
                cur.execute(f"UPDATE clientes SET {', '.join(sets)} WHERE id=%s", vals)
            else:
                c2=["nome","telefone"]; v2=[nome,telefone]
                if "cpf"            in cols: c2.append("cpf");            v2.append(cpf)
                if "email"          in cols: c2.append("email");          v2.append(email)
                if "endereco"       in cols: c2.append("endereco");       v2.append(endereco)
                if "limite_credito" in cols: c2.append("limite_credito"); v2.append(limite)
                ph=", ".join(["%s"]*len(v2))
                cur.execute(f"INSERT INTO clientes ({', '.join(c2)}) VALUES ({ph})", v2)
            conn.commit(); cur.close(); conn.close()
            messagebox.showinfo("Sucesso","Cliente salvo com sucesso!")
            win.destroy()
            if on_salvo: on_salvo()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar:\n{e}")

    ctk.CTkButton(frame_bt, text="Salvar", fg_color=COR_PRIMARIA, width=140, command=salvar).pack(side="left", padx=6)
    ctk.CTkButton(frame_bt, text="Cancelar", fg_color="#6c757d", width=120, command=win.destroy).pack(side="left", padx=6)
    win.bind("<Return>", lambda e: salvar()); win.bind("<Escape>", lambda e: win.destroy())
    ent_nome.focus_set()


def abrir_pagamento_prazo(parent, cliente_id, cliente_nome, on_pago=None):
    parent_win = parent.winfo_toplevel()
    try:
        conn=get_connection(); cur=conn.cursor()
        cur.execute("""
            SELECT vp.id, v.id, vp.valor_total, vp.valor_pago,
                   (vp.valor_total-vp.valor_pago) AS saldo, vp.criado_em, vp.status
            FROM vendas_prazo vp LEFT JOIN vendas v ON v.id=vp.venda_id
            WHERE vp.cliente_id=%s AND vp.status!='pago' ORDER BY vp.criado_em
        """, (cliente_id,))
        dividas=cur.fetchall(); cur.close(); conn.close()
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao buscar dividas:\n{e}"); return
    if not dividas:
        messagebox.showinfo("Sem dividas", f"{cliente_nome} nao possui dividas em aberto."); return

    total_devendo=sum(float(d[4]) for d in dividas)
    win=ctk.CTkToplevel(parent_win)
    win.title(f"Pagar Dividas — {cliente_nome}")
    win.geometry("680x620"); win.transient(parent_win); win.lift(); win.focus_force()
    win.after(100, win.grab_set)

    ctk.CTkLabel(win, text=f"Dividas de {cliente_nome}",
                 font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(12,4), padx=12, anchor="w")

    frame_tree=tk.Frame(win); frame_tree.pack(fill="both", expand=True, padx=12, pady=6)
    cols=("sel","venda","data","total","pago","saldo","status")
    tree=ttk.Treeview(frame_tree, columns=cols, show="headings", selectmode="none")
    tree.heading("sel",   text="");       tree.column("sel",   width=30, anchor="center")
    tree.heading("venda", text="Venda");  tree.column("venda", width=60, anchor="center")
    tree.heading("data",  text="Data");   tree.column("data",  width=130)
    tree.heading("total", text="Total");  tree.column("total", width=85, anchor="e")
    tree.heading("pago",  text="Pago");   tree.column("pago",  width=85, anchor="e")
    tree.heading("saldo", text="Saldo");  tree.column("saldo", width=85, anchor="e")
    tree.heading("status",text="Status"); tree.column("status",width=70, anchor="center")
    sb=ttk.Scrollbar(frame_tree, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set); sb.pack(side="right", fill="y"); tree.pack(fill="both", expand=True)
    tree.tag_configure("selecionado", background="#1a4a1a", foreground="#aaffaa")

    selecionados={}; iids_map={}
    for d in dividas:
        vp_id,v_id,total,pago,saldo,criado,status=d
        try: dt_s=criado.strftime("%d/%m/%Y %H:%M") if isinstance(criado,datetime) else str(criado)
        except: dt_s=str(criado)
        iid=tree.insert("",tk.END,values=("☐",v_id,dt_s,f"{float(total):.2f}",f"{float(pago):.2f}",f"{float(saldo):.2f}",status))
        selecionados[iid]=False; iids_map[iid]=d

    lbl_sel=ctk.CTkLabel(win, text=f"Total devendo: R$ {total_devendo:.2f}  |  Selecionado: R$ 0,00",
                          font=ctk.CTkFont(size=12,weight="bold"), text_color=COR_PRIMARIA)
    lbl_sel.pack(anchor="w", padx=14, pady=(0,2))

    def get_total_sel():
        return sum(float(iids_map[i][4]) for i,s in selecionados.items() if s)

    def atualizar_sel():
        ts=get_total_sel()
        lbl_sel.configure(text=f"Total devendo: R$ {total_devendo:.2f}  |  Selecionado: R$ {ts:.2f}")
        recalc_totais()

    def toggle(event):
        iid=tree.identify_row(event.y)
        if not iid: return
        selecionados[iid]=not selecionados[iid]
        vals=list(tree.item(iid)["values"]); vals[0]="✔" if selecionados[iid] else "☐"
        tree.item(iid, values=vals, tags=("selecionado",) if selecionados[iid] else ())
        atualizar_sel()
    tree.bind("<ButtonRelease-1>", toggle)

    def selecionar_todas():
        for iid in selecionados:
            selecionados[iid]=True
            vals=list(tree.item(iid)["values"]); vals[0]="✔"
            tree.item(iid, values=vals, tags=("selecionado",))
        atualizar_sel()

    # Múltiplas formas de pagamento
    FORMAS=["Dinheiro","PIX","Cartao Credito","Cartao Debito"]
    payment_entries=[]
    frame_pags_outer=ctk.CTkFrame(win); frame_pags_outer.pack(fill="x", padx=12, pady=(4,0))
    ctk.CTkLabel(frame_pags_outer, text="Formas de pagamento:",
                 font=ctk.CTkFont(size=12,weight="bold")).pack(anchor="w", padx=6, pady=(4,2))
    frame_pags=ctk.CTkFrame(frame_pags_outer); frame_pags.pack(fill="x", padx=6, pady=(0,4))

    def adicionar_linha(forma="Dinheiro", valor=""):
        row=ctk.CTkFrame(frame_pags, fg_color="transparent"); row.pack(fill="x", pady=2)
        combo=ctk.CTkComboBox(row, values=FORMAS, width=150); combo.set(forma); combo.pack(side="left", padx=(0,6))
        ctk.CTkLabel(row, text="R$").pack(side="left", padx=(0,2))
        ent=ctk.CTkEntry(row, width=110, placeholder_text="0,00")
        if valor: ent.insert(0, valor)
        ent.pack(side="left", padx=(0,4))
        idx=len(payment_entries)
        _ultimo_enter={"t":0.0}
        def on_enter(event, _e=ent, _i=idx):
            import time
            agora=time.time()
            if agora-_ultimo_enter["t"]<0.6:
                ts=get_total_sel()
                outros=sum(float(pe[1].get().strip().replace(",",".") or "0") for j,pe in enumerate(payment_entries) if j!=_i)
                rest=ts-outros
                if rest>0:
                    _e.delete(0,tk.END); _e.insert(0,f"{rest:.2f}"); recalc_totais()
                _ultimo_enter["t"]=0.0
            else:
                _ultimo_enter["t"]=agora
        ent.bind("<Return>", on_enter)
        ent.bind("<KeyRelease>", lambda e: recalc_totais())
        payment_entries.append((combo,ent))
        if idx>0:
            def remover(_r=row, _i=idx):
                payment_entries.pop(_i); _r.destroy(); recalc_totais()
            ctk.CTkButton(row, text="✕", width=28, height=28, fg_color="#d9534f", command=remover).pack(side="left", padx=2)

    adicionar_linha()
    ctk.CTkButton(frame_pags_outer, text="+ Adicionar forma", fg_color="#2d89ef", width=140,
                  command=lambda: adicionar_linha()).pack(anchor="w", padx=6, pady=(0,4))

    frame_totais=ctk.CTkFrame(win); frame_totais.pack(fill="x", padx=12, pady=(4,4))
    lbl_total_pago=ctk.CTkLabel(frame_totais, text="Total pago: R$ 0,00",
                                 font=ctk.CTkFont(size=12,weight="bold"))
    lbl_total_pago.pack(side="left", padx=(8,16))
    lbl_troco=ctk.CTkLabel(frame_totais, text="Troco: R$ 0,00",
                            font=ctk.CTkFont(size=12,weight="bold"), text_color="#28a745")
    lbl_troco.pack(side="left", padx=8)
    lbl_restante=ctk.CTkLabel(frame_totais, text="Divida restante: R$ 0,00",
                               font=ctk.CTkFont(size=12,weight="bold"), text_color="#ff6666")
    lbl_restante.pack(side="left", padx=8)

    def recalc_totais(event=None):
        ts=get_total_sel()
        recebido=sum(float(pe[1].get().strip().replace(",",".") or "0") for pe in payment_entries)
        troco=max(0.0, round(recebido-ts, 2))
        restante=max(0.0, round(ts-recebido, 2))
        lbl_total_pago.configure(text=f"Total pago: R$ {recebido:.2f}")
        lbl_troco.configure(text=f"Troco: R$ {troco:.2f}")
        lbl_restante.configure(text=f"Divida restante: R$ {restante:.2f}",
                               text_color="#ff6666" if restante>0 else "#28a745")

    def confirmar_pagamento():
        a_pagar=[iids_map[iid] for iid,sel in selecionados.items() if sel]
        if not a_pagar: messagebox.showwarning("Aviso","Selecione ao menos uma divida."); return
        ts=get_total_sel()
        recebido=sum(float(pe[1].get().strip().replace(",",".") or "0") for pe in payment_entries)
        troco=max(0.0, round(recebido-ts,2))
        restante=max(0.0, round(ts-recebido,2))
        if recebido<=0: messagebox.showerror("Aviso","Informe ao menos um valor."); return
        if restante>0:
            if not messagebox.askyesno("Pagamento parcial",
                f"Divida restante: R$ {restante:.2f}\nRegistrar como pagamento parcial?"): return
        formas_desc=", ".join(
            f"{pe[0].get()} R${float(pe[1].get().strip().replace(',','.') or 0):.2f}"
            for pe in payment_entries if float(pe[1].get().strip().replace(",",".") or "0")>0)
        try:
            conn=get_connection(); cur=conn.cursor(); conn.start_transaction()
            rec_rest=recebido
            for d in a_pagar:
                vp_id,v_id,total,pago_ant,saldo,criado,status=d
                pagar_este=min(rec_rest,float(saldo))
                novo_pago=float(pago_ant)+pagar_este
                rec_rest=max(0.0,rec_rest-float(saldo))
                novo_status="pago" if novo_pago>=float(total)-0.01 else "parcial"
                cur.execute("UPDATE vendas_prazo SET valor_pago=%s, status=%s WHERE id=%s",
                            (novo_pago,novo_status,vp_id))
                for pe in payment_entries:
                    vf=float(pe[1].get().strip().replace(",",".") or "0")
                    if vf<=0: continue
                    cur.execute("INSERT INTO pagamentos_prazo (venda_prazo_id,valor,forma_pagamento,troco) VALUES(%s,%s,%s,%s)",
                                (vp_id,vf,pe[0].get(),troco))
            conn.commit(); cur.close(); conn.close()
            messagebox.showinfo("Sucesso", f"Pagamento registrado!\nRecebido: R$ {recebido:.2f}\nTroco: R$ {troco:.2f}\nRestante: R$ {restante:.2f}")
            win.destroy()
            perguntar_e_imprimir_nota(parent_win, cliente_nome, a_pagar, ts, recebido, troco, restante, formas_desc)
            if on_pago: on_pago()
        except Exception as e:
            try: conn.rollback()
            except: pass
            messagebox.showerror("Erro", f"Falha:\n{e}")

    frame_bt=ctk.CTkFrame(win, fg_color="transparent"); frame_bt.pack(fill="x", padx=12, pady=(4,12))
    ctk.CTkButton(frame_bt, text="Selecionar Todas", fg_color="#2d89ef", command=selecionar_todas).pack(side="left", padx=6)
    ctk.CTkButton(frame_bt, text="✔ Confirmar Pagamento", fg_color="#28a745", command=confirmar_pagamento).pack(side="right", padx=6)
    ctk.CTkButton(frame_bt, text="Cancelar", fg_color="#6c757d", command=win.destroy).pack(side="right", padx=6)
    win.bind("<Escape>", lambda e: win.destroy())


def abrir_gerar_nota(parent, cliente_id, cliente_nome):
    parent_win=parent.winfo_toplevel()
    try:
        conn=get_connection(); cur=conn.cursor()
        cur.execute("""
            SELECT vp.id, v.id, vp.valor_total, vp.valor_pago,
                   vp.valor_total, vp.criado_em, vp.status
            FROM vendas_prazo vp LEFT JOIN vendas v ON v.id=vp.venda_id
            WHERE vp.cliente_id=%s AND vp.status='pago' ORDER BY vp.criado_em DESC
        """, (cliente_id,))
        vendas_pagas=cur.fetchall(); cur.close(); conn.close()
    except Exception as e:
        messagebox.showerror("Erro", f"Falha:\n{e}"); return
    if not vendas_pagas:
        messagebox.showinfo("Sem vendas", f"{cliente_nome} nao possui vendas pagas."); return

    win=ctk.CTkToplevel(parent_win)
    win.title(f"Gerar Nota — {cliente_nome}")
    win.geometry("640x460"); win.transient(parent_win); win.lift(); win.focus_force()
    win.after(100, win.grab_set)
    ctk.CTkLabel(win, text=f"Selecione as vendas — {cliente_nome}",
                 font=ctk.CTkFont(size=13,weight="bold")).pack(pady=(12,6), padx=12, anchor="w")

    frame_tree=tk.Frame(win); frame_tree.pack(fill="both", expand=True, padx=12, pady=6)
    cols=("sel","venda","data","total","status")
    tree=ttk.Treeview(frame_tree, columns=cols, show="headings", selectmode="none")
    tree.heading("sel",   text="");       tree.column("sel",   width=32,  anchor="center")
    tree.heading("venda", text="Venda");  tree.column("venda", width=70,  anchor="center")
    tree.heading("data",  text="Data");   tree.column("data",  width=160)
    tree.heading("total", text="Total");  tree.column("total", width=100, anchor="e")
    tree.heading("status",text="Status"); tree.column("status",width=80,  anchor="center")
    sb=ttk.Scrollbar(frame_tree, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set); sb.pack(side="right", fill="y"); tree.pack(fill="both", expand=True)
    tree.tag_configure("selecionado", background="#1a4a1a", foreground="#aaffaa")

    selecionados={}; iids_map={}
    for d in vendas_pagas:
        vp_id,v_id,total,pago,saldo_orig,criado,status=d
        try: dt_s=criado.strftime("%d/%m/%Y %H:%M") if isinstance(criado,datetime) else str(criado)[:16]
        except: dt_s=str(criado)[:16]
        iid=tree.insert("",tk.END,values=("☐",v_id,dt_s,f"R$ {float(total):.2f}",status))
        selecionados[iid]=False; iids_map[iid]=d

    def toggle(event):
        iid=tree.identify_row(event.y)
        if not iid: return
        selecionados[iid]=not selecionados[iid]
        vals=list(tree.item(iid)["values"]); vals[0]="✔" if selecionados[iid] else "☐"
        tree.item(iid, values=vals, tags=("selecionado",) if selecionados[iid] else ())
    tree.bind("<ButtonRelease-1>", toggle)

    def sel_todas():
        for iid in selecionados:
            selecionados[iid]=True
            vals=list(tree.item(iid)["values"]); vals[0]="✔"
            tree.item(iid, values=vals, tags=("selecionado",))

    def gerar(tipo, formato):
        a_imprimir=[iids_map[iid] for iid,sel in selecionados.items() if sel]
        if not a_imprimir: messagebox.showwarning("Aviso","Selecione ao menos uma venda."); return
        total_conta=sum(float(d[2]) for d in a_imprimir)
        total_pago=sum(float(d[3]) for d in a_imprimir)
        win.destroy()
        if tipo=="resumida":
            linhas=_montar_linhas_resumida(cliente_nome,a_imprimir,total_conta,total_pago,0.0,0.0,"Reimpressao")
            dados=_montar_nota_resumida(cliente_nome,a_imprimir,total_conta,total_pago,0.0,0.0,"Reimpressao")
        else:
            linhas=_montar_linhas_detalhada(cliente_nome,a_imprimir,total_conta,total_pago,0.0,0.0,"Reimpressao")
            dados=_montar_nota_detalhada(cliente_nome,a_imprimir,total_conta,total_pago,0.0,0.0,"Reimpressao")
        if formato=="pdf":
            _gerar_pdf(linhas, nome_arquivo="nota_pagamento")
        else:
            _imprimir_bytes(dados)

    frame_bt=ctk.CTkFrame(win, fg_color="transparent"); frame_bt.pack(fill="x", padx=12, pady=(0,12))
    ctk.CTkButton(frame_bt, text="Selecionar Todas", fg_color="#2d89ef", command=sel_todas).pack(side="left", padx=6)
    ctk.CTkButton(frame_bt, text="Impr. Resumida",   fg_color="#2d89ef",    width=120,
                  command=lambda: gerar("resumida","impressora")).pack(side="right", padx=4)
    ctk.CTkButton(frame_bt, text="Impr. Detalhada",  fg_color=COR_PRIMARIA, width=120,
                  command=lambda: gerar("detalhada","impressora")).pack(side="right", padx=4)
    ctk.CTkButton(frame_bt, text="PDF Resumida",     fg_color="#17a2b8",    width=110,
                  command=lambda: gerar("resumida","pdf")).pack(side="right", padx=4)
    ctk.CTkButton(frame_bt, text="PDF Detalhada",    fg_color="#138496",    width=110,
                  command=lambda: gerar("detalhada","pdf")).pack(side="right", padx=4)
    win.bind("<Escape>", lambda e: win.destroy())


# ══════════════════════════════════════════════════════════════════════
#  TELA PRINCIPAL DE CLIENTES
# ══════════════════════════════════════════════════════════════════════

def _construir_tela_clientes(container, parent_win):
    garantir_tabelas()

    frame_topo   = ctk.CTkFrame(container); frame_topo.pack(fill="x", padx=8, pady=(8,4))
    frame_lista  = ctk.CTkFrame(container); frame_lista.pack(fill="both", expand=True, padx=8, pady=(0,4))
    frame_detalhe= ctk.CTkFrame(container); frame_detalhe.pack(fill="both", expand=True, padx=8, pady=(0,4))
    frame_botoes = ctk.CTkFrame(container); frame_botoes.pack(fill="x", padx=8, pady=(0,8))

    ctk.CTkLabel(frame_topo, text="Clientes",
                 font=ctk.CTkFont(size=16,weight="bold")).pack(side="left", padx=(8,16))
    ctk.CTkLabel(frame_topo, text="Buscar:").pack(side="left", padx=(4,2))
    entry_busca=ctk.CTkEntry(frame_topo, width=280, placeholder_text="Nome, telefone ou CPF...")
    entry_busca.pack(side="left", padx=4)
    ctk.CTkButton(frame_topo, text="+ Novo Cliente", fg_color=COR_PRIMARIA,
                  command=lambda: abrir_cadastro_cliente(container, on_salvo=carregar_clientes)
                  ).pack(side="right", padx=8)

    cols_c=("id","nome","telefone","cpf","saldo_devedor","limite")
    tree_clientes=ttk.Treeview(frame_lista, columns=cols_c, show="headings", height=8)
    tree_clientes.heading("id",           text="ID");      tree_clientes.column("id",           width=50,  anchor="center")
    tree_clientes.heading("nome",         text="Nome");    tree_clientes.column("nome",         width=220)
    tree_clientes.heading("telefone",     text="Telefone");tree_clientes.column("telefone",     width=120)
    tree_clientes.heading("cpf",          text="CPF");     tree_clientes.column("cpf",          width=120)
    tree_clientes.heading("saldo_devedor",text="Devendo"); tree_clientes.column("saldo_devedor",width=100, anchor="e")
    tree_clientes.heading("limite",       text="Limite");  tree_clientes.column("limite",       width=100, anchor="e")
    sb_c=ttk.Scrollbar(frame_lista, orient="vertical", command=tree_clientes.yview)
    tree_clientes.configure(yscrollcommand=sb_c.set)
    sb_c.pack(side="right", fill="y"); tree_clientes.pack(fill="both", expand=True, padx=4, pady=4)
    tree_clientes.tag_configure("devendo", foreground="#ff6666")

    lbl_detalhe=ctk.CTkLabel(frame_detalhe,
        text="Selecione um cliente para ver as compras a prazo", text_color="#888888")
    lbl_detalhe.pack(anchor="w", padx=8, pady=(4,2))

    # Tree com coluna extra "Ver"
    cols_p=("venda","data","total","pago","saldo","status","ver")
    tree_prazo=ttk.Treeview(frame_detalhe, columns=cols_p, show="headings", height=6)
    tree_prazo.heading("venda", text="Venda");   tree_prazo.column("venda", width=65,  anchor="center")
    tree_prazo.heading("data",  text="Data");    tree_prazo.column("data",  width=130)
    tree_prazo.heading("total", text="Total");   tree_prazo.column("total", width=90,  anchor="e")
    tree_prazo.heading("pago",  text="Pago");    tree_prazo.column("pago",  width=90,  anchor="e")
    tree_prazo.heading("saldo", text="Saldo");   tree_prazo.column("saldo", width=90,  anchor="e")
    tree_prazo.heading("status",text="Status");  tree_prazo.column("status",width=80,  anchor="center")
    tree_prazo.heading("ver",   text="");        tree_prazo.column("ver",   width=80,  anchor="center")
    sb_p=ttk.Scrollbar(frame_detalhe, orient="vertical", command=tree_prazo.yview)
    tree_prazo.configure(yscrollcommand=sb_p.set)
    sb_p.pack(side="right", fill="y"); tree_prazo.pack(fill="both", expand=True, padx=4, pady=4)
    tree_prazo.tag_configure("aberto",  foreground="#ff9966")
    tree_prazo.tag_configure("parcial", foreground="#ffcc44")
    tree_prazo.tag_configure("pago",    foreground="#66cc66")

    btn_editar   =ctk.CTkButton(frame_botoes, text="Editar",       fg_color=COR_PRIMARIA, width=100)
    btn_pagar    =ctk.CTkButton(frame_botoes, text="Pagar Divida", fg_color="#28a745",    width=130)
    btn_cobrar   =ctk.CTkButton(frame_botoes, text="Cobrar",       fg_color="#17a2b8",    width=100)
    btn_nota     =ctk.CTkButton(frame_botoes, text="Gerar Nota",   fg_color="#2d89ef",    width=110)
    btn_inativar =ctk.CTkButton(frame_botoes, text="Inativar",     fg_color="#d9534f",    width=100)
    btn_atualizar=ctk.CTkButton(frame_botoes, text="Atualizar",    fg_color="#6c757d",    width=100)
    btn_editar.pack(side="left", padx=4, pady=6)
    btn_pagar.pack(side="left", padx=4)
    btn_cobrar.pack(side="left", padx=4)
    btn_nota.pack(side="left", padx=4)
    btn_inativar.pack(side="left", padx=4)
    btn_atualizar.pack(side="left", padx=4)

    _cliente_sel={"id":None,"nome":None}
    _todos_clientes=[]

    def carregar_clientes():
        _todos_clientes.clear()
        try:
            conn=get_connection(); cur=conn.cursor()
            cols=_colunas_existentes(cur,"clientes")
            sel_tel   ="c.telefone"           if "telefone"       in cols else "''"
            sel_cpf   ="COALESCE(c.cpf,'')"   if "cpf"           in cols else "''"
            sel_lim   ="COALESCE(c.limite_credito,0)" if "limite_credito" in cols else "0"
            w_ativo   ="AND c.ativo=1"         if "ativo"         in cols else ""
            cur.execute(f"""
                SELECT c.id, c.nome, {sel_tel}, {sel_cpf},
                       COALESCE(SUM(vp.valor_total-vp.valor_pago),0), {sel_lim}
                FROM clientes c
                LEFT JOIN vendas_prazo vp ON vp.cliente_id=c.id AND vp.status!='pago'
                WHERE 1=1 {w_ativo}
                GROUP BY c.id, c.nome ORDER BY c.nome
            """)
            for row in cur.fetchall(): _todos_clientes.append(row)
            cur.close(); conn.close()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar clientes:\n{e}")
        filtrar_clientes()

    def filtrar_clientes(event=None):
        termo=normalizar(entry_busca.get().strip())
        for i in tree_clientes.get_children(): tree_clientes.delete(i)
        for row in _todos_clientes:
            cid,nome,tel,cpf,saldo,limite=row
            txt=normalizar(f"{nome} {tel} {cpf}")
            if not termo or termo in txt:
                sf=float(saldo or 0)
                tags=("devendo",) if sf>0 else ()
                tree_clientes.insert("",tk.END, values=(cid,nome,tel,cpf,f"R$ {sf:.2f}",f"R$ {float(limite or 0):.2f}"), tags=tags)

    def carregar_prazo(cliente_id):
        for i in tree_prazo.get_children(): tree_prazo.delete(i)
        try:
            conn=get_connection(); cur=conn.cursor()
            cur.execute("""
                SELECT vp.id, v.id, vp.valor_total, vp.valor_pago,
                       (vp.valor_total-vp.valor_pago), vp.criado_em, vp.status
                FROM vendas_prazo vp LEFT JOIN vendas v ON v.id=vp.venda_id
                WHERE vp.cliente_id=%s ORDER BY vp.criado_em DESC
            """, (cliente_id,))
            for row in cur.fetchall():
                vp_id,v_id,total,pago,saldo,dt,status=row
                try: dt_s=dt.strftime("%d/%m/%Y %H:%M") if isinstance(dt,datetime) else str(dt)
                except: dt_s=str(dt)
                tree_prazo.insert("",tk.END, values=(
                    v_id,dt_s,f"R$ {float(total):.2f}",f"R$ {float(pago):.2f}",
                    f"R$ {float(saldo):.2f}",status,"👁 Ver"), tags=(status,))
            cur.close(); conn.close()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar compras a prazo:\n{e}")

    def on_click_prazo(event):
        col=tree_prazo.identify_column(event.x)
        iid=tree_prazo.identify_row(event.y)
        if not iid: return
        if col=="#7":
            vals=tree_prazo.item(iid)["values"]
            _abrir_ver_venda(vals[0])
    tree_prazo.bind("<ButtonRelease-1>", on_click_prazo)

    def _abrir_ver_venda(v_id):
        win=ctk.CTkToplevel(parent_win)
        win.title(f"Venda #{v_id}")
        win.geometry("680x460"); win.transient(parent_win); win.lift(); win.focus_force()
        win.after(100, win.grab_set)
        ctk.CTkLabel(win, text=f"Venda #{v_id} — Detalhes",
                     font=ctk.CTkFont(size=14,weight="bold")).pack(pady=(12,4), padx=12, anchor="w")
        frame_it=tk.Frame(win); frame_it.pack(fill="both", expand=True, padx=12, pady=6)
        cols_i=("item","produto","qtd","preco","subtotal")
        tree_it=ttk.Treeview(frame_it, columns=cols_i, show="headings")
        tree_it.heading("item",    text="No");      tree_it.column("item",    width=40,  anchor="center")
        tree_it.heading("produto", text="Produto"); tree_it.column("produto", width=280)
        tree_it.heading("qtd",     text="Qtd");     tree_it.column("qtd",     width=70,  anchor="center")
        tree_it.heading("preco",   text="Preco");   tree_it.column("preco",   width=90,  anchor="e")
        tree_it.heading("subtotal",text="Subtotal");tree_it.column("subtotal",width=90,  anchor="e")
        sb_i=ttk.Scrollbar(frame_it, orient="vertical", command=tree_it.yview)
        tree_it.configure(yscrollcommand=sb_i.set)
        sb_i.pack(side="right", fill="y"); tree_it.pack(fill="both", expand=True)
        total_v=0.0; rv=None
        try:
            conn=get_connection(); cur=conn.cursor()
            cur.execute("""
                SELECT iv.id, p.nome, iv.quantidade, iv.preco_unitario, iv.subtotal
                FROM itens_venda iv LEFT JOIN produtos p ON p.id=iv.produto_id
                WHERE iv.venda_id=%s ORDER BY iv.id
            """, (v_id,))
            for idx,it in enumerate(cur.fetchall(),1):
                try: qtd_f=float(it[2])
                except: qtd_f=0.0
                try: pu=float(it[3])
                except: pu=0.0
                try: sub=float(it[4])
                except: sub=qtd_f*pu
                qtd_s=f"{qtd_f:.3f}".rstrip("0").rstrip(".") if not qtd_f.is_integer() else str(int(qtd_f))
                tree_it.insert("",tk.END, values=(f"{idx:03d}",it[1] or "?",qtd_s,f"{pu:.2f}",f"{sub:.2f}"))
                total_v+=sub
            cur.execute("SELECT cliente, data_venda FROM vendas WHERE id=%s",(v_id,))
            rv=cur.fetchone(); cur.close(); conn.close()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha:\n{e}"); win.destroy(); return
        info=f"Data: {rv[1].strftime('%d/%m/%Y %H:%M') if rv and rv[1] else '?'}"
        if rv and rv[0]: info+=f"  |  Cliente: {rv[0]}"
        ctk.CTkLabel(win, text=info, text_color="#888888").pack(anchor="w", padx=12)
        ctk.CTkLabel(win, text=f"Total: R$ {total_v:.2f}",
                     font=ctk.CTkFont(size=13,weight="bold"), text_color=COR_PRIMARIA).pack(anchor="w", padx=12, pady=(4,8))
        ctk.CTkButton(win, text="Fechar", fg_color="#6c757d", command=win.destroy).pack(pady=(0,12))
        win.bind("<Escape>", lambda e: win.destroy())

    def on_cliente_select(event=None):
        sel=tree_clientes.selection()
        if not sel: return
        vals=tree_clientes.item(sel[0])["values"]
        _cliente_sel["id"]=int(vals[0]); _cliente_sel["nome"]=str(vals[1])
        lbl_detalhe.configure(text=f"Compras a prazo — {vals[1]}")
        carregar_prazo(_cliente_sel["id"])

    def on_editar():
        cid=_cliente_sel["id"]
        if not cid: messagebox.showwarning("Aviso","Selecione um cliente."); return
        abrir_cadastro_cliente(container, cliente_id=cid, on_salvo=carregar_clientes)

    def on_pagar():
        cid=_cliente_sel["id"]; nome=_cliente_sel["nome"]
        if not cid: messagebox.showwarning("Aviso","Selecione um cliente."); return
        abrir_pagamento_prazo(container, cid, nome,
                              on_pago=lambda: (carregar_clientes(), carregar_prazo(cid)))

    def on_cobrar():
        cid=_cliente_sel["id"]; nome=_cliente_sel["nome"]
        if not cid: messagebox.showwarning("Aviso","Selecione um cliente."); return
        try:
            conn=get_connection(); cur=conn.cursor()
            cur.execute("""
                SELECT vp.id, v.id, vp.valor_total, vp.valor_pago,
                       (vp.valor_total-vp.valor_pago), vp.criado_em, vp.status
                FROM vendas_prazo vp LEFT JOIN vendas v ON v.id=vp.venda_id
                WHERE vp.cliente_id=%s AND vp.status!='pago' ORDER BY vp.criado_em
            """, (cid,))
            dividas=cur.fetchall(); cur.close(); conn.close()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha:\n{e}"); return
        if not dividas:
            messagebox.showinfo("Sem dividas", f"{nome} nao possui dividas em aberto."); return

        total_conta=sum(float(d[4]) for d in dividas)
        win=ctk.CTkToplevel(parent_win)
        win.title(f"Cobrar — {nome}")
        win.geometry("660x520"); win.transient(parent_win); win.lift(); win.focus_force()
        win.after(100, win.grab_set)
        ctk.CTkLabel(win, text=f"Nota de Cobranca — {nome}",
                     font=ctk.CTkFont(size=14,weight="bold")).pack(pady=(12,4), padx=12, anchor="w")
        ctk.CTkLabel(win, text="Selecione as vendas (sem quitar o pagamento):",
                     text_color="#888888").pack(padx=12, anchor="w")

        frame_tree2=tk.Frame(win); frame_tree2.pack(fill="both", expand=True, padx=12, pady=6)
        cols2=("sel","venda","data","total","pago","saldo","status")
        tree_c=ttk.Treeview(frame_tree2, columns=cols2, show="headings", selectmode="none")
        tree_c.heading("sel",   text="");       tree_c.column("sel",   width=32, anchor="center")
        tree_c.heading("venda", text="Venda");  tree_c.column("venda", width=60, anchor="center")
        tree_c.heading("data",  text="Data");   tree_c.column("data",  width=130)
        tree_c.heading("total", text="Total");  tree_c.column("total", width=85, anchor="e")
        tree_c.heading("pago",  text="Pago");   tree_c.column("pago",  width=85, anchor="e")
        tree_c.heading("saldo", text="Saldo");  tree_c.column("saldo", width=85, anchor="e")
        tree_c.heading("status",text="Status"); tree_c.column("status",width=70, anchor="center")
        sb_c2=ttk.Scrollbar(frame_tree2, orient="vertical", command=tree_c.yview)
        tree_c.configure(yscrollcommand=sb_c2.set); sb_c2.pack(side="right", fill="y"); tree_c.pack(fill="both", expand=True)
        tree_c.tag_configure("selecionado", background="#1a3a5a", foreground="#aaccff")

        sel_map={}; iid_map={}
        for d in dividas:
            vp_id,v_id,total,pago,saldo,criado,status=d
            try: dt_s=criado.strftime("%d/%m/%Y %H:%M") if isinstance(criado,datetime) else str(criado)[:16]
            except: dt_s=str(criado)[:16]
            iid=tree_c.insert("",tk.END, values=("☐",v_id,dt_s,f"{float(total):.2f}",f"{float(pago):.2f}",f"{float(saldo):.2f}",status))
            sel_map[iid]=False; iid_map[iid]=d

        lbl_tot_cob=ctk.CTkLabel(win, text=f"Total a cobrar: R$ {total_conta:.2f}",
                                  font=ctk.CTkFont(size=12,weight="bold"), text_color=COR_PRIMARIA)
        lbl_tot_cob.pack(anchor="w", padx=14, pady=(0,4))

        def toggle_c(event):
            iid=tree_c.identify_row(event.y)
            if not iid: return
            sel_map[iid]=not sel_map[iid]
            vals=list(tree_c.item(iid)["values"]); vals[0]="✔" if sel_map[iid] else "☐"
            tree_c.item(iid, values=vals, tags=("selecionado",) if sel_map[iid] else ())
            ts=sum(float(iid_map[i][4]) for i,s in sel_map.items() if s)
            lbl_tot_cob.configure(text=f"Total a cobrar: R$ {ts:.2f}")
        tree_c.bind("<ButtonRelease-1>", toggle_c)

        def sel_todas_c():
            for iid in sel_map:
                sel_map[iid]=True
                vals=list(tree_c.item(iid)["values"]); vals[0]="✔"
                tree_c.item(iid, values=vals, tags=("selecionado",))
            lbl_tot_cob.configure(text=f"Total a cobrar: R$ {total_conta:.2f}")

        def _gerar(tipo):
            a_cobrar=[iid_map[iid] for iid,s in sel_map.items() if s]
            if not a_cobrar: messagebox.showwarning("Aviso","Selecione ao menos uma venda."); return
            tc_val=sum(float(d[4]) for d in a_cobrar)
            win.destroy()
            _popup_formato_cobranca(parent_win, nome, a_cobrar, tc_val, tipo)

        frame_bt2=ctk.CTkFrame(win, fg_color="transparent"); frame_bt2.pack(fill="x", padx=12, pady=(0,12))
        ctk.CTkButton(frame_bt2, text="Selecionar Todas", fg_color="#2d89ef", command=sel_todas_c).pack(side="left", padx=6)
        ctk.CTkButton(frame_bt2, text="Resumida",  fg_color="#17a2b8", command=lambda: _gerar("resumida")).pack(side="right", padx=6)
        ctk.CTkButton(frame_bt2, text="Detalhada", fg_color=COR_PRIMARIA, command=lambda: _gerar("detalhada")).pack(side="right", padx=6)
        ctk.CTkButton(frame_bt2, text="Cancelar", fg_color="#6c757d", command=win.destroy).pack(side="right", padx=6)
        win.bind("<Escape>", lambda e: win.destroy())

    def on_nota():
        cid=_cliente_sel["id"]; nome=_cliente_sel["nome"]
        if not cid: messagebox.showwarning("Aviso","Selecione um cliente."); return
        abrir_gerar_nota(container, cid, nome)

    def on_inativar():
        cid=_cliente_sel["id"]
        if not cid: messagebox.showwarning("Aviso","Selecione um cliente."); return
        if not messagebox.askyesno("Confirmar",f"Inativar '{_cliente_sel['nome']}'?"): return
        try:
            conn=get_connection(); cur=conn.cursor()
            cols=_colunas_existentes(cur,"clientes")
            if "ativo" in cols:
                cur.execute("UPDATE clientes SET ativo=0 WHERE id=%s",(cid,))
                conn.commit()
            cur.close(); conn.close()
            _cliente_sel["id"]=None; _cliente_sel["nome"]=None
            carregar_clientes()
        except Exception as e:
            messagebox.showerror("Erro",f"Falha:\n{e}")

    entry_busca.bind("<KeyRelease>", filtrar_clientes)
    tree_clientes.bind("<<TreeviewSelect>>", on_cliente_select)
    tree_clientes.bind("<Double-1>", on_cliente_select)
    btn_editar.configure(command=on_editar)
    btn_pagar.configure(command=on_pagar)
    btn_cobrar.configure(command=on_cobrar)
    btn_nota.configure(command=on_nota)
    btn_inativar.configure(command=on_inativar)
    btn_atualizar.configure(command=carregar_clientes)

    carregar_clientes()


def mostrar_clientes_inline(frame_main, show_frame_in_main_fn):
    """Abre a tela de clientes dentro do frame_main do PDV."""
    parent_win = frame_main.winfo_toplevel()
    frame_clientes = ctk.CTkFrame(frame_main)
    _construir_tela_clientes(frame_clientes, parent_win)
    show_frame_in_main_fn(frame_clientes)