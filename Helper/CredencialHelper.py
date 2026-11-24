"""Guarda o e-mail e a senha da Microsoft e o token do Azure DevOps no Gerenciador de Credenciais do Windows (criptografado por usuário)."""
import keyring
from keyring.errors import PasswordDeleteError

SERVICO = "DWRPA.GLPI.AberturaChamado"
CHAVE_EMAIL = "__email__"
CHAVE_TOKEN_AZURE = "__token_azure__"


def obter():
    """Retorna (email, senha) salvos ou (None, None)."""
    email = keyring.get_password(SERVICO, CHAVE_EMAIL)
    if not email:
        return None, None
    return email, keyring.get_password(SERVICO, email)


def salvar(email: str, senha: str):
    keyring.set_password(SERVICO, CHAVE_EMAIL, email)
    keyring.set_password(SERVICO, email, senha)


def apagar():
    email = keyring.get_password(SERVICO, CHAVE_EMAIL)
    for chave in filter(None, [email, CHAVE_EMAIL]):
        try:
            keyring.delete_password(SERVICO, chave)
        except PasswordDeleteError:
            pass


def obter_token_azure():
    """Token (PAT) do Azure DevOps salvo neste computador, ou None."""
    return keyring.get_password(SERVICO, CHAVE_TOKEN_AZURE) or None


def salvar_token_azure(token: str):
    keyring.set_password(SERVICO, CHAVE_TOKEN_AZURE, token)


def apagar_token_azure():
    try:
        keyring.delete_password(SERVICO, CHAVE_TOKEN_AZURE)
    except PasswordDeleteError:
        pass
