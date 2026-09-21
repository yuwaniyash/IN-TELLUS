"""
Endpoints for a company to register its own sites and map utility account
numbers to those sites. This is what resolve_site() (in pipeline.py) reads
from — without these endpoints, the only way to populate accounts/sites
was raw SQL, which doesn't scale past one developer manually seeding data.

Both endpoints are scoped by company_id from the JWT (via
get_current_company_id), never from the request body — a client can only
ever create sites/accounts under their own company, matching the same
isolation principle used everywhere else (resolve_site, raw_files, etc.).
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from Security_Layer.auth import get_current_company_id, require_admin
from Security_Layer.file_intake import get_connection

router = APIRouter(tags=["sites & accounts"])


# =======================================================
# Sites
# =======================================================

class CreateSiteRequest(BaseModel):
    site_name: str
    address: str | None = None


class SiteResponse(BaseModel):
    site_id: int
    site_name: str
    address: str | None = None


@router.post("/sites", response_model=SiteResponse)
def create_site(
    payload: CreateSiteRequest,
    current_user: dict = Depends(require_admin),
):
    """Creates a new site (e.g. 'Colombo South') under the caller's company.
    Only admins can do this — sites are structural, not something every
    member should be able to add casually."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO sites (company_id, site_name, address)
               VALUES (%s, %s, %s) RETURNING site_id, site_name, address;""",
            (current_user["company_id"], payload.site_name, payload.address)
        )
        row = cur.fetchone()
        conn.commit()
        return SiteResponse(site_id=row[0], site_name=row[1], address=row[2])
    except Exception as e:
        conn.rollback()
        # UNIQUE (company_id, site_name) violation -> friendly error instead
        # of a raw Postgres traceback leaking to the client.
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail=f"A site named '{payload.site_name}' already exists for your company."
            )
        raise HTTPException(status_code=500, detail="Failed to create site")
    finally:
        cur.close()
        conn.close()


@router.get("/sites", response_model=list[SiteResponse])
def list_sites(company_id: int = Depends(get_current_company_id)):
    """Lists all sites for the caller's company — any logged-in member can
    view this (needed to know what site_id to reference when creating an
    account mapping), only creation is admin-only."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT site_id, site_name, address FROM sites WHERE company_id = %s ORDER BY site_name;",
            (company_id,)
        )
        rows = cur.fetchall()
        return [SiteResponse(site_id=r[0], site_name=r[1], address=r[2]) for r in rows]
    finally:
        cur.close()
        conn.close()


# =======================================================
# Accounts (utility account number -> site mapping)
# =======================================================

class CreateAccountRequest(BaseModel):
    account_number: str
    site_id: int
    resource_type: str | None = None  # "electricity" / "water" / "fuel"


class AccountResponse(BaseModel):
    account_id: int
    account_number: str
    site_id: int
    resource_type: str | None = None


@router.post("/accounts", response_model=AccountResponse)
def create_account(
    payload: CreateAccountRequest,
    current_user: dict = Depends(require_admin),
):
    """Maps a utility account number (the number printed on a bill) to one
    of the caller's company's sites. This is what makes resolve_site()
    return a real site instead of 'no site mapping' on future uploads."""
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Confirm the referenced site actually belongs to this company —
        # without this check, a request could reference another company's
        # site_id (an integer is easy to guess/increment) and silently
        # create a cross-tenant link.
        cur.execute(
            "SELECT 1 FROM sites WHERE site_id = %s AND company_id = %s;",
            (payload.site_id, current_user["company_id"])
        )
        if not cur.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"Site {payload.site_id} not found for your company."
            )

        cur.execute(
            """INSERT INTO accounts (company_id, site_id, account_number, resource_type)
               VALUES (%s, %s, %s, %s)
               RETURNING account_id, account_number, site_id, resource_type;""",
            (current_user["company_id"], payload.site_id, payload.account_number, payload.resource_type)
        )
        row = cur.fetchone()
        conn.commit()
        return AccountResponse(account_id=row[0], account_number=row[1], site_id=row[2], resource_type=row[3])
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail=f"Account '{payload.account_number}' is already mapped for your company."
            )
        raise HTTPException(status_code=500, detail="Failed to create account mapping")
    finally:
        cur.close()
        conn.close()


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(company_id: int = Depends(get_current_company_id)):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT account_id, account_number, site_id, resource_type FROM accounts WHERE company_id = %s;",
            (company_id,)
        )
        rows = cur.fetchall()
        return [AccountResponse(account_id=r[0], account_number=r[1], site_id=r[2], resource_type=r[3]) for r in rows]
    finally:
        cur.close()
        conn.close()