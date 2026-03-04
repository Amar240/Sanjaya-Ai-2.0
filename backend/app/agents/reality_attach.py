from __future__ import annotations

from ..data_loader import CatalogStore
from ..schemas.plan import PlanError, PlanResponse
from ..schemas.reality import RoleRealityUSA


def attach_role_reality(
    plan: PlanResponse,
    store: CatalogStore,
) -> tuple[RoleRealityUSA | None, list[PlanError]]:
    reality = next(
        (item for item in store.role_reality_usa if item.role_id == plan.selected_role_id),
        None,
    )
    if reality is not None:
        return reality, []
    warning = PlanError(
        code="ROLE_REALITY_MISSING",
        message=(
            f"No USA role reality entry found for selected role '{plan.selected_role_id}'."
        ),
        details={"severity": "warning", "role_id": plan.selected_role_id},
    )
    return None, [warning]
