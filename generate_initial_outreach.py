"""
Initial outreach email generator.
"""

from __future__ import annotations

from sponsor_pipeline.config import Settings

# Load sender and event details from .env via Settings
_settings = Settings.from_env(require_llm=False)

YOUR_NAME = _settings.sender_name
YOUR_TITLE = _settings.sender_title
EVENT_NAME = _settings.event_name
EVENT_DATE = _settings.event_date
EVENT_VENUE = _settings.event_venue

# New email template with a better subject-body separation for the OutreachEmailGenerator integration

email_subject = "Sponsorship opportunity for {company_name} with HackConcordia student association annual {event_name} event"

email_body = """
Hello {recipient_name},

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


def generate_email(company_name, recipient_name, location):
    if not recipient_name.strip():
        recipient_name = (
            company_name  # Default to company name if no recipient name is provided
        )

    subject = email_subject.format(company_name=company_name, event_name=EVENT_NAME)

    body = email_body.format(
        recipient_name=recipient_name,
        company_name=company_name,
        your_name=YOUR_NAME,
        your_title=YOUR_TITLE,
        event_name=EVENT_NAME,
        event_date=EVENT_DATE,
        event_venue=EVENT_VENUE,
        location=location,
    )

    return subject, body


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

            # Ask if the recipient is local; default to Montreal, Quebec if blank
            local_input = (
                input("Is the recipient local? (y for yes, blank for no): ").strip().lower()
            )

            if local_input == "y":
                location = ""
            else:
                location = " in Montreal, Quebec"

            subject, body = generate_email(company_name, recipient_name, location)

            print("\n" + "=" * 80)
            print(f"Subject: {subject}")
            print("-" * 80)
            print(body)
            print("=" * 80 + "\n")

            user_input = input("Press enter to generate another email (type 'exit' or 'e' to stop): ")
            if user_input == "exit" or user_input == "e":
                break
    except KeyboardInterrupt:
        print("\nExited program.")


if __name__ == "__main__":
    raise SystemExit(main())