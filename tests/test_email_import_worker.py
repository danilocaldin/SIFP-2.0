"""Testes das partes de lógica pura do worker de importação por e-mail
(Módulo 18) — extração de token e de anexos. Nenhum teste conecta em
IMAP/Postgres real; mensagens sintéticas via email.message.EmailMessage."""

from email.message import EmailMessage

from sifp.workers.email_import_worker import _extract_attachments, _extract_token


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
    assert _extract_token(msg) == "arthur123"


def test_extract_token_prefers_delivered_to_over_to():
    msg = _build_message({
        "Delivered-To": "extratos.sifra+certo@gmail.com",
        "To": "extratos.sifra+errado@gmail.com",
    })
    assert _extract_token(msg) == "certo"


def test_extract_token_falls_back_to_to_header():
    msg = _build_message({"To": "extratos.sifra+viaencaminhamento@gmail.com"})
    assert _extract_token(msg) == "viaencaminhamento"


def test_extract_token_none_when_no_plus_address():
    msg = _build_message({"To": "extratos.sifra@gmail.com"})
    assert _extract_token(msg) is None


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
