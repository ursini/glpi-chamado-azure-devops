"""Cria o card (Bug) no board do Azure DevOps pela API, com o token (PAT) do analista.

O token precisa só do escopo Work Items: Read & write.
"""
import json
import time
import base64
import logging
import socket
import http.client
import urllib.error
import urllib.request
from urllib.parse import quote

VERSAO = "api-version=7.0"


def _conectar_ipv4(endereco, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, *args, **kwargs):
    """Abre a conexão só por IPv4: pelo IPv6 o dev.azure.com derruba metade das conexões (WinError 10054)."""
    host, porta = endereco
    erro = None
    for *_, destino in socket.getaddrinfo(host, porta, socket.AF_INET, socket.SOCK_STREAM):
        try:
            return socket.create_connection(destino, timeout, source_address)
        except OSError as ex:
            erro = ex
    raise erro or OSError(f"Sem endereço IPv4 para {host}")


class _HTTPSConnectionIPv4(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = _conectar_ipv4


class _HTTPSHandlerIPv4(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_HTTPSConnectionIPv4, req, context=self._context)


_abridor = urllib.request.build_opener(_HTTPSHandlerIPv4())


class TokenAzureRecusado(Exception):
    pass


class AzureDevOpsHelper:
    def __init__(self, config: dict, token: str):
        self.config = config
        self.base = f"{config.get('url_azure', 'https://dev.azure.com/DWRPA').rstrip('/')}/{quote(config.get('projeto_azure', 'RPA'))}"
        self.auth = "Basic " + base64.b64encode(f":{token}".encode()).decode()

    def _chamar(self, metodo: str, url: str, acao: str, corpo=None, tipo="application/json", tentativas=5):
        """A rede às vezes derruba a conexão com o dev.azure.com no aperto de mão do HTTPS
        (WinError 10054); nesse caso tenta de novo, com uma espera crescente."""
        for tentativa in range(1, tentativas + 1):
            try:
                return self._chamar_uma_vez(metodo, url, acao, corpo, tipo)
            except urllib.error.HTTPError:
                raise
            except (urllib.error.URLError, ConnectionError, TimeoutError) as ex:
                if tentativa == tentativas:
                    raise
                logging.warning(f"AZURE: CONEXÃO FALHOU AO {acao.upper()} (TENTATIVA {tentativa}/{tentativas}): {ex}")
                time.sleep(2 * tentativa)

    def _chamar_uma_vez(self, metodo: str, url: str, acao: str, corpo=None, tipo="application/json"):
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
        req = urllib.request.Request(url, data=dados, method=metodo, headers={"Authorization": self.auth, "Content-Type": tipo})
        try:
            with _abridor.open(req, timeout=60) as resposta:
                texto = resposta.read().decode("utf-8", "ignore")
                # token inválido: o Azure devolve a página de login (HTTP 203, HTML) em vez de 401
                if resposta.status == 203 or "json" not in (resposta.headers.get("Content-Type") or ""):
                    raise TokenAzureRecusado(f"O Azure recusou o token ao {acao}. "
                                             "Confira se ele está certo, não venceu e tem Work Items: Read & write.")
                return json.loads(texto)
        except urllib.error.HTTPError as ex:
            if ex.code in (401, 403):
                raise TokenAzureRecusado(f"O Azure recusou o token ao {acao} (HTTP {ex.code}). "
                                         "Confira se ele não venceu e se tem Work Items: Read & write.")
            detalhe = ex.read().decode("utf-8", "ignore")[:300]
            raise RuntimeError(f"Erro ao {acao} no Azure (HTTP {ex.code}): {detalhe}")

    def sprint_atual(self):
        """Caminho da sprint atual do time (ex.: RPA\\Sprint- 50 - Sprint 13), ou None se não achar."""
        time = quote(self.config.get("time_azure", "RPA Team"))
        dados = self._chamar("GET", f"{self.base}/{time}/_apis/work/teamsettings/iterations?$timeframe=current&{VERSAO}", "buscar a sprint atual")
        valores = dados.get("value") or []
        return valores[0]["path"] if valores else None

    def criar_bug(self, chamado, sprint) -> int:
        """Cria o Bug no padrão do board e devolve o número do card."""
        campos = {
            "System.Title": chamado.titulo_azure,
            "Microsoft.VSTS.TCM.ReproSteps": chamado.repro_steps_azure,
            "System.Tags": self.config.get("tag_card", "CONS"),
            "System.AreaPath": self.config.get("projeto_azure", "RPA"),
            "Microsoft.VSTS.Common.Priority": "2",
            "Microsoft.VSTS.Common.Severity": "3 - Medium",
        }
        if sprint:
            campos["System.IterationPath"] = sprint
        corpo = [{"op": "add", "path": f"/fields/{nome}", "value": valor} for nome, valor in campos.items()]
        dados = self._chamar("POST", f"{self.base}/_apis/wit/workitems/$Bug?{VERSAO}", "criar o card", corpo, "application/json-patch+json")
        return int(dados["id"])
