"""
relatorios.py — Relatórios do Sistema PDV
==========================================
Gera 3 tipos de relatório:
  1. Itens Vendidos     — ranking do mais vendido ao menos vendido (qtd e valor)
  2. Relatório Diário   — vendas por dia com total por forma de pagamento
  3. Curva ABC          — classificação dos produtos por participação no faturamento

Saída:
  - PDF  : via reportlab  (pip install reportlab)
  - Térmica: via win32print em formato ESC/POS 48 colunas

Ticket médio é incluído no rodapé de todos os relatórios.
"""

import os
import tempfile
import subprocess
import unicodedata
from datetime import datetime

# ── banco ──────────────────────────────────────────────────────────────
import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "pdv",
    "password": "1234",
    "database": "sistema_vendas"
}

def _conn():
    return mysql.connector.connect(**DB_CONFIG)


# ══════════════════════════════════════════════════════════════════════
#  CONSULTAS AO BANCO
# ══════════════════════════════════════════════════════════════════════

def _where_periodo(de_str, ate_str):
    """Retorna cláusula WHERE e params para filtrar por período."""
    if de_str and ate_str:
        return "WHERE v.data_venda BETWEEN %s AND %s", [de_str, ate_str]
    return "", []


def buscar_itens_vendidos(de_str=None, ate_str=None):
    """
    Retorna lista de (nome, codigo, qtd_total, valor_total)
    ordenada do maior valor_total para o menor.
    """
    where, params = _where_periodo(de_str, ate_str)
    sql = f"""
        SELECT
            COALESCE(p.nome, 'Produto removido') AS nome,
            COALESCE(p.codigo, '?')              AS codigo,
            SUM(iv.quantidade)                   AS qtd_total,
            SUM(iv.subtotal)                     AS valor_total
        FROM itens_venda iv
        LEFT JOIN produtos p ON p.id = iv.produto_id
        LEFT JOIN vendas v   ON v.id = iv.venda_id
        {where}
        GROUP BY iv.produto_id, p.nome, p.codigo
        ORDER BY valor_total DESC
    """
    conn = _conn(); cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows   # (nome, codigo, qtd_total, valor_total)


def buscar_relatorio_diario(de_str=None, ate_str=None):
    """
    Retorna:
      vendas_por_dia : [(data_str, n_vendas, valor_total)]
      por_forma      : [(forma_nome, valor_total)]
      total_geral    : float
      n_vendas_total : int
    """
    where, params = _where_periodo(de_str, ate_str)

    conn = _conn(); cur = conn.cursor()

    # vendas por dia
    sql_dia = f"""
        SELECT DATE(v.data_venda) AS dia,
               COUNT(v.id)        AS n_vendas,
               SUM(v.valor_total) AS total
        FROM vendas v
        {where}
        GROUP BY dia
        ORDER BY dia
    """
    cur.execute(sql_dia, params)
    vendas_por_dia = [(str(r[0]), int(r[1]), float(r[2] or 0)) for r in cur.fetchall()]

    # por forma de pagamento
    sql_forma = f"""
        SELECT COALESCE(fp.nome, 'Outra') AS forma,
               SUM(pg.valor)              AS total
        FROM pagamentos pg
        LEFT JOIN formas_pagamento fp ON fp.id = pg.forma_id
        LEFT JOIN vendas v             ON v.id  = pg.venda_id
        {where}
        GROUP BY fp.nome
        ORDER BY total DESC
    """
    cur.execute(sql_forma, params)
    por_forma = [(r[0], float(r[1] or 0)) for r in cur.fetchall()]

    # totais gerais
    sql_tot = f"""
        SELECT COUNT(v.id), SUM(v.valor_total)
        FROM vendas v {where}
    """
    cur.execute(sql_tot, params)
    r = cur.fetchone()
    n_vendas_total = int(r[0] or 0)
    total_geral    = float(r[1] or 0)

    cur.close(); conn.close()
    return vendas_por_dia, por_forma, total_geral, n_vendas_total


def buscar_curva_abc(de_str=None, ate_str=None):
    """
    Retorna lista de (nome, codigo, valor_total, pct, pct_acum, classe)
    ordenada do maior para o menor valor.
    Classe: A = até 70 %, B = até 90 %, C = restante.
    """
    rows = buscar_itens_vendidos(de_str, ate_str)
    total = sum(float(r[3]) for r in rows) or 1.0
    resultado = []
    acum = 0.0
    for nome, codigo, qtd, valor in rows:
        pct  = float(valor) / total * 100
        acum += pct
        classe = "A" if acum <= 70 else ("B" if acum <= 90 else "C")
        resultado.append((nome, codigo, float(valor), round(pct, 2), round(acum, 2), classe))
    return resultado, total


