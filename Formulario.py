import os
import webbrowser
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import ImageGrab

from Model.ChamadoGlpiModel import ChamadoGlpiModel, TIPOS_SERVICO, PRIORIDADES
from Helper import CredencialHelper

COR_DW = "#b2341c"
PASTA_COLADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log", "prints_colados")


class Formulario:
    """Janela que aparece antes do robô rodar, com os dados do chamado."""

    def __init__(self):
        self.resultado = None
        self.anexos = []
        self.janela = tk.Tk()
        self.janela.title("GLPI - Abertura de chamado (Consulta Processual)")
        self.janela.geometry("860x780")
        self.janela.configure(padx=16, pady=12)
        self.montar()
        self.janela.bind_all("<Control-v>", self.colar, add="+")
        self.janela.bind_all("<Control-V>", self.colar, add="+")

    def montar(self):
        j = self.janela
        tk.Label(j, text="Abertura de chamado no GLPI", font=("Segoe UI", 15, "bold"), fg=COR_DW).pack(anchor="w")
        tk.Label(j, text="O robô preenche o login da Microsoft com a senha salva neste computador. O código do SMS você digita no Chrome.",
                 font=("Segoe UI", 9), fg="#555").pack(anchor="w", pady=(0, 10))

        grade = tk.Frame(j)
        grade.pack(fill="x")
        grade.columnconfigure(1, weight=1)

        tk.Label(grade, text="Título *").grid(row=0, column=0, sticky="w", pady=3)
        self.titulo = tk.Entry(grade)
        self.titulo.grid(row=0, column=1, sticky="ew", pady=3)
        tk.Label(grade, text="SISTEMA - TRIBUNAL - O QUE ACONTECE  (ex.: EPROC - TJRJ - ADVOGADO PARADO NA TELA ALTERAR SENHA)",
                 font=("Segoe UI", 8), fg="#777").grid(row=1, column=1, sticky="w")

        tk.Label(grade, text="Card no Azure").grid(row=2, column=0, sticky="w", pady=3)
        self.card = tk.Entry(grade, width=12)
        self.card.grid(row=2, column=1, sticky="w", pady=3)
        tk.Label(grade, text="Deixe vazio para o robô criar o card no board. Se o card já existe, coloque o número.",
                 fg="#777", font=("Segoe UI", 8)).grid(row=2, column=1, sticky="w", padx=(110, 0))

        tk.Label(grade, text="Tipo de serviço").grid(row=3, column=0, sticky="w", pady=3)
        self.servico = ttk.Combobox(grade, values=TIPOS_SERVICO, state="readonly", width=20)
        self.servico.set(TIPOS_SERVICO[0])
        self.servico.grid(row=3, column=1, sticky="w", pady=3)
        tk.Label(grade, text="Erros Especifico: um tribunal ou sistema.  Erro Geral: vários tribunais, ambiente, site inteiro.",
                 font=("Segoe UI", 8), fg="#777").grid(row=4, column=1, sticky="w")

        tk.Label(grade, text="Prioridade").grid(row=5, column=0, sticky="w", pady=3)
        self.prioridade = ttk.Combobox(grade, values=list(PRIORIDADES), state="readonly", width=20)
        self.prioridade.set("Média")
        self.prioridade.grid(row=5, column=1, sticky="w", pady=3)

        topo_desc = tk.Frame(j)
        topo_desc.pack(fill="x", pady=(10, 2))
        tk.Label(topo_desc, text="Descrição * (Markdown, igual ao card: erro, o que o print mostra, resumo, tabela, ação, exemplos)").pack(side="left")
        tk.Button(topo_desc, text="Carregar de arquivo", command=self.carregar_descricao).pack(side="right")
        self.descricao = tk.Text(j, height=14, wrap="word", font=("Consolas", 10))
        self.descricao.pack(fill="both", expand=True)

        quadro_prints = tk.LabelFrame(j, text=" Prints do caso * (pelo menos um, ou marque Não tem print útil) ", fg=COR_DW, padx=8, pady=6)
        quadro_prints.pack(fill="x", pady=8)
        botoes_prints = tk.Frame(quadro_prints)
        botoes_prints.pack(side="left", anchor="n")
        tk.Button(botoes_prints, text="Anexar arquivos", width=16, command=self.escolher_anexos).pack(pady=2)
        tk.Button(botoes_prints, text="Colar print (Ctrl+V)", width=16, command=self.colar).pack(pady=2)
        tk.Button(botoes_prints, text="Remover selecionado", width=16, command=self.remover_anexo).pack(pady=2)
        self.sem_print = tk.BooleanVar(value=False)
        tk.Checkbutton(botoes_prints, text="Não tem print útil", variable=self.sem_print).pack(anchor="w", pady=(4, 0))
        self.lista_anexos = tk.Listbox(quadro_prints, height=5)
        self.lista_anexos.pack(side="left", fill="both", expand=True, padx=(8, 0))

        self.simular = tk.BooleanVar(value=False)
        rodape = tk.Frame(j)
        rodape.pack(fill="x")
        tk.Checkbutton(rodape, text="Só simular (preenche o formulário e não envia)", variable=self.simular).pack(side="left")
        tk.Button(rodape, text="Esquecer token do Azure", command=self.esquecer_token, relief="flat", fg="#777").pack(side="right")
        tk.Button(rodape, text="Esquecer senha salva", command=self.esquecer_senha, relief="flat", fg="#777").pack(side="right")

        botoes = tk.Frame(j)
        botoes.pack(fill="x", pady=(10, 0))
        tk.Button(botoes, text="Abrir chamado", bg=COR_DW, fg="white", font=("Segoe UI", 10, "bold"),
                  padx=16, pady=4, command=self.confirmar).pack(side="right")
        tk.Button(botoes, text="Cancelar", command=self.janela.destroy).pack(side="right", padx=8)

    # ------------------------------------------------------------------ prints

    def adicionar_anexo(self, caminho: str):
        if caminho not in self.anexos:
            self.anexos.append(caminho)
            self.lista_anexos.insert("end", os.path.basename(caminho))

    def escolher_anexos(self):
        arquivos = filedialog.askopenfilenames(filetypes=[("Imagens e PDF", "*.png *.jpg *.jpeg *.pdf"), ("Todos", "*.*")])
        for arquivo in arquivos:
            self.adicionar_anexo(arquivo)

    def colar(self, evento=None):
        """Ctrl+V com imagem (print) ou arquivos copiados vira anexo. Texto continua colando normal na descrição."""
        try:
            conteudo = ImageGrab.grabclipboard()
        except Exception:
            conteudo = None
        if conteudo is None:
            if evento is None:
                messagebox.showinfo("Colar print", "Não tem imagem copiada. Tire o print (Win+Shift+S) e tente de novo.")
            return None
        if isinstance(conteudo, list):
            for arquivo in conteudo:
                if os.path.isfile(arquivo):
                    self.adicionar_anexo(arquivo)
        else:
            os.makedirs(PASTA_COLADOS, exist_ok=True)
            caminho = os.path.join(PASTA_COLADOS, f"print_{datetime.now():%Y%m%d_%H%M%S_%f}.png")
            conteudo.save(caminho, "PNG")
            self.adicionar_anexo(caminho)
        return "break"

    def remover_anexo(self):
        for indice in reversed(self.lista_anexos.curselection()):
            self.lista_anexos.delete(indice)
            del self.anexos[indice]

    # ------------------------------------------------------------------ resto

    def carregar_descricao(self):
        caminho = filedialog.askopenfilename(filetypes=[("Markdown ou texto", "*.md *.txt"), ("Todos", "*.*")])
        if caminho:
            with open(caminho, encoding="utf-8") as f:
                self.descricao.delete("1.0", "end")
                self.descricao.insert("1.0", f.read())

    def esquecer_senha(self):
        CredencialHelper.apagar()
        messagebox.showinfo("Senha", "E-mail e senha salvos foram apagados deste computador.")

    def esquecer_token(self):
        CredencialHelper.apagar_token_azure()
        messagebox.showinfo("Token", "O token do Azure salvo foi apagado deste computador.")

    def confirmar(self):
        chamado = ChamadoGlpiModel(
            titulo=self.titulo.get().strip().upper(),
            descricao_markdown=self.descricao.get("1.0", "end").strip(),
            tipo_servico=self.servico.get(),
            prioridade=self.prioridade.get(),
            card_azure=self.card.get().strip(),
            anexos=list(self.anexos),
            sem_print_util=self.sem_print.get(),
            simular=self.simular.get(),
        )
        erros = chamado.validar()
        if erros:
            messagebox.showwarning("Confira os dados", "\n".join(erros))
            return
        self.resultado = chamado
        self.janela.destroy()

    def exibir(self) -> ChamadoGlpiModel | None:
        self.janela.mainloop()
        return self.resultado


