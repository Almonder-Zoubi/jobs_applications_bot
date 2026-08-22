from __future__ import annotations

from textwrap import dedent

from job_bot.models import CandidateProfile, JobPosting, MatchResult


def generate_motivation_letter(
    profile: CandidateProfile, job: JobPosting, match: MatchResult
) -> str:
    top_background = profile.background[:3]
    matched = ", ".join(match.matched_terms[:6]) or "the role requirements"
    background_lines = "\n".join(f"- {item}" for item in top_background)

    return dedent(
        f"""
        Dear {job.company} hiring team,

        I am excited to apply for the {job.title} role. Your opening stands out because it is closely aligned with my background in {matched}, and I would welcome the chance to contribute practical, reliable engineering work to your team.

        My relevant background includes:
        {background_lines}

        I am especially interested in this position because the role description points to work where I can combine technical execution with clear ownership. I bring hands-on experience, a careful approach to requirements, and the habit of turning business needs into maintainable systems.

        Based on the job requirements, I believe I can contribute quickly while continuing to grow with the team. My current work authorization status is: {profile.work_authorization}. My salary expectation is: {profile.salary_expectation}.

        Thank you for considering my application. I would be happy to discuss how my experience fits the needs of this role.

        Sincerely,
        {profile.name}
        {profile.email}
        {profile.phone}
        """
    ).strip()

