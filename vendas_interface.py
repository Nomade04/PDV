"""
vendas_interface.py
===================
- mostrar_vendas_inline: abre no frame_main do PDV (sem janela flutuante)
- mostrar_vendas: mantido para compatibilidade (abre Toplevel)
- Devolução completa: selecionar itens → opcional cupom → motivo → salvar
- Filtro de item com busca em tempo real (popup ao focar no campo)
- Botão "Pesquisar" ao lado do campo Nº Venda
- Múltiplos filtros de pagamento acumuláveis
- Calendário popup nas datas
- Rodapé de filtros ativos com X individual
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from datetime import datetime, date
import calendar as _calendar_mod
import unicodedata
import relatorios as _rel_mod

DB_CONFIG = {
    "host": "localhost",
    "user": "pdv",
    "password": "1234",
    "database": "sistema_vendas"
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


# ══════════════════════════════════════════════════════════════════════
#  CALENDÁRIO POPUP
# ══════════════════════════════════════════════════════════════════════

class CalendarioPopup(tk.Toplevel):
    def __init__(self, parent, entry_widget, initial_date=None):
        super().__init__(parent)
        self.entry = entry_widget
        self.overrideredirect(True)
        self.resizable(False, False)
        self.grab_set()
        hoje = initial_date or date.today()
        self._ano = hoje.year; self._mes = hoje.month
        self._frame = tk.Frame(self, bg="#2b2b2b", bd=1, relief="solid")
        self._frame.pack(fill="both", expand=True)
        self._construir()
        self._posicionar(parent, entry_widget)
        self.bind("<Escape>", lambda e: self.destroy())

    def _posicionar(self, parent, widget):
        self.update_idletasks()
        try:
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 2
        except Exception:
            x = parent.winfo_rootx() + 40; y = parent.winfo_rooty() + 40
        sw = self.winfo_screenwidth(); w = self.winfo_reqwidth()
        if x + w > sw: x = sw - w - 4
        self.geometry(f"+{x}+{y}")

    def _construir(self):
        for w in self._frame.winfo_children(): w.destroy()
        BG="#2b2b2b"; FG="#ffffff"; ACC="#FFA500"; HOJ="#444444"
        nav = tk.Frame(self._frame, bg=BG); nav.pack(fill="x", padx=4, pady=4)
        tk.Button(nav, text="◀", bg=BG, fg=FG, bd=0, activebackground=BG,
                  activeforeground=ACC, cursor="hand2",
                  command=self._mes_anterior).pack(side="left")
        meses = ["","Janeiro","Fevereiro","Marco","Abril","Maio","Junho",
                 "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
        tk.Label(nav, text=f"{meses[self._mes]} {self._ano}",
                 bg=BG, fg=FG, font=("Arial",10,"bold"), width=18).pack(side="left", expand=True)
        tk.Button(nav, text="▶", bg=BG, fg=FG, bd=0, activebackground=BG,
                  activeforeground=ACC, cursor="hand2",
                  command=self._mes_proximo).pack(side="right")
        dias_sem = ["Dom","Seg","Ter","Qua","Qui","Sex","Sab"]
        grid = tk.Frame(self._frame, bg=BG); grid.pack(padx=4, pady=(0,6))
        for col, ds in enumerate(dias_sem):
            tk.Label(grid, text=ds, bg=BG, fg=ACC, font=("Arial",8,"bold"), width=4).grid(row=0, column=col)
        hoje_date = date.today()
        primeiro = date(self._ano, self._mes, 1)
        inicio_col = (primeiro.weekday() + 1) % 7
        n_dias = _calendar_mod.monthrange(self._ano, self._mes)[1]
        lin, col = 1, inicio_col
        for dia in range(1, n_dias + 1):
            d = date(self._ano, self._mes, dia)
            cor_bg = HOJ if d == hoje_date else BG
            cor_fg = ACC if d == hoje_date else FG
            tk.Button(grid, text=str(dia), bg=cor_bg, fg=cor_fg, bd=0, width=4,
                      activebackground="#555555", activeforeground=FG, cursor="hand2",
                      command=lambda _d=d: self._selecionar(_d)).grid(row=lin, column=col, pady=1)
            col += 1
            if col > 6: col = 0; lin += 1

    def _mes_anterior(self):
        if self._mes == 1: self._mes=12; self._ano-=1
        else: self._mes-=1
        self._construir()

    def _mes_proximo(self):
        if self._mes == 12: self._mes=1; self._ano+=1
        else: self._mes+=1
        self._construir()

    def _selecionar(self, d):
        self.entry.delete(0, tk.END); self.entry.insert(0, d.strftime("%d/%m/%Y")); self.destroy()


def abrir_calendario(parent, entry_widget):
    txt = entry_widget.get().strip()
    try: d = datetime.strptime(txt, "%d/%m/%Y").date()
    except: d = date.today()
    CalendarioPopup(parent, entry_widget, d)


# ══════════════════════════════════════════════════════════════════════
#  REIMPRESSÃO
# ══════════════════════════════════════════════════════════════════════

def reimprimir_venda(venda_id):
    try:
        import interface as _iface
    except ImportError:
        messagebox.showerror("Erro", "Nao foi possivel importar o modulo interface."); return
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT valor_total, cliente FROM vendas WHERE id=%s", (venda_id,))
        row = cur.fetchone()
        if not row: messagebox.showwarning("Aviso", f"Venda {venda_id} nao encontrada."); conn.close(); return
        total_a_pagar = float(row[0] or 0); cliente_nome = row[1]
        cur.execute("""
            SELECT p.codigo, p.nome, iv.quantidade, iv.preco_unitario, iv.subtotal,
                   COALESCE(iv.observacao, iv.pbservacoes, NULL)
            FROM itens_venda iv LEFT JOIN produtos p ON p.id=iv.produto_id
            WHERE iv.venda_id=%s ORDER BY iv.id
        """, (venda_id,))
        itens = []
        for r in cur.fetchall():
            try: qtd=float(r[2])
            except: qtd=0.0
            try: pu=float(r[3])
            except: pu=0.0
            try: sub=float(r[4])
            except: sub=qtd*pu
            itens.append({"codigo":r[0] or "","descricao":r[1] or "","quantidade":qtd,
                          "preco_unit":pu,"subtotal":sub,"observacao":r[5]})
        cur.execute("""
            SELECT p.forma_id, fp.nome, p.valor, p.troco FROM pagamentos p
            LEFT JOIN formas_pagamento fp ON fp.id=p.forma_id WHERE p.venda_id=%s
        """, (venda_id,))
        pagamentos_map={}; payment_types_reimp=[]
        for r in cur.fetchall():
            pagamentos_map[r[0]]={"valor":float(r[2] or 0),"troco":float(r[3] or 0)}
            payment_types_reimp.append((r[1] or f"Forma {r[0]}","0,00"))
        total_pago = sum(d["valor"] for d in pagamentos_map.values())
        cur.close(); conn.close()
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao buscar dados:\n{e}"); return
    if not messagebox.askyesno("Reimprimir", f"Reimprimir cupom da venda No {venda_id}?"): return
    _iface.imprimir_cupom_thermal(venda_id=venda_id, itens=itens, pagamentos_map=pagamentos_map,
        total_a_pagar=total_a_pagar, total_pago=total_pago,
        cliente_nome=cliente_nome, payment_types=payment_types_reimp)


# ══════════════════════════════════════════════════════════════════════
#  DEVOLUÇÃO COMPLETA
# ══════════════════════════════════════════════════════════════════════

MOTIVOS_DEVOLUCAO = ["Desistencia", "Troca", "Manipulacao", "Improprio"]

def devolver_venda(parent, venda_id, on_sucesso=None):
    """
    Fluxo completo:
    1. Selecionar itens a devolver
    2. Perguntar se quer cupom (Enter=Sim, ESC=Não)
    3. Mostrar resumo + campo motivo
    4. Finalizar: salva devolução + opcionalmente imprime cupom
    """
    # Garante que parent é sempre uma janela real (não um Frame)
    parent_win = parent.winfo_toplevel()

    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT iv.id, p.nome, iv.quantidade, iv.preco_unitario, iv.subtotal, iv.produto_id, p.codigo
            FROM itens_venda iv LEFT JOIN produtos p ON p.id=iv.produto_id
            WHERE iv.venda_id=%s ORDER BY iv.id
        """, (venda_id,))
        itens = cur.fetchall(); cur.close(); conn.close()
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao carregar itens:\n{e}"); return

    if not itens:
        messagebox.showinfo("Devolucao","Esta venda nao possui itens."); return

    # ── Passo 1: Seleção de itens ────────────────────────────────────
    win = ctk.CTkToplevel(parent_win)
    win.title(f"Devolver Itens — Venda No {venda_id}")
    win.geometry("720x520")
    win.transient(parent_win)
    win.lift()
    win.focus_force()
    win.after(150, win.grab_set)

    ctk.CTkLabel(win, text=f"Devolucao — Venda No {venda_id}",
                 font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(12,2), padx=12, anchor="w")
    ctk.CTkLabel(win, text="Clique nos itens para marcar/desmarcar a devolucao:",
                 text_color="#888888").pack(padx=12, anchor="w")

    # tk.Frame puro — CTkFrame pode ocultar Treeview em Toplevel em alguns temas
    frame_tree = tk.Frame(win)
    frame_tree.pack(fill="both", expand=True, padx=12, pady=8)

    cols = ("sel","item","produto","qtd","preco","subtotal")
    tree = ttk.Treeview(frame_tree, columns=cols, show="headings", selectmode="none")
    tree.heading("sel",      text="");        tree.column("sel",      width=32,  anchor="center")
    tree.heading("item",     text="No");      tree.column("item",     width=40,  anchor="center")
    tree.heading("produto",  text="Produto"); tree.column("produto",  width=290)
    tree.heading("qtd",      text="Qtd");     tree.column("qtd",      width=70,  anchor="center")
    tree.heading("preco",    text="Preco");   tree.column("preco",    width=90,  anchor="e")
    tree.heading("subtotal", text="Subtotal");tree.column("subtotal", width=90,  anchor="e")

    sb_tree = ttk.Scrollbar(frame_tree, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb_tree.set)
    sb_tree.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    # tag_configure ANTES dos inserts
    tree.tag_configure("selecionado", background="#1a4a1a", foreground="#aaffaa")

    selecionados = {}; iids_map = {}
    for idx, it in enumerate(itens, 1):
        iv_id, nome, qtd, preco, sub, prod_id, codigo = it
        try: qtd_f = float(qtd)
        except: qtd_f = 0.0
        qtd_s = f"{qtd_f:.3f}".rstrip("0").rstrip(".") if not qtd_f.is_integer() else str(int(qtd_f))
        iid = tree.insert("", tk.END, values=(
            "☐", idx, (nome or codigo or "?")[:42],
            qtd_s, f"{float(preco or 0):.2f}", f"{float(sub or 0):.2f}"))
        selecionados[iid] = False
        iids_map[iid] = it

    lbl_total_sel = ctk.CTkLabel(win, text="Total a devolver: R$ 0,00",
                                  font=ctk.CTkFont(size=12, weight="bold"))
    lbl_total_sel.pack(anchor="w", padx=16, pady=(0,4))

    def atualizar_total():
        total = sum(float(iids_map[i][4] or 0) for i, s in selecionados.items() if s)
        lbl_total_sel.configure(text=f"Total a devolver: R$ {total:.2f}")

    def toggle(event):
        iid = tree.identify_row(event.y)
        if not iid: return
        selecionados[iid] = not selecionados[iid]
        vals = list(tree.item(iid)["values"])
        vals[0] = "✔" if selecionados[iid] else "☐"
        tree.item(iid, values=vals,
                  tags=("selecionado",) if selecionados[iid] else ())
        atualizar_total()

    tree.bind("<ButtonRelease-1>", toggle)

    def selecionar_todos():
        for iid in selecionados:
            selecionados[iid] = True
            vals = list(tree.item(iid)["values"]); vals[0] = "✔"
            tree.item(iid, values=vals, tags=("selecionado",))
        atualizar_total()

    def prosseguir():
        a_devolver = [iids_map[iid] for iid, sel in selecionados.items() if sel]
        if not a_devolver:
            messagebox.showwarning("Aviso","Selecione ao menos um item."); return
        win.destroy()
        _passo2_cupom(parent_win, venda_id, a_devolver, on_sucesso)

    frame_bt1 = tk.Frame(win)
    frame_bt1.pack(fill="x", padx=12, pady=(0,12))
    ctk.CTkButton(frame_bt1, text="Selecionar Todos", fg_color="#2d89ef",
                  command=selecionar_todos).pack(side="left", padx=6)
    ctk.CTkButton(frame_bt1, text="Prosseguir ->", fg_color="#28a745",
                  command=prosseguir).pack(side="right", padx=6)
    ctk.CTkButton(frame_bt1, text="Cancelar", fg_color="#6c757d",
                  command=win.destroy).pack(side="right", padx=6)
    win.bind("<Escape>", lambda e: win.destroy())