def pedir_credenciais():
    """Pede e-mail e senha da Microsoft. Devolve (email, senha, salvar) ou None para digitar no Chrome."""
    resultado = {}
    j = tk.Tk()
    j.title("Login Microsoft")
    j.configure(padx=16, pady=12)
    j.attributes("-topmost", True)
    tk.Label(j, text="Login da Microsoft para o GLPI", font=("Segoe UI", 12, "bold"), fg=COR_DW).grid(row=0, column=0, columnspan=2, sticky="w")
    tk.Label(j, text="O robô preenche e-mail e senha. O código do SMS você digita no Chrome.", fg="#555").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
    tk.Label(j, text="E-mail").grid(row=2, column=0, sticky="w")
    email = tk.Entry(j, width=40)
    email.grid(row=2, column=1, pady=3)
    tk.Label(j, text="Senha").grid(row=3, column=0, sticky="w")
    senha = tk.Entry(j, width=40, show="•")
    senha.grid(row=3, column=1, pady=3)
    salvar = tk.BooleanVar(value=True)
    tk.Checkbutton(j, text="Salvar neste computador (Gerenciador de Credenciais do Windows)", variable=salvar).grid(row=4, column=0, columnspan=2, sticky="w", pady=4)

    def ok():
        if email.get().strip() and senha.get():
            resultado["dados"] = (email.get().strip(), senha.get(), salvar.get())
            j.destroy()
    rodape = tk.Frame(j)
    rodape.grid(row=5, column=0, columnspan=2, sticky="e", pady=(8, 0))
    tk.Button(rodape, text="Digitar no Chrome", command=j.destroy).pack(side="left", padx=6)
    tk.Button(rodape, text="Entrar", bg=COR_DW, fg="white", command=ok).pack(side="left")
    email.focus_set()
    j.bind("<Return>", lambda _: ok())
    j.mainloop()
    return resultado.get("dados")


