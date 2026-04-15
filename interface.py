import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from datetime import datetime, date

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
        cursor.execute("""
            SELECT codigo, nome, custo, lucro_percentual, preco_sugerido, preco_venda, estoque_minimo, estoque_inicial
            FROM produtos
            WHERE codigo = %s
            LIMIT 1
        """, (codigo,))
        return cursor.fetchone()
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

    frame_pdv_actions = ctk.CTkFrame(left_panel)
    frame_pdv_actions.pack(anchor="w", pady=(12,6))
    btn_pdv_add = ctk.CTkButton(frame_pdv_actions, text="Adicionar (Enter)", fg_color=COR_PRIMARIA)
    btn_pdv_remove = ctk.CTkButton(frame_pdv_actions, text="Remover Item", fg_color="#d9534f")
    btn_pdv_add.pack(side="left", padx=6)
    btn_pdv_remove.pack(side="left", padx=6)

    right_panel = ctk.CTkFrame(pdv_body)
    right_panel.pack(side="left", fill="both", expand=True)

    colunas_pdv = ("Item", "Código", "Descrição", "Qtd", "Preço", "Subtotal")
    tree_pdv = ttk.Treeview(right_panel, columns=colunas_pdv, show="headings", selectmode="browse")
    for c in colunas_pdv:
        tree_pdv.heading(c, text=c)
        tree_pdv.column(c, width=120 if c != "Descrição" else 300)
    tree_pdv.pack(fill="both", expand=True, padx=6, pady=6)

    frame_totais = ctk.CTkFrame(pdv_frame)
    frame_totais.pack(fill="x", padx=8, pady=(0,8))
    lbl_total_text = ctk.CTkLabel(frame_totais, text="TOTAL:", font=ctk.CTkFont(size=16, weight="bold"))
    lbl_total_text.pack(side="left", padx=(6,4))
    lbl_total_value = ctk.CTkLabel(frame_totais, text="R$ 0.00", font=ctk.CTkFont(size=16, weight="bold"))
    lbl_total_value.pack(side="left")

    pdv_item_counter = {"value": 0}
    pdv_total = {"value": 0.0}

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

    # Interpreta N*codigo
    def interpretar_codigo_entrada(texto):
        txt = texto.strip()
        if not txt:
            return (None, None)
        if "*" in txt:
            parts = txt.split("*", 1)
            left = parts[0].strip()
            right = parts[1].strip()
            try:
                qtd = float(left.replace(",", "."))
            except Exception:
                qtd = None
            codigo = right if right else None
            return (qtd, codigo)
        else:
            return (None, txt)

    def adicionar_item_pdv(event=None):
        raw = entry_pdv_codigo.get().strip()
        if not raw:
            messagebox.showwarning("Aviso", "Informe o código do produto (ou N*codigo).")
            return

        qtd_from_syntax, codigo_busca = interpretar_codigo_entrada(raw)
        if not codigo_busca:
            messagebox.showwarning("Aviso", "Código inválido. Use 'codigo' ou 'N*codigo'.")
            return

        try:
            produto = buscar_produto_por_codigo(codigo_busca)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao buscar produto:\n{e}")
            return

        if not produto:
            messagebox.showwarning("Aviso", f"Produto com código '{codigo_busca}' não encontrado.")
            return

        codigo_db, nome_db, _, _, preco_sugerido_db, preco_venda_db, _, _ = produto

        if qtd_from_syntax is not None:
            quantidade = qtd_from_syntax
        else:
            try:
                quantidade = float(entry_pdv_qtd.get().strip().replace(",", ".") or "0")
            except Exception:
                messagebox.showwarning("Aviso", "Quantidade inválida.")
                return

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

        subtotal = quantidade * preco_unit

        pdv_item_counter["value"] += 1
        item_id = pdv_item_counter["value"]
        tree_pdv.insert("", tk.END, values=(item_id, codigo_db, nome_db, f"{quantidade:g}", f"{preco_unit:.2f}", f"{subtotal:.2f}"))
        pdv_total["value"] += subtotal
        lbl_total_value.configure(text=f"R$ {pdv_total['value']:.2f}")

        entry_pdv_codigo.delete(0, tk.END)
        entry_pdv_qtd.delete(0, tk.END); entry_pdv_qtd.insert(0, "1")
        entry_pdv_preco_unit.delete(0, tk.END); entry_pdv_preco_unit.insert(0, "0.00")
        atualizar_subtotal_visual()

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
            pdv_total["value"] -= subtotal
            tree_pdv.delete(s)
        lbl_total_value.configure(text=f"R$ {pdv_total['value']:.2f}")

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

    def mostrar_pdv():
        limpar_pdv()
        show_frame_in_main(pdv_frame)

    # --- Navigation and shortcuts for PDV (defined after PDV widgets exist) ---
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

    # ---------------------------
    # Finalização de venda (tecla +)
    # ---------------------------
    def mostrar_finalizacao(event=None):
        # cria frame de finalização
        frame_final = ctk.CTkFrame(frame_main)

        # Header
        ctk.CTkLabel(frame_final, text="Finalizar Venda", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="nw", pady=(8,6), padx=8)

        # Total a pagar (pega do pdv_total)
        total_a_pagar = pdv_total["value"]
        frame_total = ctk.CTkFrame(frame_final)
        frame_total.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(frame_total, text="TOTAL A PAGAR:", text_color=COR_PRIMARIA, font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=(6,8))
        lbl_total_final = ctk.CTkLabel(frame_total, text=f"R$ {total_a_pagar:.2f}", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_total_final.pack(side="left")

        # Cliente / entrega (simples)
        frame_cliente = ctk.CTkFrame(frame_final)
        frame_cliente.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(frame_cliente, text="Dados do Cliente (opcional):", text_color="#666666").pack(anchor="w")
        entry_cliente = ctk.CTkEntry(frame_cliente, width=400, placeholder_text="Nome do cliente")
        entry_cliente.pack(side="left", padx=6, pady=6)
        entry_telefone = ctk.CTkEntry(frame_cliente, width=200, placeholder_text="Fone")
        entry_telefone.pack(side="left", padx=6, pady=6)

        # Informações do pagamento (lista de tipos)
        frame_pag = ctk.CTkFrame(frame_final)
        frame_pag.pack(fill="x", padx=12, pady=6)

        # Labels e entries em ordem (para navegação com setas)
        payment_types = [
            ("Dinheiro", "0,00"),
            ("PIX", "0,00"),
            ("Cartão Créd.", "0,00"),
            ("Cartão Déb.", "0,00"),
            ("Cheque", "0,00"),
            ("A. Campo1", "0,00"),
            ("B. Campo2", "0,00")
        ]

        payment_entries = []

        # Validação: apenas dígitos, ponto e vírgula (aceita ',' e '.')
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

        # Funções para limpar/restaurar valor padrão ao entrar/sair do campo
        def on_payment_focus_in(entry_widget, default_text):
            # quando receber foco, se o texto for o default, limpa para facilitar digitação
            try:
                cur = entry_widget.get()
                if cur.strip() == default_text:
                    entry_widget.delete(0, tk.END)
            except Exception:
                pass

        def on_payment_focus_out(entry_widget, default_text):
            # quando perder foco, se vazio, restaura default
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
            # configure validation on underlying tk.Entry
            try:
                ent._entry.configure(validate="key", validatecommand=vcmd)
            except Exception:
                pass
            ent.pack(side="left", padx=6)
            payment_entries.append(ent)

            # bind focus in/out to clear/restore default
            ent.bind("<FocusIn>", lambda ev, e=ent, d=default: on_payment_focus_in(e, d))
            ent.bind("<FocusOut>", lambda ev, e=ent, d=default: on_payment_focus_out(e, d))

        # TROCO (maior e antes dos totais)
        frame_troco = ctk.CTkFrame(frame_final)
        frame_troco.pack(fill="x", padx=12, pady=(8,4))
        lbl_troco_text = ctk.CTkLabel(frame_troco, text="TROCO:", text_color=COR_PRIMARIA, font=ctk.CTkFont(size=18, weight="bold"))
        lbl_troco_text.pack(side="left", padx=(6,8))
        lbl_troco_value = ctk.CTkLabel(frame_troco, text="R$ 0.00", font=ctk.CTkFont(size=18, weight="bold"))
        lbl_troco_value.pack(side="left")

        # Totais calculados
        frame_tot_calc = ctk.CTkFrame(frame_final)
        frame_tot_calc.pack(fill="x", padx=12, pady=6)
        lbl_total_pago_text = ctk.CTkLabel(frame_tot_calc, text="TOTAL (+):", text_color=COR_PRIMARIA)
        lbl_total_pago_text.pack(side="left", padx=(6,6))
        lbl_total_pago = ctk.CTkLabel(frame_tot_calc, text="R$ 0.00", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_total_pago.pack(side="left", padx=(0,12))

        # Observações e QR placeholder
        frame_obs_pix = ctk.CTkFrame(frame_final)
        frame_obs_pix.pack(fill="both", padx=12, pady=6, expand=False)
        ctk.CTkLabel(frame_obs_pix, text="PIX - QR Code (placeholder)", text_color="#666666").pack(side="left", padx=6)
        entry_obs_final = ctk.CTkEntry(frame_obs_pix, width=400, placeholder_text="Observações")
        entry_obs_final.pack(side="left", padx=12)

        # Botões de ação (Finalizar, Voltar)
        frame_actions_final = ctk.CTkFrame(frame_final)
        frame_actions_final.pack(fill="x", padx=12, pady=10)
        btn_finalizar = ctk.CTkButton(frame_actions_final, text="Finalizar (+)", fg_color="#28a745")
        btn_voltar_final = ctk.CTkButton(frame_actions_final, text="Voltar (-)", fg_color="#6c757d")
        btn_finalizar.pack(side="left", padx=8)
        btn_voltar_final.pack(side="left", padx=8)

        # Rodapé com data/hora e dia da semana
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

        # recalcula totais e troco
        def recalcular_totais(event=None):
            def to_float(txt):
                try:
                    return float(str(txt).strip().replace(",", ".") or "0")
                except Exception:
                    return 0.0
            total_pago = sum(to_float(e.get()) for e in payment_entries)
            troco = total_pago - total_a_pagar
            lbl_total_pago.configure(text=f"R$ {total_pago:.2f}")
            lbl_troco_value.configure(text=f"R$ {max(0.0, troco):.2f}")

        for e in payment_entries:
            e.bind("<KeyRelease>", lambda ev: recalcular_totais())

        # navegação entre campos de pagamento com setas
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

        # finalizar venda
        def finalizar_venda(event=None):
            total_pago_text = lbl_total_pago.cget("text").replace("R$", "").strip()
            try:
                total_pago = float(total_pago_text.replace(",", "."))
            except Exception:
                total_pago = 0.0
            if total_pago < total_a_pagar:
                if not messagebox.askyesno("Confirmar", "O total pago é menor que o total a pagar. Deseja prosseguir mesmo assim?"):
                    return
            messagebox.showinfo("Venda", f"Venda finalizada. Total pago: R$ {total_pago:.2f}")
            limpar_pdv()
            show_frame_in_main(pdv_frame)

        def voltar_sem_finalizar(event=None):
            show_frame_in_main(pdv_frame)

        btn_finalizar.configure(command=finalizar_venda)
        btn_voltar_final.configure(command=voltar_sem_finalizar)

        # binds locais: '+' e '-' e setas e delete (use bind, não bind_all em CTk widgets)
        frame_final.bind("<KeyPress-plus>", lambda e: finalizar_venda())
        frame_final.bind("<KeyPress-KP_Add>", lambda e: finalizar_venda())
        frame_final.bind("<KeyPress-minus>", lambda e: voltar_sem_finalizar())
        frame_final.bind("<KeyPress-KP_Subtract>", lambda e: voltar_sem_finalizar())
        frame_final.bind("<Up>", lambda e: focus_prev_payment())
        frame_final.bind("<Down>", lambda e: focus_next_payment())
        frame_final.bind("<Delete>", lambda e: remover_item_pdv())

        # binds individuais para garantir navegação mesmo com foco em entry
        for ent in payment_entries:
            ent.bind("<Up>", lambda ev: focus_prev_payment())
            ent.bind("<Down>", lambda ev: focus_next_payment())
            ent.bind("<KeyPress-plus>", lambda ev: finalizar_venda())
            ent.bind("<KeyPress-KP_Add>", lambda ev: finalizar_venda())
            ent.bind("<KeyPress-minus>", lambda ev: voltar_sem_finalizar())
            ent.bind("<KeyPress-KP_Subtract>", lambda ev: voltar_sem_finalizar())

            # ao entrar limpa se for o default "0,00", ao sair restaura se vazio
            # (já ligado acima com bind FocusIn/FocusOut)

        # mostrar frame de finalização
        show_frame_in_main(frame_final)
        recalcular_totais()

    # ---------------------------
    # Estoque (Toplevel) - versão sem grab_set e sem bind_all em CTk widgets
    # ---------------------------
    def abrir_estoque():
        janela = ctk.CTkToplevel(app)
        janela.title("Controle de Estoque")
        janela.geometry("1200x700")
        janela.transient(app)
        janela.lift()
        janela.focus_force()

        # Use bind (não bind_all) no Toplevel para encaminhar atalhos locais
        janela.bind("<KeyPress-plus>", lambda e: on_global_plus())
        janela.bind("<KeyPress-KP_Add>", lambda e: on_global_plus())
        janela.bind("<Delete>", lambda e: on_global_delete())
        janela.bind("<Up>", lambda e: on_global_up())
        janela.bind("<Down>", lambda e: on_global_down())
        janela.bind("<KeyPress-minus>", lambda e: on_global_minus())
        janela.bind("<KeyPress-KP_Subtract>", lambda e: on_global_minus())

        frame_estoque = ctk.CTkFrame(janela)
        frame_estoque.pack(fill="both", expand=True)

        # Conteúdo simplificado do Estoque (mantém funcionalidade principal)
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

        # Função apagar produto do estoque (usada pelo botão)
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
                cursor.close(); conn.close()
                atualizar_tabela()
                messagebox.showinfo("Sucesso", "Produto apagado com sucesso!")
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao apagar produto:\n{e}")

        # Botões básicos
        frame_botoes_estoque = ctk.CTkFrame(frame_estoque)
        frame_botoes_estoque.pack(fill="x", padx=10, pady=10)
        btn_atualizar = ctk.CTkButton(frame_botoes_estoque, text="Atualizar", fg_color=COR_PRIMARIA, command=atualizar_tabela)
        btn_apagar = ctk.CTkButton(frame_botoes_estoque, text="Apagar", fg_color="#d9534f", command=apagar_produto)
        btn_voltar = ctk.CTkButton(frame_botoes_estoque, text="Voltar", fg_color=COR_PRIMARIA, command=janela.destroy)
        btn_atualizar.pack(side="left", padx=5); btn_apagar.pack(side="left", padx=5); btn_voltar.pack(side="left", padx=5)

    # ---------------------------
    # Global handlers that check PDV visibility before acting
    # ---------------------------
    def on_global_plus(event=None):
        if pdv_frame.winfo_ismapped():
            mostrar_finalizacao()

    def on_global_minus(event=None):
        show_frame_in_main(pdv_frame)

    def on_global_delete(event=None):
        if pdv_frame.winfo_ismapped():
            remover_item_pdv()

    def on_global_up(event=None):
        # tenta encaminhar para finalização se estiver visível
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

    # Bind global shortcuts (apenas no app root)
    app.bind_all("<KeyPress-plus>", on_global_plus)
    app.bind_all("<KeyPress-KP_Add>", on_global_plus)
    app.bind_all("<KeyPress-minus>", on_global_minus)
    app.bind_all("<KeyPress-KP_Subtract>", on_global_minus)
    app.bind_all("<Delete>", on_global_delete)
    app.bind_all("<Up>", on_global_up)
    app.bind_all("<Down>", on_global_down)

    # Welcome frame initially
    welcome_frame = ctk.CTkFrame(frame_main)
    lbl_welcome = ctk.CTkLabel(welcome_frame, text="Bem-vindo ao Sistema PDV\nUse o menu à esquerda para navegar.", font=ctk.CTkFont(size=16))
    lbl_welcome.pack(expand=True)
    show_frame_in_main(welcome_frame)

    # Menu lateral buttons
    botoes = [
        ("Clientes", None),
        ("Estoque", abrir_estoque),
        ("Compras", None),
        ("Vendas", None),
        ("Caixa", None),
        ("A Pagar", None),
        ("A Receber", None),
        ("PDV", mostrar_pdv)
    ]
    for texto, comando in botoes:
        btn = ctk.CTkButton(frame_menu, text=texto, fg_color=COR_PRIMARIA, hover_color=COR_SECUNDARIA, command=comando)
        btn.pack(pady=10, fill="x")

    app.mainloop()





