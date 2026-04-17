import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from datetime import datetime
from datetime import date
import math

# --- Configuração do banco (mesma usada no interface.py) ---
DB_CONFIG = {
    "host": "localhost",
    "user": "pdv",
    "password": "1234",
    "database": "sistema_vendas"
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def has_column(table_name: str, column_name: str) -> bool:
    """
    Verifica se a coluna existe na tabela dentro do schema 'sistema_vendas'.
    Retorna True se existir, False caso contrário.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
            LIMIT 1
        """, (DB_CONFIG["database"], table_name, column_name))
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception:
        return False

# --- Função pública para mostrar a janela de Vendas ---
def mostrar_vendas(parent):
    """
    Abre um Toplevel com a interface de Controle de Vendas.
    parent: janela principal (app) — usada para transient/lift.
    """
    janela = ctk.CTkToplevel(parent)
    janela.title("Controle de Vendas Realizadas no PDV")
    janela.geometry("1100x700")
    janela.transient(parent)
    janela.lift()
    janela.focus_force()

    # Layout: topo (lista de vendas) / rodapé (itens da venda selecionada)
    frame_top = ctk.CTkFrame(janela)
    frame_top.pack(fill="both", expand=False, padx=10, pady=(10,6))

    frame_bottom = ctk.CTkFrame(janela)
    frame_bottom.pack(fill="both", expand=True, padx=10, pady=(6,10))

    # --- Top: filtros e tabela de vendas ---
    filtros = ctk.CTkFrame(frame_top)
    filtros.pack(fill="x", padx=6, pady=6)

    lbl_periodo = ctk.CTkLabel(filtros, text="Período (De / Até):")
    lbl_periodo.pack(side="left", padx=(6,4))
    entry_de = ctk.CTkEntry(filtros, width=180)
    entry_de.insert(0, "")
    entry_de.pack(side="left", padx=4)
    entry_ate = ctk.CTkEntry(filtros, width=180)
    entry_ate.insert(0, "")
    entry_ate.pack(side="left", padx=4)

    btn_filtrar = ctk.CTkButton(filtros, text="Filtrar", fg_color="#2d89ef")
    btn_filtrar.pack(side="left", padx=8)

    btn_atualizar = ctk.CTkButton(filtros, text="Atualizar", fg_color="#FFA500")
    btn_atualizar.pack(side="left", padx=8)

    btn_remover = ctk.CTkButton(filtros, text="Remover", fg_color="#d9534f")
    btn_remover.pack(side="left", padx=8)

    btn_devolver = ctk.CTkButton(filtros, text="Devolver", fg_color="#6c757d")
    btn_devolver.pack(side="left", padx=8)

    # Treeview de vendas
    cols_vendas = ("id", "usuario", "data", "total", "cliente", "avista", "aprazo")
    tree_vendas = ttk.Treeview(frame_top, columns=cols_vendas, show="headings", height=8)
    headings = {
        "id": "Venda",
        "usuario": "Usuário",
        "data": "Data",
        "total": "Total",
        "cliente": "Cliente",
        "avista": "À Vista",
        "aprazo": "A Prazo"
    }
    for c in cols_vendas:
        tree_vendas.heading(c, text=headings[c])
        tree_vendas.column(c, width=120 if c != "data" else 200)
    tree_vendas.pack(fill="x", padx=6, pady=(6,4))

    # Label resumo (ex: total do período)
    lbl_resumo = ctk.CTkLabel(frame_top, text="R$: 0,00", font=ctk.CTkFont(size=16, weight="bold"))
    lbl_resumo.pack(anchor="e", padx=12, pady=(4,0))

    # --- Bottom: detalhes da venda selecionada (itens + pagamentos) ---
    bottom_left = ctk.CTkFrame(frame_bottom)
    bottom_left.pack(side="left", fill="both", expand=True, padx=(0,6))

    bottom_right = ctk.CTkFrame(frame_bottom, width=360)
    bottom_right.pack(side="left", fill="y", padx=(6,0))

    # Itens da venda (Treeview)
    cols_itens = ("item", "produto", "qtd", "vr_venda", "subtotal", "custo", "lucro")
    tree_itens = ttk.Treeview(bottom_left, columns=cols_itens, show="headings")
    for c in cols_itens:
        tree_itens.heading(c, text=c.capitalize())
        tree_itens.column(c, width=110)
    tree_itens.pack(fill="both", expand=True, padx=6, pady=6)

    # Pagamentos e observações
    ctk.CTkLabel(bottom_right, text="Pagamentos / Observações", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="nw", pady=(6,4), padx=6)
    frame_pags = ctk.CTkFrame(bottom_right)
    frame_pags.pack(fill="both", expand=False, padx=6, pady=4)
    tree_pags = ttk.Treeview(frame_pags, columns=("forma", "valor", "troco", "referencia"), show="headings", height=6)
    tree_pags.heading("forma", text="Forma")
    tree_pags.heading("valor", text="Valor")
    tree_pags.heading("troco", text="Troco")
    tree_pags.heading("referencia", text="Ref")
    tree_pags.column("forma", width=120)
    tree_pags.column("valor", width=80)
    tree_pags.column("troco", width=80)
    tree_pags.column("referencia", width=120)
    tree_pags.pack(fill="x", padx=6, pady=6)

    txt_obs = tk.Text(bottom_right, height=6, width=40)
    txt_obs.pack(fill="both", padx=6, pady=(6,12), expand=False)

    # Botões inferiores
    frame_botoes = ctk.CTkFrame(janela)
    frame_botoes.pack(fill="x", padx=10, pady=(0,10))
    btn_pdf = ctk.CTkButton(frame_botoes, text="Gerar PDF", fg_color="#6c757d")
    btn_rel = ctk.CTkButton(frame_botoes, text="Relatórios", fg_color="#6c757d")
    btn_reimprimir = ctk.CTkButton(frame_botoes, text="Reimprimir", fg_color="#6c757d")
    btn_voltar = ctk.CTkButton(frame_botoes, text="Voltar", fg_color="#FFA500", command=janela.destroy)
    btn_pdf.pack(side="left", padx=6)
    btn_rel.pack(side="left", padx=6)
    btn_reimprimir.pack(side="left", padx=6)
    btn_voltar.pack(side="right", padx=6)

    # --- Funções de acesso ao banco e atualização ---
    # Detecta se a coluna usuario_id existe na tabela vendas
    usuario_col_exists = has_column("vendas", "usuario_id")

    def carregar_vendas(de=None, ate=None):
        for i in tree_vendas.get_children():
            tree_vendas.delete(i)
        total_periodo = 0.0
        try:
            conn = get_connection()
            cur = conn.cursor()
            # Monta SELECT adaptando se usuario_id existe
            if usuario_col_exists:
                select_cols = "id, usuario_id, data_venda, valor_total, cliente"
            else:
                # seleciona NULL como usuario para manter a ordem das colunas na interface
                select_cols = "id, NULL AS usuario_id, data_venda, valor_total, cliente"

            sql = f"SELECT {select_cols} FROM vendas"
            params = []
            if de and ate:
                sql += " WHERE data_venda BETWEEN %s AND %s"
                params = [de, ate]
            sql += " ORDER BY data_venda DESC LIMIT 500"
            cur.execute(sql, params)
            for row in cur.fetchall():
                # row: (id, usuario_id_or_null, data_venda, valor_total, cliente)
                vid = row[0]
                uid = row[1] if len(row) > 1 else None
                dt = row[2] if len(row) > 2 else None
                total = row[3] if len(row) > 3 else 0.0
                cliente = row[4] if len(row) > 4 else ""
                dt_str = dt.strftime("%d/%m/%Y %H:%M:%S") if isinstance(dt, datetime) else str(dt)
                avista = total or 0.0
                aprazo = 0.0
                tree_vendas.insert("", tk.END, values=(vid, uid or "", dt_str, f"{total:.2f}", cliente or "", f"{avista:.2f}", f"{aprazo:.2f}"))
                total_periodo += float(total or 0.0)
            cur.close()
            conn.close()
        except mysql.connector.Error as e:
            messagebox.showerror("Erro", f"Falha ao carregar vendas:\n{e}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar vendas:\n{e}")
        lbl_resumo.configure(text=f"R$: {total_periodo:.2f}")

    def carregar_detalhes_venda(venda_id):
        # limpa
        for i in tree_itens.get_children():
            tree_itens.delete(i)
        for i in tree_pags.get_children():
            tree_pags.delete(i)
        txt_obs.delete("1.0", tk.END)
        try:
            conn = get_connection()
            cur = conn.cursor()
            # itens_venda: produto_id -> buscar nome, preco e custo
            cur.execute("""
                SELECT iv.id, p.nome, iv.quantidade, iv.preco_unitario, iv.subtotal, p.custo
                FROM itens_venda iv
                LEFT JOIN produtos p ON p.id = iv.produto_id
                WHERE iv.venda_id = %s
                ORDER BY iv.id
            """, (venda_id,))
            itens = cur.fetchall()

            # Totais auxiliares (opcionais, não alteram interface)
            total_custo = 0.0
            total_lucro = 0.0

            for idx, it in enumerate(itens, start=1):
                # it: (iv.id, p.nome, iv.quantidade, iv.preco_unitario, iv.subtotal, p.custo)
                iid = it[0]
                nome = it[1] or ""
                qtd = it[2] or 0
                preco_unit = it[3] or 0.0
                subtotal = it[4] or 0.0
                custo_unit = it[5] if len(it) > 5 else None

                # garantir tipos numéricos
                try:
                    qtd_val = float(qtd)
                except Exception:
                    qtd_val = 0.0
                try:
                    preco_unit_val = float(preco_unit)
                except Exception:
                    preco_unit_val = 0.0
                try:
                    subtotal_val = float(subtotal)
                except Exception:
                    subtotal_val = qtd_val * preco_unit_val

                try:
                    custo_unit_val = float(custo_unit) if custo_unit is not None else 0.0
                except Exception:
                    custo_unit_val = 0.0

                # custo total do item = quantidade * custo_unit
                custo_total_item = qtd_val * custo_unit_val

                # lucro do item = subtotal - custo_total_item
                lucro_item = subtotal_val - custo_total_item

                # acumular totais
                total_custo += custo_total_item
                total_lucro += lucro_item

                # formata exibição
                # qtd: manter como veio (pode ser inteiro ou decimal)
                qtd_display = f"{qtd_val}".rstrip('0').rstrip('.') if isinstance(qtd_val, float) and not qtd_val.is_integer() else f"{int(qtd_val)}"
                preco_display = f"{preco_unit_val:.2f}"
                subtotal_display = f"{subtotal_val:.2f}"
                custo_display = f"{custo_total_item:.2f}"
                lucro_display = f"{lucro_item:.2f}"

                tree_itens.insert("", tk.END, values=(f"{idx:03d}", nome, qtd_display, preco_display, subtotal_display, custo_display, lucro_display))

            # pagamentos
            cur.execute("""
                SELECT fp.nome, p.valor, p.troco, p.referencia
                FROM pagamentos p
                LEFT JOIN formas_pagamento fp ON fp.id = p.forma_id
                WHERE p.venda_id = %s
            """, (venda_id,))
            for forma, valor, troco, ref in cur.fetchall():
                try:
                    valor_display = f"{float(valor):.2f}"
                except Exception:
                    valor_display = "0.00"
                try:
                    troco_display = f"{float(troco):.2f}"
                except Exception:
                    troco_display = "0.00"
                tree_pags.insert("", tk.END, values=(forma or "", valor_display, troco_display, ref or ""))

            # observacao (se existir na tabela vendas)
            cur.execute("SELECT cliente FROM vendas WHERE id=%s", (venda_id,))
            r = cur.fetchone()
            if r and r[0]:
                txt_obs.insert("1.0", f"Cliente: {r[0]}")

            cur.close()
            conn.close()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar detalhes:\n{e}")

    # --- Eventos e binds ---
    def on_venda_select(event):
        sel = tree_vendas.selection()
        if not sel:
            return
        item = tree_vendas.item(sel[0])["values"]
        try:
            venda_id = int(item[0])
        except Exception:
            return
        carregar_detalhes_venda(venda_id)

    def on_filtrar():
        de = entry_de.get().strip() or None
        ate = entry_ate.get().strip() or None
        # espera datas no formato 'DD/MM/YYYY' ou vazio; converter para 'YYYY-MM-DD HH:MM:SS' se fornecido
        def conv(dt_txt, end_of_day=False):
            if not dt_txt:
                return None
            try:
                d = datetime.strptime(dt_txt, "%d/%m/%Y")
                if end_of_day:
                    return d.strftime("%Y-%m-%d 23:59:59")
                return d.strftime("%Y-%m-%d 00:00:00")
            except Exception:
                return None
        d1 = conv(de, False)
        d2 = conv(ate, True)
        carregar_vendas(d1, d2)

    def on_atualizar():
        carregar_vendas()

    def on_remover():
        sel = tree_vendas.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione uma venda para remover.")
            return
        item = tree_vendas.item(sel[0])["values"]
        venda_id = item[0]
        if not messagebox.askyesno("Confirmar", f"Remover venda {venda_id}?"):
            return
        try:
            conn = get_connection()
            cur = conn.cursor()
            # remover pagamentos, itens e venda (as FKs com cascade tratam parte, mas fazemos explicitamente)
            cur.execute("DELETE FROM pagamentos WHERE venda_id=%s", (venda_id,))
            cur.execute("DELETE FROM itens_venda WHERE venda_id=%s", (venda_id,))
            cur.execute("DELETE FROM vendas WHERE id=%s", (venda_id,))
            conn.commit()
            cur.close()
            conn.close()
            carregar_vendas()
            for i in tree_itens.get_children():
                tree_itens.delete(i)
            for i in tree_pags.get_children():
                tree_pags.delete(i)
            txt_obs.delete("1.0", tk.END)
            messagebox.showinfo("Sucesso", "Venda removida.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao remover venda:\n{e}")

    # ligar botões
    btn_filtrar.configure(command=on_filtrar)
    btn_atualizar.configure(command=on_atualizar)
    btn_remover.configure(command=on_remover)
    btn_devolver.configure(command=lambda: messagebox.showinfo("Info", "Funcionalidade Devolver não implementada aqui."))
    btn_pdf.configure(command=lambda: messagebox.showinfo("Info", "Gerar PDF não implementado."))
    btn_rel.configure(command=lambda: messagebox.showinfo("Info", "Relatórios não implementado."))
    btn_reimprimir.configure(command=lambda: messagebox.showinfo("Info", "Reimprimir não implementado."))

    tree_vendas.bind("<<TreeviewSelect>>", on_venda_select)
    tree_vendas.bind("<Double-1>", lambda e: on_venda_select(e))

    # Carrega inicialmente
    carregar_vendas()

    return janela