def pedir_token_azure():
    """Pede o token (PAT) do Azure DevOps. Devolve (token, salvar) ou None para criar o card à mão."""
    resultado = {}
    j = tk.Tk()
    j.title("Token do Azure DevOps")
    j.configure(padx=16, pady=12)
    j.attributes("-topmost", True)
    tk.Label(j, text="Token do Azure DevOps para criar o card", font=("Segoe UI", 12, "bold"), fg=COR_DW).grid(row=0, column=0, columnspan=2, sticky="w")
    tk.Label(j, text="O chamado já foi aberto. Com o token, o robô cria o card no board e liga com o chamado.\n"
                     "Criar em dev.azure.com/DWRPA > User settings > Personal access tokens > New Token,\n"
                     "escopo Custom defined e só Work Items: Read & write.",
             fg="#555", justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
    tk.Label(j, text="Token").grid(row=2, column=0, sticky="w")
    token = tk.Entry(j, width=60, show="•")
    token.grid(row=2, column=1, pady=3)
    salvar = tk.BooleanVar(value=True)
    tk.Checkbutton(j, text="Salvar neste computador (Gerenciador de Credenciais do Windows)", variable=salvar).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)

    def ok():
        if token.get().strip():
            resultado["dados"] = (token.get().strip(), salvar.get())
            j.destroy()
    rodape = tk.Frame(j)
    rodape.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))
    tk.Button(rodape, text="Criar o card à mão", command=j.destroy).pack(side="left", padx=6)
    tk.Button(rodape, text="Criar card", bg=COR_DW, fg="white", command=ok).pack(side="left")
    token.focus_set()
    j.bind("<Return>", lambda _: ok())
    j.mainloop()
    return resultado.get("dados")


def exibir_resultado(chamado: ChamadoGlpiModel):
    """Mostra o número do chamado e o que colar no card do Azure."""
    j = tk.Tk()
    j.title("Chamado aberto")
    j.configure(padx=16, pady=12)
    tk.Label(j, text=f"Chamado {chamado.numero_chamado} aberto", font=("Segoe UI", 14, "bold"), fg=COR_DW).pack(anchor="w")

    def linha(rotulo, valor):
        tk.Label(j, text=rotulo, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 0))
        quadro = tk.Frame(j)
        quadro.pack(fill="x")
        campo = tk.Entry(quadro, width=90)
        campo.insert(0, valor)
        campo.config(state="readonly")
        campo.pack(side="left", fill="x", expand=True)

        def copiar():
            j.clipboard_clear()
            j.clipboard_append(valor)
        tk.Button(quadro, text="Copiar", command=copiar).pack(side="left", padx=4)

    linha("Link do chamado", chamado.link_chamado)
    link_card = f"https://dev.azure.com/DWRPA/RPA/_workitems/edit/{chamado.card_azure}" if chamado.card_azure else ""
    if chamado.card_criado_pelo_robo:
        tk.Label(j, text=f"Card {chamado.card_azure} criado no board e ligado ao chamado", font=("Segoe UI", 11, "bold"),
                 fg="seagreen").pack(anchor="w", pady=(10, 0))
        linha("Link do card", link_card)
    else:
        if chamado.aviso_card:
            tk.Label(j, text=chamado.aviso_card, fg="firebrick", wraplength=720, justify="left").pack(anchor="w", pady=(10, 0))
        linha("Título do card no Azure", chamado.titulo_azure)
        linha("Última linha dos Passos de reprodução do card", chamado.linha_glpi_azure)
        tk.Label(j, text="No card: tag CONS, tipo Bug, título acima e a linha do GLPI no fim dos Passos de reprodução.",
                 fg="#555").pack(anchor="w", pady=(10, 0))
    rodape = tk.Frame(j)
    rodape.pack(fill="x", pady=(12, 0))
    tk.Button(rodape, text="Abrir chamado no navegador", command=lambda: webbrowser.open(chamado.link_chamado)).pack(side="left")
    if link_card:
        tk.Button(rodape, text="Abrir card no Azure", command=lambda: webbrowser.open(link_card)).pack(side="left", padx=6)
    tk.Button(rodape, text="Fechar", command=j.destroy).pack(side="right")
    j.mainloop()
