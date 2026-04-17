import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from datetime import datetime, date
import math
import vendas_interface


# Cores do tema
COR_PRIMARIA = "#FFA500"
COR_SECUNDARIA = "#FFD700"

# --- Configuração do banco ---
DB_CONFIG = {
    "host": "localhost",
    "user": "pdv",
    "password": "1234",
    "database": "sistema_vendas"
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def listar_produtos():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT codigo, nome, custo, lucro_percentual, preco_sugerido, preco_venda, estoque_minimo, estoque_inicial
            FROM produtos
            ORDER BY nome
        """)
        return cursor.fetchall()
    finally:
        if conn:
            conn.close()

def buscar_produto_por_codigo(codigo):
    if not codigo:
        return None
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT codigo, nome, custo, lucro_percentual, preco_sugerido, preco_venda,
                       estoque_minimo, estoque_inicial, fracionado, observacao, validade_dias, id
                FROM produtos
                WHERE codigo = %s
                LIMIT 1
            """, (codigo,))
            row = cursor.fetchone()
            return row
        except mysql.connector.Error:
            cursor.execute("""
                SELECT codigo, nome, custo, lucro_percentual, preco_sugerido, preco_venda,
                       estoque_minimo, estoque_inicial, id
                FROM produtos
                WHERE codigo = %s
                LIMIT 1
            """, (codigo,))
            row = cursor.fetchone()
            if row:
                return tuple(list(row) + [None, None, None])
            return None
    finally:
        if conn:
            conn.close()

def buscar_produtos_por_nome(nome_busca, limit=50):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        pattern = f"%{nome_busca.upper()}%"
        try:
            cur.execute("""
                SELECT id, codigo, nome, preco_venda, fracionado, custo
                FROM produtos
                WHERE UPPER(nome) LIKE %s
                ORDER BY nome
                LIMIT %s
            """, (pattern, limit))
            rows = cur.fetchall()
            return rows
        except mysql.connector.Error:
            try:
                cur.execute("""
                    SELECT id, codigo, nome, preco_venda, NULL AS fracionado, NULL AS custo
                    FROM produtos
                    WHERE UPPER(nome) LIKE %s
                    ORDER BY nome
                    LIMIT %s
                """, (pattern, limit))
                return cur.fetchall()
            except Exception:
                return []
    finally:
        if conn:
            conn.close()

