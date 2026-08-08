"""Testes das partes de lógica pura do worker de importação por e-mail
(Módulo 18) — extração de token e de anexos. Nenhum teste conecta em
IMAP/Postgres real; mensagens sintéticas via email.message.EmailMessage."""

from email.message import EmailMessage

from sifp.api.shared import MAX_UPLOAD_SIZE_BYTES
from sifp.workers.email_import_worker import _extract_attachments, _extract_sender, _extract_token


def _build_message(headers: dict, attachments: list[tuple[str, bytes]] | None = None) -> EmailMessage:
    msg = EmailMessage()
    for key, value in headers.items():
        msg[key] = value
    msg.set_content("Segue o extrato em anexo.")
    for filename, content in attachments or []:
        msg.add_attachment(content, maintype="application", subtype="octet-stream", filename=filename)
    return msg


def test_extract_token_from_delivered_to():
    msg = _build_message({"Delivered-To": "extratos.sifra+arthur123@gmail.com", "To": "extratos.sifra@gmail.com"})
    assert _extract_token(msg) == ("arthur123", True)


def test_extract_token_prefers_delivered_to_over_to():
    msg = _build_message({
        "Delivered-To": "extratos.sifra+certo@gmail.com",
        "To": "extratos.sifra+errado@gmail.com",
    })
    assert _extract_token(msg) == ("certo", True)


def test_extract_token_falls_back_to_to_header():
    """Fallback pro To/Cc continua existindo (cobre o encaminhamento
    manual, onde o próprio usuário digita o endereço), mas o token vem
    marcado como não-confiável -- ver uso em run() pra não deixar isso
    registrar o primeiro remetente confiável de um alias novo."""
    msg = _build_message({"To": "extratos.sifra+viaencaminhamento@gmail.com"})
    assert _extract_token(msg) == ("viaencaminhamento", False)


def test_extract_token_none_when_no_plus_address():
    msg = _build_message({"To": "extratos.sifra@gmail.com"})
    assert _extract_token(msg) == (None, False)


def test_extract_token_x_original_to_e_confiavel():
    msg = _build_message({"X-Original-To": "extratos.sifra+abc@gmail.com"})
    assert _extract_token(msg) == ("abc", True)


def test_extract_token_cc_nao_e_confiavel():
    msg = _build_message({"Cc": "extratos.sifra+abc@gmail.com"})
    assert _extract_token(msg) == ("abc", False)


def test_extract_attachments_finds_named_parts():
    msg = _build_message(
        {"To": "x+y@gmail.com"},
        attachments=[("extrato.xlsx", b"conteudo-fake-xlsx"), ("posicao.pdf", b"conteudo-fake-pdf")],
    )
    attachments = _extract_attachments(msg)
    names = {name for name, _ in attachments}
    assert names == {"extrato.xlsx", "posicao.pdf"}


def test_extract_attachments_empty_when_no_attachment():
    msg = _build_message({"To": "x+y@gmail.com"})
    assert _extract_attachments(msg) == []


def test_extract_attachments_ignora_anexo_acima_do_limite():
    """Achado real de auditoria: nenhum limite de tamanho de anexo --
    um anexo gigante era decodificado inteiro pra memória antes de
    qualquer validação, mesmo risco já corrigido pro upload manual."""
    pequeno = b"conteudo pequeno"
    grande = b"x" * (MAX_UPLOAD_SIZE_BYTES + 1)
    msg = _build_message(
        {"To": "x+y@gmail.com"},
        attachments=[("extrato.xlsx", pequeno), ("gigante.xlsx", grande)],
    )
    attachments = _extract_attachments(msg)
    names = {name for name, _ in attachments}
    assert names == {"extrato.xlsx"}


def test_extract_sender_plain_address():
    msg = _build_message({"From": "danilo@gmail.com", "To": "x+y@gmail.com"})
    assert _extract_sender(msg) == "danilo@gmail.com"


def test_extract_sender_strips_display_name():
    msg = _build_message({"From": "Danilo Caldin <Danilo@Gmail.com>", "To": "x+y@gmail.com"})
    assert _extract_sender(msg) == "danilo@gmail.com"


def test_extract_sender_empty_when_no_from_header():
    msg = _build_message({"To": "x+y@gmail.com"})
    assert _extract_sender(msg) == ""


def test_run_isola_erro_por_mensagem_e_continua_o_lote(monkeypatch):
    """Achado real de auditoria (3ª varredura): antes só a importação em
    si (_import_for_user) tinha try/except -- um erro em qualquer passo
    anterior do processamento de UMA mensagem (extrair token, consultar
    remetente confiável etc.) propagava pra fora do loop e travava as
    mensagens RESTANTES de TODOS os usuários naquela execução (é uma
    caixa compartilhada, roteada só por token). run() agora isola o erro
    por mensagem e continua o lote."""
    import sifp.workers.email_import_worker as worker

    monkeypatch.setattr(worker, "DATABASE_URL", "postgres://fake")
    monkeypatch.setenv("IMAP_USER", "fake@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "fake-password")

    processadas = []

    def fake_process_message(imap, lookup_conn, msg_id):
        processadas.append(msg_id)
        if msg_id == b"1":
            raise RuntimeError("erro simulado processando a mensagem 1")

    monkeypatch.setattr(worker, "_process_message", fake_process_message)

    class FakeConn:
        def __init__(self):
            self.rollback_chamado = False

        def rollback(self):
            self.rollback_chamado = True

        def close(self):
            pass

    fake_conn = FakeConn()
    monkeypatch.setattr(worker.psycopg, "connect", lambda url: fake_conn)

    class FakeImap:
        def login(self, user, password):
            pass

        def select(self, mailbox):
            pass

        def search(self, charset, criteria):
            return "OK", [b"1 2"]

        def logout(self):
            pass

    monkeypatch.setattr(worker.imaplib, "IMAP4_SSL", lambda host, port: FakeImap())

    worker.run()

    # As DUAS mensagens foram processadas (a 2 não foi travada pelo erro na 1).
    assert processadas == [b"1", b"2"]
    # A conexão compartilhada foi limpa após o erro, senão a mensagem 2
    # herdaria uma transação abortada do Postgres.
    assert fake_conn.rollback_chamado is True
