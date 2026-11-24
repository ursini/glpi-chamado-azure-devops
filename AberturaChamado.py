import os
import re
import time
import logging
import ctypes
import threading
import subprocess
from datetime import datetime
from urllib.parse import quote

from selenium import webdriver
from selenium.common import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from Abstractions.Automation import Automation
from Exceptions.NotFoundExceptionDW import NotFoundExceptionDW
from Model.ChamadoGlpiModel import ChamadoGlpiModel, PRIORIDADES
from Helper.MarkdownHelper import md2html
from Helper import CredencialHelper
from Helper.AzureDevOpsHelper import AzureDevOpsHelper, TokenAzureRecusado

ERROS_SESSAO = ("invalid session id", "no such window", "disconnected", "chrome not reachable", "target window already closed")


class AberturaChamado(Automation):
    """Abre chamado de Consulta Processual no GLPI pelo formulário RPA.

    Usa os waits da Common (Automation). O Chrome sobe com um perfil próprio e fixo,
    então o login feito na primeira vez fica salvo para as próximas execuções.
    """

    # GLPI (todos os seletores em XPath)
    SEL_LOGADO = (By.XPATH, "//a[contains(@href,'logout.php')]")
    SEL_LOGIN_GLPI = (By.XPATH, "//input[@id='login_name']")
    SEL_BOTAO_MICROSOFT = (By.XPATH, "//button[@name='samlIdpId']")
    SEL_RADIO_CONSULTAS = (By.XPATH, "//input[@name='formcreator_field_32' and @value='Consultas']")
    SEL_SERVICO = (By.XPATH, "//select[@name='formcreator_field_33']/following-sibling::span[contains(@class,'select2')][1]"
                             "//span[contains(@class,'select2-selection--single')]")
    SEL_OPCOES_SELECT2 = (By.XPATH, "//li[contains(@class,'select2-results__option')]")
    SEL_DESCRICAO = (By.XPATH, "//textarea[@name='formcreator_field_37']")
    SEL_PRIORIDADE = (By.XPATH, "//select[@name='formcreator_field_77']")
    SEL_ANEXO = (By.XPATH, "//input[@type='file' and starts-with(@name,'_uploader_formcreator_field_38')]")
    SEL_ANEXOS_ENVIADOS = (By.XPATH, "//input[starts-with(@name,'_formcreator_field_38')]")
    SEL_BOTAO_ENVIAR = (By.XPATH, "//form[starts-with(@name,'plugin_formcreator_form')]//button[@name='add']")
    SEL_LINK_CHAMADO = (By.XPATH, "//a[contains(@href,'ticket.form.php?id=')]")
    SEL_RESULTADO_BUSCA = (By.XPATH, "//table[contains(@class,'search-results')]//a[contains(@href,'ticket.form.php?id=')]")
    SEL_EDITAR_DESCRICAO = (By.XPATH, "//div[contains(@class,'ITILContent')]//a[contains(@class,'edit-timeline-item')]")
    SEL_TITULO = (By.XPATH, "//div[contains(@class,'ITILContent')]//input[@name='name']")
    SEL_RESPONDER = (By.XPATH, "//button[contains(@class,'answer-action')]")
    SEL_FORM_ACOMPANHAMENTO = (By.XPATH, "//form[contains(@action,'itilfollowup.form.php')]//textarea[@name='content']")
    XP_SALVAR_DO_FORM = "./ancestor::form//button[@name='update']"   # relativo ao campo
    XP_ADICIONAR_DO_FORM = "./ancestor::form//button[@name='add']"    # relativo ao campo
    SEL_PAGINA = (By.XPATH, "//body")
    # Microsoft
    SEL_MS_EMAIL = (By.XPATH, "//input[@name='loginfmt']")
    SEL_MS_SENHA = (By.XPATH, "//input[@name='passwd']")
    SEL_MS_AVANCAR = (By.XPATH, "//*[@id='idSIButton9']")
    SEL_MS_ERRO_SENHA = (By.XPATH, "//*[@id='passwordError']")
    SEL_MS_CONTINUAR_CONECTADO = (By.XPATH, "//*[@id='KmsiCheckboxField']")
    SEL_MS_CONTAS = (By.XPATH, "//*[@data-test-id]")

    def __init__(self, config: dict, pedir_credenciais=None, pedir_token_azure=None):
        super().__init__()
        self.config = config
        self.url = config["url_glpi"].rstrip("/")
        self.tentativas = int(config.get("tentativas", 5))
        self.pasta_perfil = os.path.expandvars(config["pasta_perfil_chrome"])
        self.pasta_prints = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log", "prints")
        # callback da tela: devolve (email, senha, salvar) ou None se o analista preferir digitar no Chrome
        self.pedir_credenciais = pedir_credenciais
        # callback da tela: devolve (token, salvar) ou None se o analista preferir criar o card à mão
        self.pedir_token_azure = pedir_token_azure

    # ------------------------------------------------------------------ navegador

    def iniciar_chrome_perfil(self):
        """Chrome normal (não anônimo) com perfil próprio do robô, para guardar o login do GLPI."""
        os.makedirs(self.pasta_perfil, exist_ok=True)
        self.ensure_download_folder()
        try:
            driver_path = ChromeDriverManager().install()
        except Exception as ex:
            # sem acesso ao site do chromedriver: o Selenium Manager (já vem no Selenium) acha ou baixa o driver
            logging.warning(f"WEBDRIVER MANAGER FALHOU, USANDO O SELENIUM MANAGER: {str(ex).splitlines()[0]}")
            driver_path = None

        for tentativa in range(1, 4):
            self.fechar_chrome_do_robo()
            driver_service = ChromeService(driver_path) if driver_path else ChromeService()
            driver_service.hide_command_prompt_window = True
            options = webdriver.ChromeOptions()
            options.add_argument(f"--user-data-dir={self.pasta_perfil}")
            options.add_argument("--profile-directory=Default")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("prefs", {"download.default_directory": self.download_folder})
            try:
                self.driver = webdriver.Chrome(options=options, service=driver_service)
                break
            except WebDriverException as ex:
                logging.warning(f"CHROME NÃO ABRIU (TENTATIVA {tentativa}/3): {str(ex).splitlines()[0]}")
                if tentativa == 3:
                    raise Exception("O Chrome do robô não abriu. Feche as janelas do Chrome do robô e rode de novo.")
                time.sleep(3 * tentativa)

        self.driver.set_page_load_timeout(120)
        self.js = self.driver
        logging.info(f"CHROME ABERTO COM PERFIL {self.pasta_perfil}")

    def fechar_chrome_do_robo(self):
        """Fecha Chrome que sobrou de uma execução anterior. Só o do perfil do robô; o Chrome normal não é tocado."""
        pasta = os.path.basename(self.pasta_perfil.rstrip("\\/"))
        comando = (
            "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*{pasta}*' }} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", comando], timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), capture_output=True)
        except Exception as ex:
            logging.warning(f"NÃO CONSEGUI FECHAR O CHROME ANTERIOR: {ex}")

    def reiniciar_chrome(self):
        logging.warning("SESSÃO DO CHROME CAIU, ABRINDO DE NOVO")
        try:
            self.driver.quit()
        except Exception:
            pass
        self.iniciar_chrome_perfil()
        self.aguardar_login()

    def abrir_pagina(self, url: str):
        """Abre a página, espera carregar e refaz o login se a sessão do GLPI tiver caído."""
        self.driver.get(url)
        self.aguardar_carregar()
        if self.na_tela_de_login():
            logging.warning("GLPI PEDIU LOGIN DE NOVO")
            self.aguardar_login()
            self.driver.get(url)
            self.aguardar_carregar()

    def aguardar_carregar(self, segundos=60):
        fim = time.time() + segundos
        while time.time() < fim:
            try:
                if self.driver.execute_script("return document.readyState") == "complete":
                    return
            except WebDriverException:
                pass
            time.sleep(0.5)

    def na_tela_de_login(self) -> bool:
        return "login.microsoftonline" in self.driver.current_url or self.existe(self.SEL_LOGIN_GLPI)

    # ------------------------------------------------------------------ login

    def aguardar_login(self):
        """Preenche o login da Microsoft com a senha salva no Windows; o código do SMS é sempre digitado à mão."""
        self.driver.get(f"{self.url}/front/central.php")
        self.aguardar_carregar()
        if self.existe(self.SEL_LOGADO):
            logging.info("GLPI JÁ ESTÁ LOGADO")
            return

        logging.info("GLPI PEDIU LOGIN")
        automatico = False
        if self.config.get("login_microsoft", True):
            try:
                automatico = self.login_microsoft()
            except Exception as ex:
                logging.warning(f"LOGIN AUTOMÁTICO NÃO CONCLUÍDO, SEGUE À MÃO: {str(ex).splitlines()[0]}")
        self.avisar("Digite o código do SMS na janela do Chrome." if automatico else
                    "Faça o login no GLPI na janela do Chrome que abriu.\n\nO robô continua sozinho assim que você entrar.")

        limite = time.time() + 60 * int(self.config.get("minutos_espera_login", 10))
        while time.time() < limite:
            if self.existe(self.SEL_LOGADO):
                logging.info("LOGIN CONFIRMADO")
                return
            if self.existe(self.SEL_MS_CONTINUAR_CONECTADO):
                self.clicar(self.driver.find_element(*self.SEL_MS_AVANCAR))
                logging.info("MICROSOFT: CONTINUAR CONECTADO = SIM")
            time.sleep(2)
        raise TimeoutException("Login no GLPI não foi feito dentro do tempo.")

    def login_microsoft(self) -> bool:
        """Clica no botão da Microsoft e preenche e-mail e senha. Devolve True se chegou na etapa do SMS."""
        if self.existe(self.SEL_BOTAO_MICROSOFT):
            self.clicar(self.driver.find_element(*self.SEL_BOTAO_MICROSOFT))
            logging.info("MICROSOFT: BOTÃO DE LOGIN CLICADO")

        fim = time.time() + 30
        while time.time() < fim and not (self.existe(self.SEL_MS_EMAIL) or self.existe(self.SEL_MS_SENHA)
                                         or self.existe(self.SEL_MS_CONTAS)):
            if self.existe(self.SEL_LOGADO):
                return False
            time.sleep(0.5)

        email, senha = CredencialHelper.obter()
        salvar = False
        if not email and self.pedir_credenciais:
            dados = self.pedir_credenciais()
            if not dados:
                return False
            email, senha, salvar = dados
        if not email:
            return False

        if self.is_element_visible(self.SEL_MS_EMAIL, 5):
            campo = self.driver.find_element(*self.SEL_MS_EMAIL)
            campo.clear()
            campo.send_keys(email)
            self.clicar(self.wait_to_be_clickable(self.SEL_MS_AVANCAR))
            logging.info("MICROSOFT: E-MAIL PREENCHIDO")
        else:
            contas = [c for c in self.driver.find_elements(*self.SEL_MS_CONTAS)
                      if c.get_attribute("data-test-id").lower() == email.lower()]
            if contas:
                self.clicar(contas[0])
                logging.info("MICROSOFT: CONTA ESCOLHIDA NA LISTA")

        campo_senha = self.wait_to_be_visible(self.SEL_MS_SENHA, 20)
        campo_senha.clear()
        campo_senha.send_keys(senha)
        self.clicar(self.wait_to_be_clickable(self.SEL_MS_AVANCAR))
        logging.info("MICROSOFT: SENHA PREENCHIDA")

        if self.is_element_visible(self.SEL_MS_ERRO_SENHA, 5):
            CredencialHelper.apagar()
            self.avisar("A Microsoft recusou a senha salva. Ela foi apagada deste computador.\n\n"
                        "Digite a senha à mão no Chrome; na próxima execução o robô pede de novo.")
            return False
        if salvar:
            CredencialHelper.salvar(email, senha)
            logging.info("MICROSOFT: E-MAIL E SENHA SALVOS NO GERENCIADOR DE CREDENCIAIS DO WINDOWS")
        return True

    # ------------------------------------------------------------------ fluxo

    def abrir_chamado(self, chamado: ChamadoGlpiModel) -> ChamadoGlpiModel:
        self.retentar("PREENCHER FORMULARIO RPA", lambda: self.preencher_formulario(chamado))

        if chamado.simular:
            logging.info("MODO SIMULAÇÃO: FORMULÁRIO PREENCHIDO E NÃO ENVIADO")
            return chamado

        self.enviar_formulario(chamado)
        self.retentar("AJUSTAR TITULO", lambda: self.ajustar_titulo(chamado))
        if not chamado.card_azure and self.config.get("criar_card_azure", True):
            self.criar_card_azure(chamado)
        if chamado.card_azure:
            self.retentar("ACOMPANHAMENTO COM CARD", lambda: self.adicionar_acompanhamento(chamado))
        return chamado

    def criar_card_azure(self, chamado: ChamadoGlpiModel):
        """Cria o card (Bug) no board com o token do analista. Se der erro, o chamado continua aberto
        e o aviso aparece na tela final para o card ser criado à mão."""
        token = CredencialHelper.obter_token_azure()
        salvar = False
        if not token and self.pedir_token_azure:
            dados = self.pedir_token_azure()
            if dados:
                token, salvar = dados
        if not token or not token.strip():
            chamado.aviso_card = "Card não criado: sem token do Azure. Crie o card à mão com os dados abaixo."
            logging.warning("CARD AZURE NÃO CRIADO: SEM TOKEN")
            return
        token = token.strip()
        if salvar:
            # salva já: se a rede cair, o token não se perde; se o Azure recusar, é apagado lá embaixo
            CredencialHelper.salvar_token_azure(token)
            logging.info("TOKEN DO AZURE SALVO NO GERENCIADOR DE CREDENCIAIS DO WINDOWS")
        try:
            azure = AzureDevOpsHelper(self.config, token)
            sprint = None
            try:
                sprint = azure.sprint_atual()
            except TokenAzureRecusado:
                raise
            except Exception as ex:
                logging.warning(f"SPRINT ATUAL NÃO ENCONTRADA, CARD VAI SEM SPRINT: {ex}")
            numero = azure.criar_bug(chamado, sprint)
            chamado.card_azure = str(numero)
            chamado.card_criado_pelo_robo = True
            logging.info(f"CARD AZURE CRIADO: {numero} ({sprint or 'sem sprint'})")
        except TokenAzureRecusado as ex:
            CredencialHelper.apagar_token_azure()
            chamado.aviso_card = f"{ex} O token salvo foi apagado; na próxima execução o robô pede de novo. Crie este card à mão."
            logging.warning(f"CARD AZURE NÃO CRIADO: {ex}")
        except Exception as ex:
            chamado.aviso_card = f"Card não criado: {ex} Crie o card à mão com os dados abaixo."
            logging.warning(f"CARD AZURE NÃO CRIADO: {ex}")

    def preencher_formulario(self, chamado: ChamadoGlpiModel):
        self.abrir_pagina(f"{self.url}/marketplace/formcreator/front/formdisplay.php?id={self.config['id_formulario_rpa']}")
        radio = self.wait_until_exists(self.SEL_RADIO_CONSULTAS)
        self.driver.execute_script("arguments[0].click();", radio)

        self.escolher_select2(self.SEL_SERVICO, f"»{chamado.tipo_servico}")
        logging.info(f"TIPO DE SERVIÇO: {chamado.tipo_servico}")

        html = md2html(chamado.descricao_markdown)
        if chamado.card_azure:
            link = f"{self.config['url_card_azure']}{chamado.card_azure}"
            html = f'<p>Card Azure DevOps: <a href="{link}">{chamado.card_azure}</a> - {chamado.titulo}</p>\n' + html
        else:
            html = f"<p><strong>{chamado.titulo}</strong></p>\n" + html
        if not chamado.anexos and chamado.sem_print_util:
            html += "\n<p><em>Sem print útil para este caso (marcado por quem abriu o chamado).</em></p>"
        html += f"\n<p><small>Ref. robô: {chamado.referencia}</small></p>"
        self.preencher_tinymce_por_id(self.wait_until_exists(self.SEL_DESCRICAO).get_attribute("id"), html)
        logging.info("DESCRIÇÃO PREENCHIDA")

        self.driver.execute_script(
            "var s=arguments[0]; s.value=arguments[1]; if(window.jQuery){jQuery(s).trigger('change');}"
            "else{s.dispatchEvent(new Event('change',{bubbles:true}));}",
            self.wait_until_exists(self.SEL_PRIORIDADE), PRIORIDADES[chamado.prioridade],
        )
        logging.info(f"PRIORIDADE: {chamado.prioridade}")

        if chamado.anexos:
            self.anexar_arquivos(chamado.anexos)

    def enviar_formulario(self, chamado: ChamadoGlpiModel):
        """Envia e pega o número. Antes de clicar de novo, procura o chamado pela referência para não duplicar."""
        for tentativa in range(1, 4):
            botoes = self.driver.find_elements(*self.SEL_BOTAO_ENVIAR)
            if not botoes:
                break
            self.clicar(botoes[0])
            logging.info(f"FORMULÁRIO ENVIADO (TENTATIVA {tentativa}/3), AGUARDANDO NÚMERO DO CHAMADO")
            if self.capturar_numero(chamado, 45):
                return
            self.salvar_print("sem_numero_chamado")
            if self.buscar_por_referencia(chamado):
                return
            if not self.existe(self.SEL_BOTAO_ENVIAR):
                break
        if not chamado.numero_chamado and self.buscar_por_referencia(chamado):
            return
        raise NotFoundExceptionDW(
            f"Formulário enviado, mas o número do chamado não apareceu. Procure em Chamados pela "
            f"referência {chamado.referencia} antes de rodar de novo, para não duplicar."
        )

    def capturar_numero(self, chamado: ChamadoGlpiModel, segundos: int) -> bool:
        fim = time.time() + segundos
        while time.time() < fim:
            try:
                for link in self.driver.find_elements(*self.SEL_LINK_CHAMADO):
                    m = re.search(r"id=(\d+)", link.get_attribute("href") or "")
                    if m:
                        self.definir_numero(chamado, m.group(1))
                        return True
            except WebDriverException:
                pass
            time.sleep(1)
        return False

    def buscar_por_referencia(self, chamado: ChamadoGlpiModel) -> bool:
        url = (f"{self.url}/front/ticket.php?is_deleted=0&itemtype=Ticket&start=0"
               f"&criteria[0][field]=21&criteria[0][searchtype]=contains&criteria[0][value]={quote(chamado.referencia)}")
        for _ in range(3):
            self.abrir_pagina(url)
            links = self.driver.find_elements(*self.SEL_RESULTADO_BUSCA)
            if links:
                self.definir_numero(chamado, re.search(r"id=(\d+)", links[0].get_attribute("href")).group(1))
                logging.info("CHAMADO ACHADO PELA REFERÊNCIA")
                return True
            time.sleep(5)
        return False

    def definir_numero(self, chamado: ChamadoGlpiModel, numero: str):
        chamado.numero_chamado = numero
        chamado.link_chamado = f"{self.url}/front/ticket.form.php?id={numero}"
        logging.info(f"CHAMADO CRIADO: {numero}")

    def ajustar_titulo(self, chamado: ChamadoGlpiModel):
        self.abrir_pagina(chamado.link_chamado)
        editar = self.wait_until_exists(self.SEL_EDITAR_DESCRICAO)
        self.driver.execute_script("arguments[0].click();", editar)
        campo = self.wait_until_exists(self.SEL_TITULO)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", campo)
        if campo.get_attribute("value") == chamado.titulo_glpi:
            logging.info("TÍTULO JÁ ESTAVA AJUSTADO")
            return
        campo.clear()
        campo.send_keys(chamado.titulo_glpi)
        self.driver.execute_script("arguments[0].click();", campo.find_element(By.XPATH, self.XP_SALVAR_DO_FORM))
        self.aguardar_carregar()
        self.aguardar_texto(chamado.titulo_glpi)
        logging.info(f"TÍTULO: {chamado.titulo_glpi}")

    def adicionar_acompanhamento(self, chamado: ChamadoGlpiModel):
        link = f"{self.config['url_card_azure']}{chamado.card_azure}"
        self.abrir_pagina(chamado.link_chamado)
        self.wait_until_exists(self.SEL_EDITAR_DESCRICAO)
        if link in self.driver.find_element(*self.SEL_PAGINA).text:
            logging.info("ACOMPANHAMENTO COM O CARD JÁ EXISTE")
            return
        self.clicar(self.wait_until_exists(self.SEL_RESPONDER))
        area = self.wait_until_exists(self.SEL_FORM_ACOMPANHAMENTO)
        self.preencher_tinymce_por_id(area.get_attribute("id"), f'<p>Card Azure DevOps: <a href="{link}">{link}</a></p>')
        self.driver.execute_script("arguments[0].click();", area.find_element(By.XPATH, self.XP_ADICIONAR_DO_FORM))
        self.aguardar_carregar()
        self.aguardar_texto(link)
        logging.info(f"ACOMPANHAMENTO COM CARD {chamado.card_azure} ADICIONADO")

    # ------------------------------------------------------------------ apoio

    def aguardar_texto(self, texto: str, segundos=40):
        """Espera o texto aparecer na página (ignora espaços diferentes, como o espaço fixo do GLPI)."""
        alvo = " ".join(texto.split())
        fim = time.time() + segundos
        while time.time() < fim:
            try:
                pagina = self.driver.execute_script("return document.body.innerText") or ""
                if alvo in " ".join(pagina.replace("\xa0", " ").split()):
                    return
            except WebDriverException:
                pass
            time.sleep(1)
        raise TimeoutException(f"Texto não apareceu na página: {texto[:60]}")

    def clicar(self, elemento):
        """Rola até o elemento e clica; se algo estiver na frente, clica por JavaScript."""
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
        try:
            elemento.click()
        except WebDriverException:
            self.driver.execute_script("arguments[0].click();", elemento)

    def escolher_select2(self, seletor_caixa, texto_opcao: str):
        """Abre a lista e escolhe a opção. Se a lista não abrir (página ainda montando), clica de novo."""
        for _ in range(6):
            self.clicar(self.wait_until_exists(seletor_caixa))
            fim = time.time() + 5
            while time.time() < fim:
                for opcao in self.driver.find_elements(*self.SEL_OPCOES_SELECT2):
                    if opcao.text.strip() == texto_opcao:
                        self.driver.execute_script(
                            "arguments[0].dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));", opcao)
                        return
                time.sleep(0.3)
            self.driver.find_element(*self.SEL_PAGINA).send_keys(Keys.ESCAPE)  # fecha a lista antes de tentar de novo
        raise NotFoundExceptionDW(f"Opção '{texto_opcao}' não apareceu na lista.")

    def preencher_tinymce_por_id(self, id_area: str, html: str):
        fim = time.time() + 30
        while time.time() < fim:
            ok = self.driver.execute_script(
                "var ed = window.tinymce && tinymce.get(arguments[0]);"
                "if(!ed){return false;} ed.setContent(arguments[1]); ed.save(); return true;",
                id_area, html,
            )
            if ok:
                return
            time.sleep(0.5)
        raise NotFoundExceptionDW("Editor de texto do GLPI não carregou.")

    def anexar_arquivos(self, anexos: list):
        entrada = self.wait_until_exists(self.SEL_ANEXO)
        for caminho in anexos:
            entrada.send_keys(os.path.abspath(caminho))
            logging.info(f"ANEXO ENVIADO: {os.path.basename(caminho)}")
        fim = time.time() + 180
        while time.time() < fim:
            enviados = self.driver.find_elements(*self.SEL_ANEXOS_ENVIADOS)
            if len(enviados) >= len(anexos):
                return
            time.sleep(1)
        raise TimeoutException("Os anexos não terminaram de subir.")

    def retentar(self, etapa: str, acao):
        for tentativa in range(1, self.tentativas + 1):
            try:
                logging.info(f"{etapa} (TENTATIVA {tentativa}/{self.tentativas})")
                return acao()
            except Exception as ex:
                self.salvar_print(etapa)
                logging.warning(f"{etapa} FALHOU: {str(ex).splitlines()[0] if str(ex) else type(ex).__name__}")
                if tentativa == self.tentativas:
                    raise
                if any(e in str(ex).lower() for e in ERROS_SESSAO):
                    self.reiniciar_chrome()
                time.sleep(min(3 * tentativa, 15))

    def existe(self, seletor) -> bool:
        try:
            return len(self.driver.find_elements(*seletor)) > 0
        except WebDriverException:
            return False

    def salvar_print(self, etapa: str):
        try:
            os.makedirs(self.pasta_prints, exist_ok=True)
            nome = f"{datetime.now():%Y%m%d_%H%M%S}_{re.sub(r'[^A-Za-z0-9]+', '_', etapa)}.png"
            self.driver.save_screenshot(os.path.join(self.pasta_prints, nome))
            logging.info(f"PRINT SALVO: log/prints/{nome}")
        except Exception:
            pass

    @staticmethod
    def avisar(mensagem: str):
        """Aviso do Windows que não trava o robô."""
        threading.Thread(
            target=lambda: ctypes.windll.user32.MessageBoxW(0, mensagem, "GLPI - Abertura de chamado", 0x40 | 0x40000),
            daemon=True,
        ).start()
