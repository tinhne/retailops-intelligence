"""Customer onboarding (provisioning): organization, store, settings and owner."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleViolationError, ConflictError
from app.domains.audit.models import AuditLog
from app.domains.identity.models import Membership, Organization, Store, StoreSettings
from app.domains.identity.permissions import Role
from app.domains.identity.provisioning import ProvisionRequest, provision, slugify
from app.provision import main
from tests.factories import login

pytestmark = pytest.mark.integration


def _request(**overrides: object) -> ProvisionRequest:
    values: dict[str, object] = {
        "organization_name": "Lotus Home Co.",
        "store_name": "Lotus Home Online",
        "currency": "VND",
        "timezone": "Asia/Ho_Chi_Minh",
        "owner_email": "Owner@LotusHome.vn",
        "owner_name": "Nguyen Van An",
    }
    values.update(overrides)
    return ProvisionRequest(**values)  # type: ignore[arg-type]


def test_provision_creates_a_real_tenant_whose_owner_can_sign_in(
    db: Session, client: TestClient
) -> None:
    result = provision(db, _request(exposure_cap=Decimal("100000000")))

    org = db.get(Organization, result.organization_id)
    store = db.get(Store, result.store_id)
    settings = db.get(StoreSettings, result.store_id)
    assert org is not None
    assert org.slug == "lotus-home-co"
    assert org.is_demo is False
    assert store is not None
    assert (store.currency, store.timezone, store.code) == ("VND", "Asia/Ho_Chi_Minh", "LOTUSHOM")
    assert settings is not None
    assert settings.exposure_cap == Decimal("100000000")
    role = db.scalar(select(Membership.role).where(Membership.organization_id == org.id))
    assert role is Role.OWNER
    assert db.scalar(select(AuditLog.action).where(AuditLog.organization_id == org.id)) == (
        "organization.provision"
    )

    login(client, "owner@lotushome.vn", result.temporary_password)
    me = client.get("/api/v1/auth/me").json()
    assert me["memberships"][0]["stores"][0]["id"] == str(store.id)
    assert "users.manage" in me["memberships"][0]["permissions"]


def test_slug_and_email_must_be_unused(db: Session) -> None:
    provision(db, _request())
    with pytest.raises(ConflictError) as slug_taken:
        provision(db, _request(owner_email="other@lotushome.vn"))
    assert slug_taken.value.code == "ORG_SLUG_IN_USE"
    with pytest.raises(ConflictError) as email_taken:
        provision(db, _request(slug="lotus-two"))
    assert email_taken.value.code == "EMAIL_IN_USE"


@pytest.mark.parametrize(
    ("field", "overrides"),
    [
        ("currency", {"currency": "dong"}),
        ("timezone", {"timezone": "Saigon"}),
        ("owner_email", {"owner_email": "not-an-email"}),
        ("slug", {"slug": "Has Spaces"}),
        ("exposure_cap", {"exposure_cap": Decimal("0")}),
    ],
)
def test_invalid_input_is_rejected_without_writing(
    db: Session, field: str, overrides: dict[str, object]
) -> None:
    with pytest.raises(BusinessRuleViolationError) as exc:
        provision(db, _request(**overrides))
    assert exc.value.details == [{"field": field}]
    assert db.scalars(select(Organization)).all() == []


def test_cli_prints_the_temporary_password_once(
    db: Session, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.orm import sessionmaker

    import app.provision as cli

    monkeypatch.setattr(cli, "get_session_factory", lambda: sessionmaker(bind=db.get_bind()))
    code = main(
        [
            "--org-name",
            "Saigon Ceramics",
            "--store-name",
            "Saigon Ceramics Online",
            "--currency",
            "vnd",
            "--timezone",
            "Asia/Ho_Chi_Minh",
            "--owner-email",
            "chu@saigonceramics.vn",
            "--owner-name",
            "Tran Thi Binh",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert out.count("temporary password (shown once):") == 1
    assert "chu@saigonceramics.vn" in out
    assert slugify("Saigon Ceramics") == "saigon-ceramics"
