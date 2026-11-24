import os
import sys
import json
import logging

PASTA_ROBO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PASTA_ROBO)
sys.path.append(os.path.join(PASTA_ROBO, "..", "DWLAW.PY.Selenium.Common", "DWLAW.PY.Selenium.Common", "DWLAW.PY.Selenium.Common"))

from tkinter import messagebox
from AberturaChamado import AberturaChamado
from Formulario import Formulario, exibir_resultado, pedir_credenciais, pedir_token_azure


def configurar_log():
    pasta_log = os.path.join(PASTA_ROBO, "log")
    os.makedirs(pasta_log, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(pasta_log, "logfile.txt"), mode="a", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main():
    configurar_log()
    with open(os.path.join(PASTA_ROBO, "config.json"), encoding="utf-8") as f:
        config = json.load(f)

    chamado = Formulario().exibir()
    if not chamado:
        logging.info("CANCELADO PELO USUÁRIO")
        return

    logging.info(f"INICIANDO ABERTURA DE CHAMADO: {chamado.titulo}")
    robo = AberturaChamado(config, pedir_credenciais, pedir_token_azure)
    try:
        robo.iniciar_chrome_perfil()
        robo.aguardar_login()
        robo.abrir_chamado(chamado)
        if chamado.simular:
            messagebox.showinfo("Simulação", "Formulário preenchido e NÃO enviado.\nConfira no Chrome e feche quando quiser.")
            return
        logging.info(f"FIM DO PROCESSO: CHAMADO {chamado.numero_chamado}")
        robo.dispose()
        exibir_resultado(chamado)
    except Exception as ex:
        logging.error(f"Erro: {ex}")
        robo.salvar_print("erro")
        try:
            robo.dispose()
        except Exception:
            pass
        messagebox.showerror("Erro na abertura do chamado",
                             f"{ex}\n\nLog em log/logfile.txt e print em log/prints."
                             + (f"\n\nChamado {chamado.numero_chamado} já foi criado." if chamado.numero_chamado else ""))
        os._exit(1)


if __name__ == "__main__":
    main()
    os._exit(0)