# ══════════════════════════════════════════════════════════════════════
#  HELPERS DE FORMATAÇÃO COMPARTILHADOS
# ══════════════════════════════════════════════════════════════════════

COLS = 48  # largura em caracteres para 80 mm

def _linha(c="-"):
    return c * COLS

def _c2(esq, dir_, w=COLS):
    sp = w - len(esq) - len(dir_)
    return esq + " " * max(sp, 1) + dir_

def _c3(col1, col2, col3, w1=24, w2=10, w3=None):
    w3 = w3 or (COLS - w1 - w2)
    s1 = col1[:w1].ljust(w1)
    s2 = col2[:w2].rjust(w2)
    s3 = col3[:(w3)].rjust(w3)
    return s1 + s2 + s3

def _ticket_medio(total, n):
    if n == 0:
        return 0.0
    return total / n

def _cabecalho_texto(titulo, de_str, ate_str):
    linhas = []
    linhas.append(_linha("="))
    linhas.append("SISTEMA PDV".center(COLS))
    linhas.append(titulo.center(COLS))
    periodo = ""
    if de_str and ate_str:
        periodo = f"{de_str}  a  {ate_str}"
    elif de_str:
        periodo = f"A partir de {de_str}"
    elif ate_str:
        periodo = f"Ate {ate_str}"
    else:
        periodo = "Periodo completo"
    linhas.append(periodo.center(COLS))
    linhas.append(f"Emitido: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}".center(COLS))
    linhas.append(_linha("="))
    return linhas

def _rodape_texto(total_geral, n_vendas):
    tm = _ticket_medio(total_geral, n_vendas)
    linhas = []
    linhas.append(_linha())
    linhas.append(_c2("Total geral:", f"R$ {total_geral:.2f}"))
    linhas.append(_c2("Num. vendas:", str(n_vendas)))
    linhas.append(_c2("Ticket medio:", f"R$ {tm:.2f}"))
    linhas.append(_linha("="))
    return linhas


# ══════════════════════════════════════════════════════════════════════
#  GERAÇÃO TEXTO (base para térmica e PDF simples)
# ══════════════════════════════════════════════════════════════════════

def _texto_itens_vendidos(rows, de_str, ate_str):
    total_geral = sum(float(r[3]) for r in rows)
    n_vendas    = None  # calculado separado se necessário

    linhas = _cabecalho_texto("ITENS VENDIDOS", de_str, ate_str)
    linhas.append(_c3("PRODUTO", "QTD", "VALOR"))
    linhas.append(_linha())
    for nome, codigo, qtd, valor in rows:
        nome_curto = nome[:23]
        try:
            if float(qtd) != int(float(qtd)):
                qtd_s = f"{float(qtd):.3f}".rstrip("0").rstrip(".")
            else:
                qtd_s = str(int(float(qtd)))
        except Exception:
            qtd_s = str(qtd)
        linhas.append(_c3(nome_curto, qtd_s, f"R${float(valor):.2f}"))
    linhas.append(_linha())
    linhas.append(_c2("TOTAL ITENS:", f"R$ {total_geral:.2f}"))
    return linhas


