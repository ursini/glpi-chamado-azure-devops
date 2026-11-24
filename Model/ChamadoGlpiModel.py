import os
import uuid
from dataclasses import dataclass, field


TIPOS_SERVICO = ["Erros Especifico", "Erro Geral"]
PRIORIDADES = {"Muito Alta": "5", "Alta": "4", "Média": "3", "Baixa": "2", "Muito Baixa": "1"}


@dataclass
class ChamadoGlpiModel:
    """Dados que o analista preenche no formulário antes do robô abrir o chamado."""

    titulo: str
    descricao_markdown: str
    tipo_servico: str = "Erros Especifico"
    prioridade: str = "Média"
    card_azure: str = ""
    anexos: list = field(default_factory=list)
    sem_print_util: bool = False
    simular: bool = False

    # referência única que vai no fim da descrição; serve para achar o chamado se o número não aparecer
    referencia: str = field(default_factory=lambda: uuid.uuid4().hex[:10].upper())

    # preenchidos pelo robô
    numero_chamado: str = ""
    link_chamado: str = ""
    card_criado_pelo_robo: bool = False   # o campo Card no Azure veio vazio e o robô criou
    aviso_card: str = ""                  # motivo de o card não ter sido criado

    @property
    def titulo_glpi(self) -> str:
        return f"RPA - Consultas | {self.titulo}"

    @property
    def titulo_azure(self) -> str:
        return f"[GLPI {self.numero_chamado}] - {self.titulo}"

    @property
    def linha_glpi_azure(self) -> str:
        return f"**GLPI:** [{self.numero_chamado}]({self.link_chamado})"

    @property
    def repro_steps_azure(self) -> str:
        return f'<div>GLPI: {self.numero_chamado} - <a href="{self.link_chamado}">{self.link_chamado}</a></div>'

    def validar(self):
        erros = []
        if not self.titulo.strip():
            erros.append("Título é obrigatório (SISTEMA - TRIBUNAL - O QUE ACONTECE).")
        elif self.titulo.count(" - ") < 2:
            erros.append("Título fora do padrão: use SISTEMA - TRIBUNAL - O QUE ACONTECE.")
        if "—" in self.titulo or "–" in self.titulo:
            erros.append("Título não pode ter travessão; use hífen simples com espaço.")
        if not self.descricao_markdown.strip():
            erros.append("Descrição é obrigatória.")
        if not self.anexos and not self.sem_print_util:
            erros.append("Coloque pelo menos um print do caso (Anexar arquivos ou Ctrl+V) "
                         "ou marque 'Não tem print útil'.")
        faltando = [a for a in self.anexos if not os.path.isfile(a)]
        if faltando:
            erros.append("Arquivo não encontrado: " + ", ".join(os.path.basename(a) for a in faltando))
        if self.tipo_servico not in TIPOS_SERVICO:
            erros.append(f"Tipo de serviço inválido: {self.tipo_servico}.")
        if self.prioridade not in PRIORIDADES:
            erros.append(f"Prioridade inválida: {self.prioridade}.")
        if self.card_azure and not self.card_azure.isdigit():
            erros.append("Card do Azure deve ser só o número (ex.: 49680).")
        return erros
