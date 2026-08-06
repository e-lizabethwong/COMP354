class PromptTemplateRegistry:
    def __init__(self, event_name: str = "Hack Canada") -> None:
        self.event_name = event_name

    def get_discovery_prompt(self, event_name: str | None = None) -> str:
        name = event_name or self.event_name
        return f"""Extract potential hackathon sponsors from the provided web content.

Focus on companies that are realistically likely to sponsor {name} (student hackathon).

Look for:
- Past hackathon or MLH sponsors
- Companies hiring interns/new grads in Canada (Toronto, Waterloo, Vancouver, Montreal)
- Developer tools with APIs/SDKs students could use in 48 hours
- Companies with Canadian offices or campus recruiting

For each company return name, website URL, and why they might sponsor.
Skip duplicates, generic placeholders, and companies with no clear sponsorship angle."""

    def get_scoring_prompt(self, event_name: str | None = None) -> str:
        name = event_name or self.event_name
        return f"""Score this company's likelihood to sponsor {name}.

Score each category 0-10:
- talent_acquisition: hiring interns/new grads, campus recruiting
- developer_ecosystem: APIs, SDKs, dev tools usable in a hackathon
- community_sponsorship: event sponsorship, student community visibility
- outreach_accessibility: realistic to contact (DevRel, campus recruiter, not just generic form)
- sponsorship_capacity: size sweet spot (seed to Series C often best; tiny startups and mega-caps score lower unless strong evidence)
- strategic_alignment: fit with {name}'s student university audience

Also provide:
- overall_score: weighted judgment, not just average of fame
- motivations: list from ["hiring_talent", "developer_adoption", "brand_community"]
- company_size: one of "too_small", "sweet_spot", "too_big", "unknown"
- explanation: 2-4 sentences citing evidence

Famous companies without hackathon sponsorship history should NOT get high scores automatically."""

    def get_research_prompt(self, event_name: str | None = None) -> str:
        name = event_name or self.event_name
        return f"""Create a detailed sponsor research report for {name} outreach.

Answer:
1. What does the company do?
2. Products/services offered
3. Recent developer products, APIs, SDKs, or AI tools launched
4. Past hackathon, MLH, student, or university sponsorship evidence
5. Do they hire interns or new grads?
6. Do they hire in Canada?
7. Waterloo alumni or university connections?
8. DevRel, community, campus recruiting, or partnerships staff?
9. Who should {name} contact (role/title)?
10. Best outreach angle (specific, not generic)
11. Suggested sponsor tier: title, gold, silver, bronze, or in_kind

Be specific and cite what you can infer from the evidence. Flag uncertainty honestly."""

    def get_contact_identification_prompt(self, event_name: str | None = None) -> str:
        name = event_name or self.event_name
        return f"""Identify the best person at this company for {name} sponsorship outreach.

Prioritize roles:
- Developer Advocate / DevRel
- Community Manager
- Developer Marketing
- Campus / University / Early Talent Recruiter
- Partnerships Manager
- Founder/CEO (only for smaller companies)

Return the top 1-3 contacts with full_name, title, role_category, relevance_score (0-10), and selection_rationale.

role_category must be one of:
devrel, dev_advocate, community_manager, dev_marketing, campus_recruiter,
university_recruiter, partnerships, founder_ceo, other"""

    def get_contact_enrichment_prompt(self) -> str:
        return """From the public web snippets provided, find contact methods for the target person or role.

ONLY use publicly visible information from the snippets. Do NOT invent emails.
Do NOT assume access to LinkedIn scraping, Apollo, Hunter, or paid databases.

Return contact methods with:
- type: email, linkedin, x_twitter, github, personal_website, team_page, blog_author, conference_speaker, community_page
- value: the URL or email
- source_url: where it was found
- confidence: 0.0-1.0

Prefer role-specific contacts over generic info@ addresses when evidence supports it."""