def _texto_diario(vendas_por_dia, por_forma, total_geral, n_vendas, de_str, ate_str):
    linhas = _cabecalho_texto("RELATORIO DIARIO", de_str, ate_str)

    linhas.append(_c3("DATA", "VENDAS", "TOTAL"))
    linhas.append(_linha())
    for dia, n, total in vendas_por_dia:
        try:
            d = datetime.strptime(dia, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            d = dia
        linhas.append(_c3(d, str(n), f"R${total:.2f}"))

    linhas.append(_linha())
    linhas.append("FORMAS DE PAGAMENTO:".ljust(COLS))
    linhas.append(_linha("-"))
    for forma, valor in por_forma:
        linhas.append(_c2(f"  {forma[:30]}", f"R$ {valor:.2f}"))

    linhas += _rodape_texto(total_geral, n_vendas)
    return linhas


def _texto_curva_abc(resultado, total_geral, de_str, ate_str):
    n_vendas_abc = None
    linhas = _cabecalho_texto("CURVA ABC", de_str, ate_str)
    linhas.append(f"{'PRODUTO':<22}{'VALOR':>9}{'%':>6}{'%AC':>6}{'CL':>3}")
    linhas.append(_linha())
    cur_classe = ""
    for nome, codigo, valor, pct, pct_acum, classe in resultado:
        if classe != cur_classe:
            cur_classe = classe
            linhas.append(f"--- CLASSE {classe} ---".center(COLS))
        nome_c = nome[:21]
        linhas.append(f"{nome_c:<22}{valor:>9.2f}{pct:>6.1f}{pct_acum:>6.1f}{classe:>3}")

    # contagem de vendas para ticket médio
    conn = _conn(); cur = _conn().cursor()
    try:
        conn2 = _conn(); cur2 = conn2.cursor()
        cur2.execute("SELECT COUNT(*) FROM vendas")
        n_total = int(cur2.fetchone()[0])
        cur2.close(); conn2.close()
    except Exception:
        n_total = 1

    linhas += _rodape_texto(total_geral, n_total)
    return linhas


# ══════════════════════════════════════════════════════════════════════
#  IMPRESSÃO TÉRMICA
# ══════════════════════════════════════════════════════════════════════

NOME_IMPRESSORA_WINDOWS = "EPSON TM-T20X"

def _imprimir_linhas(linhas):
    try:
        import win32print
    except ImportError:
        from tkinter import messagebox
        messagebox.showwarning("Impressão", "pywin32 não instalado.\npip install pywin32")
        return

    nome = NOME_IMPRESSORA_WINDOWS
    try:
        impressoras = [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        for p in impressoras:
            if NOME_IMPRESSORA_WINDOWS.upper() in p.upper():
                nome = p
                break
        else:
            nome = win32print.GetDefaultPrinter()
    except Exception:
        try:
            nome = win32print.GetDefaultPrinter()
        except Exception:
            from tkinter import messagebox
            messagebox.showwarning("Impressão", "Nenhuma impressora encontrada.")
            return

    ESC  = b'\x1b'
    GS   = b'\x1d'
    INIT = ESC + b'@'
    CUT  = GS  + b'V\x41\x03'

    buf = bytearray(INIT)
    for ln in linhas:
        buf += ln.encode("cp850", errors="replace") + b'\n'
    buf += b'\n' * 4
    buf += CUT

    try:
        hp = win32print.OpenPrinter(nome)
        try:
            hj = win32print.StartDocPrinter(hp, 1, ("Relatorio PDV", None, "RAW"))
            try:
                win32print.StartPagePrinter(hp)
                win32print.WritePrinter(hp, bytes(buf))
                win32print.EndPagePrinter(hp)
            finally:
                win32print.EndDocPrinter(hp)
        finally:
            win32print.ClosePrinter(hp)
    except Exception as e:
        from tkinter import messagebox
        messagebox.showwarning("Impressão", f"Erro ao imprimir:\n{e}")


# ══════════════════════════════════════════════════════════════════════
#  GERAÇÃO PDF (reportlab)
# ══════════════════════════════════════════════════════════════════════

# Largura de papel 80 mm em pontos (1 mm = 2.8346 pt)
PAPEL_80MM_W = 226.77  # ~80 mm em pt
MARGEM       = 10

def _pdf_linhas(linhas, titulo, caminho):
    """Gera PDF com fonte monoespaçada simulando cupom 80 mm."""
    # Tenta importar reportlab; instala automaticamente se não tiver
    try:
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        import subprocess, sys
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            from reportlab.pdfgen import canvas as rl_canvas
        except Exception:
            from tkinter import messagebox
            messagebox.showwarning("PDF",
                "Nao foi possivel instalar o reportlab automaticamente.\n"
                "Execute manualmente:  pip install reportlab\n"
                "e tente novamente.")
            return None

    FONT      = "Courier"
    FONT_SIZE = 7
    LINE_H    = FONT_SIZE + 2
    LARGURA   = PAPEL_80MM_W
    altura    = max(LINE_H * (len(linhas) + 6) + MARGEM * 2, 200)

    c = rl_canvas.Canvas(caminho, pagesize=(LARGURA, altura))
    c.setFont(FONT, FONT_SIZE)

    y = altura - MARGEM - LINE_H
    for ln in linhas:
        # Remove acentos para evitar erro de encoding no PDF
        ln_safe = unicodedata.normalize("NFD", str(ln)).encode("ascii","ignore").decode("ascii")
        c.drawString(MARGEM, y, ln_safe[:COLS])
        y -= LINE_H
        if y < MARGEM:
            c.showPage()
            c.setFont(FONT, FONT_SIZE)
            y = altura - MARGEM - LINE_H

    c.save()
    return caminho


def _abrir_pdf(caminho):
    """Abre o PDF no visualizador padrão do Windows."""
    try:
        os.startfile(caminho)
    except Exception:
        try:
            subprocess.Popen(["start", caminho], shell=True)
        except Exception:
            from tkinter import messagebox
            messagebox.showinfo("PDF", f"PDF salvo em:\n{caminho}")


# ══════════════════════════════════════════════════════════════════════
#  INTERFACE — janela de seleção de relatório
# ══════════════════════════════════════════════════════════════════════

def abrir_janela_relatorios(parent, de_str=None, ate_str=None):
    """
    Abre janela modal para escolher o tipo de relatório e o destino
    (impressora térmica ou PDF).

    de_str / ate_str : strings no formato 'YYYY-MM-DD HH:MM:SS'
                       vindas do filtro da aba Vendas (podem ser None).
    """
    import customtkinter as ctk
    from tkinter import messagebox

    win = ctk.CTkToplevel(parent)
    win.title("Relatórios")
    win.geometry("420x320")
    win.transient(parent)
    win.grab_set()
    win.focus_force()
    win.resizable(False, False)

    ctk.CTkLabel(win, text="Gerar Relatório",
                 font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(16, 4))

    # Período resumido
    if de_str or ate_str:
        def fmt(s):
            if not s:
                return "—"
            try:
                return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                return s[:10]
        periodo_txt = f"Período: {fmt(de_str)}  →  {fmt(ate_str)}"
    else:
        periodo_txt = "Período: completo"
    ctk.CTkLabel(win, text=periodo_txt, text_color="#666666").pack(pady=(0, 10))

    # Tipo de relatório
    ctk.CTkLabel(win, text="Tipo de relatório:").pack(anchor="w", padx=20)
    var_tipo = ctk.StringVar(value="itens")
    tipos = [
        ("Itens Vendidos (ranking)",         "itens"),
        ("Relatório Diário (por dia/forma)",  "diario"),
        ("Curva ABC",                         "abc"),
    ]
    for label, val in tipos:
        ctk.CTkRadioButton(win, text=label, variable=var_tipo, value=val).pack(
            anchor="w", padx=40, pady=2)

    # Destino
    ctk.CTkLabel(win, text="Destino:").pack(anchor="w", padx=20, pady=(10, 0))
    var_dest = ctk.StringVar(value="pdf")
    frame_dest = ctk.CTkFrame(win)
    frame_dest.pack(anchor="w", padx=40)
    ctk.CTkRadioButton(frame_dest, text="PDF (abre no visualizador)",
                       variable=var_dest, value="pdf").pack(side="left", padx=(0, 16))
    ctk.CTkRadioButton(frame_dest, text="Impressora térmica",
                       variable=var_dest, value="termica").pack(side="left")

    # Botões
    frame_bt = ctk.CTkFrame(win)
    frame_bt.pack(pady=16)

    def gerar():
        tipo = var_tipo.get()
        dest = var_dest.get()
        win.destroy()

        try:
            if tipo == "itens":
                rows   = buscar_itens_vendidos(de_str, ate_str)
                linhas = _texto_itens_vendidos(rows, de_str, ate_str)
                nome_arq = "relatorio_itens"
            elif tipo == "diario":
                vd, pf, tg, nv = buscar_relatorio_diario(de_str, ate_str)
                linhas = _texto_diario(vd, pf, tg, nv, de_str, ate_str)
                nome_arq = "relatorio_diario"
            else:  # abc
                res, tg = buscar_curva_abc(de_str, ate_str)
                linhas  = _texto_curva_abc(res, tg, de_str, ate_str)
                nome_arq = "relatorio_abc"

            if dest == "termica":
                _imprimir_linhas(linhas)
                messagebox.showinfo("Relatório", "Relatório enviado para a impressora!")
            else:
                caminho = os.path.join(
                    tempfile.gettempdir(),
                    f"{nome_arq}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                )
                ok = _pdf_linhas(linhas, tipo, caminho)
                if ok:
                    _abrir_pdf(caminho)

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao gerar relatório:\n{e}")

    ctk.CTkButton(frame_bt, text="Gerar", fg_color="#FFA500",
                  width=120, command=gerar).pack(side="left", padx=8)
    ctk.CTkButton(frame_bt, text="Cancelar", fg_color="#6c757d",
                  width=120, command=win.destroy).pack(side="left", padx=8)
    win.bind("<Escape>", lambda e: win.destroy())
    win.bind("<Return>", lambda e: gerar())