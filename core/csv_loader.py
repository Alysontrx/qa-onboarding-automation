"""Módulo de leitura, validação e higienização de dados de teste via CSV.

Garante validação rigorosa dos campos obrigatórios, detecção de registros
incompletos ou duplicados e proteção estrita contra vazamento de senhas em logs.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_FIELDS = {"profile_id", "email", "password", "name"}


@dataclass
class UserData:
    """Representação de um usuário de teste extraído do CSV."""

    profile_id: str
    email: str
    password: str
    name: str
    row_number: int = 0

    @property
    def masked_password(self) -> str:
        """Retorna a senha mascarada para exibição segura."""
        return "********"

    @property
    def masked_email(self) -> str:
        """Retorna o e-mail parcialmente mascarado se necessário."""
        parts = self.email.split("@")
        if len(parts) == 2 and len(parts[0]) > 2:
            return f"{parts[0][:2]}***@{parts[1]}"
        return self.email

    def __repr__(self) -> str:
        """Representação segura que nunca expõe a senha em texto claro."""
        return (
            f"UserData(profile_id='{self.profile_id}', "
            f"email='{self.email}', name='{self.name}', password='***')"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass
class CSVValidationError:
    """Registro de erro encontrado durante o processamento do CSV."""

    row_number: int
    field: str
    message: str

    def __str__(self) -> str:
        return f"Linha {self.row_number}: campo '{self.field}' inválido - {self.message}"


@dataclass
class CSVLoadResult:
    """Resultado do carregamento e validação do CSV."""

    valid_records: List[UserData]
    errors: List[CSVValidationError]
    total_rows_read: int

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def valid_count(self) -> int:
        return len(self.valid_records)


def load_users_from_csv(file_path: Path | str) -> CSVLoadResult:
    """Carrega e valida usuários a partir de um arquivo CSV.

    Args:
        file_path: Caminho do arquivo CSV.

    Returns:
        CSVLoadResult contendo registros válidos e lista de erros encontrados.

    Raises:
        FileNotFoundError: Caso o arquivo não exista.
        ValueError: Caso os cabeçalhos obrigatórios estejam ausentes.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo CSV não encontrado no caminho: {path}")

    valid_records: List[UserData] = []
    errors: List[CSVValidationError] = []

    seen_profile_ids: Set[str] = set()
    seen_emails: Set[str] = set()
    row_count = 0

    with path.open(mode="r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        if not reader.fieldnames:
            raise ValueError(f"O arquivo CSV '{path}' está vazio ou sem cabeçalhos.")

        normalized_headers = {h.strip() for h in reader.fieldnames if h}
        missing_headers = REQUIRED_FIELDS - normalized_headers
        if missing_headers:
            raise ValueError(
                f"Cabeçalhos obrigatórios ausentes no CSV: {', '.join(sorted(missing_headers))}. "
                f"Esperado conter: {', '.join(sorted(REQUIRED_FIELDS))}"
            )

        for row_index, raw_row in enumerate(reader, start=2):  # Inicia em 2 por causa do header
            row_count += 1
            # Normalizar chaves e valores
            row = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items() if k}

            profile_id = row.get("profile_id", "")
            email = row.get("email", "")
            password = row.get("password", "")
            name = row.get("name", "")

            row_has_error = False

            # Validação de campos obrigatórios não vazios
            for field_name, value in [
                ("profile_id", profile_id),
                ("email", email),
                ("password", password),
                ("name", name),
            ]:
                if not value:
                    errors.append(
                        CSVValidationError(
                            row_number=row_index,
                            field=field_name,
                            message="Campo obrigatório está vazio.",
                        )
                    )
                    row_has_error = True

            # Se campos básicos faltam, não faz sentido validar formato ou duplicidade
            if row_has_error:
                continue

            # Validação de formato de e-mail
            if not EMAIL_REGEX.match(email):
                errors.append(
                    CSVValidationError(
                        row_number=row_index,
                        field="email",
                        message=f"Formato de e-mail inválido: '{email}'.",
                    )
                )
                row_has_error = True

            # Validação de duplicidades
            if profile_id in seen_profile_ids:
                errors.append(
                    CSVValidationError(
                        row_number=row_index,
                        field="profile_id",
                        message=f"ID de perfil duplicado no lote: '{profile_id}'.",
                    )
                )
                row_has_error = True

            if email.lower() in seen_emails:
                errors.append(
                    CSVValidationError(
                        row_number=row_index,
                        field="email",
                        message=f"E-mail duplicado no lote: '{email}'.",
                    )
                )
                row_has_error = True

            if not row_has_error:
                seen_profile_ids.add(profile_id)
                seen_emails.add(email.lower())
                valid_records.append(
                    UserData(
                        profile_id=profile_id,
                        email=email,
                        password=password,
                        name=name,
                        row_number=row_index,
                    )
                )

    return CSVLoadResult(
        valid_records=valid_records,
        errors=errors,
        total_rows_read=row_count,
    )

