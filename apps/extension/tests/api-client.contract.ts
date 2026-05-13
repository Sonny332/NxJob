import {
  createApplication,
  createOutcome,
  listSuccessReferences,
  type ApplicationMethod,
  type OutcomeType
} from "../src/lib/api-client";

async function assertTrackingApiClientContract() {
  const method: ApplicationMethod = "manual";
  const outcomeType: OutcomeType = "positive_reply";

  const application = await createApplication({
    jobLeadId: "job_123",
    resumeVersionId: "resume_123",
    applicationUrl: "https://example.com/jobs/123",
    applicationMethod: method,
    submittedByUser: true
  });

  await createOutcome({
    applicationId: application.application.id,
    jobLeadId: application.application.job_lead_id,
    outcomeType,
    evidenceUrl: application.application.application_url
  });

  const references = await listSuccessReferences({ limit: 10 });
  references.success_references.forEach((reference) => {
    reference.effective_bullets.forEach((bullet) => bullet.toUpperCase());
  });
}

void assertTrackingApiClientContract;
