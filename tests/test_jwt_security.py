"""Security regression tests for app.utils.auth's JWT handling.

Context (B1 dependency audit): python-jose 3.5.0 is the latest available
version and still has an incompletely-fixed algorithm-confusion issue
(CVE-2024-33663's original fix in 3.4.0 can be bypassed with a
DER-encoded key - documented independently, not yet a formal
CVE/GHSA entry as of this audit). ecdsa 0.19.2 (a transitive dependency
of python-jose[cryptography]) has an open, upstream-declined Minerva
timing-attack advisory (PYSEC-2026-1325 / CVE-2024-23342) affecting
ECDSA signing/key generation (not verification), with no planned fix.

Neither is exploitable in this application:
- OpsMind only ever uses HS256 with a single symmetric secret
  (settings.JWT_SECRET_KEY) - there is no RSA/EC keypair anywhere in the
  codebase for an attacker to exploit via algorithm confusion, and no
  ECDSA signing/key-generation operation is ever performed (ecdsa is
  pulled in transitively but its vulnerable code path is never called).
- jwt.decode() is called with an explicit algorithms=[settings.JWT_ALGORITHM]
  allowlist (a single value), so a token whose header claims a different
  algorithm is rejected outright by python-jose's own allowlist check,
  independent of the DER-key bypass.

These tests exercise that actual protective behavior directly, so a
regression here (e.g. someone loosening the algorithms allowlist, or
introducing an asymmetric key) is caught immediately rather than relying
on the reasoning above staying true by inspection alone.

Run with: pytest tests/test_jwt_security.py -v
"""

import base64
import json
from datetime import timedelta

from jose import jwt

from app.core.config import settings
from app.utils.auth import create_access_token, verify_token


def test_valid_token_round_trips():
    token = create_access_token(thread_id="thread-123")
    assert verify_token(token.access_token) == "thread-123"


def test_token_signed_with_a_different_secret_is_rejected():
    """A token an attacker forged with a guessed/different secret must not verify.

    verify_token() catches JWTError internally and returns None rather
    than raising (see app/utils/auth.py) - that's its real, intentional
    contract, so these tests assert on the return value, not an
    exception.
    """
    forged = jwt.encode({"sub": "attacker"}, "not-the-real-secret", algorithm=settings.JWT_ALGORITHM)
    assert verify_token(forged) is None


def test_token_with_a_different_algorithm_is_rejected():
    """Regression guard for the B1 audit finding: even if python-jose's key
    validation had a gap, the algorithms=[settings.JWT_ALGORITHM] allowlist
    on decode must reject any token that doesn't declare exactly the
    configured algorithm - this is the actual mechanism that makes the
    python-jose algorithm-confusion issue (CVE-2024-33663, incompletely
    fixed as of 3.5.0) unreachable here. Uses a different HMAC algorithm
    (HS512) rather than switching to an asymmetric one, since this app
    has no RSA/EC key material to sign with in the first place - the
    absence of such key material is itself part of why the attack has no
    foothold here."""
    assert settings.JWT_ALGORITHM == "HS256", "test assumes the default configured algorithm"
    token = jwt.encode({"sub": "thread-123"}, settings.JWT_SECRET_KEY, algorithm="HS512")
    assert verify_token(token) is None


def test_none_algorithm_token_is_rejected():
    """The classic "alg: none" unsigned-token attack must also be rejected.

    Built by hand rather than via jwt.encode(): python-jose's own encoder
    refuses to construct a "none"-algorithm token at all (JWSError:
    Algorithm none not supported), which is itself a partial mitigation -
    but an attacker crafting a malicious token by hand isn't bound by
    that, so the *verification* side needs its own guard, which is what
    this test actually exercises. Uses a dummy (non-empty) third segment
    so the token passes verify_token's earlier 3-segment format check and
    reaches the actual algorithm allowlist in jwt.decode() - an empty
    signature segment would be rejected by that earlier, separate format
    check instead, which isn't the mechanism this test is targeting.
    """

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({"sub": "attacker"}).encode())
    unsigned_token = f"{header}.{payload}.x"

    assert verify_token(unsigned_token) is None


def test_expired_token_is_rejected():
    token = create_access_token(thread_id="thread-123", expires_delta=timedelta(seconds=-1))
    assert verify_token(token.access_token) is None