def _passo2_cupom(parent, venda_id, a_devolver, on_sucesso):
    """Passo 2: perguntar se quer cupom de devolução."""
    parent_win = parent.winfo_toplevel()
    win = ctk.CTkToplevel(parent_win)
    win.title("Cupom de Devolucao")
    win.geometry("340x150")
    win.transient(parent_win)
    win.lift(); win.focus_force()
    win.after(100, win.grab_set)
    win.resizable(False, False)

    ctk.CTkLabel(win, text="Deseja gerar o cupom de devolucao?",
                 font=ctk.CTkFont(size=13)).pack(pady=(24,12))
    frame_bt = ctk.CTkFrame(win); frame_bt.pack()

    def com_cupom():
        win.destroy()
        _passo3_resumo(parent, venda_id, a_devolver, imprimir=True, on_sucesso=on_sucesso)

    def sem_cupom():
        win.destroy()
        _passo3_resumo(parent, venda_id, a_devolver, imprimir=False, on_sucesso=on_sucesso)

    ctk.CTkButton(frame_bt, text="Sim (Enter)", fg_color="#28a745",
                  width=120, command=com_cupom).pack(side="left", padx=10)
    ctk.CTkButton(frame_bt, text="Nao (ESC)", fg_color="#6c757d",
                  width=120, command=sem_cupom).pack(side="left", padx=10)
    win.bind("<Return>", lambda e: com_cupom())
    win.bind("<Escape>", lambda e: sem_cupom())


