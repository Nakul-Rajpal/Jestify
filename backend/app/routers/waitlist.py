"""Router for waitlist signup endpoint."""

import logging

import resend
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.waitlist import WaitlistEntry

router = APIRouter(prefix="/waitlist", tags=["waitlist"])
logger = logging.getLogger(__name__)


class WaitlistSignupRequest(BaseModel):
    email: EmailStr


class WaitlistSignupResponse(BaseModel):
    message: str


@router.post("", response_model=WaitlistSignupResponse, status_code=201)
async def join_waitlist(
    request: WaitlistSignupRequest,
    db: AsyncSession = Depends(get_db),
) -> WaitlistSignupResponse:
    """Accept an email, save it to the waitlist, and send a confirmation email."""
    entry = WaitlistEntry(email=request.email.lower())
    db.add(entry)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This email is already on the waitlist.",
        )

    if settings.RESEND_API_KEY:
        try:
            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send({
                "from": settings.RESEND_FROM_EMAIL,
                "to": request.email,
                "subject": "You're on the Jestify waitlist!",
                "html": _build_confirmation_email(),
            })
        except Exception as exc:
            logger.warning(
                "Failed to send waitlist confirmation email to %s: %s",
                request.email,
                exc,
            )

    return WaitlistSignupResponse(
        message="You're on the waitlist! We'll email you when we launch."
    )


def _build_confirmation_email() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>You're on the Jestify waitlist!</title>
</head>
<body style="margin:0;padding:0;background:#0a0712;font-family:Inter,Arial,sans-serif;color:#f5f1ff;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0712;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0"
          style="background:linear-gradient(155deg,rgba(255,103,214,0.14) 0%,rgba(226,82,255,0.10) 46%,rgba(56,21,96,0.18) 100%);
                 border:1px solid rgba(255,255,255,0.18);border-radius:16px;padding:48px 40px;">
          <tr>
            <td align="center" style="padding-bottom:24px;">
              <h1 style="margin:0;font-size:42px;font-weight:800;letter-spacing:-0.02em;">
                <span style="color:#8b5cf6;">JEST</span><span style="color:#facc15;">IFY</span>
              </h1>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-bottom:20px;">
              <h2 style="margin:0;font-size:22px;font-weight:700;color:#f5f1ff;">
                You're on the waitlist!
              </h2>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-bottom:32px;">
              <p style="margin:0;font-size:16px;line-height:1.6;color:rgba(245,241,255,0.8);">
                Thanks for signing up! We'll notify you as soon as Jestify launches.<br>
                Get ready to learn anything, taught by your favorite characters.
              </p>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-top:24px;border-top:1px solid rgba(255,255,255,0.12);">
              <p style="margin:0;font-size:13px;color:rgba(245,241,255,0.45);">
                &copy; 2025 Jestify &mdash; jestify.org
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
