"""Testes unitários para o carregador e validador de CSV."""

import pytest
from pathlib import Path

from core.csv_loader import UserData, load_users_from_csv


def test_load_valid_csv(tmp_path: Path):
    """Valida o carregamento bem-sucedido de registros válidos."""
    csv_content = (
        "profile_id,email,password,name\n"
        "p001,user1@test.com,Pass123!,User One\n"
        "p002,user2@test.com,Pass456!,User Two\n"
    )
    csv_file = tmp_path / "valid.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = load_users_from_csv(csv_file)
    assert not result.has_errors
    assert result.valid_count == 2
    assert result.total_rows_read == 2

    user1 = result.valid_records[0]
    assert user1.profile_id == "p001"
    assert user1.email == "user1@test.com"
    assert user1.name == "User One"
    assert user1.password == "Pass123!"


def test_password_masking_security():
    """Garante que representações em string nunca exponham a senha em texto claro."""
    user = UserData(
        profile_id="p999",
        email="security@test.com",
        password="SuperSecretPassword!",
        name="Security Auditor",
    )
    repr_str = repr(user)
    str_val = str(user)

    assert "SuperSecretPassword!" not in repr_str
    assert "SuperSecretPassword!" not in str_val
    assert user.masked_password == "********"
    assert "password='***'" in repr_str


def test_missing_required_headers(tmp_path: Path):
    """Verifica se erro é lançado ao omitir cabeçalhos essenciais."""
    csv_content = "profile_id,email,name\np001,user@test.com,User Name\n"
    csv_file = tmp_path / "invalid_headers.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    with pytest.raises(ValueError, match="Cabeçalhos obrigatórios ausentes"):
        load_users_from_csv(csv_file)


def test_invalid_and_empty_rows(tmp_path: Path):
    """Valida a detecção e reporte de linhas com campos faltantes."""
    csv_content = (
        "profile_id,email,password,name\n"
        "p001,,Pass123!,User One\n"  # Email vazio
        ",user2@test.com,Pass456!,User Two\n"  # Profile vazio
        "p003,user3@test.com,,User Three\n"  # Senha vazia
    )
    csv_file = tmp_path / "empty_fields.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = load_users_from_csv(csv_file)
    assert result.has_errors
    assert len(result.errors) == 3
    assert result.valid_count == 0


def test_invalid_email_format(tmp_path: Path):
    """Valida detecção de e-mail com formato inadequado."""
    csv_content = (
        "profile_id,email,password,name\n"
        "p001,email-invalido-sem-arroba,Pass123!,User One\n"
    )
    csv_file = tmp_path / "bad_email.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = load_users_from_csv(csv_file)
    assert result.has_errors
    assert any("Formato de e-mail inválido" in err.message for err in result.errors)


def test_duplicate_records_detection(tmp_path: Path):
    """Garante que perfis ou emails duplicados no mesmo lote sejam barrados."""
    csv_content = (
        "profile_id,email,password,name\n"
        "p001,user1@test.com,Pass123!,User One\n"
        "p001,user2@test.com,Pass123!,User Two\n"  # Profile duplicado
        "p003,user1@test.com,Pass123!,User Three\n"  # Email duplicado
    )
    csv_file = tmp_path / "duplicates.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = load_users_from_csv(csv_file)
    assert result.has_errors
    assert result.valid_count == 1  # Apenas a primeira linha é aceita
    assert any("ID de perfil duplicado" in err.message for err in result.errors)
    assert any("E-mail duplicado" in err.message for err in result.errors)

