"""
Example output endpoints for Masumi agent registration
Shows example responses from the contract analysis service
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/problematic-clauses")
async def example_problematic_clauses():
    """
    Example output when problematic clauses are found in a rental contract.
    This demonstrates the service's ability to identify unfair, illegal, or exploitative clauses.
    """
    return {
        "output": """Problematic Clause 1:
Contract Content: The tenant agrees to pay a non-refundable deposit of 3 months rent, which will be retained by the landlord as a processing fee.

Analysis: This clause violates German BGB §551 which limits deposits to a maximum of 3 months' rent (cold rent + utilities). More critically, BGB §551(3) explicitly requires deposits to be refundable. Non-refundable deposits or "processing fees" disguised as deposits are illegal under German rental law. This clause is exploitative and void, as it attempts to circumvent mandatory tenant protections.

Problematic Clause 2:
Contract Content: The tenant waives all rights to challenge rent increases, including those that may exceed the local rent index (Mietspiegel).

Analysis: This clause violates mandatory tenant protections under BGB §558 and §558a. Tenants have an inalienable right to challenge rent increases that exceed legal limits, including the local rent index (Mietspiegel) and the rent brake (Mietpreisbremse) regulations. Any waiver of these rights is void under BGB §134, as it violates mandatory legal protections. This clause is unfair and potentially illegal.

Problematic Clause 3:
Contract Content: The tenant must obtain written permission from the landlord for any guests staying longer than 2 nights, and may be charged a fee of €50 per night for unauthorized guests.

Analysis: This clause violates BGB §553, which protects tenants' rights to reasonable use of their rental property. While landlords can restrict subletting, they cannot unreasonably restrict guests or charge fees for normal guest visits. The 2-night restriction and fee structure are excessive and violate the tenant's right to normal use of the property. This clause is unfair and potentially void under BGB §307 (unfair contract terms).

Problematic Clause 4:
Contract Content: The tenant agrees to pay all maintenance and repair costs, including structural repairs, regardless of fault or cause.

Analysis: This clause violates BGB §535 and §536, which clearly distinguish between tenant and landlord responsibilities. Landlords are responsible for structural repairs, major maintenance, and defects that existed before or arise during the tenancy. Tenants are only responsible for minor repairs and damages they cause. This clause attempts to shift all maintenance costs to the tenant, which is illegal and void under German rental law."""
    }


@router.get("/multiple-issues")
async def example_multiple_issues():
    """
    Example output showing multiple types of problematic clauses in a single contract.
    Demonstrates comprehensive analysis of various unfair practices.
    """
    return {
        "output": """Problematic Clause 1:
Contract Content: The tenant must pay rent in advance for the entire lease term (24 months) and agrees that no refund will be provided if the tenant terminates early, even for legally permitted reasons.

Analysis: This clause violates multiple BGB provisions. BGB §551 limits deposits to 3 months' rent, and advance rent payments cannot be used to circumvent this limit. Additionally, BGB §573c provides tenants with the right to terminate leases early under certain circumstances (e.g., job relocation, health reasons), and landlords cannot contractually waive these rights. This clause is both exploitative and void under German law.

Problematic Clause 2:
Contract Content: The tenant agrees to accept all future rent increases without objection and waives the right to request rent reduction (Mietminderung) for any defects or maintenance issues.

Analysis: This clause violates fundamental tenant protections. BGB §536 grants tenants the right to reduce rent (Mietminderung) when the property has defects that reduce its value or usability. This right cannot be waived. Additionally, BGB §558 requires rent increases to follow legal procedures and allows tenants to challenge increases. This clause attempts to eliminate core tenant protections and is void under BGB §134.

Problematic Clause 3:
Contract Content: The tenant must provide a security deposit equal to 6 months' rent, which may be increased at the landlord's discretion.

Analysis: This clause violates BGB §551(1), which explicitly limits security deposits to a maximum of 3 months' rent (excluding utilities). The 6-month requirement is illegal. Additionally, the clause allowing discretionary increases violates BGB §551(2), which requires deposits to be fixed at the start of the tenancy. This clause is exploitative and void."""
    }


@router.get("/no-issues")
async def example_no_issues():
    """
    Example output when no problematic clauses are found in a rental contract.
    Shows that the service can confirm when contracts comply with German rental law.
    """
    return {
        "output": "No problematic clauses found in the contract."
    }


@router.get("/exploitative-practices")
async def example_exploitative_practices():
    """
    Example output identifying particularly exploitative or scam-like practices.
    Demonstrates detection of clauses that are clearly designed to exploit tenants.
    """
    return {
        "output": """Problematic Clause 1:
Contract Content: The tenant agrees that the landlord may enter the property at any time without notice for "inspection purposes" and the tenant waives all privacy rights.

Analysis: This clause violates BGB §535(1) and the tenant's fundamental right to undisturbed use of the rental property. BGB §858 protects tenants' possession rights, and landlords can only enter with proper notice (typically 24-48 hours) and for legitimate reasons (repairs, viewings with proper notice). This clause attempts to eliminate all tenant privacy rights and is void under BGB §134 as it violates mandatory legal protections. This is an exploitative practice.

Problematic Clause 2:
Contract Content: The tenant agrees to pay a "finder's fee" of €2,000 to the landlord's agent, separate from the deposit, which is non-refundable and due immediately upon signing.

Analysis: This clause violates BGB §551 and consumer protection laws. The "finder's fee" appears to be an attempt to circumvent deposit limits. Under German law, landlords and agents cannot charge excessive fees to tenants. Such fees are often considered illegal, especially when disguised as separate charges. This practice is exploitative and may violate BGB §307 (unfair contract terms) and consumer protection regulations. The fee structure suggests a scam-like practice designed to extract additional money from tenants.

Problematic Clause 3:
Contract Content: The tenant agrees that all disputes will be resolved through the landlord's chosen arbitration service, and waives the right to use German courts or consumer protection agencies.

Analysis: This clause violates mandatory legal protections. BGB §307 prohibits unfair contract terms that disadvantage consumers. Tenants have the right to access German courts and consumer protection agencies, and this right cannot be waived. Additionally, forcing tenants into a landlord-controlled arbitration process is unfair and void. This clause is exploitative and designed to prevent tenants from seeking legal recourse."""
    }