def _passo3_resumo(parent, venda_id, a_devolver, imprimir, on_sucesso):
    """Passo 3: mostrar resumo dos itens + campo motivo + finalizar."""
    parent_win = parent.winfo_toplevel()
    total_dev = sum(float(it[4] or 0) for it in a_devolver)

    win = ctk.CTkToplevel(parent_win)
    win.title(f"Resumo da Devolucao — Venda No {venda_id}")
    win.geometry("620x480")
    win.transient(parent_win)
    win.lift(); win.focus_force()
    win.after(100, win.grab_set)

    ctk.CTkLabel(win, text=f"Resumo da Devolucao — Venda No {venda_id}",
                 font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(12,4), padx=12, anchor="w")

    # Tabela dos itens devolvidos — tk.Frame puro
    frame_tree = tk.Frame(win)
    frame_tree.pack(fill="both", expand=True, padx=12, pady=6)
    cols = ("produto","qtd","preco","subtotal")
    tree = ttk.Treeview(frame_tree, columns=cols, show="headings")
    tree.heading("produto","Produto");  tree.column("produto",  width=300)
    tree.heading("qtd","Qtd");          tree.column("qtd",      width=70,  anchor="center")
    tree.heading("preco","Preco Un.");  tree.column("preco",    width=100, anchor="e")
    tree.heading("subtotal","Subtotal");tree.column("subtotal", width=100, anchor="e")
    tree.pack(fill="both", expand=True)

    for it in a_devolver:
        iv_id, nome, qtd, preco, sub, prod_id, codigo = it
        try: qtd_f=float(qtd)
        except: qtd_f=0.0
        qtd_s = f"{qtd_f:.3f}".rstrip("0").rstrip(".") if not qtd_f.is_integer() else str(int(qtd_f))
        tree.insert("", tk.END, values=(
            (nome or codigo or "?")[:40], qtd_s,
            f"{float(preco or 0):.2f}", f"{float(sub or 0):.2f}"))

    # Total devolvido
    frame_tot = ctk.CTkFrame(win); frame_tot.pack(fill="x", padx=12, pady=(0,4))
    ctk.CTkLabel(frame_tot, text=f"Total devolvido: R$ {total_dev:.2f}",
                 font=ctk.CTkFont(size=13, weight="bold"),
                 text_color="#FFA500").pack(side="left", padx=8)

    # Motivo
    frame_motivo = ctk.CTkFrame(win); frame_motivo.pack(fill="x", padx=12, pady=(4,8))
    ctk.CTkLabel(frame_motivo, text="Motivo da devolucao:").pack(side="left", padx=(6,8))
    var_motivo = ctk.StringVar(value=MOTIVOS_DEVOLUCAO[0])
    combo_motivo = ctk.CTkComboBox(frame_motivo, values=MOTIVOS_DEVOLUCAO,
                                    variable=var_motivo, width=180)
    combo_motivo.pack(side="left", padx=4)

    frame_bt = ctk.CTkFrame(win); frame_bt.pack(fill="x", padx=12, pady=(0,12))

    def finalizar():
        motivo = var_motivo.get() or MOTIVOS_DEVOLUCAO[0]
        try:
            conn = get_connection(); cur = conn.cursor()
            conn.start_transaction()

            # Garante que a tabela de devoluções existe
            cur.execute("""
                CREATE TABLE IF NOT EXISTS devolucoes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    venda_id INT NOT NULL,
                    motivo VARCHAR(100),
                    total_devolvido DECIMAL(12,2),
                    data_devolucao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (venda_id) REFERENCES vendas(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS devolucao_itens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    devolucao_id INT NOT NULL,
                    produto_id INT,
                    quantidade DECIMAL(12,6),
                    preco_unitario DECIMAL(10,2),
                    subtotal DECIMAL(10,2),
                    FOREIGN KEY (devolucao_id) REFERENCES devolucoes(id) ON DELETE CASCADE
                )
            """)

            # Insere cabeçalho da devolução
            cur.execute("""
                INSERT INTO devolucoes (venda_id, motivo, total_devolvido)
                VALUES (%s, %s, %s)
            """, (venda_id, motivo, total_dev))
            dev_id = cur.lastrowid

            for it in a_devolver:
                iv_id, nome, qtd, preco, sub, prod_id, codigo = it
                try: qtd_f=float(qtd)
                except: qtd_f=0.0
                # Improprio: NÃO devolve ao estoque (produto descartado)
                devolver_estoque = (motivo.lower() != "improprio")
                if prod_id and devolver_estoque:
                    cur.execute("""
                        UPDATE produtos SET estoque_inicial=estoque_inicial+%s WHERE id=%s
                    """, (qtd_f, prod_id))
                    try:
                        cur.execute("""
                            INSERT INTO estoque_movimentos
                                (produto_id,tipo,quantidade,referencia_tipo,referencia_id,motivo)
                            VALUES(%s,'entrada',%s,'devolucao',%s,%s)
                        """, (prod_id, qtd_f, venda_id, motivo))
                    except Exception: pass
                elif prod_id and not devolver_estoque:
                    # Registra saída por descarte (impróprio)
                    try:
                        cur.execute("""
                            INSERT INTO estoque_movimentos
                                (produto_id,tipo,quantidade,referencia_tipo,referencia_id,motivo)
                            VALUES(%s,'saida',%s,'devolucao',%s,%s)
                        """, (prod_id, qtd_f, venda_id, "Descarte - Improprio"))
                    except Exception: pass
                # Registra item na devolução
                cur.execute("""
                    INSERT INTO devolucao_itens (devolucao_id, produto_id, quantidade, preco_unitario, subtotal)
                    VALUES (%s, %s, %s, %s, %s)
                """, (dev_id, prod_id, qtd_f, float(preco or 0), float(sub or 0)))

            conn.commit(); cur.close(); conn.close()

            # Imprime cupom se solicitado
            if imprimir:
                _imprimir_cupom_devolucao(venda_id, dev_id, a_devolver, total_dev, motivo)

            messagebox.showinfo("Sucesso",
                f"Devolucao No {dev_id} registrada com sucesso!\n"
                f"Motivo: {motivo}\nTotal: R$ {total_dev:.2f}")
            win.destroy()
            if on_sucesso: on_sucesso()

        except Exception as e:
            try: conn.rollback()
            except: pass
            messagebox.showerror("Erro", f"Falha ao registrar devolucao:\n{e}")

    ctk.CTkButton(frame_bt, text="✔ Finalizar Devolucao", fg_color="#28a745",
                  command=finalizar).pack(side="left", padx=6)
    ctk.CTkButton(frame_bt, text="Cancelar", fg_color="#d9534f",
                  command=win.destroy).pack(side="right", padx=6)
    win.bind("<Escape>", lambda e: win.destroy())


