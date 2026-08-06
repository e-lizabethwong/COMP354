from __future__ import annotations

from pathlib import Path
from sponsor_pipeline.config import Settings
from sponsor_pipeline.logger import get_logger
from sponsor_pipeline.models import OutreachProspect
from sponsor_pipeline.persistence.repository import SponsorRepository

logger = get_logger(__name__)

INITIAL_SUBJECT_TEMPLATE = "Sponsorship opportunity for {company_name} with HackConcordia student association annual {event_name} event"

INITIAL_BODY_TEMPLATE = """Hello {recipient_name},

My name is {your_name} and I am reaching out to you at {company_name} as {your_title} of Sponsorship for the HackConcordia student association at Concordia University. 
We are a student group focused on bringing together a community of developers and programmers through experiential learning opportunities. This January, we are hosting 
the next edition of our annual Hackathon event, {event_name}, where over 1000 students from across Canada (and beyond) will compete in teams for 24 hours straight 
to produce innovative and creative projects. We would like to invite {company_name} to be a key sponsor for {event_name}, taking place on {event_date}, 
at {event_venue}{location}.

Either through a booth at our career fair, access to participants' CVs, or even a post-event recruitment email, we believe that this partnership would provide {company_name} 
with the unique opportunity to meet with (and recruit from) over 1000 top-tier engineering and computer science students from Montreal and beyond, 
who will one day be key stakeholders in their fields. As well, sponsoring {event_name} opens up an exceptional avenue to promote your company to a vibrant student community, 
both through our event's branding or by sending company representatives as mentors or judges for our competition.

We would be happy to go over our sponsorship package and answer any questions you might have in a short 30 minute meeting, or by email if you prefer.

Thank you for your time and consideration, I look forward to hearing from you and to potentially working together on our event!

Thank you,

{your_name}
"""

FOLLOWUP_BODY_TEMPLATE = """Hi {recipient_name},

I just wanted to follow up with you to discuss this sponsorship opportunity for {company_name} at our annual hackathon, {event_name}. We would love to have {company_name} 
as a sponsor for the next edition of Canada's second largest hackathon, where we are expecting over 1000 participants from the top universities in Montreal and beyond.

Sponsoring {event_name} would provide {company_name} with significant brand exposure among a diverse group of talented engineering and computer science students 
who will one day (soon!) be key stakeholders in their fields. Partnering with us would also open up an excellent avenue for your company to recruit 
from our pool of highly skilled participants, either through a booth at our career fair, access to participants' CVs, or even a post-event recruitment email.

We offer various sponsorship packages that can be tailored to fit your company's needs, which I would be happy to go over with you in a short 30 minute meeting. 
I look forward to hearing from you soon!

Thanks,

{your_name}
HackConcordia {your_title} of Sponsorship
"""


class OutreachService:
    def __init__(self, settings: Settings, repo: SponsorRepository) -> None:
        self._settings = settings
        self._repo = repo

    def generate_initial_email(
        self,
        company_name: str,
        recipient_name: str | None = None,
        is_local: bool = False,
    ) -> tuple[str, str]:
        recipient = (recipient_name or "").strip() or company_name
        location = "" if is_local else " in Montreal, Quebec"

        subject = INITIAL_SUBJECT_TEMPLATE.format(
            company_name=company_name,
            event_name=self._settings.event_name,
        )
        body = INITIAL_BODY_TEMPLATE.format(
            recipient_name=recipient,
            company_name=company_name,
            your_name=self._settings.sender_name,
            your_title=self._settings.sender_title,
            event_name=self._settings.event_name,
            event_date=self._settings.event_date,
            event_venue=self._settings.event_venue,
            location=location,
        )
        return subject, body

    def generate_followup_email(
        self,
        company_name: str,
        recipient_name: str | None = None,
    ) -> str:
        recipient = (recipient_name or "").strip() or company_name
        return FOLLOWUP_BODY_TEMPLATE.format(
            recipient_name=recipient,
            company_name=company_name,
            your_name=self._settings.sender_name,
            your_title=self._settings.sender_title,
            event_name=self._settings.event_name,
        )

    def generate_prospect_outreach(
        self, prospect: OutreachProspect
    ) -> dict[str, str]:
        company_name = prospect.company.name
        recipient_name = prospect.primary_contact.full_name
        subject, initial_body = self.generate_initial_email(
            company_name=company_name,
            recipient_name=recipient_name,
        )
        followup_body = self.generate_followup_email(
            company_name=company_name,
            recipient_name=recipient_name,
        )
        return {
            "company": company_name,
            "contact": recipient_name,
            "subject": subject,
            "initial_email": initial_body,
            "followup_email": followup_body,
        }

    def generate_all_and_save(self, output_dir: Path) -> int:
        output_dir.mkdir(parents=True, exist_ok=True)
        prospects = self._repo.get_outreach_ready()
        logger.info("Generating outreach emails for %s prospect(s)", len(prospects))
        count = 0
        for prospect in prospects:
            outreach = self.generate_prospect_outreach(prospect)
            slug = prospect.company.name.lower().replace(" ", "_")
            out_file = output_dir / f"{slug}_emails.txt"
            content = (
                f"=== INITIAL OUTREACH ===\n"
                f"Subject: {outreach['subject']}\n\n"
                f"{outreach['initial_email']}\n"
                f"{'=' * 40}\n"
                f"=== FOLLOW-UP OUTREACH ===\n\n"
                f"{outreach['followup_email']}\n"
            )
            out_file.write_text(content, encoding="utf-8")
            count += 1
        logger.info("Saved %s outreach email files to %s", count, output_dir)
        return count