# --- Interface principal ---
def iniciar_interface():
    ctk.set_appearance_mode("light")
    app = ctk.CTk()
    app.title("Sistema PDV")
    app.attributes("-fullscreen", True)

    def sair(event=None):
        if messagebox.askyesno("Confirmação", "Deseja realmente sair do sistema?"):
            app.destroy()
    app.bind("<Escape>", sair)

    # Menu lateral
    frame_menu = ctk.CTkFrame(app, corner_radius=10)
    frame_menu.pack(side="left", fill="y", padx=10, pady=10)

    # Área principal onde trocaremos telas (PDV, welcome, etc.)
    frame_main = ctk.CTkFrame(app)
    frame_main.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    def show_frame_in_main(frame_to_show):
        for w in frame_main.winfo_children():
            w.pack_forget()
            w.grid_forget()
            w.place_forget()
        frame_to_show.pack(fill="both", expand=True)

    # ---------------------------
    # PDV screen (inside frame_main)
    # ---------------------------
    pdv_frame = ctk.CTkFrame(frame_main)
    header = ctk.CTkLabel(pdv_frame, text="PDV - Vendas", font=ctk.CTkFont(size=18, weight="bold"))
    header.pack(anchor="nw", pady=(8,6), padx=8)

    pdv_body = ctk.CTkFrame(pdv_frame)
    pdv_body.pack(fill="both", expand=True, padx=8, pady=8)

    left_panel = ctk.CTkFrame(pdv_body, width=320)
    left_panel.pack(side="left", fill="y", padx=(0,8), pady=4)

    ctk.CTkLabel(left_panel, text="Entre com o Código ou Código de barras").pack(anchor="w", pady=(6,2))
    entry_pdv_codigo = ctk.CTkEntry(left_panel, width=280)
    entry_pdv_codigo.pack(anchor="w", pady=4)

    ctk.CTkLabel(left_panel, text="Quantidade:").pack(anchor="w", pady=(8,2))
    entry_pdv_qtd = ctk.CTkEntry(left_panel, width=120)
    entry_pdv_qtd.insert(0, "1")
    entry_pdv_qtd.pack(anchor="w", pady=2)

    ctk.CTkLabel(left_panel, text="Preço Unitário:").pack(anchor="w", pady=(8,2))
    entry_pdv_preco_unit = ctk.CTkEntry(left_panel, width=140)
    entry_pdv_preco_unit.insert(0, "0.00")
    entry_pdv_preco_unit.pack(anchor="w", pady=2)

    ctk.CTkLabel(left_panel, text="SUBTOTAL:").pack(anchor="w", pady=(12,2))
    lbl_pdv_subtotal = ctk.CTkLabel(left_panel, text="R$ 0.00", font=ctk.CTkFont(size=16, weight="bold"))
    lbl_pdv_subtotal.pack(anchor="w", pady=2)

    # actions area: top row with Add and Remove, bottom row with Adjust (requested under the two)
    frame_pdv_actions_top = ctk.CTkFrame(left_panel)
    frame_pdv_actions_top.pack(anchor="w", pady=(12,4))
    btn_pdv_add = ctk.CTkButton(frame_pdv_actions_top, text="Adicionar (Enter)", fg_color=COR_PRIMARIA, width=140)
    btn_pdv_remove = ctk.CTkButton(frame_pdv_actions_top, text="Remover Item", fg_color="#d9534f", width=140)
    btn_pdv_add.pack(side="left", padx=6)
    btn_pdv_remove.pack(side="left", padx=6)

    frame_pdv_actions_bottom = ctk.CTkFrame(left_panel)
    frame_pdv_actions_bottom.pack(anchor="w", pady=(4,6))
    # novo botão: Acréscimo / Desconto (abaixo dos dois) - largura igual aos dois juntos
    btn_pdv_adjust = ctk.CTkButton(frame_pdv_actions_bottom, text="Acréscimo / Desconto", fg_color="#6c757d", width=292)
    btn_pdv_adjust.pack(side="left", padx=6)

    # área para exibir último produto registrado (descrição, preço unitário, qtd e total)
    frame_last = ctk.CTkFrame(left_panel)
    frame_last.pack(fill="x", pady=(8,4))
    lbl_last_desc = ctk.CTkLabel(frame_last, text="Último: -", anchor="w", font=ctk.CTkFont(size=16, weight="bold"))
    lbl_last_desc.pack(fill="x", padx=6, pady=(2,0))
    lbl_last_price = ctk.CTkLabel(frame_last, text="Preço unit:\nR$ 0,00", anchor="w", justify="left")
    lbl_last_price.pack(fill="x", padx=6, pady=(2,0))
    lbl_last_qtd = ctk.CTkLabel(frame_last, text="Qtd:\n0", anchor="w", justify="left")
    lbl_last_qtd.pack(fill="x", padx=6, pady=(2,0))
    lbl_last_total = ctk.CTkLabel(frame_last, text="Total:\nR$ 0,00", anchor="w", justify="left", font=ctk.CTkFont(size=14, weight="bold"))
    lbl_last_total.pack(fill="x", padx=6, pady=(2,6))

    right_panel = ctk.CTkFrame(pdv_body)
    right_panel.pack(side="left", fill="both", expand=True)

    colunas_pdv = ("Item", "Código", "Descrição", "Qtd", "Preço", "Subtotal")
    tree_pdv = ttk.Treeview(right_panel, columns=colunas_pdv, show="headings", selectmode="browse")
    for c in colunas_pdv:
        tree_pdv.heading(c, text=c)
        tree_pdv.column(c, width=120 if c != "Descrição" else 300)
    tree_pdv.pack(fill="both", expand=True, padx=6, pady=6)

    # configurar tags visuais para ajustes
    tree_pdv.tag_configure("aj_acresc", foreground="red")
    tree_pdv.tag_configure("aj_desc", foreground="green")

    frame_totais = ctk.CTkFrame(pdv_frame)
    frame_totais.pack(fill="x", padx=8, pady=(0,8))
    lbl_total_text = ctk.CTkLabel(frame_totais, text="TOTAL:", font=ctk.CTkFont(size=16, weight="bold"))
    lbl_total_text.pack(side="left", padx=(6,4))
    lbl_total_value = ctk.CTkLabel(frame_totais, text="R$ 0.00", font=ctk.CTkFont(size=20, weight="bold"))
    lbl_total_value.pack(side="left")

    # resumo de ajustes no rodapé do PDV (solicitado)
    frame_resumo_ajustes = ctk.CTkFrame(pdv_frame)
    frame_resumo_ajustes.pack(fill="x", padx=8, pady=(4,8))
    lbl_resumo_ajustes = ctk.CTkLabel(frame_resumo_ajustes, text="Ajustes: 0 itens  |  Total: R$ 0.00", anchor="w")
    lbl_resumo_ajustes.pack(side="left", padx=6)

    pdv_item_counter = {"value": 0}
    pdv_total = {"value": 0.0}

    # lista de observações de acréscimos/descontos aplicados (será concatenada nas observações da venda)
    ajustes_observacoes = []
    # mapa item_id -> observacao do ajuste (string) para persistência por item
    observacoes_por_item = {}
    ajustes_summary_total = {"value": 0.0}
    ajustes_summary_count = {"value": 0}

    def atualizar_resumo_ajustes_label():
        total = ajustes_summary_total["value"]
        count = ajustes_summary_count["value"]
        if total > 0:
            color = "red"
        elif total < 0:
            color = "green"
        else:
            color = "#444444"
        lbl_resumo_ajustes.configure(text=f"Ajustes: {count} itens  |  Total: R$ {total:.2f}", text_color=color)

    def atualizar_subtotal_visual():
        try:
            qtd = float(entry_pdv_qtd.get().strip().replace(",", ".") or "0")
            preco = float(entry_pdv_preco_unit.get().strip().replace(",", ".") or "0")
            subtotal = qtd * preco
            lbl_pdv_subtotal.configure(text=f"R$ {subtotal:.2f}")
        except Exception:
            lbl_pdv_subtotal.configure(text="R$ 0.00")

    entry_pdv_qtd.bind("<KeyRelease>", lambda e: atualizar_subtotal_visual())
    entry_pdv_preco_unit.bind("<KeyRelease>", lambda e: atualizar_subtotal_visual())

    # --- Restrição de caracteres no campo de código do PDV: não permitir '+' e '-' ---
    def validar_codigo_pdv(new_value):
        if new_value is None:
            return False
        for ch in new_value:
            if ch in "+-":
                return False
        return True

    vcmd_codigo = (app.register(lambda P: validar_codigo_pdv(P)), "%P")
    try:
        entry_pdv_codigo._entry.configure(validate="key", validatecommand=vcmd_codigo)
    except Exception:
        def block_plus_minus(event):
            if event.char in "+-":
                return "break"
        entry_pdv_codigo.bind("<KeyPress>", block_plus_minus)

    # Interpreta entradas com operadores:
    def interpretar_codigo_entrada(texto):
        txt = texto.strip()
        if not txt:
            return ("", None, None)
        if txt.startswith("$"):
            return (None, txt[1:].strip(), "$")
        if "*" in txt:
            parts = txt.split("*", 1)
            left = parts[0].strip()
            right = parts[1].strip()
            return (left if left != "" else None, right if right != "" else None, "*")
        if "/" in txt:
            parts = txt.split("/", 1)
            left = parts[0].strip()
            right = parts[1].strip()
            return (left if left != "" else None, right if right != "" else None, "/")
        return (None, txt, None)

    def atualizar_info_ultimo_produto(codigo, nome, preco_unit_display, quantidade, subtotal_display):
        lbl_last_desc.configure(text=f"{nome} ({codigo})")
        lbl_last_price.configure(text=f"Preço unit:\nR$ {preco_unit_display}")
        lbl_last_qtd.configure(text=f"Qtd:\n{quantidade}")
        lbl_last_total.configure(text=f"Total:\nR$ {subtotal_display}")

    def inserir_produto_no_pdv(produto_row, quantidade, preco_unit_override=None, ajuste_text=None, tag=None):
        """
        Insere o produto no tree_pdv.
        produto_row: tuple retornada por buscar_produto_por_codigo ou buscar_produtos_por_nome (id, codigo, nome, preco_venda, fracionado, custo)
        quantidade: float
        preco_unit_override: float ou None
        ajuste_text: texto descritivo do ajuste (será adicionado às observações)
        tag: tag para aplicar na linha (visual)
        """
        codigo_db = None
        nome_db = ""
        preco_venda_db = None
        fracionado_db = 0
        try:
            if len(produto_row) >= 6 and isinstance(produto_row[0], int):
                codigo_db = produto_row[1]
                nome_db = produto_row[2]
                preco_venda_db = produto_row[3]
                fracionado_db = int(produto_row[4]) if produto_row[4] is not None else 0
            else:
                codigo_db = produto_row[0]
                nome_db = produto_row[1]
                preco_venda_db = produto_row[5] if len(produto_row) > 5 else None
                fracionado_db = int(produto_row[8]) if len(produto_row) > 8 and produto_row[8] is not None else 0
        except Exception:
            try:
                codigo_db = produto_row[0]
                nome_db = produto_row[1]
                preco_venda_db = produto_row[5] if len(produto_row) > 5 else None
            except Exception:
                codigo_db = str(produto_row[0])
                nome_db = str(produto_row[1]) if len(produto_row) > 1 else codigo_db
                preco_venda_db = None

        try:
            base_price = float(preco_venda_db) if preco_venda_db is not None else 0.0
        except Exception:
            base_price = 0.0

        try:
            preco_unit_text = entry_pdv_preco_unit.get().strip().replace(",", ".") or ""
            if preco_unit_text != "":
                preco_unit = float(preco_unit_text)
                if preco_unit <= 0:
                    preco_unit = float(preco_venda_db) if preco_venda_db is not None else 0.0
            else:
                preco_unit = float(preco_venda_db) if preco_venda_db is not None else 0.0
        except Exception:
            preco_unit = float(preco_venda_db) if preco_venda_db is not None else 0.0

        if preco_unit_override is not None:
            preco_unit = preco_unit_override

        if preco_unit is None:
            preco_unit = 0.0

        try:
            subtotal = quantidade * preco_unit
        except Exception:
            subtotal = 0.0

        pdv_item_counter["value"] += 1
        item_id = pdv_item_counter["value"]
        if fracionado_db:
            qtd_display = f"{quantidade:.6f}".rstrip('0').rstrip('.')
        else:
            try:
                qtd_display = f"{int(quantidade)}"
            except Exception:
                qtd_display = f"{quantidade:.6f}".rstrip('0').rstrip('.')

        preco_display = f"{preco_unit:.2f}"
        if ajuste_text:
            try:
                delta = preco_unit - base_price
                sign = "-" if delta < 0 else "+"
                preco_display = f"{base_price:.2f} {sign}{abs(delta):.2f}"
            except Exception:
                preco_display = f"{preco_unit:.2f}"

        iid = tree_pdv.insert("", tk.END, values=(item_id, codigo_db, nome_db, qtd_display, preco_display, f"{subtotal:.2f}"), tags=(tag,) if tag else ())
        pdv_total["value"] += subtotal
        lbl_total_value.configure(text=f"R$ {pdv_total['value']:.2f}")

        # registrar ajuste nas observações se houver (global e por item)
        if ajuste_text:
            ajustes_observacoes.append(f"Item {item_id} ({codigo_db}): {ajuste_text}")
            observacoes_por_item[item_id] = ajuste_text
            ajustes_summary_count["value"] += 1
            try:
                old_subtotal = base_price * quantidade
            except Exception:
                old_subtotal = 0.0
            impacto = subtotal - old_subtotal
            ajustes_summary_total["value"] += impacto
            atualizar_resumo_ajustes_label()

        # atualizar último produto exibido
        atualizar_info_ultimo_produto(codigo_db, nome_db, f"{preco_unit:.2f}", qtd_display, f"{subtotal:.2f}")

        # limpa campos de entrada padrão e retorna foco para o campo de código
        entry_pdv_codigo.delete(0, tk.END)
        entry_pdv_qtd.delete(0, tk.END); entry_pdv_qtd.insert(0, "1")
        entry_pdv_preco_unit.delete(0, tk.END); entry_pdv_preco_unit.insert(0, "0.00")
        atualizar_subtotal_visual()
        entry_pdv_codigo.focus_set()

    # função que abre popin de ajuste para um produto (pode ser item selecionado ou produto a registrar)
    def abrir_popin_ajuste(produto, quantidade, preco_unit, target_tree_item=None):
        win = ctk.CTkToplevel(app)
        win.title("Acréscimo / Desconto")
        win.geometry("420x300")
        win.transient(app)
        win.grab_set()
        win.focus_force()

        try:
            codigo = produto[0] if not isinstance(produto[0], int) else produto[1]
            nome = produto[1] if not isinstance(produto[0], int) else produto[2]
        except Exception:
            codigo = str(produto[0])
            nome = str(produto[1]) if len(produto) > 1 else codigo

        ctk.CTkLabel(win, text=f"{codigo} — {nome}", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="nw", padx=8, pady=(8,6))
        ctk.CTkLabel(win, text=f"Preço unitário atual: R$ {float(preco_unit):.2f}   Qtd: {quantidade}").pack(anchor="nw", padx=8, pady=(0,8))

        frame_inputs = ctk.CTkFrame(win)
        frame_inputs.pack(fill="both", expand=True, padx=8, pady=6)

        ctk.CTkLabel(frame_inputs, text="Acréscimo (%) (use negativo para desconto):").pack(anchor="w", pady=(6,2))
        ent_pct = ctk.CTkEntry(frame_inputs, width=120)
        ent_pct.insert(0, "0")
        ent_pct.pack(anchor="w", pady=(0,6))

        ctk.CTkLabel(frame_inputs, text="Acréscimo por unidade (R$) (negativo para desconto):").pack(anchor="w", pady=(6,2))
        ent_unit = ctk.CTkEntry(frame_inputs, width=120)
        ent_unit.insert(0, "0.00")
        ent_unit.pack(anchor="w", pady=(0,6))

        ctk.CTkLabel(frame_inputs, text="Acréscimo no conjunto (R$) (negativo para desconto):").pack(anchor="w", pady=(6,2))
        ent_conj = ctk.CTkEntry(frame_inputs, width=120)
        ent_conj.insert(0, "0.00")
        ent_conj.pack(anchor="w", pady=(0,6))

        frame_buttons = ctk.CTkFrame(win)
        frame_buttons.pack(fill="x", padx=8, pady=8)
        btn_apply = ctk.CTkButton(frame_buttons, text="Aplicar", fg_color=COR_PRIMARIA)
        btn_cancel = ctk.CTkButton(frame_buttons, text="Cancelar", fg_color="#6c757d")
        btn_apply.pack(side="left", padx=6)
        btn_cancel.pack(side="right", padx=6)

        def aplicar():
            try:
                pct = float(str(ent_pct.get()).strip().replace(",", ".") or "0")
            except Exception:
                pct = 0.0
            try:
                unit_add = float(str(ent_unit.get()).strip().replace(",", ".") or "0")
            except Exception:
                unit_add = 0.0
            try:
                conj_add = float(str(ent_conj.get()).strip().replace(",", ".") or "0")
            except Exception:
                conj_add = 0.0

            add_from_conj = 0.0
            try:
                if float(quantidade) != 0:
                    add_from_conj = conj_add / float(quantidade)
            except Exception:
                add_from_conj = 0.0

            add_from_pct = (pct / 100.0) * float(preco_unit)
            added_per_unit = unit_add + add_from_conj + add_from_pct
            novo_preco_unit = float(preco_unit) + added_per_unit
            novo_subtotal = novo_preco_unit * float(quantidade)

            parts = []
            if pct != 0:
                parts.append(f"{pct:+.2f}%")
            if unit_add != 0:
                parts.append(f"{unit_add:+.2f} R$/un")
            if conj_add != 0:
                parts.append(f"{conj_add:+.2f} R$ conjunto")
            ajuste_text = " ".join(parts) if parts else "Sem ajuste"

            tag = None
            impacto_unit = added_per_unit
            if impacto_unit > 0:
                tag = "aj_acresc"
            elif impacto_unit < 0:
                tag = "aj_desc"

            if target_tree_item:
                try:
                    vals = tree_pdv.item(target_tree_item)["values"]
                    qtd_text = str(vals[3]).replace(",", ".")
                    try:
                        qtd_val = float(qtd_text)
                    except Exception:
                        qtd_val = float(quantidade)
                    try:
                        old_sub = float(str(vals[5]).replace(",", "."))
                    except Exception:
                        old_sub = 0.0
                    try:
                        base_price = float(produto[5]) if len(produto) > 5 and produto[5] is not None else float(preco_unit)
                    except Exception:
                        base_price = float(preco_unit)
                    delta = novo_preco_unit - base_price
                    sign = "-" if delta < 0 else "+"
                    preco_display = f"{base_price:.2f} {sign}{abs(delta):.2f}"
                    tree_pdv.item(target_tree_item, values=(vals[0], vals[1], vals[2], vals[3], preco_display, f"{novo_subtotal:.2f}"), tags=(tag,) if tag else ())
                    pdv_total["value"] += (novo_subtotal - old_sub)
                    lbl_total_value.configure(text=f"R$ {pdv_total['value']:.2f}")
                    ajustes_observacoes.append(f"Item {vals[0]} ({vals[1]}): {ajuste_text}")
                    try:
                        observacoes_por_item[int(vals[0])] = ajuste_text
                    except Exception:
                        pass
                    ajustes_summary_count["value"] += 1
                    ajustes_summary_total["value"] += (novo_subtotal - old_sub)
                    atualizar_resumo_ajustes_label()
                    atualizar_info_ultimo_produto(vals[1], vals[2], f"{novo_preco_unit:.2f}", qtd_val, f"{novo_subtotal:.2f}")
                except Exception as e:
                    messagebox.showerror("Erro", f"Falha ao aplicar ajuste no item:\n{e}")
                    win.destroy()
                    return
            else:
                inserir_produto_no_pdv(produto, float(quantidade), preco_unit_override=novo_preco_unit, ajuste_text=ajuste_text, tag=tag)

            win.destroy()

        btn_apply.configure(command=aplicar)
        btn_cancel.configure(command=win.destroy)
        win.bind("<Return>", lambda e: aplicar())
        win.bind("<Escape>", lambda e: win.destroy())

    def abrir_busca_produtos(nome_busca_raw, left_raw, op):
        nome_busca = (nome_busca_raw or "").strip().upper()
        if not nome_busca:
            messagebox.showwarning("Busca", "Termo de busca vazio.")
            return

        resultados = buscar_produtos_por_nome(nome_busca)
        if not resultados:
            messagebox.showinfo("Busca", f"Nenhum produto encontrado para '{nome_busca_raw}'.")
            return

        win = ctk.CTkToplevel(app)
        win.title(f"Buscar: {nome_busca_raw}")
        win.geometry("700x400")
        win.transient(app)
        win.grab_set()
        win.focus_force()

        lbl = ctk.CTkLabel(win, text=f"Resultados para: {nome_busca_raw}", font=ctk.CTkFont(size=14, weight="bold"))
        lbl.pack(anchor="nw", padx=8, pady=(8,4))

        cols = ("codigo", "nome", "preco")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        tree.heading("codigo", text="Código")
        tree.heading("nome", text="Nome")
        tree.heading("preco", text="Preço")
        tree.column("codigo", width=120)
        tree.column("nome", width=420)
        tree.column("preco", width=100, anchor="e")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        for r in resultados:
            codigo = r[1]
            nome = r[2]
            preco = r[3] if r[3] is not None else 0.0
            try:
                preco_display = f"{float(preco):.2f}"
            except Exception:
                preco_display = "0.00"
            tree.insert("", tk.END, values=(codigo, nome, preco_display), tags=(str(r[0]),))

        frame_buttons = ctk.CTkFrame(win)
        frame_buttons.pack(fill="x", padx=8, pady=(0,8))
        btn_ok = ctk.CTkButton(frame_buttons, text="Selecionar", fg_color=COR_PRIMARIA)
        btn_cancel = ctk.CTkButton(frame_buttons, text="Cancelar", fg_color="#6c757d")
        btn_ok.pack(side="left", padx=6)
        btn_cancel.pack(side="right", padx=6)

        def selecionar_e_inserir(event=None):
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Busca", "Selecione um produto.")
                return
            vals = tree.item(sel[0])["values"]
            codigo_sel = vals[0]
            produto = buscar_produto_por_codigo(codigo_sel)
            if not produto:
                messagebox.showerror("Erro", "Falha ao carregar produto selecionado.")
                win.destroy()
                return

            quantidade = None
            if op == "*":
                if left_raw is None:
                    messagebox.showwarning("Aviso", "Quantidade não informada antes do '*'.")
                    return
                try:
                    if "," in left_raw or "." in left_raw:
                        quantidade = float(left_raw.replace(",", "."))
                    else:
                        quantidade = float(int(left_raw))
                except Exception:
                    messagebox.showwarning("Aviso", "Quantidade inválida antes do '*'.")
                    return
            elif op == "/":
                if left_raw is None:
                    messagebox.showwarning("Aviso", "Valor em centavos não informado antes do '/'.")
                    return
                if not left_raw.isdigit():
                    messagebox.showwarning("Aviso", "Valor antes de '/' deve ser centavos sem vírgula (ex: 500).")
                    return
                try:
                    centavos = int(left_raw)
                except Exception:
                    messagebox.showwarning("Aviso", "Valor em centavos inválido.")
                    return
                valor_em_reais = centavos / 100.0
                try:
                    preco_unit_text = entry_pdv_preco_unit.get().strip().replace(",", ".") or ""
                    if preco_unit_text != "":
                        preco_unit = float(preco_unit_text)
                        if preco_unit <= 0:
                            preco_unit = float(produto[5]) if len(produto) > 5 and produto[5] is not None else 0.0
                    else:
                        preco_unit = float(produto[5]) if len(produto) > 5 and produto[5] is not None else 0.0
                except Exception:
                    try:
                        preco_unit = float(produto[5]) if len(produto) > 5 and produto[5] is not None else 0.0
                    except Exception:
                        preco_unit = 0.0

                fracionado_db = 0
                try:
                    if len(produto) > 8 and produto[8] is not None:
                        fracionado_db = int(produto[8])
                except Exception:
                    fracionado_db = 0

                if preco_unit is None or preco_unit <= 0:
                    messagebox.showwarning("Aviso", "Preço unitário desconhecido. Informe o preço antes de usar centavos/codigo.")
                    return

                if fracionado_db:
                    quantidade = valor_em_reais / preco_unit
                    if quantidade * preco_unit > valor_em_reais:
                        quantidade = math.floor((valor_em_reais / preco_unit) * 1000000) / 1000000.0
                else:
                    qtd_calc = math.floor(valor_em_reais / preco_unit)
                    quantidade = float(qtd_calc)

                if quantidade <= 0:
                    messagebox.showwarning("Aviso", "Valor insuficiente para comprar ao menos 1 unidade deste produto.")
                    return
            else:
                try:
                    quantidade = float(entry_pdv_qtd.get().strip().replace(",", ".") or "0")
                except Exception:
                    messagebox.showwarning("Aviso", "Quantidade inválida.")
                    return

            inserir_produto_no_pdv(produto, quantidade)
            win.destroy()

        def cancelar():
            win.destroy()

        btn_ok.configure(command=selecionar_e_inserir)
        btn_cancel.configure(command=cancelar)
        tree.bind("<Double-1>", selecionar_e_inserir)
        win.bind("<Return>", selecionar_e_inserir)
        win.bind("<Escape>", lambda e: cancelar())

    # adicionar item no PDV (tratando códigos, operadores e busca por nome)
    def adicionar_item_pdv(event=None):
        raw = entry_pdv_codigo.get().strip()
        if not raw:
            messagebox.showwarning("Aviso", "Informe o código do produto (ou sintaxe com * ou /).")
            entry_pdv_codigo.focus_set()
            return

        left_raw, codigo_busca, op = interpretar_codigo_entrada(raw)
        if not codigo_busca:
            messagebox.showwarning("Aviso", "Código inválido.")
            entry_pdv_codigo.focus_set()
            return

        # Se op == '$' => abrir popin de ajuste antes de registrar (pode ser por código ou por busca por nome)
        if op == "$":
            inner_left, inner_code, inner_op = interpretar_codigo_entrada(codigo_busca)
            contains_letter = any(ch.isalpha() for ch in inner_code) if inner_code else False

            if contains_letter:
                resultados = buscar_produtos_por_nome(inner_code)
                if not resultados:
                    messagebox.showinfo("Busca", f"Nenhum produto encontrado para '{inner_code}'.")
                    return
                if len(resultados) == 1:
                    prod = buscar_produto_por_codigo(resultados[0][1])
                    qtd = 1.0
                    if inner_op == "*":
                        try:
                            qtd = float(inner_left.replace(",", ".")) if inner_left is not None else float(entry_pdv_qtd.get().strip().replace(",", ".") or 1)
                        except Exception:
                            qtd = 1.0
                    elif inner_op == "/":
                        try:
                            centavos = int(inner_left)
                            valor_em_reais = centavos / 100.0
                            preco_base = float(prod[5]) if prod[5] is not None else 0.0
                            if preco_base > 0:
                                qtd = valor_em_reais / preco_base
                                if qtd * preco_base > valor_em_reais:
                                    qtd = math.floor((valor_em_reais / preco_base) * 1000000) / 1000000.0
                            else:
                                messagebox.showwarning("Aviso", "Preço base desconhecido para cálculo por centavos.")
                                return
                        except Exception:
                            qtd = 1.0
                    else:
                        try:
                            qtd = float(entry_pdv_qtd.get().strip().replace(",", ".") or 1)
                        except Exception:
                            qtd = 1.0
                    try:
                        preco_base = float(prod[5]) if prod[5] is not None else 0.0
                    except Exception:
                        preco_base = 0.0
                    abrir_popin_ajuste(prod, qtd, preco_base, target_tree_item=None)
                    return
                def selecionar_para_ajuste():
                    sel = tree_sel.selection()
                    if not sel:
                        messagebox.showwarning("Busca", "Selecione um produto.")
                        return
                    vals = tree_sel.item(sel[0])["values"]
                    codigo_sel = vals[0]
                    prod = buscar_produto_por_codigo(codigo_sel)
                    if not prod:
                        messagebox.showerror("Erro", "Falha ao carregar produto selecionado.")
                        win_sel.destroy()
                        return
                    qtd = 1.0
                    if inner_op == "*":
                        try:
                            qtd = float(inner_left.replace(",", ".")) if inner_left is not None else float(entry_pdv_qtd.get().strip().replace(",", ".") or 1)
                        except Exception:
                            qtd = 1.0
                    elif inner_op == "/":
                        try:
                            centavos = int(inner_left)
                            valor_em_reais = centavos / 100.0
                            preco_base = float(prod[5]) if prod[5] is not None else 0.0
                            if preco_base > 0:
                                qtd = valor_em_reais / preco_base
                                if qtd * preco_base > valor_em_reais:
                                    qtd = math.floor((valor_em_reais / preco_base) * 1000000) / 1000000.0
                            else:
                                messagebox.showwarning("Aviso", "Preço base desconhecido para cálculo por centavos.")
                                return
                        except Exception:
                            qtd = 1.0
                    win_sel.destroy()
                    abrir_popin_ajuste(prod, qtd, float(prod[5]) if prod[5] is not None else 0.0, target_tree_item=None)

                win_sel = ctk.CTkToplevel(app)
                win_sel.title("Selecionar produto para ajuste")
                win_sel.geometry("700x400")
                win_sel.transient(app)
                win_sel.grab_set()
                win_sel.focus_force()
                tree_sel = ttk.Treeview(win_sel, columns=("codigo", "nome", "preco"), show="headings")
                tree_sel.heading("codigo", text="Código"); tree_sel.heading("nome", text="Nome"); tree_sel.heading("preco", text="Preço")
                tree_sel.column("codigo", width=120); tree_sel.column("nome", width=420); tree_sel.column("preco", width=100, anchor="e")
                tree_sel.pack(fill="both", expand=True, padx=8, pady=8)
                for r in resultados:
                    preco_display = f"{float(r[3]):.2f}" if r[3] is not None else "0.00"
                    tree_sel.insert("", tk.END, values=(r[1], r[2], preco_display))
                frame_btns = ctk.CTkFrame(win_sel); frame_btns.pack(fill="x", padx=8, pady=8)
                ctk.CTkButton(frame_btns, text="Selecionar", fg_color=COR_PRIMARIA, command=selecionar_para_ajuste).pack(side="left", padx=6)
                ctk.CTkButton(frame_btns, text="Cancelar", fg_color="#6c757d", command=win_sel.destroy).pack(side="right", padx=6)
                return
            else:
                prod = buscar_produto_por_codigo(inner_code)
                if not prod:
                    messagebox.showwarning("Aviso", f"Produto com código '{inner_code}' não encontrado.")
                    entry_pdv_codigo.focus_set()
                    return
                qtd = 1.0
                if inner_op == "*":
                    if inner_left is None:
                        messagebox.showwarning("Aviso", "Quantidade não informada antes do '*'.")
                        return
                    try:
                        qtd = float(inner_left.replace(",", "."))
                    except Exception:
                        messagebox.showwarning("Aviso", "Quantidade inválida antes do '*'.")
                        return
                elif inner_op == "/":
                    if inner_left is None:
                        messagebox.showwarning("Aviso", "Valor em centavos não informado antes do '/'.")
                        return
                    if not inner_left.isdigit():
                        messagebox.showwarning("Aviso", "Valor antes de '/' deve ser centavos sem vírgula (ex: 500).")
                        return
                    try:
                        centavos = int(inner_left)
                        valor_em_reais = centavos / 100.0
                        preco_base = float(prod[5]) if prod[5] is not None else 0.0
                        if preco_base <= 0:
                            messagebox.showwarning("Aviso", "Preço base desconhecido para cálculo por centavos.")
                            return
                        if prod and len(prod) > 8 and prod[8]:
                            qtd = valor_em_reais / preco_base
                            if qtd * preco_base > valor_em_reais:
                                qtd = math.floor((valor_em_reais / preco_base) * 1000000) / 1000000.0
                        else:
                            qtd = float(math.floor(valor_em_reais / preco_base))
                    except Exception:
                        messagebox.showwarning("Aviso", "Valor em centavos inválido.")
                        return
                else:
                    try:
                        qtd = float(entry_pdv_qtd.get().strip().replace(",", ".") or "1")
                    except Exception:
                        qtd = 1.0
                try:
                    preco_base = float(prod[5]) if prod[5] is not None else 0.0
                except Exception:
                    preco_base = 0.0
                abrir_popin_ajuste(prod, qtd, preco_base, target_tree_item=None)
                return

        contains_letter = any(ch.isalpha() for ch in codigo_busca)
        if contains_letter:
            abrir_busca_produtos(codigo_busca, left_raw, op)
            return

        try:
            produto = buscar_produto_por_codigo(codigo_busca)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao buscar produto:\n{e}")
            entry_pdv_codigo.focus_set()
            return

        if not produto:
            messagebox.showwarning("Aviso", f"Produto com código '{codigo_busca}' não encontrado.")
            entry_pdv_codigo.focus_set()
            return

        preco_venda_db = None
        fracionado_db = 0
        try:
            preco_venda_db = float(produto[5]) if produto[5] is not None else None
        except Exception:
            preco_venda_db = None
        try:
            if len(produto) > 8 and produto[8] is not None:
                fracionado_db = int(produto[8])
            else:
                fracionado_db = 0
        except Exception:
            fracionado_db = 0

        quantidade = None

        if op == "*":
            if left_raw is None:
                messagebox.showwarning("Aviso", "Use N*codigo para multiplicar (ex: 5*COD).")
                entry_pdv_codigo.focus_set()
                return
            if "," in left_raw or "." in left_raw:
                try:
                    quantidade = float(left_raw.replace(",", "."))
                except Exception:
                    messagebox.showwarning("Aviso", "Quantidade inválida na sintaxe N*codigo.")
                    entry_pdv_codigo.focus_set()
                    return
            else:
                if not left_raw.isdigit():
                    messagebox.showwarning("Aviso", "Quantidade inválida antes do '*'. Use número inteiro ou decimal.")
                    entry_pdv_codigo.focus_set()
                    return
                quantidade = float(int(left_raw))

        elif op == "/":
            if left_raw is None:
                messagebox.showwarning("Aviso", "Use centavos/codigo para divisão (ex: 500/COD).")
                entry_pdv_codigo.focus_set()
                return
            if not left_raw.isdigit():
                messagebox.showwarning("Aviso", "Valor antes de '/' deve ser centavos sem vírgula (ex: 500).")
                entry_pdv_codigo.focus_set()
                return
            try:
                centavos = int(left_raw)
            except Exception:
                messagebox.showwarning("Aviso", "Valor em centavos inválido.")
                entry_pdv_codigo.focus_set()
                return
            valor_em_reais = centavos / 100.0

            try:
                preco_unit_text = entry_pdv_preco_unit.get().strip().replace(",", ".") or ""
                if preco_unit_text != "":
                    preco_unit = float(preco_unit_text)
                    if preco_unit <= 0:
                        preco_unit = preco_venda_db if preco_venda_db is not None else 0.0
                else:
                    preco_unit = preco_venda_db if preco_venda_db is not None else 0.0
            except Exception:
                preco_unit = preco_venda_db if preco_venda_db is not None else 0.0

            if preco_unit is None or preco_unit <= 0:
                messagebox.showwarning("Aviso", "Preço unitário desconhecido. Informe o preço antes de usar centavos/codigo.")
                entry_pdv_preco_unit.focus_set()
                return

            if fracionado_db:
                quantidade = valor_em_reais / preco_unit
                if quantidade * preco_unit > valor_em_reais:
                    quantidade = math.floor((valor_em_reais / preco_unit) * 1000000) / 1000000.0
            else:
                qtd_calc = math.floor(valor_em_reais / preco_unit)
                quantidade = float(qtd_calc)

            if quantidade <= 0:
                messagebox.showwarning("Aviso", "Valor insuficiente para comprar ao menos 1 unidade deste produto.")
                entry_pdv_codigo.focus_set()
                return

        else:
            if left_raw is None:
                try:
                    quantidade = float(entry_pdv_qtd.get().strip().replace(",", ".") or "0")
                except Exception:
                    messagebox.showwarning("Aviso", "Quantidade inválida.")
                    entry_pdv_qtd.focus_set()
                    return
            else:
                if "," in left_raw or "." in left_raw:
                    try:
                        quantidade = float(left_raw.replace(",", "."))
                    except Exception:
                        messagebox.showwarning("Aviso", "Quantidade inválida na sintaxe N*codigo.")
                        entry_pdv_codigo.focus_set()
                        return
                else:
                    if left_raw.isdigit():
                        quantidade = float(int(left_raw))
                    else:
                        messagebox.showwarning("Aviso", "Formato inválido. Use código ou N*codigo ou centavos/codigo.")
                        entry_pdv_codigo.focus_set()
                        return

        inserir_produto_no_pdv(produto, quantidade)

    def remover_item_pdv(event=None):
        sel = tree_pdv.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um item para remover.")
            return
        for s in sel:
            vals = tree_pdv.item(s)["values"]
            try:
                subtotal = float(str(vals[5]).replace(",", "."))
            except Exception:
                subtotal = 0.0
            # remover observação por item se existir
            try:
                item_num = int(vals[0])
                if item_num in observacoes_por_item:
                    del observacoes_por_item[item_num]
            except Exception:
                pass
            pdv_total["value"] -= subtotal
            tree_pdv.delete(s)
        lbl_total_value.configure(text=f"R$ {pdv_total['value']:.2f}")
        entry_pdv_codigo.focus_set()

    # bind do botão de ajuste: aplica ao item selecionado se houver, senão abre popin para produto a registrar
    def on_btn_adjust():
        sel = tree_pdv.selection()
        if sel:
            iid = sel[0]
            vals = tree_pdv.item(iid)["values"]
            codigo = vals[1]
            produto = buscar_produto_por_codigo(codigo)
            if not produto:
                messagebox.showerror("Erro", "Falha ao carregar produto selecionado.")
                return
            try:
                preco_unit = float(produto[5]) if produto[5] is not None else float(str(vals[4]).split()[0].replace(",", ".")) if vals[4] else 0.0
            except Exception:
                try:
                    preco_unit = float(str(vals[4]).replace(",", "."))
                except Exception:
                    preco_unit = 0.0
            try:
                qtd = float(str(vals[3]).replace(",", "."))
            except Exception:
                qtd = 1.0
            abrir_popin_ajuste(produto, qtd, preco_unit, target_tree_item=iid)
        else:
            raw = entry_pdv_codigo.get().strip()
            if not raw:
                messagebox.showinfo("Ajuste", "Selecione um item ou informe um código no campo para ajustar antes de registrar.")
                entry_pdv_codigo.focus_set()
                return
            left_raw, codigo_busca, op = interpretar_codigo_entrada(raw)
            if op == "$":
                adicionar_item_pdv()
                return
            contains_letter = any(ch.isalpha() for ch in codigo_busca)
            if contains_letter:
                abrir_busca_produtos(codigo_busca, left_raw, op)
                return
            prod = buscar_produto_por_codigo(codigo_busca)
            if not prod:
                messagebox.showwarning("Aviso", f"Produto com código '{codigo_busca}' não encontrado.")
                return
            try:
                qtd = float(entry_pdv_qtd.get().strip().replace(",", ".") or "1")
            except Exception:
                qtd = 1.0
            try:
                preco_base = float(prod[5]) if prod[5] is not None else 0.0
            except Exception:
                preco_base = 0.0
            abrir_popin_ajuste(prod, qtd, preco_base, target_tree_item=None)

    btn_pdv_adjust.configure(command=on_btn_adjust)

    btn_pdv_add.configure(command=adicionar_item_pdv)
    btn_pdv_remove.configure(command=remover_item_pdv)
    entry_pdv_codigo.bind("<Return>", adicionar_item_pdv)

    def limpar_pdv():
        for i in tree_pdv.get_children():
            tree_pdv.delete(i)
        pdv_item_counter["value"] = 0
        pdv_total["value"] = 0.0
        lbl_total_value.configure(text="R$ 0.00")
        entry_pdv_codigo.delete(0, tk.END)
        entry_pdv_qtd.delete(0, tk.END); entry_pdv_qtd.insert(0, "1")
        entry_pdv_preco_unit.delete(0, tk.END); entry_pdv_preco_unit.insert(0, "0.00")
        atualizar_subtotal_visual()
        entry_pdv_codigo.focus_set()
        ajustes_observacoes.clear()
        observacoes_por_item.clear()
        ajustes_summary_total["value"] = 0.0
        ajustes_summary_count["value"] = 0
        atualizar_resumo_ajustes_label()
        lbl_last_desc.configure(text="Último: -")
        lbl_last_price.configure(text="Preço unit:\nR$ 0,00")
        lbl_last_qtd.configure(text="Qtd:\n0")
        lbl_last_total.configure(text="Total:\nR$ 0,00")

    def mostrar_pdv():
        limpar_pdv()
        show_frame_in_main(pdv_frame)
        entry_pdv_codigo.focus_set()

    # ---------------------------
    # Finalização de venda (tecla +)
    # ---------------------------
    def mostrar_finalizacao(event=None):
        frame_final = ctk.CTkFrame(frame_main)

        ctk.CTkLabel(frame_final, text="Finalizar Venda", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="nw", pady=(8,6), padx=8)

        total_a_pagar = pdv_total["value"]
        frame_total = ctk.CTkFrame(frame_final)
        frame_total.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(frame_total, text="TOTAL A PAGAR:", text_color=COR_PRIMARIA, font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=(6,8))
        lbl_total_final = ctk.CTkLabel(frame_total, text=f"R$ {total_a_pagar:.2f}", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_total_final.pack(side="left")

        frame_cliente = ctk.CTkFrame(frame_final)
        frame_cliente.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(frame_cliente, text="Dados do Cliente (opcional):", text_color="#666666").pack(anchor="w")
        entry_cliente = ctk.CTkEntry(frame_cliente, width=400, placeholder_text="Nome do cliente")
        entry_cliente.pack(side="left", padx=6, pady=6)
        entry_telefone = ctk.CTkEntry(frame_cliente, width=200, placeholder_text="Fone")
        entry_telefone.pack(side="left", padx=6, pady=6)

        frame_pag = ctk.CTkFrame(frame_final)
        frame_pag.pack(fill="x", padx=12, pady=6)

        # Alterações solicitadas: renomear formas e adicionar PIX 2
        payment_types = [
            ("Dinheiro", "0,00"),
            ("PIX", "0,00"),
            ("Cartão Créd.", "0,00"),
            ("Cartão Déb.", "0,00"),
            ("Dinheiro 2", "0,00"),   # substitui Cheque
            ("PIX 2", "0,00"),        # novo
            ("Debito 2", "0,00"),     # substitui A. Campo1
            ("Credito 2", "0,00")     # substitui B. Campo2
        ]

        payment_entries = []

        def validar_numero_char(new_value):
            if new_value == "":
                return True
            allowed = "0123456789.,"
            for ch in new_value:
                if ch not in allowed:
                    return False
            if new_value.count(".") > 1 or new_value.count(",") > 1:
                return False
            return True

        vcmd = (app.register(lambda P: validar_numero_char(P)), "%P")

        def on_payment_focus_in(entry_widget, default_text):
            try:
                cur = entry_widget.get()
                if cur.strip() == default_text:
                    entry_widget.delete(0, tk.END)
            except Exception:
                pass

        def on_payment_focus_out(entry_widget, default_text):
            try:
                cur = entry_widget.get().strip()
                if cur == "":
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, default_text)
            except Exception:
                pass

        for i, (label_text, default) in enumerate(payment_types):
            row = ctk.CTkFrame(frame_pag)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{label_text}:", width=120, anchor="w").pack(side="left", padx=(6,8))
            ent = ctk.CTkEntry(row, width=160)
            ent.insert(0, default)
            try:
                ent._entry.configure(validate="key", validatecommand=vcmd)
            except Exception:
                pass
            ent.pack(side="left", padx=6)
            payment_entries.append(ent)
            ent.bind("<FocusIn>", lambda ev, e=ent, d=default: on_payment_focus_in(e, d))
            ent.bind("<FocusOut>", lambda ev, e=ent, d=default: on_payment_focus_out(e, d))

        frame_troco = ctk.CTkFrame(frame_final)
        frame_troco.pack(fill="x", padx=12, pady=(8,4))
        lbl_troco_text = ctk.CTkLabel(frame_troco, text="TROCO:", text_color=COR_PRIMARIA, font=ctk.CTkFont(size=18, weight="bold"))
        lbl_troco_text.pack(side="left", padx=(6,8))
        lbl_troco_value = ctk.CTkLabel(frame_troco, text="R$ 0.00", text_color="#28a745", font=ctk.CTkFont(size=18, weight="bold"))
        lbl_troco_value.pack(side="left")

        frame_restante = ctk.CTkFrame(frame_final)
        frame_restante.pack(fill="x", padx=12, pady=(4,6))
        lbl_restante_text = ctk.CTkLabel(frame_restante, text="RESTANTE A PAGAR:", text_color="#666666")
        lbl_restante_text.pack(side="left", padx=(6,8))
        lbl_restante_value = ctk.CTkLabel(frame_restante, text=f"R$ {max(0.0, total_a_pagar):.2f}", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_restante_value.pack(side="left")

        frame_tot_calc = ctk.CTkFrame(frame_final)
        frame_tot_calc.pack(fill="x", padx=12, pady=6)
        lbl_total_pago_text = ctk.CTkLabel(frame_tot_calc, text="TOTAL (+):", text_color=COR_PRIMARIA)
        lbl_total_pago_text.pack(side="left", padx=(6,6))
        lbl_total_pago = ctk.CTkLabel(frame_tot_calc, text="R$ 0.00", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_total_pago.pack(side="left", padx=(0,12))

        frame_obs_pix = ctk.CTkFrame(frame_final)
        frame_obs_pix.pack(fill="both", padx=12, pady=6, expand=False)
        ctk.CTkLabel(frame_obs_pix, text="PIX - QR Code (placeholder)", text_color="#666666").pack(side="left", padx=6)
        entry_obs_final = ctk.CTkEntry(frame_obs_pix, width=400, placeholder_text="Observações")
        entry_obs_final.pack(side="left", padx=12)

        frame_actions_final = ctk.CTkFrame(frame_final)
        frame_actions_final.pack(fill="x", padx=12, pady=10)
        btn_finalizar = ctk.CTkButton(frame_actions_final, text="Finalizar (+)", fg_color="#28a745")
        btn_voltar_final = ctk.CTkButton(frame_actions_final, text="Voltar (-)", fg_color="#6c757d")
        btn_finalizar.pack(side="left", padx=8)
        btn_voltar_final.pack(side="left", padx=8)

        frame_footer = ctk.CTkFrame(frame_final)
        frame_footer.pack(fill="x", side="bottom", padx=8, pady=6)
        lbl_datetime = ctk.CTkLabel(frame_footer, text="", text_color="#444444")
        lbl_datetime.pack(side="right", padx=8)

        def atualizar_datetime():
            now = datetime.now()
            weekday_map = {
                0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
                3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
            }
            dia_sem = weekday_map[now.weekday()]
            lbl_datetime.configure(text=f"{now.strftime('%d/%m/%Y %H:%M:%S')}  -  {dia_sem}")
            lbl_datetime.after(1000, atualizar_datetime)
        atualizar_datetime()

        def recalcular_totais(event=None):
            def to_float(txt):
                try:
                    return float(str(txt).strip().replace(",", ".") or "0")
                except Exception:
                    return 0.0
            total_pago = sum(to_float(e.get()) for e in payment_entries)
            troco = total_pago - total_a_pagar
            restante = total_a_pagar - total_pago
            lbl_total_pago.configure(text=f"R$ {total_pago:.2f}")
            lbl_troco_value.configure(text=f"R$ {max(0.0, troco):.2f}")
            lbl_restante_value.configure(text=f"R$ {max(0.0, restante):.2f}")

        for e in payment_entries:
            e.bind("<KeyRelease>", lambda ev: recalcular_totais())

        def get_focus_index():
            focused = app.focus_get()
            for idx, ent in enumerate(payment_entries):
                if focused == ent or focused == getattr(ent, "_entry", None):
                    return idx
            return None

        def focus_prev_payment(event=None):
            idx = get_focus_index()
            if idx is None:
                payment_entries[-1].focus_set()
                return
            new_idx = max(0, idx - 1)
            payment_entries[new_idx].focus_set()

        def focus_next_payment(event=None):
            idx = get_focus_index()
            if idx is None:
                payment_entries[0].focus_set()
                return
            new_idx = min(len(payment_entries) - 1, idx + 1)
            payment_entries[new_idx].focus_set()

        def finalizar_venda(event=None):
            total_pago_text = lbl_total_pago.cget("text").replace("R$", "").strip()
            try:
                total_pago = float(total_pago_text.replace(",", "."))
            except Exception:
                total_pago = 0.0
            if total_pago < total_a_pagar:
                if not messagebox.askyesno("Confirmar", "O total pago é menor que o total a pagar. Deseja prosseguir mesmo assim?"):
                    return

            cliente_nome = entry_cliente.get().strip() or None
            obs_campo = entry_obs_final.get().strip() or ""
            obs_ajustes = "\n".join(ajustes_observacoes) if ajustes_observacoes else ""
            observacoes = "\n".join(filter(None, [obs_campo, obs_ajustes])) or None

            itens = []
            for iid in tree_pdv.get_children():
                vals = tree_pdv.item(iid)["values"]
                codigo = vals[1]
                descricao = vals[2]
                qtd_text = str(vals[3]).replace(",", ".")
                try:
                    qtd_val = float(qtd_text)
                except Exception:
                    qtd_val = 0.0
                preco_unit_display = str(vals[4])
                preco_unit = 0.0
                try:
                    if " " in preco_unit_display and ( "+" in preco_unit_display or "-" in preco_unit_display):
                        parts = preco_unit_display.split()
                        base = float(parts[0].replace(",", "."))
                        sign_delta = parts[1][0]
                        delta = float(parts[1][1:].replace(",", "."))
                        if sign_delta == "-":
                            preco_unit = base - delta
                        else:
                            preco_unit = base + delta
                    else:
                        preco_unit = float(preco_unit_display.replace(",", "."))
                except Exception:
                    preco_unit = 0.0
                subtotal = float(str(vals[5]).replace(",", ".") or "0")
                # pegar observação por item (se existir)
                item_num = vals[0]
                obs_item = None
                try:
                    obs_item = observacoes_por_item.get(int(item_num), None)
                except Exception:
                    obs_item = None
                itens.append({
                    "codigo": codigo,
                    "descricao": descricao,
                    "quantidade": qtd_val,
                    "preco_unit": preco_unit,
                    "subtotal": subtotal,
                    "observacao": obs_item
                })

            # Preparar e agregar pagamentos: somar valores iguais antes de salvar
            pagamentos_map = {}  # forma_id -> {'valor': float, 'troco': float}
            for idx, ent in enumerate(payment_entries):
                txt = ent.get().strip().replace(",", ".")
                try:
                    val = float(txt) if txt != "" else 0.0
                except Exception:
                    val = 0.0
                if val <= 0:
                    continue
                forma_id = idx + 1  # manter a ordem como forma_id (a lógica de mapeamento para ids reais deve ser feita conforme seu BD)
                if forma_id not in pagamentos_map:
                    pagamentos_map[forma_id] = {"valor": 0.0, "troco": 0.0}
                pagamentos_map[forma_id]["valor"] += val

            troco_total = max(0.0, total_pago - total_a_pagar)
            if troco_total > 0 and pagamentos_map:
                preferred = None
                if 1 in pagamentos_map:
                    preferred = 1
                elif 5 in pagamentos_map:
                    preferred = 5
                else:
                    preferred = next(iter(pagamentos_map.keys()))
                pagamentos_map[preferred]["troco"] += troco_total

            # Inserir em banco com transação
            try:
                conn = get_connection()
                cur = conn.cursor()
                conn.start_transaction()

                cur.execute("SHOW COLUMNS FROM vendas")
                cols = [r[0] for r in cur.fetchall()]
                insert_cols = []
                insert_vals = []
                if "data_venda" in cols:
                    insert_cols.append("data_venda"); insert_vals.append(datetime.now())
                if "cliente" in cols:
                    insert_cols.append("cliente"); insert_vals.append(cliente_nome)
                if "valor_total" in cols:
                    insert_cols.append("valor_total"); insert_vals.append(total_a_pagar)
                if "observacoes" in cols:
                    insert_cols.append("observacoes"); insert_vals.append(observacoes)
                elif "observacao" in cols:
                    insert_cols.append("observacao"); insert_vals.append(observacoes)
                cols_sql = ", ".join(insert_cols)
                placeholders = ", ".join(["%s"] * len(insert_vals))
                sql_insert_venda = f"INSERT INTO vendas ({cols_sql}) VALUES ({placeholders})"
                cur.execute(sql_insert_venda, tuple(insert_vals))
                venda_id = cur.lastrowid

                for it in itens:
                    produto_id = None
                    try:
                        cur.execute("SELECT id FROM produtos WHERE codigo=%s LIMIT 1", (it["codigo"],))
                        r = cur.fetchone()
                        if r:
                            produto_id = r[0]
                    except Exception:
                        produto_id = None
                    qtd_to_insert = it["quantidade"]
                    preco_to_insert = it["preco_unit"]
                    subtotal_to_insert = it["subtotal"]
                    cur.execute("SHOW COLUMNS FROM itens_venda")
                    cols_itv = [r[0] for r in cur.fetchall()]
                    insert_cols_it = []
                    insert_vals_it = []
                    if "venda_id" in cols_itv:
                        insert_cols_it.append("venda_id"); insert_vals_it.append(venda_id)
                    if "produto_id" in cols_itv:
                        insert_cols_it.append("produto_id"); insert_vals_it.append(produto_id)
                    if "quantidade" in cols_itv:
                        insert_cols_it.append("quantidade"); insert_vals_it.append(qtd_to_insert)
                    if "preco_unitario" in cols_itv:
                        insert_cols_it.append("preco_unitario"); insert_vals_it.append(preco_to_insert)
                    if "subtotal" in cols_itv:
                        insert_cols_it.append("subtotal"); insert_vals_it.append(subtotal_to_insert)
                    # incluir observação por item se a coluna existir
                    if "observacao" in cols_itv:
                        insert_cols_it.append("observacao"); insert_vals_it.append(it.get("observacao"))
                    elif "observacoes" in cols_itv:
                        insert_cols_it.append("observacoes"); insert_vals_it.append(it.get("observacao"))
                    cols_sql_it = ", ".join(insert_cols_it)
                    placeholders_it = ", ".join(["%s"] * len(insert_vals_it))
                    sql_it = f"INSERT INTO itens_venda ({cols_sql_it}) VALUES ({placeholders_it})"
                    cur.execute(sql_it, tuple(insert_vals_it))

                    if produto_id is not None:
                        try:
                            cur.execute("SHOW TABLES LIKE 'estoque_movimentos'")
                            if cur.fetchone():
                                cur.execute("""
                                    INSERT INTO estoque_movimentos (produto_id, tipo, quantidade, referencia_tipo, referencia_id, motivo)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (produto_id, 'saida', qtd_to_insert, 'venda', venda_id, 'Venda PDV'))
                        except Exception:
                            pass

                        try:
                            cur.execute("SHOW COLUMNS FROM produtos")
                            prod_cols = [r[0] for r in cur.fetchall()]
                            if "estoque_inicial" in prod_cols:
                                cur.execute("""
                                    UPDATE produtos
                                    SET estoque_inicial = estoque_inicial - %s
                                    WHERE id = %s
                                """, (qtd_to_insert, produto_id))
                        except Exception:
                            pass

                # Inserir pagamentos agregados (um por forma_id)
                for forma_id, data in pagamentos_map.items():
                    cur.execute("SHOW COLUMNS FROM pagamentos")
                    cols_pag = [r[0] for r in cur.fetchall()]
                    insert_cols_p = []
                    insert_vals_p = []
                    if "venda_id" in cols_pag:
                        insert_cols_p.append("venda_id"); insert_vals_p.append(venda_id)
                    if "forma_id" in cols_pag:
                        insert_cols_p.append("forma_id"); insert_vals_p.append(forma_id)
                    if "valor" in cols_pag:
                        insert_cols_p.append("valor"); insert_vals_p.append(data["valor"])
                    if "troco" in cols_pag:
                        insert_cols_p.append("troco"); insert_vals_p.append(data["troco"])
                    if "referencia" in cols_pag:
                        insert_cols_p.append("referencia"); insert_vals_p.append(None)
                    cols_sql_p = ", ".join(insert_cols_p)
                    placeholders_p = ", ".join(["%s"] * len(insert_vals_p))
                    sql_p = f"INSERT INTO pagamentos ({cols_sql_p}) VALUES ({placeholders_p})"
                    cur.execute(sql_p, tuple(insert_vals_p))

                conn.commit()
                cur.close()
                conn.close()
                messagebox.showinfo("Venda", f"Venda finalizada e salva. ID: {venda_id}  Total pago: R$ {total_pago:.2f}")
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                messagebox.showerror("Erro", f"Falha ao salvar venda:\n{e}")
                return

            limpar_pdv()
            show_frame_in_main(pdv_frame)
            entry_pdv_codigo.focus_set()

        def voltar_sem_finalizar(event=None):
            show_frame_in_main(pdv_frame)
            entry_pdv_codigo.focus_set()

        btn_finalizar.configure(command=finalizar_venda)
        btn_voltar_final.configure(command=voltar_sem_finalizar)

        frame_final.bind("<KeyPress-plus>", lambda e: finalizar_venda())
        frame_final.bind("<KeyPress-KP_Add>", lambda e: finalizar_venda())
        frame_final.bind("<KeyPress-minus>", lambda e: voltar_sem_finalizar())
        frame_final.bind("<KeyPress-KP_Subtract>", lambda e: voltar_sem_finalizar())
        frame_final.bind("<Up>", lambda e: focus_prev_payment())
        frame_final.bind("<Down>", lambda e: focus_next_payment())
        frame_final.bind("<Delete>", lambda e: remover_item_pdv())

        for ent in payment_entries:
            ent.bind("<Up>", lambda ev: focus_prev_payment())
            ent.bind("<Down>", lambda ev: focus_next_payment())
            ent.bind("<KeyPress-plus>", lambda ev: finalizar_venda())
            ent.bind("<KeyPress-KP_Add>", lambda ev: finalizar_venda())
            ent.bind("<KeyPress-minus>", lambda ev: voltar_sem_finalizar())
            ent.bind("<KeyPress-KP_Subtract>", lambda ev: voltar_sem_finalizar())

        show_frame_in_main(frame_final)
        recalcular_totais()
        if payment_entries:
            payment_entries[0].focus_set()

    # ---------------------------
    # Estoque (Toplevel)
    # ---------------------------
    def abrir_estoque():
        janela = ctk.CTkToplevel(app)
        janela.title("Controle de Estoque")
        janela.geometry("1200x700")
        janela.transient(app)
        janela.lift()
        janela.focus_force()

        frame_estoque = ctk.CTkFrame(janela)
        frame_estoque.pack(fill="both", expand=True)

        frame_cadastro = ctk.CTkFrame(janela)

        header_frame = ctk.CTkFrame(frame_cadastro)
        header_frame.pack(fill="x", pady=(10,6), padx=12)
        ctk.CTkLabel(header_frame, text="Controle de Estoque", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header_frame, text="Estoque » Novo produto", text_color="#666666").pack(anchor="w")

        content_frame = ctk.CTkFrame(frame_cadastro)
        content_frame.pack(fill="both", expand=True, padx=12, pady=6)

        left_col = ctk.CTkFrame(content_frame)
        left_col.pack(side="left", fill="y", padx=(0,12), pady=4)

        middle_col = ctk.CTkFrame(content_frame, width=260)
        middle_col.pack(side="left", fill="y", padx=(0,12), pady=4)

        right_col = ctk.CTkFrame(content_frame)
        right_col.pack(side="left", fill="both", expand=True, pady=4)

        lbl_codigo = ctk.CTkLabel(left_col, text="Código:", text_color=COR_PRIMARIA)
        lbl_codigo.pack(anchor="w", pady=(4,2))
        entry_codigo = ctk.CTkEntry(left_col, width=260)
        entry_codigo.pack(anchor="w", pady=(0,6))

        var_desativar = tk.IntVar(value=0)
        chk_desativar = ctk.CTkCheckBox(left_col, text="Desativar este produto", variable=var_desativar)
        chk_desativar.pack(anchor="w", pady=(0,8))

        lbl_nome = ctk.CTkLabel(left_col, text="Nome:", text_color=COR_PRIMARIA)
        lbl_nome.pack(anchor="w", pady=(4,2))
        entry_nome = ctk.CTkEntry(left_col, width=520)
        entry_nome.pack(anchor="w", pady=(0,8))

        frame_valores = ctk.CTkFrame(left_col)
        frame_valores.pack(fill="x", pady=6)

        sub_custo = ctk.CTkFrame(frame_valores)
        sub_custo.pack(side="left", padx=6)
        lbl_custo = ctk.CTkLabel(sub_custo, text="Custo:", text_color=COR_PRIMARIA)
        lbl_custo.pack(anchor="w")
        entry_custo = ctk.CTkEntry(sub_custo, width=120)
        entry_custo.insert(0, "0,00")
        entry_custo.pack()

        sub_lucro = ctk.CTkFrame(frame_valores)
        sub_lucro.pack(side="left", padx=6)
        lbl_lucro = ctk.CTkLabel(sub_lucro, text="Lucro (%):", text_color=COR_PRIMARIA)
        lbl_lucro.pack(anchor="w")
        entry_lucro = ctk.CTkEntry(sub_lucro, width=80)
        entry_lucro.insert(0, "0")
        entry_lucro.pack()

        sub_sug = ctk.CTkFrame(frame_valores)
        sub_sug.pack(side="left", padx=6)
        lbl_sugestao = ctk.CTkLabel(sub_sug, text="Sugestão:", text_color=COR_PRIMARIA)
        lbl_sugestao.pack(anchor="w")
        entry_sugestao = ctk.CTkEntry(sub_sug, width=120)
        entry_sugestao.insert(0, "0,00")
        entry_sugestao.configure(state="readonly")
        entry_sugestao.pack()

        sub_preco = ctk.CTkFrame(frame_valores)
        sub_preco.pack(side="left", padx=6)
        lbl_preco = ctk.CTkLabel(sub_preco, text="Preço de Venda:", text_color=COR_PRIMARIA)
        lbl_preco.pack(anchor="w")
        entry_preco = ctk.CTkEntry(sub_preco, width=120)
        entry_preco.insert(0, "0,00")
        entry_preco.pack()
        lbl_preco_pct = ctk.CTkLabel(sub_preco, text="0,0%", text_color="#888888")
        lbl_preco_pct.pack(anchor="w", pady=(4,0))

        frame_estoques = ctk.CTkFrame(left_col)
        frame_estoques.pack(fill="x", pady=6)
        sub_min = ctk.CTkFrame(frame_estoques)
        sub_min.pack(side="left", padx=6)
        lbl_minimo = ctk.CTkLabel(sub_min, text="Estoque Mínimo:", text_color=COR_PRIMARIA)
        lbl_minimo.pack(anchor="w")
        entry_minimo = ctk.CTkEntry(sub_min, width=100)
        entry_minimo.insert(0, "0")
        entry_minimo.pack()
        sub_ini = ctk.CTkFrame(frame_estoques)
        sub_ini.pack(side="left", padx=6)
        lbl_estoque = ctk.CTkLabel(sub_ini, text="Est. Inicial:", text_color=COR_PRIMARIA)
        lbl_estoque.pack(anchor="w")
        entry_estoque = ctk.CTkEntry(sub_ini, width=100)
        entry_estoque.insert(0, "0")
        entry_estoque.pack()

        frame_fracao = ctk.CTkFrame(left_col)
        frame_fracao.pack(fill="x", pady=6)
        var_fracionado = tk.IntVar(value=0)
        chk_fracionado = ctk.CTkCheckBox(frame_fracao, text="Produto que pode ser Fracionado (ex.: 0,500)", variable=var_fracionado)
        chk_fracionado.pack(side="left", padx=6)
        entry_fracionado = ctk.CTkEntry(frame_fracao, width=120)
        entry_fracionado.insert(0, "")
        entry_fracionado.pack(side="left", padx=8)
        def toggle_fracionado():
            state = "normal" if var_fracionado.get() else "disabled"
            entry_fracionado.configure(state=state)
        var_fracionado.trace_add("write", lambda *args: toggle_fracionado())
        toggle_fracionado()

        frame_validade = ctk.CTkFrame(left_col)
        frame_validade.pack(fill="x", pady=6)
        lbl_validade = ctk.CTkLabel(frame_validade, text="Data de Validade (DD/MM/AAAA):", text_color=COR_PRIMARIA)
        lbl_validade.pack(anchor="w")
        entry_validade = ctk.CTkEntry(frame_validade, width=140)
        entry_validade.insert(0, "")
        entry_validade.pack(side="left", padx=(0,8))
        lbl_validade_dias = ctk.CTkLabel(frame_validade, text="Dias até validade: -", text_color="#888888")
        lbl_validade_dias.pack(side="left")

        def calcular_dias_validade(event=None):
            txt = entry_validade.get().strip()
            if not txt:
                lbl_validade_dias.configure(text="Dias até validade: -")
                return None
            try:
                dt = datetime.strptime(txt, "%d/%m/%Y").date()
                dias = (dt - date.today()).days
                lbl_validade_dias.configure(text=f"Dias até validade: {dias}")
                return dias
            except Exception:
                lbl_validade_dias.configure(text="Dias até validade: formato inválido")
                return None

        entry_validade.bind("<FocusOut>", lambda ev: calcular_dias_validade())
        entry_validade.bind("<KeyRelease>", lambda ev: calcular_dias_validade())

        var_balanca = tk.IntVar(value=0)
        chk_balanca = ctk.CTkCheckBox(middle_col, text="Será codificado na Balança", variable=var_balanca)
        chk_balanca.pack(anchor="w", pady=(6,8))
        lbl_cod_balanca = ctk.CTkLabel(middle_col, text="Cód. Balança:", text_color=COR_PRIMARIA)
        lbl_cod_balanca.pack(anchor="w")
        entry_cod_balanca = ctk.CTkEntry(middle_col, width=160)
        entry_cod_balanca.pack(anchor="w", pady=(0,6))
        lbl_validade_dias_info = ctk.CTkLabel(middle_col, text="Valid. (em dias):", text_color=COR_PRIMARIA)
        lbl_validade_dias_info.pack(anchor="w")
        entry_validade_dias = ctk.CTkEntry(middle_col, width=120)
        entry_validade_dias.insert(0, "0")
        entry_validade_dias.configure(state="readonly")
        entry_validade_dias.pack(anchor="w", pady=(0,6))

        lbl_info_balanca = ctk.CTkLabel(middle_col, text="6 dígitos OU 5 dígitos", text_color="#888888")
        lbl_info_balanca.pack(anchor="w", pady=(4,8))

        var_tipo = tk.StringVar(value="unidade")
        ctk.CTkRadioButton(middle_col, text="Peso", variable=var_tipo, value="peso").pack(anchor="w", pady=(4,2))
        ctk.CTkRadioButton(middle_col, text="Unidade", variable=var_tipo, value="unidade").pack(anchor="w", pady=(0,6))

        ctk.CTkLabel(right_col, text="Obs. / Aplicação:", text_color=COR_PRIMARIA).pack(anchor="nw")
        entry_obs = tk.Text(right_col, width=60, height=12)
        entry_obs.pack(fill="both", pady=(4,0), expand=True)

        lbl_help = ctk.CTkLabel(right_col, text="Para trabalhar com produtos em KG ou outras medidas, consulte o suporte ou o Manual Online.", text_color="#a0a0a0")
        lbl_help.pack(anchor="w", pady=(8,4))

        frame_cadastro_botoes = ctk.CTkFrame(frame_cadastro)
        frame_cadastro_botoes.pack(fill="x", pady=10, padx=12)
        btn_cancelar = ctk.CTkButton(frame_cadastro_botoes, text="Cancelar", fg_color="red")
        btn_salvar = ctk.CTkButton(frame_cadastro_botoes, text="Salvar", fg_color=COR_PRIMARIA)
        btn_voltar = ctk.CTkButton(frame_cadastro_botoes, text="Voltar", fg_color=COR_PRIMARIA)
        btn_cancelar.pack(side="left", padx=8)
        btn_salvar.pack(side="left", padx=8)
        btn_voltar.pack(side="left", padx=8)

        colunas = ("Código", "Nome", "Custo", "Lucro (%)", "Sugest.", "Vr. Venda", "Qtd. Mín.", "Qtd. Atual")
        tree = ttk.Treeview(frame_estoque, columns=colunas, show="headings")
        for col in colunas:
            tree.heading(col, text=col)
            tree.column(col, width=140)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def atualizar_tabela():
            for item in tree.get_children():
                tree.delete(item)
            try:
                for p in listar_produtos():
                    tree.insert("", tk.END, values=p)
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao carregar produtos:\n{e}")

        atualizar_tabela()

        editing_codigo = {"value": None}

        def mostrar_cadastro_novo():
            editing_codigo["value"] = None
            entry_codigo.configure(state="normal")
            entry_codigo.delete(0, tk.END)
            entry_nome.delete(0, tk.END)
            entry_custo.delete(0, tk.END); entry_custo.insert(0, "0,00")
            entry_lucro.delete(0, tk.END); entry_lucro.insert(0, "0")
            entry_sugestao.configure(state="normal"); entry_sugestao.delete(0, tk.END); entry_sugestao.insert(0, "0,00"); entry_sugestao.configure(state="readonly")
            entry_preco.delete(0, tk.END); entry_preco.insert(0, "0,00")
            lbl_preco_pct.configure(text="0,0%")
            entry_minimo.delete(0, tk.END); entry_minimo.insert(0, "0")
            entry_estoque.delete(0, tk.END); entry_estoque.insert(0, "0")
            entry_obs.delete("1.0", tk.END)
            entry_validade.delete(0, tk.END)
            lbl_validade_dias.configure(text="Dias até validade: -")
            entry_validade_dias.configure(state="normal"); entry_validade_dias.delete(0, tk.END); entry_validade_dias.insert(0, "0"); entry_validade_dias.configure(state="readonly")
            frame_estoque.pack_forget()
            frame_cadastro.pack(fill="both", expand=True)

        def apagar_produto():
            selecionado = tree.selection()
            if not selecionado:
                messagebox.showwarning("Aviso", "Selecione um produto para apagar.")
                return
            if not messagebox.askyesno("Confirmação", "Deseja realmente apagar este produto?"):
                return
            valores = tree.item(selecionado[0])["values"]
            codigo = valores[0]
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM produtos WHERE codigo=%s", (codigo,))
                conn.commit()
                cursor.close()
                conn.close()
                atualizar_tabela()
                messagebox.showinfo("Sucesso", "Produto apagado com sucesso!")
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao apagar produto:\n{e}")

        def alterar_produto():
            selecionado = tree.selection()
            if not selecionado:
                messagebox.showwarning("Aviso", "Selecione um produto para alterar.")
                return
            valores = tree.item(selecionado[0])["values"]
            codigo = valores[0]
            produto = buscar_produto_por_codigo(codigo)
            if not produto:
                messagebox.showerror("Erro", "Falha ao carregar dados do produto selecionado.")
                return

            entry_codigo.configure(state="normal")
            entry_codigo.delete(0, tk.END); entry_codigo.insert(0, str(produto[0]))
            entry_nome.delete(0, tk.END); entry_nome.insert(0, str(produto[1]))
            entry_custo.delete(0, tk.END); entry_custo.insert(0, f"{float(produto[2]):.2f}".replace(".", ","))
            entry_lucro.delete(0, tk.END); entry_lucro.insert(0, str(produto[3]))
            entry_sugestao.configure(state="normal"); entry_sugestao.delete(0, tk.END)
            try:
                entry_sugestao.insert(0, f"{float(produto[4]):.2f}".replace(".", ","))
            except Exception:
                entry_sugestao.insert(0, "0,00")
            entry_sugestao.configure(state="readonly")
            entry_preco.delete(0, tk.END)
            try:
                entry_preco.insert(0, f"{float(produto[5]):.2f}".replace(".", ","))
            except Exception:
                entry_preco.insert(0, "0,00")
            try:
                custo_val = float(produto[2])
                preco_val = float(produto[5])
                pct = ((preco_val - custo_val) / custo_val * 100) if custo_val != 0 else 0
            except Exception:
                pct = 0
            lbl_preco_pct.configure(text=f"{pct:.1f}%")
            entry_minimo.delete(0, tk.END); entry_minimo.insert(0, str(produto[6]))
            entry_estoque.delete(0, tk.END); entry_estoque.insert(0, str(produto[7]))
            entry_obs.delete("1.0", tk.END)
            if len(produto) > 9 and produto[9] is not None:
                entry_obs.insert("1.0", str(produto[9]))
            entry_validade.delete(0, tk.END)
            if len(produto) > 10 and produto[10] is not None:
                try:
                    dias = int(produto[10])
                    lbl_validade_dias.configure(text=f"Dias até validade: {dias}")
                    entry_validade_dias.configure(state="normal"); entry_validade_dias.delete(0, tk.END); entry_validade_dias.insert(0, str(dias)); entry_validade_dias.configure(state="readonly")
                except Exception:
                    lbl_validade_dias.configure(text="Dias até validade: -")
                    entry_validade_dias.configure(state="normal"); entry_validade_dias.delete(0, tk.END); entry_validade_dias.insert(0, "0"); entry_validade_dias.configure(state="readonly")
            else:
                lbl_validade_dias.configure(text="Dias até validade: -")
                entry_validade_dias.configure(state="normal"); entry_validade_dias.delete(0, tk.END); entry_validade_dias.insert(0, "0"); entry_validade_dias.configure(state="readonly")

            editing_codigo["value"] = codigo
            frame_estoque.pack_forget()
            frame_cadastro.pack(fill="both", expand=True)

        def parse_num(text):
            try:
                return float(str(text).strip().replace(",", "."))
            except Exception:
                return 0.0

        def atualizar_sugestao_por_custo_lucro(event=None):
            custo = parse_num(entry_custo.get())
            try:
                lucro_pct = float(str(entry_lucro.get()).strip().replace(",", ".") or 0)
            except Exception:
                lucro_pct = 0.0
            preco_sug = custo * (1 + lucro_pct / 100.0)
            entry_sugestao.configure(state="normal")
            entry_sugestao.delete(0, tk.END)
            entry_sugestao.insert(0, f"{preco_sug:.2f}".replace(".", ","))
            entry_sugestao.configure(state="readonly")
            try:
                preco_venda = parse_num(entry_preco.get())
                pct = ((preco_venda - custo) / custo * 100) if custo != 0 else 0
            except Exception:
                pct = 0
            lbl_preco_pct.configure(text=f"{pct:.1f}%")

        def atualizar_lucro_por_custo_preco(event=None):
            custo = parse_num(entry_custo.get())
            preco_venda = parse_num(entry_preco.get())
            if custo > 0:
                lucro_pct = (preco_venda - custo) / custo * 100.0
            else:
                lucro_pct = 0.0
            entry_lucro.delete(0, tk.END)
            entry_lucro.insert(0, f"{lucro_pct:.2f}".replace(".", ","))
            atualizar_sugestao_por_custo_lucro()
            lbl_preco_pct.configure(text=f"{lucro_pct:.1f}%")

        def validar_numero_simples(new_value):
            if new_value == "":
                return True
            allowed = "0123456789.,"
            for ch in new_value:
                if ch not in allowed:
                    return False
            return True

        vcmd_num = (janela.register(lambda P: validar_numero_simples(P)), "%P")

        try:
            entry_custo._entry.configure(validate="key", validatecommand=vcmd_num)
            entry_preco._entry.configure(validate="key", validatecommand=vcmd_num)
            entry_lucro._entry.configure(validate="key", validatecommand=vcmd_num)
        except Exception:
            pass

        entry_custo.bind("<FocusOut>", lambda ev: atualizar_sugestao_por_custo_lucro())
        entry_custo.bind("<KeyRelease>", lambda ev: atualizar_sugestao_por_custo_lucro())
        entry_lucro.bind("<FocusOut>", lambda ev: atualizar_sugestao_por_custo_lucro())
        entry_lucro.bind("<KeyRelease>", lambda ev: atualizar_sugestao_por_custo_lucro())
        entry_preco.bind("<FocusOut>", lambda ev: atualizar_lucro_por_custo_preco())
        entry_preco.bind("<KeyRelease>", lambda ev: atualizar_lucro_por_custo_preco())

        def salvar_produto():
            codigo = entry_codigo.get().strip()
            nome = entry_nome.get().strip()
            custo_text = entry_custo.get().strip().replace(",", ".") or "0"
            lucro_text = entry_lucro.get().strip().replace(",", ".") or "0"
            preco_text = entry_preco.get().strip().replace(",", ".") or "0"
            minimo_text = entry_minimo.get().strip() or "0"
            estoque_text = entry_estoque.get().strip() or "0"
            observacao_text = entry_obs.get("1.0", tk.END).strip()

            validade_dias_val = None
            try:
                dias_calc = calcular_dias_validade()
                if dias_calc is not None:
                    validade_dias_val = int(dias_calc)
            except Exception:
                validade_dias_val = None

            if not codigo or not nome:
                messagebox.showwarning("Aviso", "Código e Nome são obrigatórios.")
                return

            try:
                custo = float(custo_text)
                lucro = float(lucro_text)
                preco = float(preco_text)
                minimo = int(float(minimo_text))
                estoque_inicial = int(float(estoque_text))
            except Exception:
                messagebox.showwarning("Aviso", "Verifique os valores numéricos.")
                return

            preco_sugerido = custo * (1 + lucro / 100.0)

            try:
                conexao = get_connection()
                cursor = conexao.cursor()
                if editing_codigo["value"]:
                    try:
                        cursor.execute("""
                            UPDATE produtos SET codigo=%s, nome=%s, custo=%s, lucro_percentual=%s,
                            preco_venda=%s, estoque_minimo=%s, estoque_inicial=%s, observacao=%s, validade_dias=%s
                            WHERE codigo=%s
                        """, (
                            codigo, nome, custo, lucro, preco, minimo, estoque_inicial, observacao_text, validade_dias_val,
                            editing_codigo["value"]
                        ))
                    except mysql.connector.Error:
                        cursor.execute("""
                            UPDATE produtos SET codigo=%s, nome=%s, custo=%s, lucro_percentual=%s,
                            preco_venda=%s, estoque_minimo=%s, estoque_inicial=%s
                            WHERE codigo=%s
                        """, (
                            codigo, nome, custo, lucro, preco, minimo, estoque_inicial,
                            editing_codigo["value"]
                        ))
                else:
                    try:
                        cursor.execute("""
                            INSERT INTO produtos (codigo, nome, custo, lucro_percentual, preco_venda, estoque_minimo, estoque_inicial, observacao, validade_dias)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            codigo, nome, custo, lucro, preco, minimo, estoque_inicial, observacao_text, validade_dias_val
                        ))
                    except mysql.connector.Error:
                        cursor.execute("""
                            INSERT INTO produtos (codigo, nome, custo, lucro_percentual, preco_venda, estoque_minimo, estoque_inicial)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            codigo, nome, custo, lucro, preco, minimo, estoque_inicial
                        ))
                conexao.commit()
                cursor.close()
                conexao.close()
                messagebox.showinfo("Sucesso", "Produto salvo com sucesso!")
                editing_codigo["value"] = None
                frame_cadastro.pack_forget()
                frame_estoque.pack(fill="both", expand=True)
                atualizar_tabela()
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao salvar produto:\n{e}")

        def cancelar_cadastro():
            if messagebox.askyesno("Cancelar", "Deseja cancelar o cadastro?"):
                editing_codigo["value"] = None
                frame_cadastro.pack_forget()
                frame_estoque.pack(fill="both", expand=True)

        btn_salvar.configure(command=salvar_produto)
        btn_cancelar.configure(command=cancelar_cadastro)
        btn_voltar.configure(command=cancelar_cadastro)

        frame_botoes_estoque = ctk.CTkFrame(frame_estoque)
        frame_botoes_estoque.pack(fill="x", padx=10, pady=10)

        botoes_estoque = [
            ("Novo", mostrar_cadastro_novo),
            ("Alterar", alterar_produto),
            ("Apagar", apagar_produto),
            ("Atualizar", atualizar_tabela),
            ("Voltar", janela.destroy)
        ]

        for texto, comando in botoes_estoque:
            btn = ctk.CTkButton(frame_botoes_estoque, text=texto, fg_color=COR_PRIMARIA, hover_color=COR_SECUNDARIA, command=comando)
            btn.pack(side="left", padx=5, pady=5)

        frame_cadastro.pack_forget()
        frame_estoque.pack(fill="both", expand=True)

    # ---------------------------
    # Global handlers that check PDV visibility before acting
    # ---------------------------
    def on_global_plus(event=None):
        if pdv_frame.winfo_ismapped():
            mostrar_finalizacao()

    def on_global_minus(event=None):
        show_frame_in_main(pdv_frame)
        entry_pdv_codigo.focus_set()

    def on_global_delete(event=None):
        if pdv_frame.winfo_ismapped():
            remover_item_pdv()

    def on_global_up(event=None):
        children = frame_main.winfo_children()
        if children:
            current = children[0]
            for w in current.winfo_children():
                try:
                    if isinstance(w, ctk.CTkLabel) and "Finalizar Venda" in w.cget("text"):
                        current.event_generate("<Up>")
                        return
                except Exception:
                    pass
        if pdv_frame.winfo_ismapped():
            select_prev_item()

    def on_global_down(event=None):
        children = frame_main.winfo_children()
        if children:
            current = children[0]
            for w in current.winfo_children():
                try:
                    if isinstance(w, ctk.CTkLabel) and "Finalizar Venda" in w.cget("text"):
                        current.event_generate("<Down>")
                        return
                except Exception:
                    pass
        if pdv_frame.winfo_ismapped():
            select_next_item()

    def select_prev_item(event=None):
        if not pdv_frame.winfo_ismapped():
            return
        items = tree_pdv.get_children()
        if not items:
            return
        sel = tree_pdv.selection()
        if not sel:
            tree_pdv.selection_set(items[-1])
            tree_pdv.see(items[-1])
            return
        cur = sel[0]
        try:
            idx = items.index(cur)
        except ValueError:
            idx = 0
        new_idx = max(0, idx - 1)
        tree_pdv.selection_set(items[new_idx])
        tree_pdv.see(items[new_idx])

    def select_next_item(event=None):
        if not pdv_frame.winfo_ismapped():
            return
        items = tree_pdv.get_children()
        if not items:
            return
        sel = tree_pdv.selection()
        if not sel:
            tree_pdv.selection_set(items[0])
            tree_pdv.see(items[0])
            return
        cur = sel[0]
        try:
            idx = items.index(cur)
        except ValueError:
            idx = 0
        new_idx = min(len(items) - 1, idx + 1)
        tree_pdv.selection_set(items[new_idx])
        tree_pdv.see(items[new_idx])

    app.bind_all("<KeyPress-plus>", on_global_plus)
    app.bind_all("<KeyPress-KP_Add>", on_global_plus)
    app.bind_all("<KeyPress-minus>", on_global_minus)
    app.bind_all("<KeyPress-KP_Subtract>", on_global_minus)
    app.bind_all("<Delete>", on_global_delete)
    app.bind_all("<Up>", on_global_up)
    app.bind_all("<Down>", on_global_down)

    welcome_frame = ctk.CTkFrame(frame_main)
    lbl_welcome = ctk.CTkLabel(welcome_frame, text="Bem-vindo ao Sistema PDV\nUse o menu à esquerda para navegar.", font=ctk.CTkFont(size=16))
    lbl_welcome.pack(expand=True)
    show_frame_in_main(welcome_frame)

    botoes = [
        ("Clientes", None),
        ("Estoque", abrir_estoque),
        ("Compras", None),
        ("Vendas", lambda: vendas_interface.mostrar_vendas(app)),
        ("Caixa", None),
        ("A Pagar", None),
        ("A Receber", None),
        ("PDV", mostrar_pdv)
    ]
    for texto, comando in botoes:
        btn = ctk.CTkButton(frame_menu, text=texto, fg_color=COR_PRIMARIA, hover_color=COR_SECUNDARIA, command=comando)
        btn.pack(pady=10, fill="x")

    app.mainloop()