def _imprimir_cupom_devolucao(venda_id, dev_id, a_devolver, total_dev, motivo):
    """Imprime cupom de devolução na impressora térmica."""
    try:
        import win32print
    except ImportError:
        messagebox.showwarning("Impressao", "pywin32 nao instalado.\npip install pywin32"); return

    LARGURA = 48
    def _l(c="-"): return c * LARGURA
    def _c2(e, d, w=LARGURA):
        sp = w - len(e) - len(d); return e + " " * max(sp,1) + d
    def _txt(s):
        s = unicodedata.normalize("NFD", str(s)).encode("ascii","ignore").decode("ascii")
        return s.encode("cp850", errors="replace")

    ESC=b'\x1b'; GS=b'\x1d'
    INIT=ESC+b'@'; BOLD_ON=ESC+b'E\x01'; BOLD_OFF=ESC+b'E\x00'
    AC=ESC+b'a\x01'; AL=ESC+b'a\x00'; DBL_ON=GS+b'!\x11'; DBL_OFF=GS+b'!\x00'
    CUT=GS+b'V\x41\x03'

    now = datetime.now()
    buf = bytearray(INIT)
    buf += AC + DBL_ON + BOLD_ON + _txt("Mercearia Godoi\n") + DBL_OFF + BOLD_OFF
    buf += _txt("Rua: Antonia Rosa de Melo Bolanho, 40\n".center(LARGURA))
    buf += _txt("Jd. Nova Biritiba - Biritiba Mirim - SP\n".center(LARGURA))
    buf += _txt("Telefone: (11) 97147-4599\n".center(LARGURA))
    buf += _txt(_l() + "\n")
    buf += BOLD_ON + _txt("CUPOM DE DEVOLUCAO\n".center(LARGURA)) + BOLD_OFF
    buf += _txt(_l() + "\n")
    buf += AL
    buf += _txt(f"Devolucao No: {dev_id}\n")
    buf += _txt(f"Venda No    : {venda_id}\n")
    buf += _txt(f"Data        : {now.strftime('%d/%m/%Y %H:%M:%S')}\n")
    buf += _txt(f"Motivo      : {motivo}\n")
    buf += _txt(_l() + "\n")
    buf += BOLD_ON + _txt(_c2("PRODUTO", "QTD   PRECO  SUBTOT") + "\n") + BOLD_OFF
    buf += _txt(_l() + "\n")

    for it in a_devolver:
        iv_id, nome, qtd, preco, sub, prod_id, codigo = it
        try: qtd_f=float(qtd)
        except: qtd_f=0.0
        qtd_s = f"{qtd_f:.3f}".rstrip("0").rstrip(".") if not qtd_f.is_integer() else str(int(qtd_f))
        buf += _txt((nome or codigo or "?")[:LARGURA] + "\n")
        buf += _txt(f"  {qtd_s} x{float(preco or 0):>7.2f} ={float(sub or 0):>8.2f}\n")

    buf += _txt(_l() + "\n")
    buf += BOLD_ON + _txt(_c2("TOTAL DEVOLVIDO", f"R$ {total_dev:.2f}") + "\n") + BOLD_OFF
    buf += _txt(_l() + "\n")
    buf += AC + _txt("Obrigado pela preferencia!\n")
    buf += _txt(f"Mercearia Godoi - {now.strftime('%d/%m/%Y')}\n")
    buf += _txt(_l() + "\n")
    buf += b'\n' * 4 + CUT

    NOME_IMP = "EPSON TM-T20X"
    try:
        imps = [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        nome_imp = next((p for p in imps if NOME_IMP.upper() in p.upper()),
                        win32print.GetDefaultPrinter())
        hp = win32print.OpenPrinter(nome_imp)
        try:
            hj = win32print.StartDocPrinter(hp, 1, ("Cupom Devolucao", None, "RAW"))
            try:
                win32print.StartPagePrinter(hp)
                win32print.WritePrinter(hp, bytes(buf))
                win32print.EndPagePrinter(hp)
            finally: win32print.EndDocPrinter(hp)
        finally: win32print.ClosePrinter(hp)
    except Exception as e:
        messagebox.showwarning("Impressao", f"Erro ao imprimir:\n{e}")


# ══════════════════════════════════════════════════════════════════════
#  POPUP DE BUSCA DE PRODUTO (filtro de item em tempo real)
# ══════════════════════════════════════════════════════════════════════

class PopupBuscaProduto(tk.Toplevel):
    """
    Popup de busca em tempo real que aparece ao focar no campo de item.
    Pesquisa por nome OU código enquanto o usuário digita.
    """
    def __init__(self, parent, entry_widget, on_selecao):
        super().__init__(parent)
        self.entry       = entry_widget
        self.on_selecao  = on_selecao
        self.overrideredirect(True)
        self.resizable(False, False)

        self._frame = tk.Frame(self, bg="#2b2b2b", bd=1, relief="solid")
        self._frame.pack(fill="both", expand=True)

        self._tree = ttk.Treeview(self._frame,
                                   columns=("codigo","nome","preco"),
                                   show="headings", height=8)
        self._tree.heading("codigo", text="Codigo"); self._tree.column("codigo", width=100)
        self._tree.heading("nome",   text="Nome");   self._tree.column("nome",   width=240)
        self._tree.heading("preco",  text="Preco");  self._tree.column("preco",  width=80, anchor="e")
        self._tree.pack(fill="both", expand=True, padx=4, pady=4)
        self._tree.bind("<ButtonRelease-1>", self._confirmar)
        self._tree.bind("<Return>", self._confirmar)

        self._posicionar()
        self.bind("<Escape>", lambda e: self.fechar())
        self._tree.bind("<Escape>", lambda e: self.fechar())

        # Atualiza ao mudar o texto do entry
        self.entry.bind("<KeyRelease>", self._on_key, add="+")
        self.entry.bind("<FocusOut>",   self._on_focus_out, add="+")
        self._buscar(self.entry.get().strip())

    def _posicionar(self):
        self.update_idletasks()
        try:
            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height() + 2
        except Exception:
            return
        sw = self.winfo_screenwidth(); w = 430
        if x + w > sw: x = sw - w - 4
        self.geometry(f"{w}x220+{x}+{y}")

    def _on_key(self, event=None):
        self._buscar(self.entry.get().strip())

    def _on_focus_out(self, event=None):
        # Fecha apenas se o foco foi para fora do popup e do entry
        try:
            fw = self.focus_get()
            if fw and (str(fw).startswith(str(self)) or fw == self.entry):
                return
        except Exception:
            pass
        self.after(150, self._verificar_foco)

    def _verificar_foco(self):
        try:
            fw = self.focus_get()
            if fw and str(fw).startswith(str(self)):
                return
            self.fechar()
        except Exception:
            self.fechar()

    def _buscar(self, termo):
        for i in self._tree.get_children(): self._tree.delete(i)
        if not termo: return
        try:
            conn = get_connection(); cur = conn.cursor()
            p = f"%{termo.upper()}%"
            cur.execute("""
                SELECT codigo, nome, preco_venda FROM produtos
                WHERE UPPER(nome) LIKE %s OR UPPER(codigo) LIKE %s
                ORDER BY nome LIMIT 50
            """, (p, p))
            for r in cur.fetchall():
                try: preco_s = f"{float(r[2]):.2f}"
                except: preco_s = "0.00"
                self._tree.insert("", tk.END, values=(r[0], r[1], preco_s))
            cur.close(); conn.close()
        except Exception:
            pass

    def _confirmar(self, event=None):
        sel = self._tree.selection()
        if not sel: return
        vals = self._tree.item(sel[0])["values"]
        self.fechar()
        self.on_selecao(str(vals[0]), str(vals[1]))

    def fechar(self):
        try:
            self.entry.unbind("<KeyRelease>")
            self.entry.unbind("<FocusOut>")
        except Exception: pass
        try: self.destroy()
        except Exception: pass


# ══════════════════════════════════════════════════════════════════════
#  CONSTRUÇÃO DA TELA DE VENDAS (reutilizável inline ou Toplevel)
# ══════════════════════════════════════════════════════════════════════

def _construir_tela_vendas(container, parent_win):
    """
    Constrói todos os widgets da tela de vendas dentro de `container`.
    parent_win é a janela raiz para diálogos modais.
    """
    filtros_ativos = {}
    formas_filtro_selecionadas = []
    _popup_item_ref = {"popup": None}

    # ── layout ──────────────────────────────────────────────────────
    frame_filtros_bar    = ctk.CTkFrame(container)
    frame_filtros_bar.pack(fill="x", padx=6, pady=(6,0))

    frame_top = ctk.CTkFrame(container)
    frame_top.pack(fill="x", padx=6, pady=(4,0))

    frame_rodape_filtros = ctk.CTkFrame(container, height=36, fg_color="#1e1e1e")
    frame_rodape_filtros.pack(fill="x", padx=6, pady=(2,0))
    frame_rodape_filtros.pack_propagate(False)

    frame_bottom = ctk.CTkFrame(container)
    frame_bottom.pack(fill="both", expand=True, padx=6, pady=(4,0))

    frame_botoes = ctk.CTkFrame(container)
    frame_botoes.pack(fill="x", padx=6, pady=(4,6))

    # ── filtros linha 1 ─────────────────────────────────────────────
    linha1 = ctk.CTkFrame(frame_filtros_bar)
    linha1.pack(fill="x", padx=4, pady=(4,2))

    ctk.CTkLabel(linha1, text="De:").pack(side="left", padx=(4,2))
    entry_de = ctk.CTkEntry(linha1, width=108, placeholder_text="DD/MM/AAAA")
    entry_de.pack(side="left", padx=2)
    ctk.CTkButton(linha1, text="📅", width=30, fg_color="#555",
                  command=lambda: abrir_calendario(parent_win, entry_de)).pack(side="left", padx=(0,6))

    ctk.CTkLabel(linha1, text="Ate:").pack(side="left", padx=(2,2))
    entry_ate = ctk.CTkEntry(linha1, width=108, placeholder_text="DD/MM/AAAA")
    entry_ate.pack(side="left", padx=2)
    ctk.CTkButton(linha1, text="📅", width=30, fg_color="#555",
                  command=lambda: abrir_calendario(parent_win, entry_ate)).pack(side="left", padx=(0,8))

    ctk.CTkLabel(linha1, text="Horario De:").pack(side="left", padx=(2,2))
    entry_hora_de = ctk.CTkEntry(linha1, width=65, placeholder_text="HH:MM")
    entry_hora_de.pack(side="left", padx=2)
    ctk.CTkLabel(linha1, text="Ate:").pack(side="left", padx=(4,2))
    entry_hora_ate = ctk.CTkEntry(linha1, width=65, placeholder_text="HH:MM")
    entry_hora_ate.pack(side="left", padx=2)

    # Nº Venda + botão pesquisar
    ctk.CTkLabel(linha1, text="No Venda:").pack(side="left", padx=(14,2))
    entry_num_venda = ctk.CTkEntry(linha1, width=80)
    entry_num_venda.pack(side="left", padx=2)
    btn_pesq_num = ctk.CTkButton(linha1, text="🔍", width=36, fg_color="#2d89ef")
    btn_pesq_num.pack(side="left", padx=(2,4))

    # ── filtros linha 2 ─────────────────────────────────────────────
    linha2 = ctk.CTkFrame(frame_filtros_bar)
    linha2.pack(fill="x", padx=4, pady=(2,4))

    ctk.CTkLabel(linha2, text="Pagamento:").pack(side="left", padx=(4,2))
    _fp_nome_id = {}
    formas_lista = ["Selecione..."]
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT id, nome FROM formas_pagamento WHERE ativo=1 ORDER BY nome")
        _fps = cur.fetchall(); cur.close(); conn.close()
        formas_lista += [f[1] for f in _fps]
        _fp_nome_id = {f[1]: f[0] for f in _fps}
    except Exception: pass

    combo_pagamento = ctk.CTkComboBox(linha2, values=formas_lista, width=140)
    combo_pagamento.set("Selecione...")
    combo_pagamento.pack(side="left", padx=2)

    def adicionar_filtro_pagamento():
        nome = combo_pagamento.get()
        if not nome or nome == "Selecione...": return
        fid = _fp_nome_id.get(nome)
        if fid is None: return
        for fid_ex, _ in formas_filtro_selecionadas:
            if fid_ex == fid: return
        formas_filtro_selecionadas.append((fid, nome))
        chave = f"pag_{fid}"
        def _rem_pag(_fid=fid, _nome=nome):
            if (_fid, _nome) in formas_filtro_selecionadas:
                formas_filtro_selecionadas.remove((_fid, _nome))
        filtros_ativos[chave] = {"label": f"Pagto: {nome}", "remover": _rem_pag}
        atualizar_rodape(); carregar_vendas()

    ctk.CTkButton(linha2, text="+ Add", fg_color="#2d89ef", width=70,
                  command=adicionar_filtro_pagamento).pack(side="left", padx=(2,10))

    # Filtro de item — popup em tempo real ao focar
    ctk.CTkLabel(linha2, text="Item:").pack(side="left", padx=(4,2))
    entry_item = ctk.CTkEntry(linha2, width=170, placeholder_text="Nome ou codigo...")
    entry_item.pack(side="left", padx=2)
    _item_selecionado = {"codigo": None, "nome": None}

    def abrir_popup_item(event=None):
        if _popup_item_ref["popup"]:
            try: _popup_item_ref["popup"].fechar()
            except: pass
        def on_sel(cod, nom):
            _item_selecionado["codigo"] = cod
            _item_selecionado["nome"]   = nom
            entry_item.delete(0, tk.END)
            entry_item.insert(0, f"{cod} — {nom[:28]}")
        p = PopupBuscaProduto(parent_win, entry_item, on_sel)
        _popup_item_ref["popup"] = p

    entry_item.bind("<FocusIn>", abrir_popup_item)

    def adicionar_filtro_item():
        cod  = _item_selecionado.get("codigo")
        nome = _item_selecionado.get("nome")
        txt  = entry_item.get().strip()
        if not cod and not txt: return
        chave_cod = cod or txt
        chave = f"item_{chave_cod}"
        if chave in filtros_ativos: return
        filtros_ativos[chave] = {"label": f"Item: {(nome or txt)[:22]}", "remover": None}
        atualizar_rodape(); carregar_vendas()
        entry_item.delete(0, tk.END)
        _item_selecionado["codigo"] = None; _item_selecionado["nome"] = None

    ctk.CTkButton(linha2, text="+ Add", fg_color="#2d89ef", width=70,
                  command=adicionar_filtro_item).pack(side="left", padx=(2,10))

    # Valor
    ctk.CTkLabel(linha2, text="Valor R$:").pack(side="left", padx=(4,2))
    entry_val_min = ctk.CTkEntry(linha2, width=70, placeholder_text="Min")
    entry_val_min.pack(side="left", padx=2)
    ctk.CTkLabel(linha2, text="–").pack(side="left")
    entry_val_max = ctk.CTkEntry(linha2, width=70, placeholder_text="Max")
    entry_val_max.pack(side="left", padx=(2,8))

    btn_filtrar   = ctk.CTkButton(linha2, text="🔍 Filtrar",   fg_color="#28a745", width=100)
    btn_limpar    = ctk.CTkButton(linha2, text="✖ Limpar",    fg_color="#6c757d",  width=86)
    btn_atualizar = ctk.CTkButton(linha2, text="↺ Atualizar", fg_color="#FFA500",  width=100)
    btn_filtrar.pack(side="left", padx=4)
    btn_limpar.pack(side="left", padx=4)
    btn_atualizar.pack(side="left", padx=4)

    btn_remover  = ctk.CTkButton(linha2, text="🗑 Remover",  fg_color="#d9534f", width=100)
    btn_devolver = ctk.CTkButton(linha2, text="↩ Devolver", fg_color="#17a2b8", width=100)
    btn_remover.pack(side="right", padx=4)
    btn_devolver.pack(side="right", padx=4)

    # ── tabela vendas ───────────────────────────────────────────────
    cols_v = ("id","data","total","cliente","formas_pag")
    tree_vendas = ttk.Treeview(frame_top, columns=cols_v, show="headings", height=9)
    tree_vendas.heading("id",         text="No Venda");  tree_vendas.column("id",         width=80,  anchor="center")
    tree_vendas.heading("data",       text="Data/Hora"); tree_vendas.column("data",       width=160)
    tree_vendas.heading("total",      text="Total R$");  tree_vendas.column("total",      width=100, anchor="e")
    tree_vendas.heading("cliente",    text="Cliente");   tree_vendas.column("cliente",    width=180)
    tree_vendas.heading("formas_pag", text="Pagamento"); tree_vendas.column("formas_pag", width=260)
    sb = ttk.Scrollbar(frame_top, orient="vertical", command=tree_vendas.yview)
    tree_vendas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tree_vendas.pack(fill="x", padx=(4,0), pady=4)

    lbl_resumo = ctk.CTkLabel(frame_top,
        text="Total: R$ 0,00  |  Vendas: 0  |  Ticket medio: R$ 0,00",
        font=ctk.CTkFont(size=11, weight="bold"))
    lbl_resumo.pack(anchor="e", padx=10, pady=(0,2))

    # ── rodapé filtros ──────────────────────────────────────────────
    ctk.CTkLabel(frame_rodape_filtros, text="Filtros ativos:",
                 text_color="#888888", font=ctk.CTkFont(size=10)).pack(side="left", padx=(8,4))
    frame_tags = ctk.CTkFrame(frame_rodape_filtros, fg_color="transparent")
    frame_tags.pack(side="left", fill="x", expand=True)

    def atualizar_rodape():
        for w in frame_tags.winfo_children(): w.destroy()
        if not filtros_ativos:
            ctk.CTkLabel(frame_tags, text="Nenhum filtro aplicado",
                         text_color="#666666", font=ctk.CTkFont(size=10)).pack(side="left", padx=4)
            return
        for chave, info in list(filtros_ativos.items()):
            fr = ctk.CTkFrame(frame_tags, fg_color="#3a3a3a", corner_radius=8)
            fr.pack(side="left", padx=3, pady=4)
            ctk.CTkLabel(fr, text=info["label"], font=ctk.CTkFont(size=10),
                         text_color="#dddddd").pack(side="left", padx=(6,2))
            def _rm(ch=chave):
                fn = filtros_ativos.get(ch, {}).get("remover")
                if fn: fn()
                filtros_ativos.pop(ch, None)
                atualizar_rodape(); carregar_vendas()
            ctk.CTkButton(fr, text="✕", width=20, height=18, fg_color="#555555",
                          font=ctk.CTkFont(size=9), command=_rm).pack(side="left", padx=(0,4))

    atualizar_rodape()

    # ── detalhes ────────────────────────────────────────────────────
    bottom_left  = ctk.CTkFrame(frame_bottom)
    bottom_left.pack(side="left", fill="both", expand=True, padx=(0,4))
    bottom_right = ctk.CTkFrame(frame_bottom, width=300)
    bottom_right.pack(side="left", fill="y")

    cols_i = ("item","produto","qtd","vr_venda","subtotal","custo","lucro")
    tree_itens = ttk.Treeview(bottom_left, columns=cols_i, show="headings")
    tree_itens.heading("item",    text="No");      tree_itens.column("item",    width=36, anchor="center")
    tree_itens.heading("produto", text="Produto"); tree_itens.column("produto", width=200)
    tree_itens.heading("qtd",     text="Qtd");     tree_itens.column("qtd",     width=60, anchor="center")
    tree_itens.heading("vr_venda",text="Preco");   tree_itens.column("vr_venda",width=75, anchor="e")
    tree_itens.heading("subtotal",text="Subtotal");tree_itens.column("subtotal",width=75, anchor="e")
    tree_itens.heading("custo",   text="Custo");   tree_itens.column("custo",   width=65, anchor="e")
    tree_itens.heading("lucro",   text="Lucro");   tree_itens.column("lucro",   width=65, anchor="e")
    tree_itens.pack(fill="both", expand=True, padx=4, pady=4)

    ctk.CTkLabel(bottom_right, text="Pagamentos / Obs.",
                 font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="nw", pady=(4,2), padx=6)
    frame_pags = ctk.CTkFrame(bottom_right); frame_pags.pack(fill="x", padx=6, pady=2)
    tree_pags = ttk.Treeview(frame_pags, columns=("forma","valor","troco"), show="headings", height=5)
    tree_pags.heading("forma", text="Forma");  tree_pags.column("forma", width=110)
    tree_pags.heading("valor", text="Valor");  tree_pags.column("valor", width=80, anchor="e")
    tree_pags.heading("troco", text="Troco");  tree_pags.column("troco", width=80, anchor="e")
    tree_pags.pack(fill="x", padx=4, pady=2)
    txt_obs = tk.Text(bottom_right, height=4, width=32)
    txt_obs.pack(fill="x", padx=6, pady=(4,6))

    # ── botões inferiores ───────────────────────────────────────────
    btn_rel        = ctk.CTkButton(frame_botoes, text="📊 Relatorios", fg_color="#6c757d")
    btn_reimprimir = ctk.CTkButton(frame_botoes, text="🖨 Reimprimir", fg_color="#FFA500")
    btn_rel.pack(side="left", padx=6, pady=4)
    btn_reimprimir.pack(side="left", padx=6)

    # ── funções de dados ────────────────────────────────────────────

    def _conv_data(dt_txt, end_of_day=False):
        txt = (dt_txt or "").strip()
        if not txt: return None
        try:
            d = datetime.strptime(txt, "%d/%m/%Y")
            return d.strftime(f"%Y-%m-%d {'23:59:59' if end_of_day else '00:00:00'}")
        except Exception: return None

    def carregar_vendas():
        for i in tree_vendas.get_children(): tree_vendas.delete(i)

        de_sql  = _conv_data(entry_de.get(),  False)
        ate_sql = _conv_data(entry_ate.get(), True)
        hd = entry_hora_de.get().strip(); ha = entry_hora_ate.get().strip()
        if de_sql and hd:  de_sql  = de_sql[:10]  + " " + hd  + ":00"
        if ate_sql and ha: ate_sql = ate_sql[:10] + " " + ha  + ":59"
        nv = entry_num_venda.get().strip()
        try: vmin = float(entry_val_min.get().strip().replace(",",".")) if entry_val_min.get().strip() else None
        except: vmin = None
        try: vmax = float(entry_val_max.get().strip().replace(",",".")) if entry_val_max.get().strip() else None
        except: vmax = None

        conds=[]; params=[]
        if de_sql:   conds.append("v.data_venda >= %s"); params.append(de_sql)
        if ate_sql:  conds.append("v.data_venda <= %s"); params.append(ate_sql)
        if nv:       conds.append("v.id = %s");          params.append(nv)
        if vmin is not None: conds.append("v.valor_total >= %s"); params.append(vmin)
        if vmax is not None: conds.append("v.valor_total <= %s"); params.append(vmax)
        for fid, _ in formas_filtro_selecionadas:
            conds.append("EXISTS (SELECT 1 FROM pagamentos pg WHERE pg.venda_id=v.id AND pg.forma_id=%s)")
            params.append(fid)
        for chave in filtros_ativos:
            if chave.startswith("item_"):
                cod_item = chave[5:]
                conds.append("""EXISTS (
                    SELECT 1 FROM itens_venda iv LEFT JOIN produtos p ON p.id=iv.produto_id
                    WHERE iv.venda_id=v.id AND (UPPER(p.codigo) LIKE %s OR UPPER(p.nome) LIKE %s)
                )""")
                params.append(f"%{cod_item.upper()}%"); params.append(f"%{cod_item.upper()}%")

        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        sql = f"""
            SELECT v.id, v.data_venda, v.valor_total, v.cliente,
                   GROUP_CONCAT(DISTINCT fp.nome ORDER BY fp.nome SEPARATOR ', ') AS formas
            FROM vendas v
            LEFT JOIN pagamentos pg ON pg.venda_id=v.id
            LEFT JOIN formas_pagamento fp ON fp.id=pg.forma_id
            {where}
            GROUP BY v.id, v.data_venda, v.valor_total, v.cliente
            ORDER BY v.data_venda DESC LIMIT 1000
        """
        total_p=0.0; n_v=0
        try:
            conn=get_connection(); cur=conn.cursor()
            cur.execute(sql, params)
            for row in cur.fetchall():
                vid, dt, total, cliente, formas = row
                dt_s = dt.strftime("%d/%m/%Y %H:%M:%S") if isinstance(dt, datetime) else str(dt)
                tree_vendas.insert("", tk.END, values=(vid, dt_s, f"{float(total or 0):.2f}",
                                                        cliente or "", formas or ""))
                total_p += float(total or 0); n_v += 1
            cur.close(); conn.close()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar vendas:\n{e}")
        tm = total_p/n_v if n_v>0 else 0.0
        lbl_resumo.configure(text=f"Total: R$ {total_p:.2f}  |  Vendas: {n_v}  |  Ticket medio: R$ {tm:.2f}")

    def carregar_detalhes(venda_id):
        for i in tree_itens.get_children(): tree_itens.delete(i)
        for i in tree_pags.get_children():  tree_pags.delete(i)
        txt_obs.delete("1.0", tk.END)
        try:
            conn=get_connection(); cur=conn.cursor()
            cur.execute("""
                SELECT iv.id, p.nome, iv.quantidade, iv.preco_unitario, iv.subtotal, p.custo
                FROM itens_venda iv LEFT JOIN produtos p ON p.id=iv.produto_id
                WHERE iv.venda_id=%s ORDER BY iv.id
            """, (venda_id,))
            for idx, it in enumerate(cur.fetchall(), 1):
                try: qtd_f=float(it[2])
                except: qtd_f=0.0
                try: pu=float(it[3])
                except: pu=0.0
                try: sub=float(it[4])
                except: sub=qtd_f*pu
                try: cu=float(it[5]) if it[5] else 0.0
                except: cu=0.0
                lucro=sub-(qtd_f*cu)
                qtd_s = f"{qtd_f:.3f}".rstrip("0").rstrip(".") if not qtd_f.is_integer() else str(int(qtd_f))
                tree_itens.insert("", tk.END, values=(f"{idx:03d}", it[1] or "?", qtd_s,
                    f"{pu:.2f}", f"{sub:.2f}", f"{qtd_f*cu:.2f}", f"{lucro:.2f}"))
            cur.execute("""
                SELECT fp.nome, p.valor, p.troco FROM pagamentos p
                LEFT JOIN formas_pagamento fp ON fp.id=p.forma_id WHERE p.venda_id=%s
            """, (venda_id,))
            for r in cur.fetchall():
                tree_pags.insert("", tk.END, values=(r[0] or "", f"{float(r[1] or 0):.2f}", f"{float(r[2] or 0):.2f}"))
            cur.execute("SELECT cliente FROM vendas WHERE id=%s", (venda_id,))
            r=cur.fetchone()
            if r and r[0]: txt_obs.insert("1.0", f"Cliente: {r[0]}")
            cur.close(); conn.close()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar detalhes:\n{e}")

    def _get_vid():
        sel=tree_vendas.selection()
        if not sel: return None
        try: return int(tree_vendas.item(sel[0])["values"][0])
        except: return None

    # ── eventos ─────────────────────────────────────────────────────

    def on_select(event=None):
        vid=_get_vid()
        if vid: carregar_detalhes(vid)

    def pesquisar_num_venda():
        nv = entry_num_venda.get().strip()
        if not nv: return
        for chave in ["num"]: filtros_ativos.pop(chave, None)
        filtros_ativos["num"] = {"label": f"Venda No {nv}",
                                  "remover": lambda: entry_num_venda.delete(0,tk.END)}
        atualizar_rodape(); carregar_vendas()

    def on_filtrar():
        for ch in ["periodo","horario","num","valor"]: filtros_ativos.pop(ch, None)
        de_txt=entry_de.get().strip(); ate_txt=entry_ate.get().strip()
        if de_txt or ate_txt:
            filtros_ativos["periodo"]={"label":f"Periodo: {de_txt or '?'} -> {ate_txt or '?'}",
                "remover":lambda:(entry_de.delete(0,tk.END),entry_ate.delete(0,tk.END))}
        hd=entry_hora_de.get().strip(); ha=entry_hora_ate.get().strip()
        if hd or ha:
            filtros_ativos["horario"]={"label":f"Horario: {hd or '00:00'}-{ha or '23:59'}",
                "remover":lambda:(entry_hora_de.delete(0,tk.END),entry_hora_ate.delete(0,tk.END))}
        nv=entry_num_venda.get().strip()
        if nv:
            filtros_ativos["num"]={"label":f"Venda No {nv}",
                "remover":lambda:entry_num_venda.delete(0,tk.END)}
        vmin=entry_val_min.get().strip(); vmax=entry_val_max.get().strip()
        if vmin or vmax:
            filtros_ativos["valor"]={"label":f"Valor: R${vmin or '0'}-R${vmax or 'inf'}",
                "remover":lambda:(entry_val_min.delete(0,tk.END),entry_val_max.delete(0,tk.END))}
        atualizar_rodape(); carregar_vendas()

    def on_limpar():
        entry_de.delete(0,tk.END); entry_ate.delete(0,tk.END)
        entry_hora_de.delete(0,tk.END); entry_hora_ate.delete(0,tk.END)
        entry_num_venda.delete(0,tk.END)
        entry_val_min.delete(0,tk.END); entry_val_max.delete(0,tk.END)
        combo_pagamento.set("Selecione..."); entry_item.delete(0,tk.END)
        _item_selecionado["codigo"]=None; _item_selecionado["nome"]=None
        formas_filtro_selecionadas.clear()
        filtros_ativos.clear(); atualizar_rodape(); carregar_vendas()

    def on_remover():
        vid=_get_vid()
        if not vid: messagebox.showwarning("Aviso","Selecione uma venda."); return
        if not messagebox.askyesno("Confirmar",f"Remover venda {vid}?"): return
        try:
            conn=get_connection(); cur=conn.cursor()
            cur.execute("DELETE FROM pagamentos WHERE venda_id=%s",(vid,))
            cur.execute("DELETE FROM itens_venda WHERE venda_id=%s",(vid,))
            cur.execute("DELETE FROM vendas WHERE id=%s",(vid,))
            conn.commit(); cur.close(); conn.close()
            carregar_vendas()
            for i in tree_itens.get_children(): tree_itens.delete(i)
            for i in tree_pags.get_children():  tree_pags.delete(i)
            txt_obs.delete("1.0",tk.END)
            messagebox.showinfo("Sucesso","Venda removida.")
        except Exception as e: messagebox.showerror("Erro",f"Falha:\n{e}")

    def on_devolver():
        vid=_get_vid()
        if not vid: messagebox.showwarning("Aviso","Selecione uma venda para devolver."); return
        devolver_venda(parent_win, vid, on_sucesso=carregar_vendas)

    def on_reimprimir():
        vid=_get_vid()
        if not vid: messagebox.showwarning("Aviso","Selecione uma venda."); return
        reimprimir_venda(vid)

    def on_relatorios():
        de_sql  = _conv_data(entry_de.get(), False)
        ate_sql = _conv_data(entry_ate.get(), True)
        _rel_mod.abrir_janela_relatorios(parent_win, de_sql, ate_sql)

    # binds
    entry_de.bind("<Button-1>",  lambda e: abrir_calendario(parent_win, entry_de))
    entry_ate.bind("<Button-1>", lambda e: abrir_calendario(parent_win, entry_ate))
    entry_num_venda.bind("<Return>", lambda e: pesquisar_num_venda())
    btn_pesq_num.configure(command=pesquisar_num_venda)
    btn_filtrar.configure(command=on_filtrar)
    btn_limpar.configure(command=on_limpar)
    btn_atualizar.configure(command=carregar_vendas)
    btn_remover.configure(command=on_remover)
    btn_devolver.configure(command=on_devolver)
    btn_reimprimir.configure(command=on_reimprimir)
    btn_rel.configure(command=on_relatorios)

    tree_vendas.bind("<<TreeviewSelect>>", on_select)
    tree_vendas.bind("<Double-1>", on_select)

    carregar_vendas()


# ══════════════════════════════════════════════════════════════════════
#  PONTOS DE ENTRADA
# ══════════════════════════════════════════════════════════════════════

def mostrar_vendas_inline(frame_main, show_frame_in_main_fn):
    """
    Abre a tela de vendas dentro do frame_main do PDV (sem janela flutuante).
    show_frame_in_main_fn: função do interface.py que troca o frame visível.
    """
    # Obtém a janela raiz a partir do frame_main
    parent_win = frame_main.winfo_toplevel()

    frame_vendas = ctk.CTkFrame(frame_main)
    _construir_tela_vendas(frame_vendas, parent_win)
    show_frame_in_main_fn(frame_vendas)


def mostrar_vendas(parent):
    """Mantido para compatibilidade — abre em Toplevel."""
    janela = ctk.CTkToplevel(parent)
    janela.title("Controle de Vendas Realizadas no PDV")
    sw = parent.winfo_screenwidth(); sh = parent.winfo_screenheight()
    janela.geometry(f"{min(1280,sw-40)}x{min(880,sh-60)}")
    janela.minsize(1100, 750)
    janela.transient(parent); janela.lift(); janela.focus_force()
    _construir_tela_vendas(janela, janela)
    return janela