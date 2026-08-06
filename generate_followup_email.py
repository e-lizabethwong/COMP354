"""
Follow-up email generator
"""

from __future__ import annotations

from sponsor_pipeline.config import Settings

# Load sender and event details from .env via Settings
_settings = Settings.from_env(require_llm=False)

YOUR_NAME = _settings.sender_name
YOUR_TITLE = _settings.sender_title
EVENT_NAME = _settings.event_name

# No subject cause follow-up emails are replies to original outreach emails
email_body = """
Hi {recipient_name},

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


def generate_email(company_name, recipient_name):
    if not recipient_name.strip():
        recipient_name = (
            company_name  # Default to company name if no recipient name is provided
        )

    body = email_body.format(
        recipient_name=recipient_name,
        company_name=company_name,
        your_name=YOUR_NAME,
        your_title=YOUR_TITLE,
        event_name=EVENT_NAME,
    )

    return body


# Input prompts
def main():
    try:
        while True:
            while True:
                company_name = input("Enter the company name: ").strip()
                if company_name:
                    break
                else:
                    print(
                        "Company name cannot be blank. Please enter a valid company name."
                    )

            recipient_name = input(
                "Enter the recipient's name (leave blank to use company name): "
            ).strip()

            email = generate_email(company_name, recipient_name)
            print("\n" + "=" * 80)
            print(email)
            print("=" * 80 + "\n")

            user_input = input("Press enter to generate another follow-up email (type 'exit' or 'e' to stop): ")
            if user_input == "exit" or user_input == "e":
                break
    except KeyboardInterrupt:
        print("\nExited program.")


if __name__ == "__main__":
    raise SystemExit(main())