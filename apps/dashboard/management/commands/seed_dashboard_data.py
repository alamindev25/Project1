from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.dashboard.models import (
    DocumentTemplate,
    DocumentType,
    HelpArticle,
    TemplateCategory,
)


def _field(name, label, field_type, order, required=False, is_required=False, placeholder=None, options=None, **extra):
    has_conditions = bool(extra.get("conditions"))
    is_visible = extra.pop("is_visible", not has_conditions)
    if "required" in extra:
        is_required = extra.pop("required")
    elif required:
        is_required = required

    if field_type == "repeater" and extra.get("min_items"):
        try:
            if int(extra["min_items"]) >= 1:
                is_required = True
        except (ValueError, TypeError):
            pass

    data = {
        "name": name,
        "label": label,
        "type": field_type,
        "is_required": bool(is_required),
        "is_visible": bool(is_visible),
        "order": order,
    }
    if placeholder:
        data["placeholder"] = placeholder
    if options:
        data["options"] = options
    for key, value in extra.items():
        data[key] = value
    return data


SALES_CLIENT_SCHEMAS = {
    "sales proposal": [
        _field("company_name", "Company Name", "text", 1),
        _field("client_name", "Client Name", "text", 2),
        _field("proposal_date", "Proposal Date", "date", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("proposal_summary", "Proposal Summary", "textarea", 5),
        _field("scope_of_work", "Scope of Work", "textarea", 6),
        _field("deliverables", "Deliverables", "textarea", 7),
        _field("timeline", "Timeline", "textarea", 8),
        _field("pricing_details", "Pricing Details", "textarea", 9),
        _field("payment_terms", "Payment Terms", "textarea", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "client onboarding": [
        _field("company_name", "Company Name", "text", 1),
        _field("client_name", "Client Name", "text", 2),
        _field("onboarding_date", "Onboarding Date", "date", 3),
        _field("account_manager", "Account Manager", "text", 4),
        _field("client_contact_information", "Client Contact Information", "textarea", 5),
        _field("service_product_purchased", "Service/Product Purchased", "textarea", 6),
        _field("onboarding_checklist", "Onboarding Checklist", "textarea", 7),
        _field("initial_setup_requirements", "Initial Setup Requirements", "textarea", 8),
        _field("timeline_for_implementation", "Timeline for Implementation", "textarea", 9),
        _field("additional_notes", "Additional Notes", "textarea", 10, required=False),
    ],
    "follow-up email": [
        _field("company_name", "Company Name", "text", 1),
        _field("client_name", "Client Name", "text", 2),
        _field("sender_name", "Sender Name", "text", 3),
        _field("sender_position", "Sender Position", "text", 4, required=False),
        _field("follow_up_date", "Follow-Up Date", "date", 5),
        _field("subject_line", "Subject Line", "text", 6),
        _field("previous_interaction_summary", "Previous Interaction Summary", "textarea", 7),
        _field("follow_up_message", "Follow-Up Message", "textarea", 8),
        _field("call_to_action", "Call to Action", "textarea", 9),
        _field("contact_information", "Contact Information", "textarea", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "service agreement": [
        _field("company_name", "Company Name", "text", 1),
        _field("client_name", "Client Name", "text", 2),
        _field("agreement_date", "Agreement Date", "date", 3),
        _field("service_description", "Service Description", "textarea", 4),
        _field("scope_of_services", "Scope of Services", "textarea", 5),
        _field("term_of_agreement", "Term of Agreement", "textarea", 6),
        _field("payment_terms", "Payment Terms", "textarea", 7),
        _field("responsibilities_of_company", "Responsibilities of Company", "textarea", 8),
        _field("responsibilities_of_client", "Responsibilities of Client", "textarea", 9),
        _field("termination_terms", "Termination Terms", "textarea", 10),
        _field("confidentiality_clause", "Confidentiality Clause", "textarea", 11, required=False),
        _field("additional_terms", "Additional Terms", "textarea", 12, required=False),
    ],
    "quote template": [
        _field("company_name", "Company Name", "text", 1),
        _field("client_name", "Client Name", "text", 2),
        _field("quote_title", "Quote Title", "text", 3),
        _field("quote_date", "Quote Date", "date", 4),
        _field("prepared_by", "Prepared By", "text", 5),
        _field(
            "itemized_services_products",
            "Itemized Services/Products",
            "repeater",
            6,
            children=[
                _field("item_description", "Description", "text", 1),
                _field("item_quantity", "Quantity", "number", 2),
                _field("item_unit_price", "Unit Price", "currency", 3),
                _field("item_total", "Total", "currency", 4),
            ],
            min_items=1,
        ),
        _field("subtotal", "Subtotal", "currency", 7),
        _field("taxes_fees", "Taxes/Fees", "currency", 8, required=False),
        _field("total_amount", "Total Amount", "currency", 9),
        _field("payment_terms", "Payment Terms", "textarea", 10),
        _field("validity_period", "Validity Period", "text", 11),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "meeting summary": [
        _field("company_name", "Company Name", "text", 1),
        _field("client_name", "Client Name", "text", 2),
        _field("meeting_title", "Meeting Title", "text", 3),
        _field("meeting_date", "Meeting Date", "date", 4),
        _field("meeting_time", "Meeting Time", "text", 5, required=False),
        _field("location", "Location", "text", 6, required=False),
        _field("participants", "Participants", "textarea", 7),
        _field("meeting_objective", "Meeting Objective", "textarea", 8),
        _field("discussion_summary", "Discussion Summary", "textarea", 9),
        _field("key_decisions_made", "Key Decisions Made", "textarea", 10),
        _field("action_items", "Action Items", "textarea", 11),
        _field("next_steps", "Next Steps", "textarea", 12, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "crm report": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_title", "Report Title", "text", 2),
        _field("reporting_period", "Reporting Period", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("report_date", "Report Date", "date", 5),
        _field("client_overview", "Client Overview", "textarea", 6),
        _field("sales_activities", "Sales Activities", "textarea", 7),
        _field("pipeline_status", "Pipeline Status", "textarea", 8),
        _field("opportunities", "Opportunities", "textarea", 9, required=False),
        _field("challenges", "Challenges", "textarea", 10, required=False),
        _field("recommendations", "Recommendations", "textarea", 11, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "pitch deck outline": [
        _field("company_name", "Company Name", "text", 1),
        _field("presentation_title", "Presentation Title", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("presentation_date", "Presentation Date", "date", 4),
        _field("target_audience", "Target Audience", "textarea", 5),
        _field("problem_statement", "Problem Statement", "textarea", 6),
        _field("proposed_solution", "Proposed Solution", "textarea", 7),
        _field("value_proposition", "Value Proposition", "textarea", 8),
        _field("market_opportunity", "Market Opportunity", "textarea", 9, required=False),
        _field("business_model", "Business Model", "textarea", 10, required=False),
        _field("competitive_advantage", "Competitive Advantage", "textarea", 11, required=False),
        _field("financial_highlights", "Financial Highlights", "textarea", 12, required=False),
        _field("call_to_action", "Call to Action", "textarea", 13),
        _field("additional_notes", "Additional Notes", "textarea", 14, required=False),
    ],
    "account plan": [
        _field("company_name", "Company Name", "text", 1),
        _field("client_name", "Client Name", "text", 2),
        _field("plan_title", "Plan Title", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("plan_date", "Plan Date", "date", 5),
        _field("account_overview", "Account Overview", "textarea", 6),
        _field("client_objectives", "Client Objectives", "textarea", 7),
        _field("strategic_goals", "Strategic Goals", "textarea", 8),
        _field("key_opportunities", "Key Opportunities", "textarea", 9, required=False),
        _field("risks_challenges", "Risks & Challenges", "textarea", 10, required=False),
        _field("action_steps", "Action Steps", "textarea", 11),
        _field("timeline", "Timeline", "textarea", 12, required=False),
        _field("success_metrics", "Success Metrics", "textarea", 13, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 14, required=False),
    ],
    "action plan": [
        _field("company_name", "Company Name", "text", 1),
        _field("plan_title", "Plan Title", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("plan_date", "Plan Date", "date", 4),
        _field("objective", "Objective", "textarea", 5),
        _field("key_tasks", "Key Tasks", "textarea", 6),
        _field("responsible_parties", "Responsible Parties", "textarea", 7),
        _field("deadlines", "Deadlines", "textarea", 8),
        _field("resources_needed", "Resources Needed", "textarea", 9, required=False),
        _field("risks_mitigation", "Risks & Mitigation", "textarea", 10, required=False),
        _field("progress_notes", "Progress Notes", "textarea", 11, required=False),
    ],
    "sales report": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_title", "Report Title", "text", 2),
        _field("reporting_period", "Reporting Period", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("report_date", "Report Date", "date", 5),
        _field("sales_summary", "Sales Summary", "textarea", 6),
        _field("revenue_performance", "Revenue Performance", "textarea", 7),
        _field("key_deals_closed", "Key Deals Closed", "textarea", 8, required=False),
        _field("pipeline_overview", "Pipeline Overview", "textarea", 9, required=False),
        _field("challenges", "Challenges", "textarea", 10, required=False),
        _field("recommendations", "Recommendations", "textarea", 11, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "win/loss analysis": [
        _field("company_name", "Company Name", "text", 1),
        _field("analysis_title", "Analysis Title", "text", 2),
        _field("reporting_period", "Reporting Period", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("analysis_date", "Analysis Date", "date", 5),
        _field("overview_summary", "Overview Summary", "textarea", 6),
        _field("wins", "Wins", "textarea", 7),
        _field("losses", "Losses", "textarea", 8),
        _field("key_factors", "Key Factors", "textarea", 9),
        _field("competitive_insights", "Competitive Insights", "textarea", 10, required=False),
        _field("lessons_learned", "Lessons Learned", "textarea", 11),
        _field("strategic_recommendations", "Strategic Recommendations", "textarea", 12, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "partnership proposal": [
        _field("company_name", "Company Name", "text", 1),
        _field("partner_name", "Partner Name", "text", 2),
        _field("proposal_title", "Proposal Title", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("proposal_date", "Proposal Date", "date", 5),
        _field("partnership_overview", "Partnership Overview", "textarea", 6),
        _field("objectives", "Objectives", "textarea", 7),
        _field("scope_of_collaboration", "Scope of Collaboration", "textarea", 8),
        _field("roles_responsibilities", "Roles & Responsibilities", "textarea", 9),
        _field("value_proposition", "Value Proposition", "textarea", 10),
        _field("timeline", "Timeline", "textarea", 11, required=False),
        _field("financial_terms", "Financial Terms", "textarea", 12, required=False),
        _field("additional_terms", "Additional Terms", "textarea", 13, required=False),
        _field("call_to_action", "Call to Action", "textarea", 14),
    ],
    "client feedback form": [
        _field("company_name", "Company Name", "text", 1),
        _field("client_name", "Client Name", "text", 2),
        _field("feedback_title", "Feedback Title", "text", 3),
        _field("submission_date", "Submission Date", "date", 4),
        _field("service_product_used", "Service/Product Used", "textarea", 5),
        _field("overall_experience", "Overall Experience", "textarea", 6),
        _field("satisfaction_rating", "Satisfaction Rating", "text", 7),
        _field("what_worked_well", "What Worked Well", "textarea", 8, required=False),
        _field("areas_for_improvement", "Areas for Improvement", "textarea", 9, required=False),
        _field("likelihood_to_recommend", "Likelihood to Recommend", "text", 10, required=False),
        _field("additional_comments", "Additional Comments", "textarea", 11, required=False),
        _field("client_acknowledgment_name", "Client Acknowledgment Name", "text", 12, required=False),
        _field("client_acknowledgment_date", "Client Acknowledgment Date", "date", 13, required=False),
    ],
}


HR_SCHEMAS = {
    "offer letter": [
        _field("company_name", "Company Name", "text", 1),
        _field("candidate_name", "Candidate Name", "text", 2),
        _field("job_title", "Job Title", "text", 3),
        _field("department", "Department", "text", 4),
        _field("start_date", "Start Date", "date", 5),
        _field("compensation_details", "Compensation Details", "textarea", 6),
        _field("employment_type", "Employment Type", "text", 7),
        _field("reporting_manager", "Reporting Manager", "text", 8),
        _field("work_location", "Work Location", "text", 9),
        _field("conditions_of_employment", "Conditions of Employment", "textarea", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "employment contract": [
        _field("company_name", "Company Name", "text", 1),
        _field("employee_name", "Employee Name", "text", 2),
        _field("job_title", "Job Title", "text", 3),
        _field("department", "Department", "text", 4),
        _field("start_date", "Start Date", "date", 5),
        _field("compensation", "Compensation", "textarea", 6),
        _field("work_schedule", "Work Schedule", "textarea", 7),
        _field("duties_responsibilities", "Duties & Responsibilities", "textarea", 8),
        _field("benefits", "Benefits", "textarea", 9, required=False),
        _field("termination_terms", "Termination Terms", "textarea", 10),
        _field("confidentiality_clause", "Confidentiality Clause", "textarea", 11, required=False),
        _field("additional_terms", "Additional Terms", "textarea", 12, required=False),
    ],
    "termination letter": [
        _field("company_name", "Company Name", "text", 1),
        _field("employee_name", "Employee Name", "text", 2),
        _field("job_title", "Job Title", "text", 3),
        _field("department", "Department", "text", 4),
        _field("termination_date", "Termination Date", "date", 5),
        _field("reason_for_termination", "Reason for Termination", "textarea", 6),
        _field("final_compensation_details", "Final Compensation Details", "textarea", 7),
        _field("return_of_company_property", "Return of Company Property", "textarea", 8),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "performance review": [
        _field("company_name", "Company Name", "text", 1),
        _field("employee_name", "Employee Name", "text", 2),
        _field("job_title", "Job Title", "text", 3),
        _field("department", "Department", "text", 4),
        _field("review_period", "Review Period", "text", 5),
        _field("reviewer_name", "Reviewer Name", "text", 6),
        _field("performance_summary", "Performance Summary", "textarea", 7),
        _field("key_achievements", "Key Achievements", "textarea", 8),
        _field("areas_for_improvement", "Areas for Improvement", "textarea", 9),
        _field("goals_for_next_period", "Goals for Next Period", "textarea", 10),
        _field("overall_rating", "Overall Rating", "text", 11),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "job description": [
        _field("company_name", "Company Name", "text", 1),
        _field("job_title", "Job Title", "text", 2),
        _field("department", "Department", "text", 3),
        _field("reporting_to", "Reporting To", "text", 4),
        _field("employment_type", "Employment Type", "text", 5),
        _field("work_location", "Work Location", "text", 6),
        _field("position_summary", "Position Summary", "textarea", 7),
        _field("key_responsibilities", "Key Responsibilities", "textarea", 8),
        _field("required_qualifications", "Required Qualifications", "textarea", 9),
        _field("preferred_qualifications", "Preferred Qualifications", "textarea", 10, required=False),
        _field("compensation_range", "Compensation Range", "textarea", 11, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "onboarding checklist": [
        _field("company_name", "Company Name", "text", 1),
        _field("employee_name", "Employee Name", "text", 2),
        _field("job_title", "Job Title", "text", 3),
        _field("department", "Department", "text", 4),
        _field("start_date", "Start Date", "date", 5),
        _field("prepared_by", "Prepared By", "text", 6),
        _field("pre_start_requirements", "Pre-Start Requirements", "textarea", 7),
        _field("first_day_tasks", "First Day Tasks", "textarea", 8),
        _field("first_week_objectives", "First Week Objectives", "textarea", 9),
        _field("training_setup", "Training & Setup", "textarea", 10),
        _field("required_documents", "Required Documents", "textarea", 11),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "employee handbook": [
        _field("company_name", "Company Name", "text", 1),
        _field("handbook_title", "Handbook Title", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("company_overview", "Company Overview", "textarea", 5),
        _field("code_of_conduct", "Code of Conduct", "textarea", 6),
        _field("workplace_policies", "Workplace Policies", "textarea", 7),
        _field("attendance_policy", "Attendance Policy", "textarea", 8),
        _field("compensation_benefits", "Compensation & Benefits", "textarea", 9),
        _field("disciplinary_procedures", "Disciplinary Procedures", "textarea", 10),
        _field("confidentiality_data_use", "Confidentiality & Data Use", "textarea", 11),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "pip template": [
        _field("company_name", "Company Name", "text", 1),
        _field("employee_name", "Employee Name", "text", 2),
        _field("job_title", "Job Title", "text", 3),
        _field("department", "Department", "text", 4),
        _field("plan_start_date", "Plan Start Date", "date", 5),
        _field("plan_duration", "Plan Duration", "text", 6),
        _field("manager_name", "Manager Name", "text", 7),
        _field("performance_issues", "Performance Issues", "textarea", 8),
        _field("expected_improvements", "Expected Improvements", "textarea", 9),
        _field("action_plan", "Action Plan", "textarea", 10),
        _field("evaluation_criteria", "Evaluation Criteria", "textarea", 11),
        _field("consequences_of_non_compliance", "Consequences of Non-Compliance", "textarea", 12),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "warning letter": [
        _field("company_name", "Company Name", "text", 1),
        _field("employee_name", "Employee Name", "text", 2),
        _field("job_title", "Job Title", "text", 3),
        _field("department", "Department", "text", 4),
        _field("issue_date", "Issue Date", "date", 5),
        _field("warning_type", "Warning Type", "text", 6),
        _field("description_of_issue", "Description of Issue", "textarea", 7),
        _field("previous_incidents", "Previous Incidents", "textarea", 8, required=False),
        _field("expected_behavior", "Expected Behavior", "textarea", 9),
        _field("corrective_actions", "Corrective Actions", "textarea", 10),
        _field("review_period", "Review Period", "text", 11),
        _field("consequences", "Consequences", "textarea", 12),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "reference letter": [
        _field("company_name", "Company Name", "text", 1),
        _field("employee_name", "Employee Name", "text", 2),
        _field("job_title", "Job Title", "text", 3),
        _field("employment_period", "Employment Period", "text", 4),
        _field("prepared_by", "Prepared By", "text", 5),
        _field("relationship_to_employee", "Relationship to Employee", "text", 6),
        _field("performance_summary", "Performance Summary", "textarea", 7),
        _field("key_strengths", "Key Strengths", "textarea", 8),
        _field("reason_for_leaving", "Reason for Leaving", "textarea", 9, required=False),
        _field("recommendation_statement", "Recommendation Statement", "textarea", 10),
        _field("contact_information", "Contact Information", "textarea", 11, required=False),
    ],
    "internal audit checklist": [
        _field("company_name", "Company Name", "text", 1),
        _field("audit_title", "Audit Title", "text", 2),
        _field("audit_date", "Audit Date", "date", 3),
        _field("conducted_by", "Conducted By", "text", 4),
        _field("department", "Department", "text", 5),
        _field("scope_of_audit", "Scope of Audit", "textarea", 6),
        _field("audit_criteria", "Audit Criteria", "textarea", 7),
        _field("findings", "Findings", "textarea", 8),
        _field("non_compliance_issues", "Non-Compliance Issues", "textarea", 9, required=False),
        _field("corrective_actions", "Corrective Actions", "textarea", 10),
        _field("follow_up_date", "Follow-Up Date", "date", 11, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "office incident report": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_date", "Report Date", "date", 2),
        _field("reported_by", "Reported By", "text", 3),
        _field("department", "Department", "text", 4),
        _field("incident_date", "Incident Date", "date", 5),
        _field("incident_description", "Incident Description", "textarea", 6),
        _field("individuals_involved", "Individuals Involved", "textarea", 7),
        _field("immediate_actions_taken", "Immediate Actions Taken", "textarea", 8),
        _field("impact_assessment", "Impact Assessment", "textarea", 9),
        _field("preventive_measures", "Preventive Measures", "textarea", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "mail handling log": [
        _field("company_name", "Company Name", "text", 1),
        _field("log_date", "Log Date", "date", 2),
        _field("received_by", "Received By", "text", 3),
        _field("sender_name", "Sender Name", "text", 4),
        _field("recipient_name", "Recipient Name", "text", 5),
        _field("mail_type", "Mail Type", "text", 6),
        _field("received_time", "Received Time", "text", 7),
        _field("delivered_time", "Delivered Time", "text", 8, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "office maintenance request": [
        _field("company_name", "Company Name", "text", 1),
        _field("request_date", "Request Date", "date", 2),
        _field("requested_by", "Requested By", "text", 3),
        _field("department", "Department", "text", 4),
        _field("issue_description", "Issue Description", "textarea", 5),
        _field("location", "Location", "text", 6),
        _field("urgency_level", "Urgency Level", "text", 7),
        _field("requested_action", "Requested Action", "textarea", 8),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "document control register": [
        _field("company_name", "Company Name", "text", 1),
        _field("register_date", "Register Date", "date", 2),
        _field("maintained_by", "Maintained By", "text", 3),
        _field("document_title", "Document Title", "text", 4),
        _field("version_number", "Version Number", "text", 5),
        _field("issue_date", "Issue Date", "date", 6),
        _field("approved_by", "Approved By", "text", 7),
        _field(
            "document_status",
            "Document Status",
            "select",
            8,
            options=["Active", "Archived", "Under Review", "Draft"],
        ),
        _field("storage_location", "Storage Location", "text", 9),
        _field("review_schedule", "Review Schedule", "text", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "leave policy": [
        _field("company_name", "Company Name", "text", 1),
        _field("policy_title", "Policy Title", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("policy_purpose", "Policy Purpose", "textarea", 5),
        _field("eligibility_criteria", "Eligibility Criteria", "textarea", 6),
        _field("types_of_leave_covered", "Types of Leave Covered", "textarea", 7),
        _field("leave_request_procedure", "Leave Request Procedure", "textarea", 8),
        _field("approval_process", "Approval Process", "textarea", 9),
        _field("leave_duration_entitlement", "Leave Duration & Entitlement", "textarea", 10),
        _field("documentation_requirements", "Documentation Requirements", "textarea", 11, required=False),
        _field("unapproved_absence_consequences", "Unapproved Absence Consequences", "textarea", 12),
        _field("return_to_work_expectations", "Return to Work Expectations", "textarea", 13, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 14, required=False),
    ],
}


HR_TEMPLATES = {
    "offer letter": """OFFER LETTER\n\nCompany: [Company Name]\nCandidate: [Candidate Name]\nJob Title: [Job Title]\nDepartment: [Department]\nStart Date: [Start Date]\nCompensation Details: [Compensation Details]\nEmployment Type: [Employment Type]\nReporting Manager: [Reporting Manager]\nWork Location: [Work Location]\n\nCONDITIONS OF EMPLOYMENT\n[Conditions of Employment]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nACCEPTANCE\nEmployer Signature: _________________________\nDate: ___________\nCandidate Signature: _________________________\nDate: ___________""",
    "employment contract": """EMPLOYMENT CONTRACT\n\nCompany: [Company Name]\nEmployee: [Employee Name]\nJob Title: [Job Title]\nDepartment: [Department]\nStart Date: [Start Date]\n\nCOMPENSATION\n[Compensation]\n\nWORK SCHEDULE\n[Work Schedule]\n\nDUTIES & RESPONSIBILITIES\n[Duties & Responsibilities]\n\nBENEFITS\n[Benefits]\n\nCONFIDENTIALITY\n[Confidentiality Clause]\n\nADDITIONAL TERMS\n[Additional Terms]\n\nTERMINATION TERMS\n[Termination Terms]\n\nACCEPTANCE\nEmployer Signature: _________________________\nDate: ___________\nEmployee Signature: _________________________\nDate: ___________""",
    "termination letter": """TERMINATION LETTER\n\nCompany: [Company Name]\nEmployee: [Employee Name]\nJob Title: [Job Title]\nDepartment: [Department]\nTermination Date: [Termination Date]\n\nREASON FOR TERMINATION\n[Reason for Termination]\n\nFINAL COMPENSATION\n[Final Compensation Details]\n\nRETURN OF COMPANY PROPERTY\n[Return of Company Property]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nAUTHORIZED REPRESENTATIVE\nEmployer Signature: _________________________\nDate: ___________""",
    "performance review": """PERFORMANCE REVIEW\n\nCompany: [Company Name]\nEmployee: [Employee Name]\nJob Title: [Job Title]\nDepartment: [Department]\nReview Period: [Review Period]\nReviewer: [Reviewer Name]\n\nPERFORMANCE SUMMARY\n[Performance Summary]\n\nKEY ACHIEVEMENTS\n[Key Achievements]\n\nAREAS FOR IMPROVEMENT\n[Areas for Improvement]\n\nGOALS FOR NEXT PERIOD\n[Goals for Next Period]\n\nOVERALL RATING\n[Overall Rating]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nACKNOWLEDGED\nReviewer Signature: _________________________\nDate: ___________\nEmployee Signature: _________________________\nDate: ___________""",
    "job description": """JOB DESCRIPTION\n\nCompany: [Company Name]\nJob Title: [Job Title]\nDepartment: [Department]\nReporting To: [Reporting To]\nEmployment Type: [Employment Type]\nWork Location: [Work Location]\n\nPOSITION SUMMARY\n[Position Summary]\n\nKEY RESPONSIBILITIES\n[Key Responsibilities]\n\nREQUIRED QUALIFICATIONS\n[Required Qualifications]\n\nPREFERRED QUALIFICATIONS\n[Preferred Qualifications]\n\nCOMPENSATION RANGE\n[Compensation Range]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "onboarding checklist": """ONBOARDING CHECKLIST\n\nCompany: [Company Name]\nEmployee: [Employee Name]\nJob Title: [Job Title]\nDepartment: [Department]\nStart Date: [Start Date]\nPrepared By: [Prepared By]\n\nPRE-START REQUIREMENTS\n[Pre-Start Requirements]\n\nFIRST DAY TASKS\n[First Day Tasks]\n\nFIRST WEEK OBJECTIVES\n[First Week Objectives]\n\nTRAINING & SETUP\n[Training & Setup]\n\nREQUIRED DOCUMENTS\n[Required Documents]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "employee handbook": """EMPLOYEE HANDBOOK\n\nCompany: [Company Name]\nHandbook Title: [Handbook Title]\nEffective Date: [Effective Date]\nPrepared By: [Prepared By]\n\nCOMPANY OVERVIEW\n[Company Overview]\n\nCODE OF CONDUCT\n[Code of Conduct]\n\nWORKPLACE POLICIES\n[Workplace Policies]\n\nATTENDANCE POLICY\n[Attendance Policy]\n\nCOMPENSATION & BENEFITS\n[Compensation & Benefits]\n\nDISCIPLINARY PROCEDURES\n[Disciplinary Procedures]\n\nCONFIDENTIALITY & DATA USE\n[Confidentiality & Data Use]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nACKNOWLEDGMENT\nEmployee Name: _________________________\nSignature: _________________________\nDate: ___________""",
    "pip template": """PERFORMANCE IMPROVEMENT PLAN (PIP)\n\nCompany: [Company Name]\nEmployee: [Employee Name]\nJob Title: [Job Title]\nDepartment: [Department]\nPlan Start Date: [Plan Start Date]\nPlan Duration: [Plan Duration]\nManager: [Manager Name]\n\nPERFORMANCE ISSUES\n[Performance Issues]\n\nEXPECTED IMPROVEMENTS\n[Expected Improvements]\n\nACTION PLAN\n[Action Plan]\n\nEVALUATION CRITERIA\n[Evaluation Criteria]\n\nCONSEQUENCES OF NON-COMPLIANCE\n[Consequences of Non-Compliance]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nACKNOWLEDGMENT\nManager Signature: _________________________\nDate: ___________\nEmployee Signature: _________________________\nDate: ___________""",
    "warning letter": """WARNING LETTER\n\nCompany: [Company Name]\nEmployee: [Employee Name]\nJob Title: [Job Title]\nDepartment: [Department]\nIssue Date: [Issue Date]\nWarning Type: [Warning Type]\n\nDESCRIPTION OF ISSUE\n[Description of Issue]\n\nPREVIOUS INCIDENTS\n[Previous Incidents]\n\nEXPECTED BEHAVIOR\n[Expected Behavior]\n\nCORRECTIVE ACTIONS\n[Corrective Actions]\n\nREVIEW PERIOD\n[Review Period]\n\nCONSEQUENCES\n[Consequences]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nACKNOWLEDGED\nManager Signature: _________________________\nDate: ___________\nEmployee Signature: _________________________\nDate: ___________""",
    "reference letter": """REFERENCE LETTER\n\nCompany: [Company Name]\nEmployee: [Employee Name]\nJob Title: [Job Title]\nEmployment Period: [Employment Period]\nPrepared By: [Prepared By]\nRelationship to Employee: [Relationship to Employee]\n\nPERFORMANCE SUMMARY\n[Performance Summary]\n\nKEY STRENGTHS\n[Key Strengths]\n\nREASON FOR LEAVING\n[Reason for Leaving]\n\nRECOMMENDATION STATEMENT\n[Recommendation Statement]\n\nCONTACT INFORMATION\n[Contact Information]\n\nAUTHORIZED SIGNATURE\nSignature: _________________________\nDate: ___________""",
    "internal audit checklist": """INTERNAL AUDIT CHECKLIST\n\nCompany: [Company Name]\nAudit Title: [Audit Title]\nAudit Date: [Audit Date]\nConducted By: [Conducted By]\nDepartment: [Department]\n\nSCOPE OF AUDIT\n[Scope of Audit]\n\nAUDIT CRITERIA\n[Audit Criteria]\n\nFINDINGS\n[Findings]\n\nNON-COMPLIANCE ISSUES\n[Non-Compliance Issues]\n\nCORRECTIVE ACTIONS\n[Corrective Actions]\n\nFOLLOW-UP DATE\n[Follow-Up Date]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nACKNOWLEDGED\nAuditor Signature: _________________________\nDate: ___________\nManager Signature: _________________________\nDate: ___________""",
    "office incident report": """OFFICE INCIDENT REPORT\n\nCompany: [Company Name]\nReport Date: [Report Date]\nReported By: [Reported By]\nDepartment: [Department]\nIncident Date: [Incident Date]\n\nINCIDENT DESCRIPTION\n[Incident Description]\n\nINDIVIDUALS INVOLVED\n[Individuals Involved]\n\nIMMEDIATE ACTIONS TAKEN\n[Immediate Actions Taken]\n\nIMPACT ASSESSMENT\n[Impact Assessment]\n\nPREVENTIVE MEASURES\n[Preventive Measures]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nACKNOWLEDGED\nReported By Signature: _________________________\nDate: ___________\nManager Signature: _________________________\nDate: ___________""",
    "mail handling log": """MAIL HANDLING LOG\n\nCompany: [Company Name]\nLog Date: [Log Date]\nReceived By: [Received By]\nSender Name: [Sender Name]\nRecipient Name: [Recipient Name]\nMail Type: [Mail Type]\nReceived Time: [Received Time]\nDelivered Time: [Delivered Time]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "office maintenance request": """OFFICE MAINTENANCE REQUEST\n\nCompany: [Company Name]\nRequest Date: [Request Date]\nRequested By: [Requested By]\nDepartment: [Department]\nIssue Description: [Issue Description]\nLocation: [Location]\nUrgency Level: [Urgency Level]\nRequested Action: [Requested Action]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nAPPROVAL (Optional)\nManager Signature: _________________________\nDate: ___________""",
    "document control register": """DOCUMENT CONTROL REGISTER\n\nCompany: [Company Name]\nRegister Date: [Register Date]\nMaintained By: [Maintained By]\nDocument Title: [Document Title]\nVersion Number: [Version Number]\nIssue Date: [Issue Date]\nApproved By: [Approved By]\nDocument Status: [Document Status]\nStorage Location: [Storage Location]\nReview Schedule: [Review Schedule]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nAUTHORIZED\nSignature: _________________________\nDate: ___________""",
    "leave policy": """LEAVE POLICY\n\nCompany: [Company Name]\nPolicy Title: [Policy Title]\nEffective Date: [Effective Date]\nPrepared By: [Prepared By]\n\nPOLICY PURPOSE\n[Policy Purpose]\n\nELIGIBILITY CRITERIA\n[Eligibility Criteria]\n\nTYPES OF LEAVE COVERED\n[Types of Leave Covered]\n\nLEAVE DURATIONS & ENTITLEMENT\n[Leave Duration & Entitlement]\n\nLEAVE REQUEST PROCEDURE\n[Leave Request Procedure]\n\nAPPROVAL PROCESS\n[Approval Process]\n\nDOCUMENTATION REQUIREMENTS\n[Documentation Requirements]\n\nUNAPPROVED ABSENCE CONSEQUENCES\n[Unapproved Absence Consequences]\n\nRETURN TO WORK EXPECTATIONS\n[Return to Work Expectations]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nACKNOWLEDGMENT\nEmployee Name: _________________________\nSignature: _________________________\nDate: ___________""",
}


SALES_CLIENT_TEMPLATES = {
    "sales proposal": """SALES PROPOSAL\n\nCompany: [Company Name]\nClient: [Client Name]\nProposal Date: [Proposal Date]\nPrepared By: [Prepared By]\n\nEXECUTIVE SUMMARY\n[Proposal Summary]\n\nSCOPE OF WORK\n[Scope of Work]\n\nDELIVERABLES\n[Deliverables]\n\nPROJECT TIMELINE\n[Timeline]\n\nPRICING DETAILS\n[Pricing Details]\n\nPAYMENT TERMS\n[Payment Terms]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nACCEPTANCE\nCompany Representative: _________________________\nDate: ___________\nClient: _________________________\nDate: ___________""",
    "client onboarding": """CLIENT ONBOARDING DOCUMENT\n\nCompany: [Company Name]\nClient: [Client Name]\nOnboarding Date: [Onboarding Date]\nAccount Manager: [Account Manager]\n\nCLIENT CONTACT INFORMATION\n[Client Contact Information]\n\nSERVICE / PRODUCT PURCHASED\n[Service/Product Purchased]\n\nONBOARDING CHECKLIST\n[Onboarding Checklist]\n\nINITIAL SETUP REQUIREMENTS\n[Initial Setup Requirements]\n\nIMPLEMENTATION TIMELINE\n[Timeline for Implementation]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "follow-up email": """Subject: [Subject Line]\n\nDear [Client Name],\n\nThis follow-up is issued on behalf of [Company Name] on [Follow-Up Date].\n\nPREVIOUS INTERACTION SUMMARY\n[Previous Interaction Summary]\n\nFOLLOW-UP DETAILS\n[Follow-Up Message]\n\nNEXT STEPS\n[Call to Action]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nSincerely,\n[Sender Name]\n[Sender Position]\n[Company Name]\n[Contact Information]""",
    "service agreement": """SERVICE AGREEMENT\n\nThis Service Agreement is entered into by [Company Name] and [Client Name] as of [Agreement Date].\n\nSERVICE DESCRIPTION\n[Service Description]\n\nSCOPE OF SERVICES\n[Scope of Services]\n\nTERM OF AGREEMENT\n[Term of Agreement]\n\nPAYMENT TERMS\n[Payment Terms]\n\nRESPONSIBILITIES OF COMPANY\n[Responsibilities of Company]\n\nRESPONSIBILITIES OF CLIENT\n[Responsibilities of Client]\n\nTERMINATION\n[Termination Terms]\n\nCONFIDENTIALITY\n[Confidentiality Clause]\n\nADDITIONAL TERMS\n[Additional Terms]\n\nACCEPTANCE\nCompany Representative: _________________________\nDate: ___________\nClient: _________________________\nDate: ___________""",
    "quote template": """QUOTE\n\nCompany: [Company Name]\nClient: [Client Name]\nQuote Title: [Quote Title]\nQuote Date: [Quote Date]\nPrepared By: [Prepared By]\n\nITEMIZED SERVICES/PRODUCTS\n[Itemized Services/Products]\n\nSUBTOTAL\n[Subtotal]\n\nTAXES/FEES\n[Taxes/Fees]\n\nTOTAL AMOUNT\n[Total Amount]\n\nPAYMENT TERMS\n[Payment Terms]\n\nVALIDITY PERIOD\n[Validity Period]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "meeting summary": """MEETING SUMMARY\n\nCompany: [Company Name]\nClient: [Client Name]\nMeeting Title: [Meeting Title]\nMeeting Date: [Meeting Date]\nMeeting Time: [Meeting Time]\nLocation: [Location]\n\nPARTICIPANTS\n[Participants]\n\nMEETING OBJECTIVE\n[Meeting Objective]\n\nDISCUSSION SUMMARY\n[Discussion Summary]\n\nKEY DECISIONS MADE\n[Key Decisions Made]\n\nACTION ITEMS\n[Action Items]\n\nNEXT STEPS\n[Next Steps]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "crm report": """CUSTOMER RELATIONSHIP MANAGEMENT REPORT\n\nCompany: [Company Name]\nReport Title: [Report Title]\nReporting Period: [Reporting Period]\nPrepared By: [Prepared By]\nReport Date: [Report Date]\n\nCLIENT OVERVIEW\n[Client Overview]\n\nSALES ACTIVITIES\n[Sales Activities]\n\nPIPELINE STATUS\n[Pipeline Status]\n\nOPPORTUNITIES\n[Opportunities]\n\nCHALLENGES\n[Challenges]\n\nRECOMMENDATIONS\n[Recommendations]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "pitch deck outline": """PITCH DECK OUTLINE\n\nCompany: [Company Name]\nPresentation Title: [Presentation Title]\nPrepared By: [Prepared By]\nPresentation Date: [Presentation Date]\nTarget Audience: [Target Audience]\n\nPROBLEM STATEMENT\n[Problem Statement]\n\nPROPOSED SOLUTION\n[Proposed Solution]\n\nVALUE PROPOSITION\n[Value Proposition]\n\nMARKET OPPORTUNITY\n[Market Opportunity]\n\nBUSINESS MODEL\n[Business Model]\n\nCOMPETITIVE ADVANTAGE\n[Competitive Advantage]\n\nFINANCIAL HIGHLIGHTS\n[Financial Highlights]\n\nCALL TO ACTION\n[Call to Action]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "account plan": """ACCOUNT PLAN\n\nCompany: [Company Name]\nClient: [Client Name]\nPlan Title: [Plan Title]\nPrepared By: [Prepared By]\nPlan Date: [Plan Date]\n\nACCOUNT OVERVIEW\n[Account Overview]\n\nCLIENT OBJECTIVES\n[Client Objectives]\n\nSTRATEGIC GOALS\n[Strategic Goals]\n\nKEY OPPORTUNITIES\n[Key Opportunities]\n\nRISKS & CHALLENGES\n[Risks & Challenges]\n\nACTION STEPS\n[Action Steps]\n\nTIMELINE\n[Timeline]\n\nSUCCESS METRICS\n[Success Metrics]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "action plan": """ACTION PLAN\n\nCompany: [Company Name]\nPlan Title: [Plan Title]\nPrepared By: [Prepared By]\nPlan Date: [Plan Date]\n\nOBJECTIVE\n[Objective]\n\nKEY TASKS\n[Key Tasks]\n\nRESPONSIBLE PARTIES\n[Responsible Parties]\n\nDEADLINES\n[Deadlines]\n\nRESOURCES NEEDED\n[Resources Needed]\n\nRISKS & MITIGATION\n[Risks & Mitigation]\n\nPROGRESS NOTES\n[Progress Notes]""",
    "sales report": """SALES REPORT\n\nCompany: [Company Name]\nReport Title: [Report Title]\nReporting Period: [Reporting Period]\nPrepared By: [Prepared By]\nReport Date: [Report Date]\n\nSALES SUMMARY\n[Sales Summary]\n\nREVENUE PERFORMANCE\n[Revenue Performance]\n\nKEY DEALS CLOSED\n[Key Deals Closed]\n\nPIPELINE OVERVIEW\n[Pipeline Overview]\n\nCHALLENGES\n[Challenges]\n\nRECOMMENDATIONS\n[Recommendations]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "win/loss analysis": """WIN / LOSS ANALYSIS\n\nCompany: [Company Name]\nAnalysis Title: [Analysis Title]\nReporting Period: [Reporting Period]\nPrepared By: [Prepared By]\nAnalysis Date: [Analysis Date]\n\nOVERVIEW SUMMARY\n[Overview Summary]\n\nWINS\n[Wins]\n\nLOSSES\n[Losses]\n\nKEY FACTORS\n[Key Factors]\n\nCOMPETITIVE INSIGHTS\n[Competitive Insights]\n\nLESSONS LEARNED\n[Lessons Learned]\n\nSTRATEGIC RECOMMENDATIONS\n[Strategic Recommendations]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "partnership proposal": """PARTNERSHIP PROPOSAL\n\nCompany: [Company Name]\nPartner: [Partner Name]\nProposal Title: [Proposal Title]\nPrepared By: [Prepared By]\nProposal Date: [Proposal Date]\n\nPARTNERSHIP OVERVIEW\n[Partnership Overview]\n\nOBJECTIVES\n[Objectives]\n\nSCOPE OF COLLABORATION\n[Scope of Collaboration]\n\nROLES & RESPONSIBILITIES\n[Roles & Responsibilities]\n\nVALUE PROPOSITION\n[Value Proposition]\n\nTIMELINE\n[Timeline]\n\nFINANCIAL TERMS\n[Financial Terms]\n\nADDITIONAL TERMS\n[Additional Terms]\n\nCALL TO ACTION\n[Call to Action]\n\nACCEPTANCE\nCompany Representative: _________________________\nDate: ___________\nPartner Representative: _________________________\nDate: ___________""",
    "client feedback form": """CLIENT FEEDBACK FORM\n\nCompany: [Company Name]\nClient: [Client Name]\nFeedback Title: [Feedback Title]\nSubmission Date: [Submission Date]\n\nSERVICE/PRODUCT USED\n[Service/Product Used]\n\nOVERALL EXPERIENCE\n[Overall Experience]\n\nSATISFACTION RATING\n[Satisfaction Rating]\n\nWHAT WORKED WELL\n[What Worked Well]\n\nAREAS FOR IMPROVEMENT\n[Areas for Improvement]\n\nLIKELIHOOD TO RECOMMEND\n[Likelihood to Recommend]\n\nADDITIONAL COMMENTS\n[Additional Comments]\n\nCLIENT ACKNOWLEDGMENT\nName: [Client Acknowledgment Name]\nDate: [Client Acknowledgment Date]""",
}


FINANCE_SCHEMAS = {
    "invoice": [
        _field("company_name", "Company Name", "text", 1),
        _field("company_address", "Company Address", "textarea", 2),
        _field("invoice_number", "Invoice Number", "text", 3),
        _field("invoice_date", "Invoice Date", "date", 4),
        _field("due_date", "Due Date", "date", 5),
        _field("bill_to", "Bill To", "textarea", 6),
        _field("description_of_services_products", "Description of Services/Products", "textarea", 7),
        _field("quantity", "Quantity", "number", 8),
        _field("unit_price", "Unit Price", "currency", 9),
        _field("subtotal", "Subtotal", "currency", 10, required=False, calculated=True, formula="quantity * unit_price"),
        _field("taxes", "Taxes", "currency", 11, required=False),
        _field("total_amount", "Total Amount", "currency", 12, required=False, calculated=True, formula="subtotal + taxes"),
        _field("payment_instructions", "Payment Instructions", "textarea", 13),
        _field("additional_notes", "Additional Notes", "textarea", 14, required=False),
    ],
    "receipt": [
        _field("company_name", "Company Name", "text", 1),
        _field("receipt_number", "Receipt Number", "text", 2),
        _field("payment_date", "Payment Date", "date", 3),
        _field("received_from", "Received From", "text", 4),
        _field("payment_method", "Payment Method", "text", 5),
        _field("description", "Description", "textarea", 6),
        _field("amount_paid", "Amount Paid", "currency", 7),
        _field("remaining_balance", "Remaining Balance", "currency", 8, required=False),
        _field("received_by", "Received By", "text", 9),
        _field("additional_notes", "Additional Notes", "textarea", 10, required=False),
    ],
    "purchase order": [
        _field("company_name", "Company Name", "text", 1),
        _field("company_address", "Company Address", "textarea", 2),
        _field("purchase_order_number", "Purchase Order Number", "text", 3),
        _field("order_date", "Order Date", "date", 4),
        _field("vendor_name", "Vendor Name", "text", 5),
        _field("vendor_address", "Vendor Address", "textarea", 6),
        _field("description_of_goods_services", "Description of Goods/Services", "textarea", 7),
        _field("quantity", "Quantity", "number", 8),
        _field("unit_price", "Unit Price", "currency", 9),
        _field("subtotal", "Subtotal", "currency", 10, required=False, calculated=True, formula="quantity * unit_price"),
        _field("taxes", "Taxes", "currency", 11, required=False),
        _field("total_amount", "Total Amount", "currency", 12, required=False, calculated=True, formula="subtotal + taxes"),
        _field("delivery_date", "Delivery Date", "date", 13),
        _field("payment_terms", "Payment Terms", "textarea", 14),
        _field("authorized_by", "Authorized By", "text", 15),
        _field("additional_notes", "Additional Notes", "textarea", 16, required=False),
    ],
    "expense report": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_date", "Report Date", "date", 2),
        _field("employee_name", "Employee Name", "text", 3),
        _field("department", "Department", "text", 4),
        _field("expense_period", "Expense Period", "text", 5),
        _field("expense_description", "Expense Description", "textarea", 6),
        _field("expense_category", "Expense Category", "select", 7, options=["Travel", "Meals", "Office Supplies", "Software/Subscriptions", "Client Entertainment", "Other"]),
        _field("amount", "Amount", "currency", 8),
        _field("payment_method", "Payment Method", "text", 9),
        _field("business_purpose", "Business Purpose", "textarea", 10),
        _field("approval_status", "Approval Status", "text", 11),
        _field("approved_by", "Approved By", "text", 12),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "budget proposal": [
        _field("company_name", "Company Name", "text", 1),
        _field("proposal_title", "Proposal Title", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("department", "Department", "text", 4),
        _field("budget_period", "Budget Period", "text", 5),
        _field("objective", "Objective", "textarea", 6),
        _field("estimated_expenses", "Estimated Expenses", "currency", 7),
        _field("revenue_projections", "Revenue Projections", "currency", 8, required=False),
        _field("net_position", "Net Position", "currency", 9, required=False),
        _field("budget_breakdown", "Budget Breakdown", "textarea", 10),
        _field("justification", "Justification", "textarea", 11),
        _field("risk_considerations", "Risk Considerations", "textarea", 12, required=False),
        _field("approval_required_by", "Approval Required By", "text", 13),
        _field("additional_notes", "Additional Notes", "textarea", 14, required=False),
    ],
    "payment terms": [
        _field("company_name", "Company Name", "text", 1),
        _field("effective_date", "Effective Date", "date", 2),
        _field("payment_due_terms", "Payment Due Terms", "textarea", 3),
        _field("accepted_payment_methods", "Accepted Payment Methods", "textarea", 4),
        _field("late_payment_policy", "Late Payment Policy", "textarea", 5),
        _field("fees_penalties", "Fees & Penalties", "textarea", 6, required=False),
        _field("refund_policy", "Refund Policy", "textarea", 7, required=False),
        _field("dispute_resolution", "Dispute Resolution", "textarea", 8, required=False),
        _field("contact_information", "Contact Information", "textarea", 9),
        _field("additional_notes", "Additional Notes", "textarea", 10, required=False),
    ],
    "billing statement": [
        _field("company_name", "Company Name", "text", 1),
        _field("statement_date", "Statement Date", "date", 2),
        _field("statement_period", "Statement Period", "text", 3),
        _field("customer_name", "Customer Name", "text", 4),
        _field("customer_address", "Customer Address", "textarea", 5),
        _field("previous_balance", "Previous Balance", "currency", 6),
        _field("payments_received", "Payments Received", "currency", 7),
        _field("adjustments", "Adjustments", "currency", 8, required=False),
        _field("new_charges", "New Charges", "currency", 9),
        _field("total_amount_due", "Total Amount Due", "currency", 10, required=False, calculated=True, formula="previous_balance - payments_received + adjustments + new_charges"),
        _field("due_date", "Due Date", "date", 11),
        _field("payment_instructions", "Payment Instructions", "textarea", 12),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "financial summary": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_title", "Report Title", "text", 2),
        _field("reporting_period", "Reporting Period", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("total_revenue", "Total Revenue", "currency", 5),
        _field("total_expenses", "Total Expenses", "currency", 6),
        _field("net_profit_loss", "Net Profit/Loss", "currency", 7),
        _field("key_highlights", "Key Highlights", "textarea", 8),
        _field("financial_insights", "Financial Insights", "textarea", 9, required=False),
        _field("recommendations", "Recommendations", "textarea", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "profit & loss statement": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_title", "Report Title", "text", 2),
        _field("reporting_period", "Reporting Period", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("revenue_items", "Revenue Items", "textarea", 5),
        _field("cost_of_goods_sold", "Cost of Goods Sold", "textarea", 6),
        _field("operating_expenses", "Operating Expenses", "textarea", 7),
        _field("other_income", "Other Income", "currency", 8, required=False),
        _field("other_expenses", "Other Expenses", "currency", 9, required=False),
        _field("net_profit_loss", "Net Profit/Loss", "currency", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "balance sheet": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_date", "Report Date", "date", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("assets", "Assets", "textarea", 4),
        _field("liabilities", "Liabilities", "textarea", 5),
        _field("equity", "Equity", "textarea", 6),
        _field("additional_notes", "Additional Notes", "textarea", 7, required=False),
    ],
    "cash flow statement": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_title", "Report Title", "text", 2),
        _field("reporting_period", "Reporting Period", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("cash_inflows", "Cash Inflows", "textarea", 5),
        _field("cash_outflows", "Cash Outflows", "textarea", 6),
        _field("net_cash_flow", "Net Cash Flow", "currency", 7),
        _field("opening_balance", "Opening Balance", "currency", 8),
        _field("closing_balance", "Closing Balance", "currency", 9),
        _field("additional_notes", "Additional Notes", "textarea", 10, required=False),
    ],
    "break-even analysis": [
        _field("company_name", "Company Name", "text", 1),
        _field("analysis_title", "Analysis Title", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("fixed_costs", "Fixed Costs", "currency", 4),
        _field("variable_cost_per_unit", "Variable Cost per Unit", "currency", 5),
        _field("selling_price_per_unit", "Selling Price per Unit", "currency", 6),
        _field("break_even_point_units", "Break-Even Point (Units)", "number", 7),
        _field("break_even_revenue", "Break-Even Revenue", "currency", 8),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "petty cash log": [
        _field("company_name", "Company Name", "text", 1),
        _field("log_date", "Log Date", "date", 2),
        _field("custodian_name", "Custodian Name", "text", 3),
        _field("opening_balance", "Opening Balance", "currency", 4),
        _field("transactions", "Transactions", "textarea", 5),
        _field("closing_balance", "Closing Balance", "currency", 6),
        _field("additional_notes", "Additional Notes", "textarea", 7, required=False),
    ],
    "tax summary": [
        _field("company_name", "Company Name", "text", 1),
        _field("reporting_period", "Reporting Period", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("total_revenue", "Total Revenue", "currency", 4),
        _field("taxable_income", "Taxable Income", "currency", 5),
        _field("taxes_owed", "Taxes Owed", "currency", 6),
        _field("taxes_paid", "Taxes Paid", "currency", 7, required=False),
        _field("outstanding_tax_balance", "Outstanding Tax Balance", "currency", 8, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "credit note": [
        _field("company_name", "Company Name", "text", 1),
        _field("credit_note_number", "Credit Note Number", "text", 2),
        _field("issue_date", "Issue Date", "date", 3),
        _field("customer_name", "Customer Name", "text", 4),
        _field("original_invoice_number", "Original Invoice Number", "text", 5),
        _field("reason_for_credit", "Reason for Credit", "textarea", 6),
        _field("description", "Description", "textarea", 7),
        _field("amount_credited", "Amount Credited", "currency", 8),
        _field("base_amount", "Base Amount", "currency", 9, required=False),
        _field("tax_refund", "Tax Refund", "currency", 10, required=False),
        _field("remaining_balance", "Remaining Balance", "currency", 11, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "debit note": [
        _field("company_name", "Company Name", "text", 1),
        _field("debit_note_number", "Debit Note Number", "text", 2),
        _field("issue_date", "Issue Date", "date", 3),
        _field("counterparty_type", "Counterparty Type", "select", 4, options=["Customer", "Vendor"]),
        _field("customer_vendor_name", "Customer/Vendor Name", "text", 5),
        _field("related_invoice_or_po_number", "Related Invoice / PO Number", "text", 6, required=False),
        _field("reason_for_debit", "Reason for Debit", "textarea", 7),
        _field("description", "Description", "textarea", 8),
        _field("amount_charged", "Amount Charged", "currency", 9),
        _field("updated_balance", "Updated Balance", "currency", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "audit report": [
        _field("company_name", "Company Name", "text", 1),
        _field("audit_period", "Audit Period", "text", 2),
        _field("auditor_name_firm", "Auditor Name / Firm", "text", 3),
        _field("scope_of_audit", "Scope of Audit", "textarea", 4),
        _field("key_findings", "Key Findings", "textarea", 5),
        _field("compliance_status", "Compliance Status", "text", 6),
        _field("financial_accuracy_summary", "Financial Accuracy Summary", "textarea", 7),
        _field("recommendations", "Recommendations", "textarea", 8, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "loan agreement": [
        _field("lender_name", "Lender Name", "text", 1),
        _field("borrower_name", "Borrower Name", "text", 2),
        _field("loan_amount", "Loan Amount", "currency", 3),
        _field("interest_rate", "Interest Rate", "text", 4),
        _field("loan_term", "Loan Term", "text", 5),
        _field("payment_schedule", "Payment Schedule", "textarea", 6),
        _field("start_date", "Start Date", "date", 7),
        _field("maturity_date", "Maturity Date", "date", 8, required=False, calculated=True, formula="start_date + loan_term"),
        _field("late_payment_terms", "Late Payment Terms", "textarea", 9),
        _field("early_repayment_terms", "Early Repayment Terms", "textarea", 10, required=False),
        _field("default_terms", "Default Terms", "textarea", 11),
        _field("governing_state", "Governing State", "text", 12),
        _field("additional_terms", "Additional Terms", "textarea", 13, required=False),
    ],
    "reimbursement form": [
        _field("company_name", "Company Name", "text", 1),
        _field("submission_date", "Submission Date", "date", 2),
        _field("employee_name", "Employee Name", "text", 3),
        _field("department", "Department", "text", 4),
        _field("expense_date", "Expense Date", "date", 5),
        _field("expense_description", "Expense Description", "textarea", 6),
        _field("expense_category", "Expense Category", "select", 7, options=["Travel", "Meals", "Office Supplies", "Software/Subscriptions", "Client Entertainment", "Other"]),
        _field("amount", "Amount", "currency", 8),
        _field("payment_method_used", "Payment Method Used", "text", 9),
        _field("business_purpose", "Business Purpose", "textarea", 10),
        _field("total_reimbursement_amount", "Total Reimbursement Amount", "currency", 11),
        _field("approved_by", "Approved By", "text", 12),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "payroll summary": [
        _field("company_name", "Company Name", "text", 1),
        _field("payroll_period", "Payroll Period", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("employee_names", "Employee Name(s)", "textarea", 4),
        _field("gross_pay", "Gross Pay", "currency", 5),
        _field("deductions", "Deductions", "currency", 6),
        _field("net_pay", "Net Pay", "currency", 7),
        _field("payment_date", "Payment Date", "date", 8),
        _field("payment_method", "Payment Method", "text", 9),
        _field("additional_notes", "Additional Notes", "textarea", 10, required=False),
    ],
    "vendor payment": [
        _field("company_name", "Company Name", "text", 1),
        _field("payment_date", "Payment Date", "date", 2),
        _field("vendor_name", "Vendor Name", "text", 3),
        _field("vendor_address", "Vendor Address", "textarea", 4, required=False),
        _field("invoice_number", "Invoice Number", "text", 5),
        _field("description_of_payment", "Description of Payment", "textarea", 6),
        _field("payment_amount", "Payment Amount", "currency", 7),
        _field("payment_method", "Payment Method", "text", 8),
        _field("payment_reference", "Payment Reference", "text", 9, required=False),
        _field("authorized_by", "Authorized By", "text", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
}


FINANCE_TEMPLATES = {
    "invoice": """INVOICE\n\nThis Invoice (\"Invoice\") is issued by [Company Name] on [Invoice Date] for services and/or products provided.\n\nINVOICE DETAILS\nInvoice Number: [Invoice Number]\nInvoice Date: [Invoice Date]\nDue Date: [Due Date]\n\nBILL TO\n[Bill To]\n\n1. DESCRIPTION OF SERVICES / PRODUCTS\n[Description of Services/Products]\n\n2. QUANTITY & PRICING\nQuantity: [Quantity]\nUnit Price: [Unit Price]\n\n3. FINANCIAL SUMMARY\nSubtotal: [Subtotal]\nTaxes: [Taxes]\nTotal Amount Due: [Total Amount]\n\n4. PAYMENT INSTRUCTIONS\n[Payment Instructions]\n\n5. ADDITIONAL NOTES\n[Additional Notes]\n\nThis Invoice serves as an official request for payment and should be processed accordingly.""",
    "receipt": """RECEIPT\n\nThis Receipt (\"Receipt\") is issued by [Company Name] on [Payment Date] to confirm payment received.\n\nRECEIPT DETAILS\nReceipt Number: [Receipt Number]\nPayment Date: [Payment Date]\n\nRECEIVED FROM\n[Received From]\n\n1. PAYMENT DETAILS\nPayment Method: [Payment Method]\nDescription: [Description]\nAmount Paid: [Amount Paid]\n\n[Remaining Balance Section]\n\n2. RECEIVED BY\n[Received By]\n\n3. ADDITIONAL NOTES\n[Additional Notes]\n\nThis Receipt serves as official confirmation of payment and should be retained for financial records.""",
    "purchase order": """PURCHASE ORDER\n\nThis Purchase Order (\"Order\") is issued by [Company Name] on [Order Date] to formally request the purchase of goods and/or services from the vendor listed below.\n\nPO NUMBER: [Purchase Order Number]\nORDER DATE: [Order Date]\n\nVENDOR MAILING LABEL\n[Vendor Name]\n[Vendor Address]\n\n1. DESCRIPTION OF GOODS / SERVICES\n[Description of Goods/Services]\n\n2. QUANTITY & PRICING\nQuantity: [Quantity]\nUnit Price: [Unit Price]\n\n3. FINANCIAL SUMMARY\nSubtotal: [Subtotal]\nTaxes: [Taxes]\nTotal Amount: [Total Amount]\n\n4. DELIVERY DETAILS\nExpected Delivery Date: [Delivery Date]\n\n5. PAYMENT TERMS\n[Payment Terms]\n\n6. AUTHORIZATION\nThis Order must be approved prior to fulfillment.\nAuthorized By: [Authorized By]\n\n7. ADDITIONAL NOTES\n[Additional Notes]\n\nAuthorized Signature: _________________________\nDate: ___________""",
    "expense report": """EXPENSE REPORT\n\nThis Expense Report (\"Report\") is submitted to [Company Name] on [Report Date] to document and request approval for business-related expenses incurred during the reporting period.\n\nEMPLOYEE DETAILS\nEmployee Name: [Employee Name]\nDepartment: [Department]\n\nREPORTING PERIOD\n[Expense Period]\n\nEXPENSE DETAILS\nDescription: [Expense Description]\nCategory: [Expense Category]\nAmount: [Amount]\nPayment Method: [Payment Method]\n\nBUSINESS PURPOSE\n[Business Purpose]\n\nAPPROVAL STATUS\nStatus: [Approval Status]\nApproved By: [Approved By]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nEmployee Signature: _________________________\nDate: ___________\n\nManager Signature: _________________________\nDate: ___________""",
    "budget proposal": """BUDGET PROPOSAL\n\nThis Budget Proposal (\"Proposal\") is prepared by [Company Name] to outline projected financial allocations, expected outcomes, and operational priorities for the specified budget period.\n\nPROPOSAL DETAILS\nTitle: [Proposal Title]\nPrepared By: [Prepared By]\nDepartment: [Department]\nBudget Period: [Budget Period]\n\n1. OBJECTIVE\n[Objective]\n\n2. ESTIMATED EXPENSES\n[Estimated Expenses]\n\n3. REVENUE PROJECTIONS\n[Revenue Projections]\n\n4. FINANCIAL OVERVIEW\nTotal Expenses: [Estimated Expenses]\nProjected Revenue: [Revenue Projections]\nNet Position: [Net Position]\n\n5. BUDGET BREAKDOWN\n[Budget Breakdown]\n\n6. JUSTIFICATION\n[Justification]\n\n7. RISK CONSIDERATIONS\n[Risk Considerations]\n\n8. APPROVAL\nApproved By: [Approval Required By]\n\n9. ADDITIONAL NOTES\n[Additional Notes]\n\nPrepared By: _________________________\nDate: ___________\n\nApproved By: _________________________\nDate: ___________""",
    "payment terms": """PAYMENT TERMS\n\nThese Payment Terms (\"Terms\") are established by [Company Name] and are effective as of [Effective Date].\n\n1. PAYMENT DUE TERMS\n[Payment Due Terms]\n\n2. ACCEPTED PAYMENT METHODS\n[Accepted Payment Methods]\n\n3. LATE PAYMENT POLICY\n[Late Payment Policy]\n\n4. FEES & PENALTIES\n[Fees & Penalties]\n\n5. REFUND POLICY\n[Refund Policy]\n\n6. DISPUTE RESOLUTION\n[Dispute Resolution]\n\n7. CONTACT INFORMATION\n[Contact Information]\n\n8. ADDITIONAL NOTES\n[Additional Notes]\n\nACKNOWLEDGMENT (Optional)\nAuthorized Representative Signature: _________________________\nDate: ___________""",
    "billing statement": """BILLING STATEMENT\n\nThis Billing Statement (\"Statement\") is issued by [Company Name] on [Statement Date] to provide a summary of account activity and outstanding balances for the period listed below.\n\nSTATEMENT DETAILS\nStatement Period: [Statement Period]\nStatement Date: [Statement Date]\n\nCUSTOMER INFORMATION\nCustomer Name: [Customer Name]\nCustomer Address: [Customer Address]\n\n1. ACCOUNT SUMMARY\nPrevious Balance: [Previous Balance]\nPayments Received: [Payments Received]\nAdjustments: [Adjustments]\nNew Charges: [New Charges]\nTotal Amount Due: [Total Amount Due]\n\n2. PAYMENT DUE DATE\nDue Date: [Due Date]\n\n3. PAYMENT INSTRUCTIONS\n[Payment Instructions]\n\n4. ADDITIONAL NOTES\n[Additional Notes]\n\nThis Statement serves as an official record of account activity and should be retained for financial reference.""",
    "financial summary": """FINANCIAL SUMMARY REPORT\n\nThis Financial Summary (\"Report\") is prepared by [Company Name] to provide a high-level overview of financial performance for the specified reporting period.\n\nREPORT DETAILS\nTitle: [Report Title]\nReporting Period: [Reporting Period]\nPrepared By: [Prepared By]\n\n1. FINANCIAL OVERVIEW\nTotal Revenue: [Total Revenue]\nTotal Expenses: [Total Expenses]\nNet Profit / Loss: [Net Profit/Loss]\n\n2. KEY HIGHLIGHTS\n[Key Highlights]\n\n3. FINANCIAL INSIGHTS\n[Financial Insights]\n\n4. RECOMMENDATIONS\n[Recommendations]\n\n5. ADDITIONAL NOTES\n[Additional Notes]\n\nPrepared By: _________________________\nDate: ___________""",
    "profit & loss statement": """PROFIT & LOSS STATEMENT\n\nThis Profit & Loss Statement (\"Statement\") is prepared by [Company Name] to summarize financial performance for the reporting period.\n\nREPORT DETAILS\nTitle: [Report Title]\nReporting Period: [Reporting Period]\nPrepared By: [Prepared By]\n\n1. REVENUE\n[Revenue Items]\n\n2. COST OF GOODS SOLD\n[Cost of Goods Sold]\n\n3. OPERATING EXPENSES\n[Operating Expenses]\n\n4. OTHER INCOME / EXPENSES\nOther Income: [Other Income]\nOther Expenses: [Other Expenses]\n\n5. NET PROFIT / LOSS\nNet Profit / Loss: [Net Profit/Loss]\n\n6. ADDITIONAL NOTES\n[Additional Notes]\n\nPrepared By: _________________________\nDate: ___________""",
    "balance sheet": """BALANCE SHEET\n\nThis Balance Sheet (\"Statement\") is prepared by [Company Name] as of [Report Date] to present the financial position of the organization.\n\nREPORT DETAILS\nReport Date: [Report Date]\nPrepared By: [Prepared By]\n\n1. ASSETS\n[Assets]\n\n2. LIABILITIES\n[Liabilities]\n\n3. EQUITY\n[Equity]\n\n4. ADDITIONAL NOTES\n[Additional Notes]\n\nPrepared By: _________________________\nDate: ___________""",
    "cash flow statement": """CASH FLOW STATEMENT\n\nThis Cash Flow Statement (\"Statement\") is prepared by [Company Name] to track the movement of cash during the reporting period and provide insight into liquidity and financial stability.\n\nREPORT DETAILS\nTitle: [Report Title]\nReporting Period: [Reporting Period]\nPrepared By: [Prepared By]\n\n1. CASH FLOW SUMMARY\nCash Inflows: [Cash Inflows]\nCash Outflows: [Cash Outflows]\nNet Cash Flow: [Net Cash Flow]\n\n2. CASH POSITION\nOpening Balance: [Opening Balance]\nClosing Balance: [Closing Balance]\n\n3. ADDITIONAL NOTES\n[Additional Notes]\n\nPrepared By: _________________________\nDate: ___________""",
    "break-even analysis": """BREAK-EVEN ANALYSIS\n\nThis Break-Even Analysis (\"Analysis\") is prepared by [Company Name] to determine the level of sales required to cover total costs and achieve profitability.\n\nANALYSIS DETAILS\nTitle: [Analysis Title]\nPrepared By: [Prepared By]\n\n1. COST STRUCTURE\nFixed Costs: [Fixed Costs]\nVariable Cost per Unit: [Variable Cost per Unit]\n\n2. PRICING STRUCTURE\nSelling Price per Unit: [Selling Price per Unit]\n\n3. BREAK-EVEN POINT\nBreak-Even (Units): [Break-Even Point (Units)]\nBreak-Even Revenue: [Break-Even Revenue]\n\n4. ADDITIONAL NOTES\n[Additional Notes]\n\nPrepared By: _________________________\nDate: ___________""",
    "petty cash log": """PETTY CASH LOG\n\nThis Petty Cash Log (\"Log\") is maintained by [Company Name] on [Log Date] to record and monitor small cash transactions used for operational expenses.\n\nCASH CUSTODIAN\n[Custodian Name]\n\n1. CASH SUMMARY\nOpening Balance: [Opening Balance]\nClosing Balance: [Closing Balance]\n\n2. TRANSACTION DETAILS\n[Transactions]\n\n3. ADDITIONAL NOTES\n[Additional Notes]\n\nCustodian Signature: _________________________\nDate: ___________""",
    "tax summary": """TAX SUMMARY\n\nThis Tax Summary (\"Summary\") is prepared by [Company Name] to present an overview of tax-related financial data for the specified reporting period.\n\nREPORT DETAILS\nReporting Period: [Reporting Period]\nPrepared By: [Prepared By]\n\n1. TAX OVERVIEW\nTotal Revenue: [Total Revenue]\nTaxable Income: [Taxable Income]\nTaxes Owed: [Taxes Owed]\nTaxes Paid: [Taxes Paid]\nOutstanding Balance: [Outstanding Tax Balance]\n\n2. ADDITIONAL NOTES\n[Additional Notes]\n\nPrepared By: _________________________\nDate: ___________""",
    "credit note": """CREDIT NOTE\n\nThis Credit Note (\"Note\") is issued by [Company Name] on [Issue Date] to adjust or reduce the amount owed by the customer.\n\nCREDIT NOTE DETAILS\nCredit Note Number: [Credit Note Number]\nIssue Date: [Issue Date]\nOriginal Invoice: [Original Invoice Number]\n\nCUSTOMER\n[Customer Name]\n\n1. REASON FOR CREDIT\n[Reason for Credit]\n\n2. DESCRIPTION OF ADJUSTMENT\nDescription: [Description]\nAmount Credited: [Amount Credited]\nBase Amount: [Base Amount]\nTax Refund: [Tax Refund]\n\n3. FINANCIAL IMPACT\nRemaining Balance: [Remaining Balance]\n\n4. ADDITIONAL NOTES\n[Additional Notes]\n\nAuthorized Representative Signature: _________________________\nDate: ___________""",
    "debit note": """DEBIT NOTE\n\nThis Debit Note (\"Note\") is issued by [Company Name] on [Issue Date] to notify of an adjustment resulting in an additional amount owed.\n\nDEBIT NOTE DETAILS\nDebit Note Number: [Debit Note Number]\nIssue Date: [Issue Date]\nRelated Invoice / PO Number: [Related Invoice / PO Number]\nCounterparty Type: [Counterparty Type]\n\nCUSTOMER / VENDOR\n[Customer/Vendor Name]\n\n1. REASON FOR DEBIT\n[Reason for Debit]\n\n2. DESCRIPTION OF CHARGES\nDescription: [Description]\nAmount Charged: [Amount Charged]\n\n3. FINANCIAL IMPACT\nUpdated Balance: [Updated Balance]\n\n4. ADDITIONAL NOTES\n[Additional Notes]\n\nAuthorized Representative Signature: _________________________\nDate: ___________""",
    "audit report": """AUDIT REPORT\n\nThis Audit Report (\"Report\") presents the results of an independent review conducted for [Company Name] for the period specified below.\n\nAUDIT DETAILS\nAudit Period: [Audit Period]\nAuditor: [Auditor Name / Firm]\n\n1. PURPOSE OF AUDIT\n[Scope of Audit]\n\n2. KEY FINDINGS\n[Key Findings]\n\n3. COMPLIANCE STATUS\n[Compliance Status]\n\n4. FINANCIAL ACCURACY\n[Financial Accuracy Summary]\n\n5. RECOMMENDATIONS\n[Recommendations]\n\n6. ADDITIONAL NOTES\n[Additional Notes]\n\nAuditor Signature: _________________________\nDate: ___________""",
    "loan agreement": """LOAN AGREEMENT\n\nThis Loan Agreement (\"Agreement\") is entered into between [Lender Name] (\"Lender\") and [Borrower Name] (\"Borrower\") and establishes the terms and conditions of a loan arrangement between the Parties.\n\n1. LOAN DETAILS\nLoan Amount: [Loan Amount]\nInterest Rate: [Interest Rate]\nLoan Term: [Loan Term]\n\n2. PAYMENT TERMS\nPayment Schedule: [Payment Schedule]\nStart Date: [Start Date]\nMaturity Date: [Maturity Date]\n\n3. LATE PAYMENTS\n[Late Payment Terms]\n\n4. EARLY REPAYMENT\n[Early Repayment Terms]\n\n5. DEFAULT\n[Default Terms]\n\n6. GOVERNING LAW\n[Governing State]\n\n7. ADDITIONAL TERMS\n[Additional Terms]\n\nLENDER\n[Lender Name]\nSignature: _________________________\nDate: ___________\n\nBORROWER\n[Borrower Name]\nSignature: _________________________\nDate: ___________""",
    "reimbursement form": """REIMBURSEMENT FORM\n\nThis Reimbursement Form (\"Form\") is submitted to [Company Name] on [Submission Date] to request repayment for business-related expenses incurred.\n\nEMPLOYEE DETAILS\nEmployee Name: [Employee Name]\nDepartment: [Department]\n\n1. EXPENSE INFORMATION\nExpense Date: [Expense Date]\nDescription: [Expense Description]\nCategory: [Expense Category]\nAmount: [Amount]\nPayment Method: [Payment Method Used]\n\n2. BUSINESS PURPOSE\n[Business Purpose]\n\n3. REIMBURSEMENT SUMMARY\nTotal Reimbursement: [Total Reimbursement Amount]\n\n4. APPROVAL\nApproved By: [Approved By]\n\n5. ADDITIONAL NOTES\n[Additional Notes]\n\nEmployee Signature: _________________________\nDate: ___________\n\nManager Signature: _________________________\nDate: ___________""",
    "payroll summary": """PAYROLL SUMMARY\n\nThis Payroll Summary (\"Summary\") is prepared by [Company Name] to provide an overview of employee compensation for the specified payroll period.\n\nPAYROLL DETAILS\nPayroll Period: [Payroll Period]\nPrepared By: [Prepared By]\n\n1. EMPLOYEE PAY SUMMARY\n[Employee Name(s)]\nGross Pay: [Gross Pay]\nDeductions: [Deductions]\nNet Pay: [Net Pay]\n\n2. PAYMENT DETAILS\nPayment Date: [Payment Date]\nPayment Method: [Payment Method]\n\n3. ADDITIONAL NOTES\n[Additional Notes]\n\nPrepared By: _________________________\nDate: ___________""",
    "vendor payment": """VENDOR PAYMENT RECORD\n\nThis Vendor Payment Record (\"Record\") is issued by [Company Name] to document payment made to a vendor for goods and/or services.\n\nPAYMENT DETAILS\nPayment Date: [Payment Date]\nVendor Name: [Vendor Name]\nVendor Address: [Vendor Address]\n\n1. PAYMENT INFORMATION\nInvoice Number: [Invoice Number]\nDescription: [Description of Payment]\nPayment Amount: [Payment Amount]\nPayment Method: [Payment Method]\nPayment Reference: [Payment Reference]\n\n2. AUTHORIZATION\nAuthorized By: [Authorized By]\n\n3. ADDITIONAL NOTES\n[Additional Notes]\n\nAuthorized Representative Signature: _________________________\nDate: ___________""",
}


OPS_SCHEMAS = {
    "shipping manifest": [
        _field("company_name", "Company Name", "text", 1),
        _field("shipment_id", "Shipment ID", "text", 2),
        _field("shipment_date", "Shipment Date", "date", 3),
        _field("origin_location", "Origin Location", "text", 4),
        _field("destination_location", "Destination Location", "text", 5),
        _field("carrier_name", "Carrier Name", "text", 6),
        _field("driver_name", "Driver Name", "text", 7, required=False),
        _field("tracking_number", "Tracking Number", "text", 8, required=False),
        _field("item_descriptions", "Item Description(s)", "textarea", 9),
        _field("quantity", "Quantity", "text", 10),
        _field("weight", "Weight", "text", 11, required=False),
        _field("special_instructions", "Special Instructions", "textarea", 12, required=False),
    ],
    "inventory log": [
        _field("company_name", "Company Name", "text", 1),
        _field("log_date", "Log Date", "date", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("item_names", "Item Name(s)", "textarea", 4),
        _field("sku_product_code", "SKU / Product Code", "text", 5, required=False),
        _field("quantity_in", "Quantity In", "text", 6, required=False),
        _field("quantity_out", "Quantity Out", "text", 7, required=False),
        _field("current_stock_level", "Current Stock Level", "text", 8),
        _field("location", "Location", "text", 9, required=False),
        _field("notes", "Notes", "textarea", 10, required=False),
    ],
    "delivery order": [
        _field("company_name", "Company Name", "text", 1),
        _field("delivery_order_number", "Delivery Order Number", "text", 2),
        _field("order_date", "Order Date", "date", 3),
        _field("delivery_date", "Delivery Date", "date", 4),
        _field("customer_name", "Customer Name", "text", 5),
        _field("delivery_address", "Delivery Address", "textarea", 6),
        _field("contact_information", "Contact Information", "text", 7, required=False),
        _field("item_descriptions", "Item Description(s)", "textarea", 8),
        _field("quantity", "Quantity", "text", 9),
        _field("delivery_instructions", "Delivery Instructions", "textarea", 10, required=False),
        _field("received_by", "Received By", "text", 11, required=False),
        _field("delivery_status", "Delivery Status", "select", 12, options=["Pending", "In Transit", "Delivered", "Delayed"]),
    ],
    "logistics plan": [
        _field("company_name", "Company Name", "text", 1),
        _field("plan_title", "Plan Title", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("plan_date", "Plan Date", "date", 4),
        _field("objectives", "Objectives", "textarea", 5),
        _field("scope_of_operations", "Scope of Operations", "textarea", 6),
        _field("transportation_strategy", "Transportation Strategy", "textarea", 7),
        _field("inventory_handling_plan", "Inventory Handling Plan", "textarea", 8),
        _field("risk_factors", "Risk Factors", "textarea", 9, required=False),
        _field("contingency_plan", "Contingency Plan", "textarea", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "supply chain report": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_period", "Report Period", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("supply_chain_overview", "Supply Chain Overview", "textarea", 4),
        _field("supplier_performance", "Supplier Performance", "textarea", 5),
        _field("inventory_performance", "Inventory Performance", "textarea", 6),
        _field("transportation_performance", "Transportation Performance", "textarea", 7),
        _field("key_issues", "Key Issues", "textarea", 8, required=False),
        _field("recommendations", "Recommendations", "textarea", 9, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 10, required=False),
    ],
    "warehouse checklist": [
        _field("company_name", "Company Name", "text", 1),
        _field("checklist_date", "Checklist Date", "date", 2),
        _field("supervisor_name", "Supervisor Name", "text", 3),
        _field("warehouse_location", "Warehouse Location", "text", 4),
        _field("safety_checks", "Safety Checks", "textarea", 5),
        _field("inventory_checks", "Inventory Checks", "textarea", 6),
        _field("equipment_checks", "Equipment Checks", "textarea", 7),
        _field("cleanliness_status", "Cleanliness Status", "text", 8),
        _field("issues_identified", "Issues Identified", "textarea", 9, required=False),
        _field("action_required", "Action Required", "textarea", 10, required=False),
    ],
    "fleet report": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_period", "Report Period", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("vehicle_ids", "Vehicle ID(s)", "textarea", 4),
        _field("driver_names", "Driver Name(s)", "textarea", 5, required=False),
        _field("mileage", "Mileage", "text", 6),
        _field("fuel_usage", "Fuel Usage", "text", 7, required=False),
        _field("maintenance_status", "Maintenance Status", "textarea", 8),
        _field("incidents_issues", "Incidents / Issues", "textarea", 9, required=False),
        _field("operational_status", "Operational Status", "text", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "vendor agreement": [
        _field("company_name", "Company Name", "text", 1),
        _field("vendor_name", "Vendor Name", "text", 2),
        _field("agreement_start_date", "Agreement Start Date", "date", 3),
        _field("services_goods_provided", "Services / Goods Provided", "textarea", 4),
        _field("payment_terms", "Payment Terms", "textarea", 5),
        _field("delivery_terms", "Delivery Terms", "textarea", 6),
        _field("performance_expectations", "Performance Expectations", "textarea", 7),
        _field("termination_conditions", "Termination Conditions", "textarea", 8),
        _field("confidentiality_terms", "Confidentiality Terms", "textarea", 9, required=False),
        _field("governing_state", "Governing State", "text", 10),
        _field("additional_terms", "Additional Terms", "textarea", 11, required=False),
    ],
    "procurement request": [
        _field("company_name", "Company Name", "text", 1),
        _field("request_id", "Request ID", "text", 2),
        _field("request_date", "Request Date", "date", 3),
        _field("requested_by", "Requested By", "text", 4),
        _field("department", "Department", "text", 5),
        _field("item_descriptions", "Item Description(s)", "textarea", 6),
        _field("quantity", "Quantity", "text", 7),
        _field("estimated_cost", "Estimated Cost", "currency", 8),
        _field("preferred_vendor", "Preferred Vendor", "text", 9, required=False),
        _field("justification", "Justification", "textarea", 10),
        _field("required_by_date", "Required By Date", "date", 11, required=False),
        _field("approval_status", "Approval Status", "text", 12),
        _field("approved_by", "Approved By", "text", 13, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 14, required=False),
    ],
    "goods receipt note (grn)": [
        _field("company_name", "Company Name", "text", 1),
        _field("grn_number", "GRN Number", "text", 2),
        _field("receipt_date", "Receipt Date", "date", 3),
        _field("supplier_name", "Supplier Name", "text", 4),
        _field("purchase_order_number", "Purchase Order Number", "text", 5),
        _field("delivery_reference", "Delivery Reference", "text", 6, required=False),
        _field("item_descriptions", "Item Description(s)", "textarea", 7),
        _field("quantity_received", "Quantity Received", "text", 8),
        _field("condition_of_goods", "Condition of Goods", "text", 9),
        _field("received_by", "Received By", "text", 10),
        _field("inspected_by", "Inspected By", "text", 11, required=False),
        _field("remarks", "Remarks", "textarea", 12, required=False),
    ],
}


OPS_TEMPLATES = {
    "shipping manifest": """SHIPPING MANIFEST\n\nThis Shipping Manifest (\"Manifest\") is issued by [Company Name] to formally document the shipment details and handling requirements.\n\nSHIPMENT DETAILS\nShipment ID: [Shipment ID]\nShipment Date: [Shipment Date]\nCarrier Name: [Carrier Name]\nDriver Name: [Driver Name]\nTracking Number: [Tracking Number]\n\nROUTE INFORMATION\nOrigin Location: [Origin Location]\nDestination Location: [Destination Location]\n\nITEMIZED SHIPMENT DETAILS\nItem Description(s): [Item Description(s)]\nQuantity: [Quantity]\nWeight: [Weight]\n\nSPECIAL INSTRUCTIONS\n[Special Instructions]\n\nDISPATCHER\n[Company Name]\nSignature: _________________________\nDate: ___________\n\nRECEIVER (Optional)\nSignature: _________________________\nDate: ___________""",
    "inventory log": """INVENTORY LOG\n\nThis Inventory Log (\"Log\") is maintained by [Company Name] to monitor inventory movement and stock levels.\n\nLOG DETAILS\nLog Date: [Log Date]\nPrepared By: [Prepared By]\n\nINVENTORY RECORD\nItem Name(s): [Item Name(s)]\nSKU / Product Code: [SKU / Product Code]\nQuantity In: [Quantity In]\nQuantity Out: [Quantity Out]\nCurrent Stock Level: [Current Stock Level]\nLocation: [Location]\n\nNOTES\n[Notes]\n\nPrepared By\n[Company Name]\nSignature: _________________________\nDate: ___________""",
    "delivery order": """DELIVERY ORDER\n\nThis Delivery Order (\"Order\") is issued by [Company Name] to authorize and confirm the delivery of goods.\n\nORDER DETAILS\nDelivery Order Number: [Delivery Order Number]\nOrder Date: [Order Date]\nDelivery Date: [Delivery Date]\n\nCUSTOMER INFORMATION\nCustomer Name: [Customer Name]\nDelivery Address: [Delivery Address]\nContact Information: [Contact Information]\n\nDELIVERY ITEMS\nItem Description(s): [Item Description(s)]\nQuantity: [Quantity]\n\nDELIVERY INSTRUCTIONS\n[Delivery Instructions]\n\nDELIVERY STATUS\n[Delivery Status]\n\nRECEIPT CONFIRMATION\nReceived By: [Received By]\n\nDISPATCHER\n[Company Name]\nSignature: _________________________\nDate: ___________\n\nRECEIVER\nSignature: _________________________\nDate: ___________""",
    "logistics plan": """LOGISTICS PLAN\n\nThis Logistics Plan (\"Plan\") is developed by [Company Name] to outline transportation, inventory, and distribution strategy.\n\nPLAN DETAILS\nPlan Title: [Plan Title]\nPlan Date: [Plan Date]\nPrepared By: [Prepared By]\n\nOBJECTIVES\n[Objectives]\n\nSCOPE OF OPERATIONS\n[Scope of Operations]\n\nTRANSPORTATION STRATEGY\n[Transportation Strategy]\n\nINVENTORY HANDLING PLAN\n[Inventory Handling Plan]\n\nRISK FACTORS\n[Risk Factors]\n\nCONTINGENCY PLAN\n[Contingency Plan]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nPREPARED BY\n[Prepared By]\nSignature: _________________________\nDate: ___________\n\nAPPROVED BY\nSignature: _________________________\nDate: ___________""",
    "supply chain report": """SUPPLY CHAIN REPORT\n\nThis Supply Chain Report (\"Report\") is prepared by [Company Name] to evaluate supply chain performance during the reporting period.\n\nREPORT DETAILS\nReport Period: [Report Period]\nPrepared By: [Prepared By]\n\nSUPPLY CHAIN OVERVIEW\n[Supply Chain Overview]\n\nSUPPLIER PERFORMANCE\n[Supplier Performance]\n\nINVENTORY PERFORMANCE\n[Inventory Performance]\n\nTRANSPORTATION PERFORMANCE\n[Transportation Performance]\n\nKEY ISSUES\n[Key Issues]\n\nRECOMMENDATIONS\n[Recommendations]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nPREPARED AND CERTIFIED BY\n[Prepared By]\nSignature: _________________________\nDate: ___________""",
    "warehouse checklist": """WAREHOUSE CHECKLIST\n\nThis Warehouse Checklist (\"Checklist\") is issued by [Company Name] to ensure safe and efficient warehouse operations.\n\nCHECKLIST DETAILS\nDate: [Checklist Date]\nSupervisor: [Supervisor Name]\nWarehouse Location: [Warehouse Location]\n\nSAFETY CHECKS\n[Safety Checks]\n\nINVENTORY CHECKS\n[Inventory Checks]\n\nEQUIPMENT CHECKS\n[Equipment Checks]\n\nCLEANLINESS STATUS\n[Cleanliness Status]\n\nISSUES IDENTIFIED\n[Issues Identified]\n\nACTION REQUIRED\n[Action Required]\n\nSupervisor\n[Company Name]\nSignature: _________________________\nDate: ___________""",
    "fleet report": """FLEET REPORT\n\nThis Fleet Report (\"Report\") is prepared by [Company Name] to monitor vehicle usage and operational condition.\n\nREPORT DETAILS\nReport Period: [Report Period]\nPrepared By: [Prepared By]\n\nVEHICLE PERFORMANCE\nVehicle ID(s): [Vehicle ID(s)]\nDriver Name(s): [Driver Name(s)]\nMileage: [Mileage]\nFuel Usage: [Fuel Usage]\n\nMAINTENANCE STATUS\n[Maintenance Status]\n\nINCIDENTS / ISSUES\n[Incidents / Issues]\n\nOPERATIONAL STATUS\n[Operational Status]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nPREPARED AND CERTIFIED BY\n[Prepared By]\nSignature: _________________________\nDate: ___________""",
    "vendor agreement": """VENDOR AGREEMENT\n\nThis Vendor Agreement (\"Agreement\") is entered into between [Company Name] and [Vendor Name] as of [Agreement Start Date].\n\nSERVICES / GOODS PROVIDED\n[Services / Goods Provided]\n\nPAYMENT TERMS\n[Payment Terms]\n\nDELIVERY TERMS\n[Delivery Terms]\n\nPERFORMANCE EXPECTATIONS\n[Performance Expectations]\n\nTERMINATION CONDITIONS\n[Termination Conditions]\n\nCONFIDENTIALITY TERMS\n[Confidentiality Terms]\n\nGOVERNING STATE\n[Governing State]\n\nADDITIONAL TERMS\n[Additional Terms]\n\nCOMPANY REPRESENTATIVE\n[Company Name]\nSignature: _________________________\nDate: ___________\n\nVENDOR REPRESENTATIVE\n[Vendor Name]\nSignature: _________________________\nDate: ___________""",
    "procurement request": """PROCUREMENT REQUEST\n\nThis Procurement Request (\"Request\") is submitted to [Company Name] to initiate the purchase of goods and/or services.\n\nREQUEST DETAILS\nRequest ID: [Request ID]\nRequest Date: [Request Date]\nRequested By: [Requested By]\nDepartment: [Department]\n\nREQUESTED ITEMS\nItem Description(s): [Item Description(s)]\nQuantity: [Quantity]\nEstimated Cost: [Estimated Cost]\n\nPREFERRED VENDOR\n[Preferred Vendor]\n\nBUSINESS JUSTIFICATION\n[Justification]\n\nREQUIRED BY DATE\n[Required By Date]\n\nAPPROVAL STATUS\nStatus: [Approval Status]\nApproved By: [Approved By]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nREQUESTER\n[Requested By]\nSignature: _________________________\nDate: ___________\n\nAPPROVER\n[Approved By]\nSignature: _________________________\nDate: ___________""",
    "goods receipt note (grn)": """GOODS RECEIPT NOTE (GRN)\n\nThis Goods Receipt Note (\"GRN\") is issued by [Company Name] to acknowledge and document receipt of delivered goods.\n\nRECEIPT DETAILS\nGRN Number: [GRN Number]\nReceipt Date: [Receipt Date]\nSupplier Name: [Supplier Name]\nPurchase Order Number: [Purchase Order Number]\nDelivery Reference: [Delivery Reference]\n\nRECEIVED ITEMS\nItem Description(s): [Item Description(s)]\nQuantity Received: [Quantity Received]\n\nCONDITION OF GOODS\n[Condition of Goods]\n\nINSPECTION & VERIFICATION\nReceived By: [Received By]\nInspected By: [Inspected By]\n\nREMARKS\n[Remarks]\n\nRECEIVER\n[Company Name]\nSignature: _________________________\nDate: ___________\n\nINSPECTOR (Optional)\nSignature: _________________________\nDate: ___________""",
}


LEGAL_SCHEMAS = {
    "non-disclosure agreement (freelancer nda)": [
        _field("disclosing_party_name", "Disclosing Party Name", "text", 1),
        _field("freelancer_name", "Freelancer Name", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("purpose_of_disclosure", "Purpose of Disclosure", "textarea", 4),
        _field("confidential_information_description", "Confidential Information Description", "textarea", 5),
        _field("duration_of_confidentiality", "Duration of Confidentiality", "text", 6),
        _field("permitted_use", "Permitted Use", "textarea", 7),
        _field("exclusions", "Exclusions", "textarea", 8, required=False),
        _field("governing_state", "Governing State", "text", 9),
        _field("additional_terms", "Additional Terms", "textarea", 10, required=False),
    ],
    "employee non-disclosure agreement (employee nda)": [
        _field("company_name", "Company Name", "text", 1),
        _field("employee_name", "Employee Name", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("position_role", "Position / Role", "text", 4),
        _field("confidential_information_description", "Confidential Information Description", "textarea", 5),
        _field("use_restrictions", "Use Restrictions", "textarea", 6),
        _field("duration_of_confidentiality", "Duration of Confidentiality", "text", 7),
        _field("return_of_materials_clause", "Return of Materials Clause", "textarea", 8),
        _field("governing_state", "Governing State", "text", 9),
        _field("additional_terms", "Additional Terms", "textarea", 10, required=False),
    ],
    "service agreement": [
        _field("company_name", "Company Name", "text", 1),
        _field("client_name", "Client Name", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("services_provided", "Services Provided", "textarea", 4),
        _field("payment_terms", "Payment Terms", "textarea", 5),
        _field("service_duration", "Service Duration", "text", 6),
        _field("deliverables", "Deliverables", "textarea", 7),
        _field("client_responsibilities", "Client Responsibilities", "textarea", 8),
        _field("limitation_of_liability", "Limitation of Liability", "textarea", 9),
        _field("termination_terms", "Termination Terms", "textarea", 10),
        _field("governing_state", "Governing State", "text", 11),
        _field("additional_terms", "Additional Terms", "textarea", 12, required=False),
    ],
    "partnership agreement": [
        _field("partnership_name", "Partnership Name", "text", 1),
        _field("partner_names", "Partner Names", "textarea", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("business_purpose", "Business Purpose", "textarea", 4),
        _field("ownership_structure", "Ownership Structure", "textarea", 5),
        _field("capital_contributions", "Capital Contributions", "textarea", 6),
        _field("profit_loss_distribution", "Profit & Loss Distribution", "textarea", 7),
        _field("roles_responsibilities", "Roles & Responsibilities", "textarea", 8),
        _field("decision_making_process", "Decision-Making Process", "textarea", 9),
        _field("exit_dissolution_terms", "Exit / Dissolution Terms", "textarea", 10),
        _field("governing_state", "Governing State", "text", 11),
        _field("additional_terms", "Additional Terms", "textarea", 12, required=False),
    ],
    "consulting contract": [
        _field("consultant_name", "Consultant Name", "text", 1),
        _field("client_name", "Client Name", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("services_provided", "Services Provided", "textarea", 4),
        _field("payment_terms", "Payment Terms", "textarea", 5),
        _field("contract_duration", "Contract Duration", "text", 6),
        _field("deliverables", "Deliverables", "textarea", 7),
        _field("confidentiality_clause", "Confidentiality Clause", "textarea", 8),
        _field("termination_terms", "Termination Terms", "textarea", 9),
        _field("governing_state", "Governing State", "text", 10),
        _field("additional_terms", "Additional Terms", "textarea", 11, required=False),
    ],
    "terms of service": [
        _field("company_name", "Company Name", "text", 1),
        _field("effective_date", "Effective Date", "date", 2),
        _field("services_description", "Services Description", "textarea", 3),
        _field("user_responsibilities", "User Responsibilities", "textarea", 4),
        _field("prohibited_activities", "Prohibited Activities", "textarea", 5),
        _field("limitation_of_liability", "Limitation of Liability", "textarea", 6),
        _field("termination_clause", "Termination Clause", "textarea", 7),
        _field("governing_state", "Governing State", "text", 8),
        _field("contact_information", "Contact Information", "textarea", 9),
        _field("additional_terms", "Additional Terms", "textarea", 10, required=False),
    ],
    "privacy policy": [
        _field("company_name", "Company Name", "text", 1),
        _field("effective_date", "Effective Date", "date", 2),
        _field("data_collected", "Data Collected", "textarea", 3),
        _field("how_data_is_used", "How Data Is Used", "textarea", 4),
        _field("data_sharing_practices", "Data Sharing Practices", "textarea", 5),
        _field("data_security_measures", "Data Security Measures", "textarea", 6),
        _field("user_rights", "User Rights", "textarea", 7),
        _field("cookies_tracking", "Cookies / Tracking", "textarea", 8, required=False),
        _field("third_party_services", "Third-Party Services", "textarea", 9, required=False),
        _field("governing_state", "Governing State", "text", 10),
        _field("contact_information", "Contact Information", "textarea", 11),
        _field("additional_terms", "Additional Terms", "textarea", 12, required=False),
    ],
    "cease and desist letter": [
        _field("sender_name", "Sender Name", "text", 1),
        _field("recipient_name", "Recipient Name", "text", 2),
        _field("date", "Date", "date", 3),
        _field("violation_description", "Violation Description", "textarea", 4),
        _field("demand_actions", "Demand Actions", "textarea", 5),
        _field("deadline_for_compliance", "Deadline for Compliance", "date", 6),
        _field("consequences_of_non_compliance", "Consequences of Non-Compliance", "textarea", 7),
        _field("governing_state", "Governing State", "text", 8),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "letter of intent (loi)": [
        _field("sender_name", "Sender Name", "text", 1),
        _field("recipient_name", "Recipient Name", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("purpose_of_agreement", "Purpose of Agreement", "textarea", 4),
        _field("proposed_terms", "Proposed Terms", "textarea", 5),
        _field("timeline", "Timeline", "textarea", 6),
        _field("responsibilities_of_parties", "Responsibilities of Parties", "textarea", 7),
        _field("non_binding_clause", "Non-Binding Clause", "textarea", 8),
        _field("confidentiality_clause", "Confidentiality Clause", "textarea", 9, required=False),
        _field("governing_state", "Governing State", "text", 10),
        _field("additional_terms", "Additional Terms", "textarea", 11, required=False),
    ],
    "intellectual property assignment agreement": [
        _field("assignor_name", "Assignor Name", "text", 1),
        _field("assignee_name", "Assignee Name", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("description_of_work_ip", "Description of Work / IP", "textarea", 4),
        _field("consideration", "Consideration", "textarea", 5),
        _field("scope_of_rights_transferred", "Scope of Rights Transferred", "textarea", 6),
        _field("warranties", "Warranties", "textarea", 7),
        _field("further_assurances_clause", "Further Assurances Clause", "textarea", 8, required=False),
        _field("governing_state", "Governing State", "text", 9),
        _field("additional_terms", "Additional Terms", "textarea", 10, required=False),
    ],
    "vendor contract": [
        _field("company_name", "Company Name", "text", 1),
        _field("vendor_name", "Vendor Name", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("goods_services_provided", "Goods / Services Provided", "textarea", 4),
        _field("pricing_payment_terms", "Pricing & Payment Terms", "textarea", 5),
        _field("delivery_terms", "Delivery Terms", "textarea", 6),
        _field("quality_standards", "Quality Standards", "textarea", 7),
        _field("termination_clause", "Termination Clause", "textarea", 8),
        _field("liability_clause", "Liability Clause", "textarea", 9),
        _field("governing_state", "Governing State", "text", 10),
        _field("additional_terms", "Additional Terms", "textarea", 11, required=False),
    ],
    "confidentiality agreement": [
        _field("party_a_name", "Party A Name", "text", 1),
        _field("party_b_name", "Party B Name", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("purpose_of_disclosure", "Purpose of Disclosure", "textarea", 4),
        _field("confidential_information_definition", "Confidential Information Definition", "textarea", 5),
        _field("obligations_of_both_parties", "Obligations of Both Parties", "textarea", 6),
        _field("duration_of_confidentiality", "Duration of Confidentiality", "text", 7),
        _field("exclusions", "Exclusions", "textarea", 8, required=False),
        _field("governing_state", "Governing State", "text", 9),
        _field("additional_terms", "Additional Terms", "textarea", 10, required=False),
    ],
    "independent contractor agreement": [
        _field("company_name", "Company Name", "text", 1),
        _field("contractor_name", "Contractor Name", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("services_provided", "Services Provided", "textarea", 4),
        _field("compensation_terms", "Compensation Terms", "textarea", 5),
        _field("contract_duration", "Contract Duration", "text", 6),
        _field("deliverables", "Deliverables", "textarea", 7),
        _field("independent_status_clause", "Independent Status Clause", "textarea", 8),
        _field("confidentiality_clause", "Confidentiality Clause", "textarea", 9),
        _field("termination_terms", "Termination Terms", "textarea", 10),
        _field("governing_state", "Governing State", "text", 11),
        _field("additional_terms", "Additional Terms", "textarea", 12, required=False),
    ],
    "release of liability agreement": [
        _field("releasing_party_name", "Releasing Party Name", "text", 1),
        _field("receiving_party_name", "Receiving Party Name", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("activity_description", "Activity Description", "textarea", 4),
        _field("risks_acknowledgment", "Risks Acknowledgment", "textarea", 5),
        _field("waiver_clause", "Waiver Clause", "textarea", 6),
        _field("indemnification_clause", "Indemnification Clause", "textarea", 7),
        _field("governing_state", "Governing State", "text", 8),
        _field("additional_terms", "Additional Terms", "textarea", 9, required=False),
    ],
    "legal notice": [
        _field("sender_name", "Sender Name", "text", 1),
        _field("recipient_name", "Recipient Name", "text", 2),
        _field("date", "Date", "date", 3),
        _field("subject", "Subject", "text", 4),
        _field("notice_content", "Notice Content", "textarea", 5),
        _field("required_action", "Required Action", "textarea", 6),
        _field("deadline", "Deadline", "date", 7),
        _field("governing_state", "Governing State", "text", 8),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
}


LEGAL_TEMPLATES = {
    "non-disclosure agreement (freelancer nda)": """NON-DISCLOSURE AGREEMENT (FREELANCER NDA)\n\nThis Non-Disclosure Agreement (\"Agreement\") is entered into as of [Effective Date] between [Disclosing Party Name] (\"Disclosing Party\") and [Freelancer Name] (\"Recipient\").\n\n1. PURPOSE\n[Purpose of Disclosure]\n\n2. DEFINITION OF CONFIDENTIAL INFORMATION\n[Confidential Information Description]\n\n3. OBLIGATIONS OF RECIPIENT\nThe Recipient agrees to maintain confidentiality, restrict disclosure, and use reasonable safeguards.\n\n4. PERMITTED USE\n[Permitted Use]\n\n5. EXCLUSIONS\n[Exclusions]\n\n6. TERM AND DURATION\n[Duration of Confidentiality]\n\n7. GOVERNING LAW\nThis Agreement shall be governed by the laws of the State of [Governing State].\n\n8. ADDITIONAL TERMS\n[Additional Terms]\n\nDISCLOSING PARTY\n[Disclosing Party Name]\nSignature: _________________________\nDate: ___________\n\nRECIPIENT (FREELANCER)\n[Freelancer Name]\nSignature: _________________________\nDate: ___________""",
    "employee non-disclosure agreement (employee nda)": """EMPLOYEE NON-DISCLOSURE AGREEMENT (EMPLOYEE NDA)\n\nThis Employee Non-Disclosure Agreement (\"Agreement\") is entered into as of [Effective Date] between [Company Name] (\"Company\") and [Employee Name] (\"Employee\").\n\n1. POSITION / ROLE\n[Position / Role]\n\n2. CONFIDENTIAL INFORMATION\n[Confidential Information Description]\n\n3. USE RESTRICTIONS\n[Use Restrictions]\n\n4. RETURN OF MATERIALS\n[Return of Materials Clause]\n\n5. DURATION OF CONFIDENTIALITY\n[Duration of Confidentiality]\n\n6. GOVERNING LAW\nThis Agreement shall be governed by the laws of the State of [Governing State].\n\n7. ADDITIONAL TERMS\n[Additional Terms]\n\nEMPLOYER\n[Company Name]\nSignature: _________________________\nDate: ___________\n\nEMPLOYEE\n[Employee Name]\nSignature: _________________________\nDate: ___________""",
    "service agreement": """SERVICE AGREEMENT\n\nThis Service Agreement (\"Agreement\") is entered into as of [Effective Date] between [Company Name] (\"Service Provider\") and [Client Name] (\"Client\").\n\n1. SERVICES\n[Services Provided]\n\n2. DELIVERABLES\n[Deliverables]\n\n3. PAYMENT TERMS\n[Payment Terms]\n\n4. SERVICE DURATION\n[Service Duration]\n\n5. CLIENT RESPONSIBILITIES\n[Client Responsibilities]\n\n6. LIMITATION OF LIABILITY\n[Limitation of Liability]\n\n7. TERMINATION\n[Termination Terms]\n\n8. GOVERNING LAW\nThis Agreement shall be governed by the laws of the State of [Governing State].\n\n9. ADDITIONAL TERMS\n[Additional Terms]\n\nSERVICE PROVIDER\n[Company Name]\nSignature: _________________________\nDate: ___________\n\nCLIENT\n[Client Name]\nSignature: _________________________\nDate: ___________""",
    "partnership agreement": """PARTNERSHIP AGREEMENT\n\nThis Partnership Agreement (\"Agreement\") is entered into as of [Effective Date] by and between [Partner Names].\n\n1. PARTNERSHIP NAME\n[Partnership Name]\n\n2. BUSINESS PURPOSE\n[Business Purpose]\n\n3. OWNERSHIP STRUCTURE\n[Ownership Structure]\n\n4. CAPITAL CONTRIBUTIONS\n[Capital Contributions]\n\n5. PROFIT & LOSS DISTRIBUTION\n[Profit & Loss Distribution]\n\n6. ROLES & RESPONSIBILITIES\n[Roles & Responsibilities]\n\n7. DECISION-MAKING PROCESS\n[Decision-Making Process]\n\n8. EXIT / DISSOLUTION TERMS\n[Exit / Dissolution Terms]\n\n9. GOVERNING LAW\nThis Agreement shall be governed by the laws of the State of [Governing State].\n\n10. ADDITIONAL TERMS\n[Additional Terms]\n\nPARTNERS\nSignature: _________________________\nDate: ___________""",
    "consulting contract": """CONSULTING CONTRACT\n\nThis Consulting Contract (\"Contract\") is entered into as of [Effective Date] between [Consultant Name] and [Client Name].\n\n1. SERVICES\n[Services Provided]\n\n2. DELIVERABLES\n[Deliverables]\n\n3. PAYMENT TERMS\n[Payment Terms]\n\n4. CONTRACT DURATION\n[Contract Duration]\n\n5. CONFIDENTIALITY\n[Confidentiality Clause]\n\n6. TERMINATION\n[Termination Terms]\n\n7. GOVERNING LAW\nThis Contract shall be governed by the laws of the State of [Governing State].\n\n8. ADDITIONAL TERMS\n[Additional Terms]\n\nCONSULTANT\n[Consultant Name]\nSignature: _________________________\nDate: ___________\n\nCLIENT\n[Client Name]\nSignature: _________________________\nDate: ___________""",
    "terms of service": """TERMS OF SERVICE\n\nThese Terms of Service (\"Terms\") govern the use of services provided by [Company Name] as of [Effective Date].\n\n1. SERVICES\n[Services Description]\n\n2. USER RESPONSIBILITIES\n[User Responsibilities]\n\n3. PROHIBITED ACTIVITIES\n[Prohibited Activities]\n\n4. LIMITATION OF LIABILITY\n[Limitation of Liability]\n\n5. TERMINATION\n[Termination Clause]\n\n6. GOVERNING LAW\nThese Terms shall be governed by the laws of the State of [Governing State].\n\n7. CONTACT INFORMATION\n[Contact Information]\n\n8. ADDITIONAL TERMS\n[Additional Terms]""",
    "privacy policy": """PRIVACY POLICY\n\nThis Privacy Policy (\"Policy\") outlines how [Company Name] collects, uses, and protects user information as of [Effective Date].\n\n1. DATA COLLECTED\n[Data Collected]\n\n2. HOW DATA IS USED\n[How Data Is Used]\n\n3. DATA SHARING PRACTICES\n[Data Sharing Practices]\n\n4. DATA SECURITY MEASURES\n[Data Security Measures]\n\n5. USER RIGHTS\n[User Rights]\n\n6. COOKIES / TRACKING\n[Cookies / Tracking]\n\n7. THIRD-PARTY SERVICES\n[Third-Party Services]\n\n8. GOVERNING LAW\nThis Policy shall be governed by the laws of the State of [Governing State].\n\n9. CONTACT INFORMATION\n[Contact Information]\n\n10. ADDITIONAL TERMS\n[Additional Terms]""",
    "cease and desist letter": """CEASE AND DESIST LETTER\n\nThis Cease and Desist Letter (\"Letter\") is issued on [Date] by [Sender Name] to [Recipient Name].\n\n1. VIOLATION DESCRIPTION\n[Violation Description]\n\n2. DEMAND ACTIONS\n[Demand Actions]\n\n3. DEADLINE FOR COMPLIANCE\n[Deadline for Compliance]\n\n4. CONSEQUENCES OF NON-COMPLIANCE\n[Consequences of Non-Compliance]\n\n5. GOVERNING LAW\nThis matter shall be governed by the laws of the State of [Governing State].\n\n6. ADDITIONAL NOTES\n[Additional Notes]\n\nSENDER\n[Sender Name]\nSignature: _________________________\nDate: ___________""",
    "letter of intent (loi)": """LETTER OF INTENT (LOI)\n\nThis Letter of Intent (\"LOI\") is issued on [Effective Date] by [Sender Name] to [Recipient Name].\n\n1. PURPOSE OF AGREEMENT\n[Purpose of Agreement]\n\n2. PROPOSED TERMS\n[Proposed Terms]\n\n3. TIMELINE\n[Timeline]\n\n4. RESPONSIBILITIES OF PARTIES\n[Responsibilities of Parties]\n\n5. NON-BINDING CLAUSE\n[Non-Binding Clause]\n\n6. CONFIDENTIALITY CLAUSE\n[Confidentiality Clause]\n\n7. GOVERNING LAW\nThis LOI shall be governed by the laws of the State of [Governing State].\n\n8. ADDITIONAL TERMS\n[Additional Terms]\n\nSENDER\n[Sender Name]\nSignature: _________________________\nDate: ___________\n\nRECIPIENT (ACKNOWLEDGMENT)\n[Recipient Name]\nSignature: _________________________\nDate: ___________""",
    "intellectual property assignment agreement": """INTELLECTUAL PROPERTY ASSIGNMENT AGREEMENT\n\nThis Intellectual Property Assignment Agreement (\"Agreement\") is entered into as of [Effective Date] between [Assignor Name] and [Assignee Name].\n\n1. DESCRIPTION OF WORK / IP\n[Description of Work / IP]\n\n2. CONSIDERATION\n[Consideration]\n\n3. SCOPE OF RIGHTS TRANSFERRED\n[Scope of Rights Transferred]\n\n4. WARRANTIES\n[Warranties]\n\n5. FURTHER ASSURANCES CLAUSE\n[Further Assurances Clause]\n\n6. GOVERNING LAW\nThis Agreement shall be governed by the laws of the State of [Governing State].\n\n7. ADDITIONAL TERMS\n[Additional Terms]\n\nASSIGNOR\n[Assignor Name]\nSignature: _________________________\nDate: ___________\n\nASSIGNEE\n[Assignee Name]\nSignature: _________________________\nDate: ___________""",
    "vendor contract": """VENDOR CONTRACT\n\nThis Vendor Contract (\"Agreement\") is entered into as of [Effective Date] between [Company Name] and [Vendor Name].\n\n1. GOODS / SERVICES PROVIDED\n[Goods / Services Provided]\n\n2. PRICING & PAYMENT TERMS\n[Pricing & Payment Terms]\n\n3. DELIVERY TERMS\n[Delivery Terms]\n\n4. QUALITY STANDARDS\n[Quality Standards]\n\n5. LIABILITY CLAUSE\n[Liability Clause]\n\n6. TERMINATION CLAUSE\n[Termination Clause]\n\n7. GOVERNING LAW\nThis Agreement shall be governed by the laws of the State of [Governing State].\n\n8. ADDITIONAL TERMS\n[Additional Terms]\n\nCOMPANY\n[Company Name]\nSignature: _________________________\nDate: ___________\n\nVENDOR\n[Vendor Name]\nSignature: _________________________\nDate: ___________""",
    "confidentiality agreement": """CONFIDENTIALITY AGREEMENT\n\nThis Confidentiality Agreement (\"Agreement\") is entered into as of [Effective Date] between [Party A Name] and [Party B Name].\n\n1. PURPOSE OF DISCLOSURE\n[Purpose of Disclosure]\n\n2. CONFIDENTIAL INFORMATION DEFINITION\n[Confidential Information Definition]\n\n3. OBLIGATIONS OF BOTH PARTIES\n[Obligations of Both Parties]\n\n4. EXCLUSIONS\n[Exclusions]\n\n5. DURATION OF CONFIDENTIALITY\n[Duration of Confidentiality]\n\n6. GOVERNING LAW\nThis Agreement shall be governed by the laws of the State of [Governing State].\n\n7. ADDITIONAL TERMS\n[Additional Terms]\n\nPARTY A\n[Party A Name]\nSignature: _________________________\nDate: ___________\n\nPARTY B\n[Party B Name]\nSignature: _________________________\nDate: ___________""",
    "independent contractor agreement": """INDEPENDENT CONTRACTOR AGREEMENT\n\nThis Independent Contractor Agreement (\"Agreement\") is entered into as of [Effective Date] between [Company Name] and [Contractor Name].\n\n1. SERVICES PROVIDED\n[Services Provided]\n\n2. DELIVERABLES\n[Deliverables]\n\n3. COMPENSATION TERMS\n[Compensation Terms]\n\n4. CONTRACT DURATION\n[Contract Duration]\n\n5. INDEPENDENT STATUS CLAUSE\n[Independent Status Clause]\n\n6. CONFIDENTIALITY CLAUSE\n[Confidentiality Clause]\n\n7. TERMINATION TERMS\n[Termination Terms]\n\n8. GOVERNING LAW\nThis Agreement shall be governed by the laws of the State of [Governing State].\n\n9. ADDITIONAL TERMS\n[Additional Terms]\n\nCOMPANY\n[Company Name]\nSignature: _________________________\nDate: ___________\n\nCONTRACTOR\n[Contractor Name]\nSignature: _________________________\nDate: ___________""",
    "release of liability agreement": """RELEASE OF LIABILITY AGREEMENT\n\nThis Release of Liability Agreement (\"Agreement\") is entered into as of [Effective Date] between [Releasing Party Name] and [Receiving Party Name].\n\n1. ACTIVITY DESCRIPTION\n[Activity Description]\n\n2. RISKS ACKNOWLEDGMENT\n[Risks Acknowledgment]\n\n3. WAIVER CLAUSE\n[Waiver Clause]\n\n4. INDEMNIFICATION CLAUSE\n[Indemnification Clause]\n\n5. GOVERNING LAW\nThis Agreement shall be governed by the laws of the State of [Governing State].\n\n6. ADDITIONAL TERMS\n[Additional Terms]\n\nRELEASING PARTY\n[Releasing Party Name]\nSignature: _________________________\nDate: ___________""",
    "legal notice": """LEGAL NOTICE\n\nThis Legal Notice (\"Notice\") is issued on [Date] by [Sender Name] to [Recipient Name].\n\nSUBJECT: [Subject]\n\n1. NOTICE\n[Notice Content]\n\n2. REQUIRED ACTION\n[Required Action]\n\n3. DEADLINE\n[Deadline]\n\n4. GOVERNING LAW\nThis Notice shall be governed by the laws of the State of [Governing State].\n\n5. ADDITIONAL NOTES\n[Additional Notes]""",
}


MARKETING_SCHEMAS = {
    "press release": [
        _field("company_name", "Company Name", "text", 1),
        _field("announcement_title", "Announcement Title", "text", 2),
        _field("release_date", "Release Date", "date", 3),
        _field("location", "Location", "text", 4),
        _field("announcement_summary", "Announcement Summary", "textarea", 5),
        _field("key_highlights", "Key Highlights", "textarea", 6),
        _field("executive_quote", "Executive Quote", "textarea", 7),
        _field("product_service_details", "Product/Service Details", "textarea", 8),
        _field("availability", "Availability", "textarea", 9),
        _field("media_contact_name", "Media Contact Name", "text", 10),
        _field("media_contact_email", "Media Contact Email", "text", 11),
        _field("media_contact_phone", "Media Contact Phone", "text", 12, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "campaign brief": [
        _field("campaign_name", "Campaign Name", "text", 1),
        _field("company_name", "Company Name", "text", 2),
        _field("campaign_objective", "Campaign Objective", "textarea", 3),
        _field("target_audience", "Target Audience", "textarea", 4),
        _field("key_message", "Key Message", "textarea", 5),
        _field("marketing_channels", "Marketing Channels", "textarea", 6),
        _field("campaign_timeline", "Campaign Timeline", "textarea", 7),
        _field("budget_overview", "Budget Overview", "textarea", 8),
        _field("key_deliverables", "Key Deliverables", "textarea", 9),
        _field("success_metrics", "Success Metrics", "textarea", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "social media plan": [
        _field("company_name", "Company Name", "text", 1),
        _field("plan_duration", "Plan Duration", "text", 2),
        _field("target_audience", "Target Audience", "textarea", 3),
        _field("platforms", "Platforms", "textarea", 4),
        _field("content_strategy", "Content Strategy", "textarea", 5),
        _field("posting_schedule", "Posting Schedule", "textarea", 6),
        _field("engagement_strategy", "Engagement Strategy", "textarea", 7),
        _field("kpis", "KPIs", "textarea", 8),
        _field("budget", "Budget", "textarea", 9, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 10, required=False),
    ],
    "brand guidelines": [
        _field("company_name", "Company Name", "text", 1),
        _field("brand_mission", "Brand Mission", "textarea", 2),
        _field("brand_vision", "Brand Vision", "textarea", 3),
        _field("target_audience", "Target Audience", "textarea", 4),
        _field("brand_voice", "Brand Voice", "textarea", 5),
        _field("tone_guidelines", "Tone Guidelines", "textarea", 6),
        _field("color_palette", "Color Palette", "textarea", 7),
        _field("typography", "Typography", "textarea", 8),
        _field("logo_usage_rules", "Logo Usage Rules", "textarea", 9),
        _field("content_style_guidelines", "Content Style Guidelines", "textarea", 10),
        _field("dos_and_donts", "Do's and Don'ts", "textarea", 11),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "email newsletter": [
        _field("company_name", "Company Name", "text", 1),
        _field("newsletter_title", "Newsletter Title", "text", 2),
        _field("date", "Date", "date", 3),
        _field("subject_line", "Subject Line", "text", 4),
        _field("greeting", "Greeting", "textarea", 5),
        _field("main_content", "Main Content", "textarea", 6),
        _field("featured_section", "Featured Section", "textarea", 7, required=False),
        _field("call_to_action", "Call to Action", "textarea", 8),
        _field("closing_message", "Closing Message", "textarea", 9),
        _field("contact_information", "Contact Information", "textarea", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "ad copy": [
        _field("company_name", "Company Name", "text", 1),
        _field("campaign_name", "Campaign Name", "text", 2),
        _field("target_audience", "Target Audience", "textarea", 3),
        _field("platform", "Platform", "text", 4),
        _field("headline", "Headline", "text", 5),
        _field("primary_text", "Primary Text", "textarea", 6),
        _field("supporting_text", "Supporting Text", "textarea", 7, required=False),
        _field("call_to_action", "Call to Action", "textarea", 8),
        _field("key_benefits", "Key Benefits", "textarea", 9),
        _field("offer_details", "Offer Details", "textarea", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "content calendar": [
        _field("company_name", "Company Name", "text", 1),
        _field("calendar_duration", "Calendar Duration", "text", 2),
        _field("platforms", "Platforms", "textarea", 3),
        _field("content_themes", "Content Themes", "textarea", 4),
        _field("posting_frequency", "Posting Frequency", "text", 5),
        _field("content_types", "Content Types", "textarea", 6),
        _field("responsible_team", "Responsible Team", "textarea", 7),
        _field("key_dates", "Key Dates", "textarea", 8),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "influencer brief": [
        _field("company_name", "Company Name", "text", 1),
        _field("campaign_name", "Campaign Name", "text", 2),
        _field("influencer_name", "Influencer Name", "text", 3),
        _field("platforms", "Platform(s)", "textarea", 4),
        _field("campaign_objective", "Campaign Objective", "textarea", 5),
        _field("target_audience", "Target Audience", "textarea", 6),
        _field("content_requirements", "Content Requirements", "textarea", 7),
        _field("deliverables", "Deliverables", "textarea", 8),
        _field("posting_guidelines", "Posting Guidelines", "textarea", 9),
        _field("timeline", "Timeline", "textarea", 10),
        _field("compensation_details", "Compensation Details", "textarea", 11),
        _field("approval_process", "Approval Process", "textarea", 12),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "marketing report": [
        _field("company_name", "Company Name", "text", 1),
        _field("reporting_period", "Reporting Period", "text", 2),
        _field("campaign_name", "Campaign Name", "text", 3, required=False),
        _field("objectives", "Objectives", "textarea", 4),
        _field("channels_used", "Channels Used", "textarea", 5),
        _field("key_metrics", "Key Metrics", "textarea", 6),
        _field("performance_summary", "Performance Summary", "textarea", 7),
        _field("insights", "Insights", "textarea", 8),
        _field("recommendations", "Recommendations", "textarea", 9),
        _field("budget_summary", "Budget Summary", "textarea", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "event proposal": [
        _field("company_name", "Company Name", "text", 1),
        _field("event_name", "Event Name", "text", 2),
        _field("event_objective", "Event Objective", "textarea", 3),
        _field("event_description", "Event Description", "textarea", 4),
        _field("target_audience", "Target Audience", "textarea", 5),
        _field("event_date", "Event Date", "date", 6),
        _field("event_location", "Event Location", "text", 7),
        _field("budget_overview", "Budget Overview", "textarea", 8),
        _field("key_activities", "Key Activities", "textarea", 9),
        _field("timeline", "Timeline", "textarea", 10),
        _field("expected_outcomes", "Expected Outcomes", "textarea", 11),
        _field("responsible_team", "Responsible Team", "textarea", 12),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
}


MARKETING_TEMPLATES = {
    "press release": """PRESS RELEASE\n\nThis Press Release (\"Release\") is issued on [Release Date] by [Company Name] from [Location].\n\nSUBJECT: [Announcement Title]\n\n1. ANNOUNCEMENT SUMMARY\n[Announcement Summary]\n\n2. KEY HIGHLIGHTS\n[Key Highlights]\n\n3. EXECUTIVE STATEMENT\n[Executive Quote]\n\n4. PRODUCT / SERVICE DETAILS\n[Product/Service Details]\n\n5. AVAILABILITY\n[Availability]\n\n6. MEDIA CONTACT\nName: [Media Contact Name]\nEmail: [Media Contact Email]\nPhone: [Media Contact Phone]\n\n7. ADDITIONAL NOTES\n[Additional Notes]""",
    "campaign brief": """CAMPAIGN BRIEF\n\nThis Campaign Brief (\"Brief\") is prepared for [Campaign Name], initiated by [Company Name].\n\n1. CAMPAIGN OBJECTIVE\n[Campaign Objective]\n\n2. TARGET AUDIENCE\n[Target Audience]\n\n3. KEY MESSAGE\n[Key Message]\n\n4. MARKETING CHANNELS\n[Marketing Channels]\n\n5. CAMPAIGN TIMELINE\n[Campaign Timeline]\n\n6. BUDGET OVERVIEW\n[Budget Overview]\n\n7. KEY DELIVERABLES\n[Key Deliverables]\n\n8. SUCCESS METRICS\n[Success Metrics]\n\n9. ADDITIONAL NOTES\n[Additional Notes]""",
    "social media plan": """SOCIAL MEDIA PLAN\n\nThis Social Media Plan (\"Plan\") is developed for [Company Name] covering [Plan Duration].\n\n1. TARGET AUDIENCE\n[Target Audience]\n\n2. PLATFORMS\n[Platforms]\n\n3. CONTENT STRATEGY\n[Content Strategy]\n\n4. POSTING SCHEDULE\n[Posting Schedule]\n\n5. ENGAGEMENT STRATEGY\n[Engagement Strategy]\n\n6. KPIs\n[KPIs]\n\n7. BUDGET\n[Budget]\n\n8. ADDITIONAL NOTES\n[Additional Notes]""",
    "brand guidelines": """BRAND GUIDELINES\n\nThis document defines the official standards for [Company Name].\n\n1. BRAND MISSION\n[Brand Mission]\n\n2. BRAND VISION\n[Brand Vision]\n\n3. TARGET AUDIENCE\n[Target Audience]\n\n4. BRAND VOICE\n[Brand Voice]\n\n5. TONE GUIDELINES\n[Tone Guidelines]\n\n6. COLOR PALETTE\n[Color Palette]\n\n7. TYPOGRAPHY\n[Typography]\n\n8. LOGO USAGE RULES\n[Logo Usage Rules]\n\n9. CONTENT STYLE GUIDELINES\n[Content Style Guidelines]\n\n10. DO'S AND DON'TS\n[Do's and Don'ts]\n\n11. ADDITIONAL NOTES\n[Additional Notes]""",
    "email newsletter": """EMAIL NEWSLETTER\n\nThis Email Newsletter is issued by [Company Name] on [Date].\n\nNEWSLETTER TITLE: [Newsletter Title]\nSUBJECT: [Subject Line]\n\n1. GREETING\n[Greeting]\n\n2. MAIN CONTENT\n[Main Content]\n\n3. FEATURED SECTION\n[Featured Section]\n\n4. CALL TO ACTION\n[Call to Action]\n\n5. CLOSING MESSAGE\n[Closing Message]\n\n6. CONTACT INFORMATION\n[Contact Information]\n\n7. ADDITIONAL NOTES\n[Additional Notes]""",
    "ad copy": """AD COPY\n\nThis Ad Copy is developed for [Campaign Name] by [Company Name].\n\n1. TARGET AUDIENCE\n[Target Audience]\n\n2. PLATFORM\n[Platform]\n\n3. HEADLINE\n[Headline]\n\n4. PRIMARY TEXT\n[Primary Text]\n\n5. SUPPORTING TEXT\n[Supporting Text]\n\n6. KEY BENEFITS\n[Key Benefits]\n\n7. OFFER DETAILS\n[Offer Details]\n\n8. CALL TO ACTION\n[Call to Action]\n\n9. ADDITIONAL NOTES\n[Additional Notes]""",
    "content calendar": """CONTENT CALENDAR\n\nThis Content Calendar is developed for [Company Name] for [Calendar Duration].\n\n1. PLATFORMS\n[Platforms]\n\n2. CONTENT THEMES\n[Content Themes]\n\n3. POSTING FREQUENCY\n[Posting Frequency]\n\n4. CONTENT TYPES\n[Content Types]\n\n5. RESPONSIBLE TEAM\n[Responsible Team]\n\n6. KEY DATES\n[Key Dates]\n\n7. ADDITIONAL NOTES\n[Additional Notes]""",
    "influencer brief": """INFLUENCER BRIEF\n\nThis Influencer Brief is issued by [Company Name] for [Campaign Name] and intended for [Influencer Name].\n\n1. CAMPAIGN OBJECTIVE\n[Campaign Objective]\n\n2. TARGET AUDIENCE\n[Target Audience]\n\n3. PLATFORMS\n[Platform(s)]\n\n4. CONTENT REQUIREMENTS\n[Content Requirements]\n\n5. DELIVERABLES\n[Deliverables]\n\n6. POSTING GUIDELINES\n[Posting Guidelines]\n\n7. TIMELINE\n[Timeline]\n\n8. COMPENSATION DETAILS\n[Compensation Details]\n\n9. APPROVAL PROCESS\n[Approval Process]\n\n10. ADDITIONAL NOTES\n[Additional Notes]""",
    "marketing report": """MARKETING REPORT\n\nThis Marketing Report is prepared for [Company Name] covering [Reporting Period].\n\nCAMPAIGN NAME: [Campaign Name]\n\n1. OBJECTIVES\n[Objectives]\n\n2. CHANNELS USED\n[Channels Used]\n\n3. KEY METRICS\n[Key Metrics]\n\n4. PERFORMANCE SUMMARY\n[Performance Summary]\n\n5. INSIGHTS\n[Insights]\n\n6. RECOMMENDATIONS\n[Recommendations]\n\n7. BUDGET SUMMARY\n[Budget Summary]\n\n8. ADDITIONAL NOTES\n[Additional Notes]""",
    "event proposal": """EVENT PROPOSAL\n\nThis Event Proposal is prepared by [Company Name] for the event [Event Name].\n\n1. EVENT OBJECTIVE\n[Event Objective]\n\n2. EVENT DESCRIPTION\n[Event Description]\n\n3. TARGET AUDIENCE\n[Target Audience]\n\n4. EVENT DATE\n[Event Date]\n\n5. EVENT LOCATION\n[Event Location]\n\n6. BUDGET OVERVIEW\n[Budget Overview]\n\n7. KEY ACTIVITIES\n[Key Activities]\n\n8. TIMELINE\n[Timeline]\n\n9. EXPECTED OUTCOMES\n[Expected Outcomes]\n\n10. RESPONSIBLE TEAM\n[Responsible Team]\n\n11. ADDITIONAL NOTES\n[Additional Notes]""",
}


GENERAL_SCHEMAS = {
    "cover letter": [
        _field("sender_name", "Sender Name", "text", 1),
        _field("sender_address", "Sender Address", "textarea", 2),
        _field("recipient_name", "Recipient Name", "text", 3),
        _field("recipient_address", "Recipient Address", "textarea", 4),
        _field("date", "Date", "date", 5),
        _field("position_subject", "Position/Subject", "text", 6),
        _field("opening_paragraph", "Opening Paragraph", "textarea", 7),
        _field("experience_summary", "Experience Summary", "textarea", 8),
        _field("key_achievements", "Key Achievements", "textarea", 9),
        _field("closing_statement", "Closing Statement", "textarea", 10),
        _field("contact_information", "Contact Information", "textarea", 11),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "meeting agenda": [
        _field("company_name", "Company Name", "text", 1),
        _field("meeting_title", "Meeting Title", "text", 2),
        _field("date", "Date", "date", 3),
        _field("time", "Time", "text", 4),
        _field("location", "Location", "text", 5),
        _field("meeting_objective", "Meeting Objective", "textarea", 6),
        _field("attendees", "Attendees", "textarea", 7),
        _field("agenda_items", "Agenda Items", "textarea", 8),
        _field("presenter_owner", "Presenter/Owner", "text", 9),
        _field("time_allocation", "Time Allocation", "text", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "project plan": [
        _field("company_name", "Company Name", "text", 1),
        _field("project_name", "Project Name", "text", 2),
        _field("project_manager", "Project Manager", "text", 3),
        _field("start_date", "Start Date", "date", 4),
        _field("end_date", "End Date", "date", 5),
        _field("project_objective", "Project Objective", "textarea", 6),
        _field("scope_description", "Scope Description", "textarea", 7),
        _field("key_deliverables", "Key Deliverables", "textarea", 8),
        _field("milestones", "Milestones", "textarea", 9),
        _field("responsible_parties", "Responsible Parties", "textarea", 10),
        _field("timeline", "Timeline", "textarea", 11),
        _field("risks", "Risks", "textarea", 12),
        _field("mitigation_strategies", "Mitigation Strategies", "textarea", 13),
        _field("additional_notes", "Additional Notes", "textarea", 14, required=False),
    ],
    "status report": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_title", "Report Title", "text", 2),
        _field("reporting_period", "Reporting Period", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("project_department", "Project/Department", "text", 5),
        _field("key_updates", "Key Updates", "textarea", 6),
        _field("completed_tasks", "Completed Tasks", "textarea", 7),
        _field("pending_tasks", "Pending Tasks", "textarea", 8),
        _field("issues_challenges", "Issues/Challenges", "textarea", 9),
        _field("action_items", "Action Items", "textarea", 10),
        _field("next_steps", "Next Steps", "textarea", 11),
        _field("status_level", "Status Level", "text", 12),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "checklist": [
        _field("company_name", "Company Name", "text", 1),
        _field("checklist_title", "Checklist Title", "text", 2),
        _field("date", "Date", "date", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("department_project", "Department/Project", "text", 5),
        _field("checklist_items", "Checklist Items", "textarea", 6),
        _field("responsible_person", "Responsible Person", "text", 7),
        _field("status", "Status", "text", 8),
        _field("notes", "Notes", "textarea", 9, required=False),
    ],
    "to-do list": [
        _field("company_name", "Company Name", "text", 1),
        _field("list_title", "List Title", "text", 2),
        _field("date", "Date", "date", 3),
        _field("assigned_to", "Assigned To", "text", 4),
        _field("task_items", "Task Items", "textarea", 5),
        _field("priority_level", "Priority Level", "text", 6),
        _field("due_date", "Due Date", "date", 7),
        _field("status", "Status", "text", 8),
        _field("notes", "Notes", "textarea", 9, required=False),
    ],
    "notes template": [
        _field("company_name", "Company Name", "text", 1),
        _field("title", "Title", "text", 2),
        _field("date", "Date", "date", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("subject_topic", "Subject/Topic", "text", 5),
        _field("key_points", "Key Points", "textarea", 6),
        _field("discussion_details", "Discussion Details", "textarea", 7),
        _field("action_items", "Action Items", "textarea", 8, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "invoice": [
        _field("company_name", "Company Name", "text", 1),
        _field("company_address", "Company Address", "textarea", 2),
        _field("company_contact", "Company Contact", "text", 3),
        _field("client_name", "Client Name", "text", 4),
        _field("client_address", "Client Address", "textarea", 5),
        _field("invoice_number", "Invoice Number", "text", 6),
        _field("invoice_date", "Invoice Date", "date", 7),
        _field("due_date", "Due Date", "date", 8),
        _field("service_product_description", "Service/Product Description", "textarea", 9),
        _field("quantity", "Quantity", "text", 10),
        _field("unit_price", "Unit Price", "text", 11),
        _field("total_amount", "Total Amount", "text", 12),
        _field("payment_terms", "Payment Terms", "textarea", 13),
        _field("payment_method", "Payment Method", "textarea", 14),
        _field("payment_instructions", "Payment Instructions", "textarea", 15, required=False),
        _field("notes", "Notes", "textarea", 16, required=False),
    ],
    "contract agreement": [
        _field("company_name", "Company Name", "text", 1),
        _field("company_address", "Company Address", "textarea", 2),
        _field("client_name", "Client Name", "text", 3),
        _field("client_address", "Client Address", "textarea", 4),
        _field("agreement_date", "Agreement Date", "date", 5),
        _field("services_description", "Services Description", "textarea", 6),
        _field("payment_terms", "Payment Terms", "textarea", 7),
        _field("term_duration", "Term Duration", "text", 8),
        _field("termination_conditions", "Termination Conditions", "textarea", 9),
        _field("confidentiality_terms", "Confidentiality Terms", "textarea", 10),
        _field("liability_terms", "Liability Terms", "textarea", 11),
        _field("governing_state", "Governing State", "text", 12),
        _field("additional_terms", "Additional Terms", "textarea", 13, required=False),
    ],
    "proposal": [
        _field("company_name", "Company Name", "text", 1),
        _field("company_address", "Company Address", "textarea", 2),
        _field("client_name", "Client Name", "text", 3),
        _field("client_address", "Client Address", "textarea", 4),
        _field("proposal_date", "Proposal Date", "date", 5),
        _field("project_title", "Project Title", "text", 6),
        _field("project_overview", "Project Overview", "textarea", 7),
        _field("scope_of_work", "Scope of Work", "textarea", 8),
        _field("deliverables", "Deliverables", "textarea", 9),
        _field("timeline", "Timeline", "textarea", 10),
        _field("pricing_details", "Pricing Details", "textarea", 11),
        _field("terms_and_conditions", "Terms and Conditions", "textarea", 12),
        _field("expiration_date", "Expiration Date", "date", 13),
        _field("additional_notes", "Additional Notes", "textarea", 14, required=False),
    ],
    "presentation outline": [
        _field("company_name", "Company Name", "text", 1),
        _field("presentation_title", "Presentation Title", "text", 2),
        _field("presenter_name", "Presenter Name", "text", 3),
        _field("date", "Date", "date", 4),
        _field("audience", "Audience", "text", 5),
        _field("presentation_objective", "Presentation Objective", "textarea", 6),
        _field("key_topics", "Key Topics", "textarea", 7),
        _field("introduction_points", "Introduction Points", "textarea", 8),
        _field("main_content_sections", "Main Content Sections", "textarea", 9),
        _field("supporting_data_examples", "Supporting Data/Examples", "textarea", 10, required=False),
        _field("key_takeaways", "Key Takeaways", "textarea", 11),
        _field("call_to_action", "Call to Action", "textarea", 12),
        _field("estimated_duration", "Estimated Duration", "text", 13, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 14, required=False),
    ],
}


GENERAL_TEMPLATES = {
    "cover letter": """COVER LETTER\n\n[Sender Name]\n[Sender Address]\n\n[Date]\n\n[Recipient Name]\n[Recipient Address]\n\nSUBJECT: Application for [Position/Subject]\n\nDear [Recipient Name],\n\n[Opening Paragraph]\n\nMy professional experience includes:\n\n[Experience Summary]\n\nNotable achievements include:\n\n[Key Achievements]\n\n[Closing Statement]\n\nYou may contact me at:\n\n[Contact Information]\n\nSincerely,\n\n[Sender Name]\n\nSignature: _________________________\nDate: ___________\n\n[Additional Notes]""",
    "meeting agenda": """[Company Name]\n\nMEETING AGENDA: [Meeting Title]\n\nDate: [Date]\nTime: [Time]\nLocation: [Location]\n\nMEETING OBJECTIVE\n[Meeting Objective]\n\nATTENDEES\n[Attendees]\n\nAGENDA OVERVIEW\nAgenda Item: [Agenda Items]\nPresenter / Owner: [Presenter/Owner]\nTime Allocation: [Time Allocation]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "project plan": """PROJECT PLAN\n\n[Company Name]\n\nPROJECT PLAN: [Project Name]\nProject Manager: [Project Manager]\nStart Date: [Start Date]\nEnd Date: [End Date]\n\n1. PROJECT OBJECTIVE\n[Project Objective]\n\n2. PROJECT SCOPE\n[Scope Description]\n\n3. KEY DELIVERABLES\n[Key Deliverables]\n\n4. PROJECT TIMELINE & MILESTONES\nMilestones: [Milestones]\nResponsible Parties: [Responsible Parties]\nTimeline: [Timeline]\n\n5. RISKS AND MITIGATION\nRisks: [Risks]\nMitigation Strategies: [Mitigation Strategies]\n\n6. ADDITIONAL NOTES\n[Additional Notes]""",
    "status report": """STATUS REPORT\n\n[Company Name]\n\nSTATUS REPORT: [Report Title]\nReporting Period: [Reporting Period]\nPrepared By: [Prepared By]\nProject/Department: [Project/Department]\n\nKEY UPDATES\n[Key Updates]\n\nCOMPLETED TASKS\n[Completed Tasks]\n\nPENDING TASKS\n[Pending Tasks]\n\nISSUES/CHALLENGES\n[Issues/Challenges]\n\nACTION ITEMS\n[Action Items]\n\nNEXT STEPS\n[Next Steps]\n\nSTATUS LEVEL\n[Status Level]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "checklist": """[Company Name]\n\nCHECKLIST: [Checklist Title]\nDate: [Date]\nPrepared By: [Prepared By]\nDepartment / Project: [Department/Project]\n\nChecklist Items: [Checklist Items]\nResponsible Person: [Responsible Person]\nStatus: [Status]\nNotes: [Notes]""",
    "to-do list": """[Company Name]\n\nTO-DO LIST: [List Title]\nDate: [Date]\nAssigned To: [Assigned To]\n\nTask Items: [Task Items]\nPriority Level: [Priority Level]\nDue Date: [Due Date]\nStatus: [Status]\nNotes: [Notes]""",
    "notes template": """[Company Name]\n\nNOTES: [Title]\nDate: [Date]\nPrepared By: [Prepared By]\nSubject / Topic: [Subject/Topic]\n\nKEY POINTS\n[Key Points]\n\nDISCUSSION DETAILS\n[Discussion Details]\n\nACTION ITEMS\n[Action Items]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "invoice": """[Company Name]\n[Company Address]\nContact: [Company Contact]\n\nINVOICE\nInvoice Number: [Invoice Number]\nInvoice Date: [Invoice Date]\nDue Date: [Due Date]\n\nBILL TO:\n[Client Name]\n[Client Address]\n\nDescription: [Service/Product Description]\nQuantity: [Quantity]\nUnit Price: [Unit Price]\nTotal Amount: [Total Amount]\n\nPayment Terms: [Payment Terms]\nPayment Method: [Payment Method]\nPayment Instructions: [Payment Instructions]\n\nNotes: [Notes]""",
    "contract agreement": """CONTRACT AGREEMENT\n\nThis Contract Agreement is entered into as of [Agreement Date] by and between [Company Name], [Company Address] and [Client Name], [Client Address].\n\nSERVICES\n[Services Description]\n\nPAYMENT TERMS\n[Payment Terms]\n\nTERM DURATION\n[Term Duration]\n\nTERMINATION CONDITIONS\n[Termination Conditions]\n\nCONFIDENTIALITY TERMS\n[Confidentiality Terms]\n\nLIABILITY TERMS\n[Liability Terms]\n\nGOVERNING STATE\n[Governing State]\n\nADDITIONAL TERMS\n[Additional Terms]\n\nSIGNATURES\n[Company Name]\nAuthorized Representative\nSignature: _________________________\nDate: ___________\n\n[Client Name]\nSignature: _________________________\nDate: ___________""",
    "proposal": """PROPOSAL\n\nPrepared By:\n[Company Name]\n[Company Address]\n\nPrepared For:\n[Client Name]\n[Client Address]\n\nProposal Date: [Proposal Date]\nProject Title: [Project Title]\n\nPROJECT OVERVIEW\n[Project Overview]\n\nSCOPE OF WORK\n[Scope of Work]\n\nDELIVERABLES\n[Deliverables]\n\nTIMELINE\n[Timeline]\n\nPRICING DETAILS\n[Pricing Details]\n\nTERMS AND CONDITIONS\n[Terms and Conditions]\n\nEXPIRATION DATE\n[Expiration Date]\n\nADDITIONAL NOTES\n[Additional Notes]\n\nSIGNATURES\n[Company Name]\nAuthorized Representative\nSignature: _________________________\nDate: ___________\n\n[Client Name]\nSignature: _________________________\nDate: ___________""",
    "presentation outline": """[Company Name]\n\nPRESENTATION OUTLINE: [Presentation Title]\nPresenter: [Presenter Name]\nDate: [Date]\nAudience: [Audience]\n\nPRESENTATION OBJECTIVE\n[Presentation Objective]\n\nINTRODUCTION POINTS\n[Introduction Points]\n\nKEY TOPICS\n[Key Topics]\n\nMAIN CONTENT SECTIONS\n[Main Content Sections]\n\nSUPPORTING DATA/EXAMPLES\n[Supporting Data/Examples]\n\nKEY TAKEAWAYS\n[Key Takeaways]\n\nCALL TO ACTION\n[Call to Action]\n\nESTIMATED DURATION\n[Estimated Duration]\n\nADDITIONAL NOTES\n[Additional Notes]""",
}


COMPLIANCE_SCHEMAS = {
    "compliance checklist": [
        _field("company_name", "Company Name", "text", 1),
        _field("department", "Department", "text", 2),
        _field("compliance_area", "Compliance Area", "text", 3),
        _field("review_period", "Review Period", "text", 4),
        _field("responsible_person", "Responsible Person", "text", 5),
        _field("checklist_items", "Checklist Items", "textarea", 6),
        _field("status", "Status", "text", 7),
        _field("notes", "Notes", "textarea", 8, required=False),
        _field("review_date", "Review Date", "date", 9),
    ],
    "audit trail": [
        _field("company_name", "Company Name", "text", 1),
        _field("process_system_name", "Process/System Name", "text", 2),
        _field("audit_period", "Audit Period", "text", 3),
        _field("responsible_department", "Responsible Department", "text", 4),
        _field("activity_description", "Activity Description", "textarea", 5),
        _field("user_responsible_person", "User/Responsible Person", "text", 6),
        _field("date_time", "Date & Time", "text", 7),
        _field("action_taken", "Action Taken", "textarea", 8),
        _field("status", "Status", "text", 9),
        _field("additional_notes", "Additional Notes", "textarea", 10, required=False),
    ],
    "data retention policy": [
        _field("company_name", "Company Name", "text", 1),
        _field("policy_effective_date", "Policy Effective Date", "date", 2),
        _field("data_types", "Data Types", "textarea", 3),
        _field("retention_periods", "Retention Periods", "textarea", 4),
        _field("storage_methods", "Storage Methods", "textarea", 5),
        _field("access_control", "Access Control", "textarea", 6),
        _field("data_disposal_methods", "Data Disposal Methods", "textarea", 7),
        _field("responsible_department", "Responsible Department", "text", 8),
        _field("compliance_standards", "Compliance Standards", "textarea", 9),
        _field("additional_notes", "Additional Notes", "textarea", 10, required=False),
    ],
    "gdpr policy": [
        _field("company_name", "Company Name", "text", 1),
        _field("policy_effective_date", "Policy Effective Date", "date", 2),
        _field("data_controller_name", "Data Controller Name", "text", 3),
        _field("types_of_personal_data_collected", "Types of Personal Data Collected", "textarea", 4),
        _field("purpose_of_data_processing", "Purpose of Data Processing", "textarea", 5),
        _field("legal_basis_for_processing", "Legal Basis for Processing", "textarea", 6),
        _field("data_subject_rights", "Data Subject Rights", "textarea", 7),
        _field("data_retention_period", "Data Retention Period", "textarea", 8),
        _field("data_protection_measures", "Data Protection Measures", "textarea", 9),
        _field("third_party_sharing", "Third-Party Sharing", "textarea", 10),
        _field("contact_information", "Contact Information", "textarea", 11),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "regulatory filing": [
        _field("company_name", "Company Name", "text", 1),
        _field("filing_title", "Filing Title", "text", 2),
        _field("regulatory_authority", "Regulatory Authority", "text", 3),
        _field("filing_date", "Filing Date", "date", 4),
        _field("reporting_period", "Reporting Period", "text", 5),
        _field("description_of_filing", "Description of Filing", "textarea", 6),
        _field("key_disclosures", "Key Disclosures", "textarea", 7),
        _field("supporting_documents", "Supporting Documents", "textarea", 8),
        _field("responsible_officer", "Responsible Officer", "text", 9),
        _field("submission_status", "Submission Status", "text", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "risk register": [
        _field("company_name", "Company Name", "text", 1),
        _field("department", "Department", "text", 2),
        _field("reporting_period", "Reporting Period", "text", 3),
        _field("risk_categories", "Risk Categories", "textarea", 4),
        _field("identified_risks", "Identified Risks", "textarea", 5),
        _field("risk_impact", "Risk Impact", "text", 6),
        _field("likelihood", "Likelihood", "text", 7),
        _field("mitigation_plan", "Mitigation Plan", "textarea", 8),
        _field("risk_owner", "Risk Owner", "text", 9),
        _field("status", "Status", "text", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "incident form": [
        _field("company_name", "Company Name", "text", 1),
        _field("incident_title", "Incident Title", "text", 2),
        _field("date_of_incident", "Date of Incident", "date", 3),
        _field("time_of_incident", "Time of Incident", "text", 4),
        _field("location", "Location", "text", 5),
        _field("reported_by", "Reported By", "text", 6),
        _field("incident_description", "Incident Description", "textarea", 7),
        _field("individuals_involved", "Individuals Involved", "textarea", 8),
        _field("immediate_action_taken", "Immediate Action Taken", "textarea", 9),
        _field("severity_level", "Severity Level", "text", 10),
        _field("follow_up_actions", "Follow-Up Actions", "textarea", 11),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "ethics policy": [
        _field("company_name", "Company Name", "text", 1),
        _field("policy_effective_date", "Policy Effective Date", "date", 2),
        _field("core_values", "Core Values", "textarea", 3),
        _field("code_of_conduct", "Code of Conduct", "textarea", 4),
        _field("conflict_of_interest_policy", "Conflict of Interest Policy", "textarea", 5),
        _field("reporting_violations", "Reporting Violations", "textarea", 6),
        _field("disciplinary_actions", "Disciplinary Actions", "textarea", 7),
        _field("compliance_responsibility", "Compliance Responsibility", "text", 8),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "records index": [
        _field("company_name", "Company Name", "text", 1),
        _field("department", "Department", "text", 2),
        _field("index_date", "Index Date", "date", 3),
        _field("record_categories", "Record Categories", "textarea", 4),
        _field("record_name", "Record Name", "text", 5),
        _field("record_description", "Record Description", "textarea", 6),
        _field("storage_location", "Storage Location", "text", 7),
        _field("retention_period", "Retention Period", "text", 8),
        _field("responsible_person", "Responsible Person", "text", 9),
        _field("status", "Status", "text", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "compliance report": [
        _field("company_name", "Company Name", "text", 1),
        _field("reporting_period", "Reporting Period", "text", 2),
        _field("department", "Department", "text", 3),
        _field("compliance_areas", "Compliance Areas", "textarea", 4),
        _field("findings", "Findings", "textarea", 5),
        _field("violations_identified", "Violations Identified", "textarea", 6),
        _field("corrective_actions", "Corrective Actions", "textarea", 7),
        _field("responsible_parties", "Responsible Parties", "textarea", 8),
        _field("status", "Status", "text", 9),
        _field("review_date", "Review Date", "date", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
}


BUSINESS_OPERATION_SCHEMAS = {
    "internal memo": [
        _field("company_name", "Company Name", "text", 1),
        _field("memo_date", "Date", "date", 2),
        _field("from_name", "From", "text", 3),
        _field("to_name", "To", "text", 4),
        _field("subject", "Subject", "text", 5),
        _field("purpose", "Purpose", "textarea", 6),
        _field("key_message", "Key Message", "textarea", 7),
        _field("action_required", "Action Required", "textarea", 8, required=False),
        _field("deadline", "Deadline", "text", 9, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 10, required=False),
    ],
    "company policy notice": [
        _field("company_name", "Company Name", "text", 1),
        _field("policy_title", "Policy Title", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("department", "Department", "text", 4),
        _field("policy_overview", "Policy Overview", "textarea", 5),
        _field("policy_details", "Policy Details", "textarea", 6),
        _field("responsibilities", "Responsibilities", "textarea", 7),
        _field("compliance_requirements", "Compliance Requirements", "textarea", 8),
        _field("consequences", "Consequences", "textarea", 9),
        _field("additional_notes", "Additional Notes", "textarea", 10, required=False),
    ],
    "sop summary": [
        _field("company_name", "Company Name", "text", 1),
        _field("procedure_title", "Procedure Title", "text", 2),
        _field("department", "Department", "text", 3),
        _field("effective_date", "Effective Date", "date", 4),
        _field("prepared_by", "Prepared By", "text", 5),
        _field("purpose", "Purpose", "textarea", 6),
        _field("scope", "Scope", "textarea", 7),
        _field("key_steps", "Key Steps", "textarea", 8),
        _field("roles_and_responsibilities", "Roles and Responsibilities", "textarea", 9),
        _field("compliance_requirements", "Compliance Requirements", "textarea", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "incident report": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_date", "Report Date", "date", 2),
        _field("incident_date", "Incident Date", "date", 3),
        _field("incident_time", "Incident Time", "text", 4),
        _field("location", "Location", "text", 5),
        _field("reported_by", "Reported By", "text", 6),
        _field("individuals_involved", "Individuals Involved", "textarea", 7),
        _field("incident_description", "Incident Description", "textarea", 8),
        _field("immediate_actions_taken", "Immediate Actions Taken", "textarea", 9),
        _field("root_cause", "Root Cause", "textarea", 10, required=False),
        _field("corrective_actions", "Corrective Actions", "textarea", 11),
        _field("status", "Status", "text", 12),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "equipment checklist": [
        _field("company_name", "Company Name", "text", 1),
        _field("checklist_title", "Checklist Title", "text", 2),
        _field("date", "Date", "date", 3),
        _field("department", "Department", "text", 4),
        _field("equipment_name", "Equipment Name", "text", 5),
        _field("inspection_item", "Inspection Item", "textarea", 6),
        _field("condition_status", "Condition Status", "text", 7),
        _field("responsible_person", "Responsible Person", "text", 8),
        _field("notes", "Notes", "textarea", 9, required=False),
    ],
    "process documentation": [
        _field("company_name", "Company Name", "text", 1),
        _field("process_title", "Process Title", "text", 2),
        _field("department", "Department", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("effective_date", "Effective Date", "date", 5),
        _field("process_objective", "Process Objective", "textarea", 6),
        _field("scope", "Scope", "textarea", 7),
        _field("process_steps", "Process Steps", "textarea", 8),
        _field("tools_resources", "Tools/Resources", "textarea", 9),
        _field("roles_and_responsibilities", "Roles and Responsibilities", "textarea", 10),
        _field("performance_metrics", "Performance Metrics", "textarea", 11),
        _field("risks", "Risks", "textarea", 12, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "meeting minutes": [
        _field("company_name", "Company Name", "text", 1),
        _field("meeting_title", "Meeting Title", "text", 2),
        _field("date", "Date", "date", 3),
        _field("time", "Time", "text", 4),
        _field("location", "Location", "text", 5),
        _field("meeting_facilitator", "Meeting Facilitator", "text", 6),
        _field("attendees", "Attendees", "textarea", 7),
        _field("agenda_items", "Agenda Items", "textarea", 8),
        _field("discussion_summary", "Discussion Summary", "textarea", 9),
        _field("decisions_made", "Decisions Made", "textarea", 10),
        _field("action_items", "Action Items", "textarea", 11),
        _field("responsible_person", "Responsible Person", "text", 12),
        _field("deadlines", "Deadlines", "textarea", 13),
        _field("additional_notes", "Additional Notes", "textarea", 14, required=False),
    ],
    "action plan": [
        _field("company_name", "Company Name", "text", 1),
        _field("plan_title", "Plan Title", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("date", "Date", "date", 4),
        _field("objective", "Objective", "textarea", 5),
        _field("key_initiatives", "Key Initiatives", "textarea", 6),
        _field("tasks", "Tasks", "textarea", 7),
        _field("responsible_parties", "Responsible Parties", "textarea", 8),
        _field("timeline", "Timeline", "textarea", 9),
        _field("resources_required", "Resources Required", "textarea", 10),
        _field("success_metrics", "Success Metrics", "textarea", 11),
        _field("risks", "Risks", "textarea", 12, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "operational report": [
        _field("company_name", "Company Name", "text", 1),
        _field("report_title", "Report Title", "text", 2),
        _field("reporting_period", "Reporting Period", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("department", "Department", "text", 5),
        _field("executive_summary", "Executive Summary", "textarea", 6),
        _field("key_metrics", "Key Metrics", "textarea", 7),
        _field("performance_analysis", "Performance Analysis", "textarea", 8),
        _field("challenges", "Challenges", "textarea", 9),
        _field("action_items", "Action Items", "textarea", 10),
        _field("recommendations", "Recommendations", "textarea", 11),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "project brief": [
        _field("company_name", "Company Name", "text", 1),
        _field("project_name", "Project Name", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("date", "Date", "date", 4),
        _field("project_objective", "Project Objective", "textarea", 5),
        _field("background", "Background", "textarea", 6),
        _field("scope", "Scope", "textarea", 7),
        _field("key_deliverables", "Key Deliverables", "textarea", 8),
        _field("stakeholders", "Stakeholders", "textarea", 9),
        _field("timeline", "Timeline", "textarea", 10),
        _field("success_criteria", "Success Criteria", "textarea", 11),
        _field("risks", "Risks", "textarea", 12, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
    "work log": [
        _field("company_name", "Company Name", "text", 1),
        _field("employee_name", "Employee Name", "text", 2),
        _field("department", "Department", "text", 3),
        _field("date", "Date", "date", 4),
        _field("task_description", "Task Description", "textarea", 5),
        _field("hours_worked", "Hours Worked", "number", 6),
        _field("start_time", "Start Time", "text", 7),
        _field("end_time", "End Time", "text", 8),
        _field("status", "Status", "text", 9),
        _field("supervisor", "Supervisor", "text", 10),
        _field("notes", "Notes", "textarea", 11, required=False),
    ],
    "task assignment sheet": [
        _field("company_name", "Company Name", "text", 1),
        _field("assignment_title", "Assignment Title", "text", 2),
        _field("assigned_by", "Assigned By", "text", 3),
        _field("date", "Date", "date", 4),
        _field("department", "Department", "text", 5),
        _field("task_description", "Task Description", "textarea", 6),
        _field("assigned_to", "Assigned To", "text", 7),
        _field("priority_level", "Priority Level", "text", 8),
        _field("deadline", "Deadline", "date", 9),
        _field("status", "Status", "text", 10),
        _field("notes", "Notes", "textarea", 11, required=False),
    ],
    "risk assessment": [
        _field("company_name", "Company Name", "text", 1),
        _field("assessment_title", "Assessment Title", "text", 2),
        _field("department", "Department", "text", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("assessment_date", "Assessment Date", "date", 5),
        _field("risk_overview", "Risk Overview", "textarea", 6),
        _field("identified_risks", "Identified Risks", "textarea", 7),
        _field("risk_impact", "Risk Impact", "textarea", 8),
        _field("risk_likelihood", "Risk Likelihood", "textarea", 9),
        _field("risk_mitigation_strategies", "Risk Mitigation Strategies", "textarea", 10),
        _field("risk_owner", "Risk Owner", "text", 11),
        _field("monitoring_plan", "Monitoring Plan", "textarea", 12),
        _field("additional_notes", "Additional Notes", "textarea", 13, required=False),
    ],
}


BUSINESS_OPERATION_TEMPLATES = {
    "internal memo": """[Company Name]\n\nINTERNAL MEMORANDUM\n\nDate: [Date]\nFrom: [From]\nTo: [To]\n\nSubject: [Subject]\n\n---\n\nPURPOSE\n\nThe purpose of this memorandum is to:\n\n[Purpose]\n\n---\n\nKEY MESSAGE\n\n[Key Message]\n\n---\n\nACTION REQUIRED\n\n[Action Required]\n\nDeadline: [Deadline]\n\n---\n\nADDITIONAL NOTES\n\n[Additional Notes]\n\n---\n\nThis Internal Memorandum serves as an official communication of record.""",
    "company policy notice": """[Company Name]\n\nCOMPANY POLICY NOTICE: [Policy Title]\n\nEffective Date: [Effective Date]\nDepartment: [Department]\n\n---\n\nPURPOSE\n\nThis Policy Notice is established to define and enforce standardized procedures related to:\n\n[Policy Overview]\n\n---\n\nPOLICY DETAILS\n\n[Policy Details]\n\n---\n\nROLES & RESPONSIBILITIES\n\n[Responsibilities]\n\n---\n\nCOMPLIANCE & MONITORING\n\n[Compliance Requirements]\n\n---\n\nENFORCEMENT & CONSEQUENCES\n\n[Consequences]\n\n---\n\nADDITIONAL NOTES\n\n[Additional Notes]\n\n---\n\nThis Policy Notice serves as an official directive of [Company Name].""",
    "sop summary": """[Company Name]\n\nSTANDARD OPERATING PROCEDURE (SOP) SUMMARY: [Procedure Title]\n\nDepartment: [Department]\nEffective Date: [Effective Date]\nPrepared By: [Prepared By]\n\n---\n\nPURPOSE\n\nThis SOP is established to:\n\n[Purpose]\n\n---\n\nSCOPE\n\n[Scope]\n\n---\n\nKEY PROCEDURAL STEPS\n\n[Key Steps]\n\n---\n\nROLES & RESPONSIBILITIES\n\n[Roles and Responsibilities]\n\n---\n\nCOMPLIANCE & CONTROL\n\n[Compliance Requirements]\n\n---\n\nADDITIONAL NOTES\n\n[Additional Notes]\n\n---\n\nThis SOP Summary serves as an official operational guideline.""",
    "incident report": """[Company Name]\n\nINCIDENT REPORT\n\nReport Date: [Report Date]\nIncident Date: [Incident Date]\nTime: [Incident Time]\nLocation: [Location]\n\nReported By: [Reported By]\nIndividuals Involved: [Individuals Involved]\n\n---\n\nPURPOSE\n\nThis Incident Report is established to formally document and address an incident that has occurred within Company operations.\n\n---\n\nINCIDENT DESCRIPTION\n\n[Incident Description]\n\n---\n\nIMMEDIATE RESPONSE & ACTIONS TAKEN\n\n[Immediate Actions Taken]\n\n---\n\nROOT CAUSE ANALYSIS\n\n[Root Cause]\n\n---\n\nCORRECTIVE & PREVENTIVE ACTIONS\n\n[Corrective Actions]\n\n---\n\nSTATUS & RESOLUTION\n\n[Status]\n\n---\n\nADDITIONAL NOTES\n\n[Additional Notes]\n\n---\n\nFINAL REVIEW & AUTHORIZATION\n\nPrepared By: ___________________________   Date: __________\nReviewed By: ___________________________   Date: __________\nAuthorized Signature: ___________________________   Date: __________\n\n---\n\nThis Incident Report serves as an official Company record.""",
    "equipment checklist": """[Company Name]\n\nEQUIPMENT CHECKLIST: [Checklist Title]\n\nDate: [Date]\nDepartment: [Department]\n\n---\n\nINSPECTION OVERVIEW\n\nEquipment Name: [Equipment Name]\nInspection Item: [Inspection Item]\nCondition Status: [Condition Status]\nResponsible Person: [Responsible Person]\nNotes: [Notes]\n\n---\n\nFINAL VERIFICATION\n\nCompletion of this checklist confirms that all required inspections have been performed and documented in accordance with Company standards.""",
    "process documentation": """[Company Name]\n\nPROCESS DOCUMENTATION: [Process Title]\n\nDepartment: [Department]\nPrepared By: [Prepared By]\nEffective Date: [Effective Date]\n\n---\n\nPROCESS OBJECTIVE\n\n[Process Objective]\n\n---\n\nSCOPE\n\n[Scope]\n\n---\n\nPROCESS WORKFLOW\n\n[Process Steps]\n\n---\n\nTOOLS AND RESOURCES\n\n[Tools/Resources]\n\n---\n\nROLES AND RESPONSIBILITIES\n\n[Roles and Responsibilities]\n\n---\n\nPERFORMANCE METRICS\n\n[Performance Metrics]\n\n---\n\nRISKS\n\n[Risks]\n\n---\n\nADDITIONAL NOTES\n\n[Additional Notes]""",
    "meeting minutes": """[Company Name]\n\nMEETING MINUTES: [Meeting Title]\n\nDate: [Date]\nTime: [Time]\nLocation: [Location]\n\nFacilitator: [Meeting Facilitator]\nAttendees: [Attendees]\n\n---\n\nAGENDA OVERVIEW\n\n[Agenda Items]\n\n---\n\nDISCUSSION SUMMARY\n\n[Discussion Summary]\n\n---\n\nDECISIONS & OUTCOMES\n\n[Decisions Made]\n\n---\n\nACTION ITEMS & ASSIGNMENTS\n\nAction Item | Responsible Person | Deadline\n[Action Items] | [Responsible Person] | [Deadlines]\n\n---\n\nADDITIONAL NOTES\n\n[Additional Notes]\n\n---\n\nThese Meeting Minutes serve as the official record of the meeting.""",
    "action plan": """[Company Name]\n\nACTION PLAN: [Plan Title]\n\nPrepared By: [Prepared By]\nDate: [Date]\n\n---\n\nOBJECTIVE\n\n[Objective]\n\n---\n\nKEY INITIATIVES\n\n[Key Initiatives]\n\n---\n\nTASK BREAKDOWN\n\nTask | Responsible Party | Timeline | Resources\n[Tasks] | [Responsible Parties] | [Timeline] | [Resources Required]\n\n---\n\nSUCCESS METRICS\n\n[Success Metrics]\n\n---\n\nRISKS\n\n[Risks]\n\n---\n\nADDITIONAL NOTES\n\n[Additional Notes]""",
    "operational report": """[Company Name]\n\nOPERATIONAL REPORT: [Report Title]\n\nReporting Period: [Reporting Period]\nPrepared By: [Prepared By]\nDepartment: [Department]\n\n---\n\nEXECUTIVE SUMMARY\n\n[Executive Summary]\n\n---\n\nKEY METRICS\n\n[Key Metrics]\n\n---\n\nPERFORMANCE ANALYSIS\n\n[Performance Analysis]\n\n---\n\nCHALLENGES\n\n[Challenges]\n\n---\n\nACTION ITEMS\n\n[Action Items]\n\n---\n\nRECOMMENDATIONS\n\n[Recommendations]\n\n---\n\nADDITIONAL NOTES\n\n[Additional Notes]""",
    "project brief": """[Company Name]\n\nPROJECT BRIEF: [Project Name]\n\nPrepared By: [Prepared By]\nDate: [Date]\n\n---\n\nPROJECT OBJECTIVE\n\n[Project Objective]\n\n---\n\nBACKGROUND\n\n[Background]\n\n---\n\nSCOPE\n\n[Scope]\n\n---\n\nKEY DELIVERABLES\n\n[Key Deliverables]\n\n---\n\nSTAKEHOLDERS\n\n[Stakeholders]\n\n---\n\nPROJECT TIMELINE\n\n[Timeline]\n\n---\n\nSUCCESS CRITERIA\n\n[Success Criteria]\n\n---\n\nRISKS\n\n[Risks]\n\n---\n\nADDITIONAL NOTES\n\n[Additional Notes]""",
    "work log": """[Company Name]\n\nWORK LOG\n\nEmployee Name: [Employee Name]\nDepartment: [Department]\nDate: [Date]\n\n---\n\nWORK SUMMARY\n\nTask Description | Start Time | End Time | Hours Worked | Status\n[Task Description] | [Start Time] | [End Time] | [Hours Worked] | [Status]\n\n---\n\nSUPERVISOR REVIEW & VALIDATION\n\nSupervisor: [Supervisor]\n\n---\n\nNOTES\n\n[Notes]\n\n---\n\nEmployee Signature: ___________________________   Date: __________\nSupervisor Signature: ___________________________   Date: __________\n\n---\n\nThis Work Log serves as an official Company document.""",
    "task assignment sheet": """[Company Name]\n\nTASK ASSIGNMENT SHEET: [Assignment Title]\n\nAssigned By: [Assigned By]\nDate: [Date]\nDepartment: [Department]\n\n---\n\nASSIGNMENT OVERVIEW\n\nTask Description | Assigned To | Priority Level | Deadline | Status\n[Task Description] | [Assigned To] | [Priority Level] | [Deadline] | [Status]\n\n---\n\nACCOUNTABILITY & RESPONSIBILITY\n\n[Notes]\n\n---\n\nThis Task Assignment Sheet serves as an official record of assigned responsibilities.""",
    "risk assessment": """[Company Name]\n\nRISK ASSESSMENT: [Assessment Title]\n\nDepartment: [Department]\nPrepared By: [Prepared By]\nAssessment Date: [Assessment Date]\n\n---\n\nRISK OVERVIEW\n\n[Risk Overview]\n\n---\n\nIDENTIFIED RISKS\n\n[Identified Risks]\n\n---\n\nRISK ANALYSIS\n\nImpact: [Risk Impact]\nLikelihood: [Risk Likelihood]\n\n---\n\nMITIGATION STRATEGIES\n\n[Risk Mitigation Strategies]\n\n---\n\nRISK OWNERSHIP\n\n[Risk Owner]\n\n---\n\nMONITORING AND REVIEW\n\n[Monitoring Plan]\n\n---\n\nADDITIONAL NOTES\n\n[Additional Notes]""",
}


BUSINESS_OPERATION_BASE_CONTENT = {
    "internal memo": {"document_number": 1, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False}, "signature_configuration": {"required": False}, "output_logic": {"include_action_required_only_if_provided": True, "include_deadline_only_if_provided": True, "include_additional_notes_only_if_provided": True}},
    "company policy notice": {"document_number": 2, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False}, "signature_configuration": {"required": False}, "output_logic": {"include_additional_notes_only_if_provided": True}},
    "sop summary": {"document_number": 3, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False}, "signature_configuration": {"required": False}, "output_logic": {"include_additional_notes_only_if_provided": True}},
    "incident report": {"document_number": 4, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True}, "signature_configuration": {"prepared_by_signature": {"required": True, "fields": ["name", "date"]}, "reviewed_by_signature": {"required": True, "fields": ["name", "date"]}, "authorized_signature": {"required": True, "fields": ["name", "date"]}}, "output_logic": {"include_root_cause_only_if_provided": True, "include_additional_notes_only_if_provided": True}},
    "equipment checklist": {"document_number": 5, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False}, "signature_configuration": {"required": False}, "output_logic": {"include_notes_only_if_provided": True}},
    "process documentation": {"document_number": 6, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False}, "signature_configuration": {"required": False}, "output_logic": {"include_risks_only_if_provided": True, "include_additional_notes_only_if_provided": True}},
    "meeting minutes": {"document_number": 7, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False}, "signature_configuration": {"required": False}, "output_logic": {"include_additional_notes_only_if_provided": True}},
    "action plan": {"document_number": 8, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False}, "signature_configuration": {"required": False}, "output_logic": {"include_risks_only_if_provided": True, "include_additional_notes_only_if_provided": True}},
    "operational report": {"document_number": 9, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False}, "signature_configuration": {"required": False}, "output_logic": {"include_additional_notes_only_if_provided": True}},
    "project brief": {"document_number": 10, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False}, "signature_configuration": {"required": False}, "output_logic": {"include_risks_only_if_provided": True, "include_additional_notes_only_if_provided": True}},
    "work log": {"document_number": 11, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True}, "signature_configuration": {"employee_signature": {"required": True, "fields": ["name", "date"]}, "supervisor_signature": {"required": True, "fields": ["name", "date"]}}, "output_logic": {"include_notes_only_if_provided": True}},
    "task assignment sheet": {"document_number": 12, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False}, "signature_configuration": {"required": False}, "output_logic": {"include_notes_only_if_provided": True}},
    "risk assessment": {"document_number": 13, "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False}, "signature_configuration": {"required": False}, "output_logic": {"include_additional_notes_only_if_provided": True}},
}


ADMIN_OFFICE_SCHEMAS = {
    "office policy": [
        _field("company_name", "Company Name", "text", 1),
        _field("policy_title", "Policy Title", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("prepared_by", "Prepared By", "text", 4),
        _field("purpose", "Purpose", "textarea", 5),
        _field("policy_details", "Policy Details", "textarea", 6),
        _field("employee_responsibilities", "Employee Responsibilities", "textarea", 7),
        _field("compliance_requirements", "Compliance Requirements", "textarea", 8),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "visitor log": [
        _field("company_name", "Company Name", "text", 1),
        _field("log_date", "Log Date", "date", 2),
        _field("visitor_name", "Visitor Name", "text", 3),
        _field("company_organization", "Company/Organization", "text", 4, required=False),
        _field("purpose_of_visit", "Purpose of Visit", "textarea", 5),
        _field("person_visiting", "Person Visiting", "text", 6),
        _field("check_in_time", "Check-In Time", "text", 7),
        _field("check_out_time", "Check-Out Time", "text", 8, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "office supply request": [
        _field("company_name", "Company Name", "text", 1),
        _field("request_date", "Request Date", "date", 2),
        _field("employee_name", "Employee Name", "text", 3),
        _field("department", "Department", "text", 4),
        _field("items_requested", "Items Requested", "textarea", 5),
        _field("quantity", "Quantity", "text", 6),
        _field("business_justification", "Business Justification", "textarea", 7),
        _field("approval_status", "Approval Status", "text", 8, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "expense claim": [
        _field("company_name", "Company Name", "text", 1),
        _field("employee_name", "Employee Name", "text", 2),
        _field("department", "Department", "text", 3),
        _field("submission_date", "Submission Date", "date", 4),
        _field("expense_date", "Expense Date", "date", 5),
        _field("expense_description", "Expense Description", "textarea", 6),
        _field("amount", "Amount", "currency", 7),
        _field("payment_method", "Payment Method", "text", 8, required=False),
        _field("supporting_details", "Supporting Details", "textarea", 9),
        _field("approval_status", "Approval Status", "text", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "meeting room booking": [
        _field("company_name", "Company Name", "text", 1),
        _field("booking_date", "Booking Date", "date", 2),
        _field("requested_by", "Requested By", "text", 3),
        _field("department", "Department", "text", 4),
        _field("meeting_title", "Meeting Title", "text", 5),
        _field("meeting_date", "Meeting Date", "date", 6),
        _field("start_time", "Start Time", "text", 7),
        _field("end_time", "End Time", "text", 8),
        _field("number_of_attendees", "Number of Attendees", "number", 9),
        _field("room_requested", "Room Requested", "text", 10, required=False),
        _field("special_requirements", "Special Requirements", "textarea", 11, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 12, required=False),
    ],
    "staff announcement": [
        _field("company_name", "Company Name", "text", 1),
        _field("announcement_title", "Announcement Title", "text", 2),
        _field("announcement_date", "Announcement Date", "date", 3),
        _field("issued_by", "Issued By", "text", 4),
        _field("department", "Department", "text", 5, required=False),
        _field("announcement_details", "Announcement Details", "textarea", 6),
        _field("effective_date", "Effective Date", "date", 7, required=False),
        _field("action_required", "Action Required", "textarea", 8, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "internal notice": [
        _field("company_name", "Company Name", "text", 1),
        _field("notice_title", "Notice Title", "text", 2),
        _field("issue_date", "Issue Date", "date", 3),
        _field("issued_by", "Issued By", "text", 4),
        _field("department", "Department", "text", 5, required=False),
        _field("notice_details", "Notice Details", "textarea", 6),
        _field("effective_date", "Effective Date", "date", 7, required=False),
        _field("required_actions", "Required Actions", "textarea", 8, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 9, required=False),
    ],
    "filing guide": [
        _field("company_name", "Company Name", "text", 1),
        _field("guide_title", "Guide Title", "text", 2),
        _field("prepared_by", "Prepared By", "text", 3),
        _field("issue_date", "Issue Date", "date", 4),
        _field("purpose", "Purpose", "textarea", 5),
        _field("filing_procedures", "Filing Procedures", "textarea", 6),
        _field("document_categories", "Document Categories", "textarea", 7),
        _field("storage_location", "Storage Location", "textarea", 8),
        _field("access_permissions", "Access Permissions", "textarea", 9, required=False),
        _field("compliance_requirements", "Compliance Requirements", "textarea", 10),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "correspondence log": [
        _field("company_name", "Company Name", "text", 1),
        _field("log_date", "Log Date", "date", 2),
        _field("recorded_by", "Recorded By", "text", 3),
        _field("correspondence_type", "Correspondence Type", "text", 4),
        _field("sender_recipient_name", "Sender/Recipient Name", "text", 5),
        _field("department", "Department", "text", 6, required=False),
        _field("subject", "Subject", "text", 7),
        _field("summary_of_communication", "Summary of Communication", "textarea", 8),
        _field("action_required", "Action Required", "textarea", 9, required=False),
        _field("follow_up_date", "Follow-Up Date", "date", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
    "delegation of duties": [
        _field("company_name", "Company Name", "text", 1),
        _field("delegation_title", "Delegation Title", "text", 2),
        _field("effective_date", "Effective Date", "date", 3),
        _field("delegated_by", "Delegated By", "text", 4),
        _field("delegated_to", "Delegated To", "text", 5),
        _field("department", "Department", "text", 6, required=False),
        _field("duties_assigned", "Duties Assigned", "textarea", 7),
        _field("authority_level", "Authority Level", "textarea", 8),
        _field("duration", "Duration", "text", 9),
        _field("conditions_limitations", "Conditions & Limitations", "textarea", 10, required=False),
        _field("additional_notes", "Additional Notes", "textarea", 11, required=False),
    ],
}


ADMIN_OFFICE_TEMPLATES = {
    "office policy": """OFFICE POLICY\n\nThis Office Policy (\"Policy\") is issued by [Company Name] and is effective as of [Effective Date].\n\nPOLICY TITLE:\n[Policy Title]\n\nPREPARED BY:\n[Prepared By]\n\n---\n\nPURPOSE\n[Purpose]\n\n---\n\nPOLICY DETAILS\n[Policy Details]\n\n---\n\nEMPLOYEE RESPONSIBILITIES\n[Employee Responsibilities]\n\n---\n\nCOMPLIANCE\n[Compliance Requirements]\n\n---\n\nADDITIONAL NOTES\n[Additional Notes]\n\n---\n\nACKNOWLEDGMENT (Optional):\nEmployee Name: _________________________\nSignature: _________________________\nDate: ___________""",
    "visitor log": """[Company Name]\n\nVISITOR LOG\n\nLog Date: [Log Date]\n\n---\n\nVisitor Name: [Visitor Name]\nCompany / Organization: [Company/Organization]\nPurpose of Visit: [Purpose of Visit]\nPerson Visiting: [Person Visiting]\nCheck-In Time: [Check-In Time]\nCheck-Out Time: [Check-Out Time]\n\n---\n\nADDITIONAL NOTES\n[Additional Notes]\n\n---\n\nVISITOR ACKNOWLEDGMENT (OPTIONAL)\nVisitor Signature: _________________________\nTime: _________________________""",
    "office supply request": """[Company Name]\n\nOFFICE SUPPLY REQUEST\n\nRequest Date: [Request Date]\nEmployee Name: [Employee Name]\nDepartment: [Department]\n\n---\n\nITEMS REQUESTED\n[Items Requested]\n\nQUANTITY\n[Quantity]\n\nBUSINESS JUSTIFICATION\n[Business Justification]\n\nAPPROVAL STATUS\n[Approval Status]\n\nADDITIONAL NOTES\n[Additional Notes]\n\n---\n\nMANAGER APPROVAL (OPTIONAL)\nManager Name: _________________________\nSignature: _____________________________\nDate: ________________________________""",
    "expense claim": """[Company Name]\n\nEXPENSE CLAIM\n\nSubmission Date: [Submission Date]\nEmployee Name: [Employee Name]\nDepartment: [Department]\n\n---\n\nExpense Date: [Expense Date]\nDescription: [Expense Description]\nAmount: [Amount]\nPayment Method: [Payment Method]\nSupporting Details: [Supporting Details]\nApproval Status: [Approval Status]\nAdditional Notes: [Additional Notes]\n\n---\n\nMANAGER APPROVAL\nManager Name: _________________________\nSignature: _____________________________\nDate: ________________________________""",
    "meeting room booking": """[Company Name]\n\nMEETING ROOM BOOKING\n\nBooking Date: [Booking Date]\nRequested By: [Requested By]\nDepartment: [Department]\nMeeting Title: [Meeting Title]\nMeeting Date: [Meeting Date]\nStart Time: [Start Time]\nEnd Time: [End Time]\nNumber of Attendees: [Number of Attendees]\nRoom Requested: [Room Requested]\nSpecial Requirements: [Special Requirements]\nAdditional Notes: [Additional Notes]""",
    "staff announcement": """[Company Name]\n\nSTAFF ANNOUNCEMENT: [Announcement Title]\n\nAnnouncement Date: [Announcement Date]\nIssued By: [Issued By]\nDepartment: [Department]\n\n---\n\nANNOUNCEMENT DETAILS\n[Announcement Details]\n\nEffective Date: [Effective Date]\nAction Required: [Action Required]\nAdditional Notes: [Additional Notes]""",
    "internal notice": """[Company Name]\n\nINTERNAL NOTICE: [Notice Title]\n\nIssue Date: [Issue Date]\nIssued By: [Issued By]\nDepartment: [Department]\n\n---\n\nNOTICE DETAILS\n[Notice Details]\n\nEffective Date: [Effective Date]\nRequired Actions: [Required Actions]\nAdditional Notes: [Additional Notes]""",
    "filing guide": """FILING GUIDE\n\nThis Filing Guide (\"Guide\") is issued by [Company Name] on [Issue Date].\n\nGUIDE TITLE:\n[Guide Title]\nPREPARED BY:\n[Prepared By]\n\n---\n\nPURPOSE\n[Purpose]\n\nFILING PROCEDURES\n[Filing Procedures]\n\nDOCUMENT CATEGORIES\n[Document Categories]\n\nSTORAGE LOCATION\n[Storage Location]\n\nACCESS PERMISSIONS\n[Access Permissions]\n\nCOMPLIANCE REQUIREMENTS\n[Compliance Requirements]\n\nADDITIONAL NOTES\n[Additional Notes]""",
    "correspondence log": """[Company Name]\n\nCORRESPONDENCE LOG\n\nLog Date: [Log Date]\nRecorded By: [Recorded By]\nCorrespondence Type: [Correspondence Type]\nSender / Recipient: [Sender/Recipient Name]\nDepartment: [Department]\nSubject: [Subject]\nSummary of Communication: [Summary of Communication]\nAction Required: [Action Required]\nFollow-Up Date: [Follow-Up Date]\nAdditional Notes: [Additional Notes]""",
    "delegation of duties": """DELEGATION OF DUTIES\n\nThis Delegation of Duties (\"Delegation\") is issued by [Company Name] and becomes effective on [Effective Date].\n\nDELEGATION TITLE:\n[Delegation Title]\n\nDelegated By: [Delegated By]\nDelegated To: [Delegated To]\nDepartment: [Department]\nDuties Assigned: [Duties Assigned]\nAuthority Level: [Authority Level]\nDuration: [Duration]\nConditions & Limitations: [Conditions & Limitations]\nAdditional Notes: [Additional Notes]\n\nACKNOWLEDGED AND ACCEPTED:\n[Delegated By] Signature: _________________________ Date: ___________\n[Delegated To] Signature: _________________________ Date: ___________""",
}


ADMIN_OFFICE_BASE_CONTENT = {
    "office policy": {
        "document_number": 1,
        "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
        "signature_configuration": {"employee_acknowledgment": {"required": False, "fields": ["name", "date"]}},
        "output_logic": {"include_optional_sections_only_if_provided": True},
    },
    "visitor log": {
        "document_number": 2,
        "actions": {"download_pdf": True, "send_via_email": False, "send_for_signature": False},
        "signature_configuration": {"visitor_signature": {"required": False, "fields": ["name", "time"]}},
        "output_logic": {"include_optional_fields_only_if_provided": True},
    },
    "office supply request": {
        "document_number": 3,
        "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
        "signature_configuration": {"manager_approval": {"required": False, "fields": ["name", "date"]}},
        "output_logic": {"include_optional_fields_only_if_provided": True},
    },
    "expense claim": {
        "document_number": 4,
        "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
        "signature_configuration": {"manager_approval": {"required": True, "fields": ["name", "date"]}},
        "output_logic": {"include_optional_fields_only_if_provided": True},
    },
    "meeting room booking": {
        "document_number": 5,
        "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
        "signature_configuration": {"required": False},
        "output_logic": {"include_optional_fields_only_if_provided": True},
    },
    "staff announcement": {
        "document_number": 6,
        "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
        "signature_configuration": {"required": False},
        "output_logic": {"include_optional_fields_only_if_provided": True},
    },
    "internal notice": {
        "document_number": 7,
        "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
        "signature_configuration": {"required": False},
        "output_logic": {"include_optional_fields_only_if_provided": True},
    },
    "filing guide": {
        "document_number": 8,
        "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
        "signature_configuration": {"required": False},
        "output_logic": {"include_optional_fields_only_if_provided": True},
    },
    "correspondence log": {
        "document_number": 9,
        "actions": {"download_pdf": True, "send_via_email": False, "send_for_signature": False},
        "signature_configuration": {"required": False},
        "output_logic": {"include_optional_fields_only_if_provided": True},
    },
    "delegation of duties": {
        "document_number": 10,
        "actions": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
        "signature_configuration": {
            "delegator_signature": {"required": True, "fields": ["name", "date"]},
            "delegate_signature": {"required": True, "fields": ["name", "date"]},
        },
        "output_logic": {"include_optional_fields_only_if_provided": True},
    },
}


COMPLIANCE_TEMPLATES = {
    "compliance checklist": """COMPLIANCE CHECKLIST\n\nThis Compliance Checklist (\"Checklist\") is prepared for [Company Name] within the [Department] for the period of [Review Period].\n\n1. COMPLIANCE AREA\n[Compliance Area]\n\n2. RESPONSIBLE PERSON\n[Responsible Person]\n\n3. CHECKLIST OVERVIEW\n[Checklist Items]\n\n4. STATUS SUMMARY\n[Status]\n\n5. CORRECTIVE ACTIONS\n- Identify the issue and root cause\n- Assign responsibility for resolution\n- Set deadlines for correction\n- Monitor progress until full compliance is achieved\n\n6. REVIEW DATE\n[Review Date]\n\n7. AUDIT AND VERIFICATION\nThis Checklist may be used for internal audits, external reviews, or compliance verification processes.\n\n8. ADDITIONAL NOTES\n[Additional Notes]""",
    "audit trail": """AUDIT TRAIL\n\nThis Audit Trail (\"Audit Record\") is maintained for [Company Name] covering [Process/System Name] during [Audit Period].\n\n1. RESPONSIBLE DEPARTMENT\n[Responsible Department]\n\n2. AUDIT RECORD OVERVIEW\n[Activity Description]\n\n3. ACCOUNTABILITY\n[User/Responsible Person]\n\n4. STATUS\n[Status]\n\n5. DATA INTEGRITY AND SECURITY\nAll audit records must be securely stored and protected from unauthorized access, modification, or deletion.\n\n6. REVIEW AND VERIFICATION\nAudit records should be reviewed periodically to ensure accuracy and compliance.\n\n7. ADDITIONAL NOTES\n[Additional Notes]""",
    "data retention policy": """DATA RETENTION POLICY\n\nThis Data Retention Policy (\"Policy\") is established by [Company Name] and is effective as of [Policy Effective Date].\n\n1. POLICY PURPOSE\nThis Policy defines how data is collected, retained, stored, accessed, and disposed of throughout its lifecycle.\n\n2. DATA TYPES\n[Data Types]\n\n3. RETENTION PERIODS\n[Retention Periods]\n\n4. STORAGE METHODS\n[Storage Methods]\n\n5. ACCESS CONTROL\n[Access Control]\n\n6. DATA DISPOSAL METHODS\n[Data Disposal Methods]\n\n7. RESPONSIBLE DEPARTMENT\n[Responsible Department]\n\n8. COMPLIANCE STANDARDS\n[Compliance Standards]\n\n9. POLICY REVIEW AND UPDATES\nThis Policy must be reviewed periodically and updated as necessary.\n\n10. ADDITIONAL NOTES\n[Additional Notes]""",
    "gdpr policy": """GDPR POLICY\n\nThis GDPR Policy (\"Policy\") is established by [Company Name] and is effective as of [Policy Effective Date].\n\n1. DATA CONTROLLER\n[Data Controller Name]\n\n2. PERSONAL DATA COLLECTION\n[Types of Personal Data Collected]\n\n3. PURPOSE OF PROCESSING\n[Purpose of Data Processing]\n\n4. LEGAL BASIS\n[Legal Basis for Processing]\n\n5. DATA SUBJECT RIGHTS\n[Data Subject Rights]\n\n6. DATA RETENTION\n[Data Retention Period]\n\n7. DATA PROTECTION MEASURES\n[Data Protection Measures]\n\n8. THIRD-PARTY SHARING\n[Third-Party Sharing]\n\n9. INTERNATIONAL DATA TRANSFERS\nAppropriate safeguards will be implemented for transfers outside applicable jurisdictions.\n\n10. DATA BREACH RESPONSE\nSteps will be taken to identify, contain, and notify where required.\n\n11. CONTACT INFORMATION\n[Contact Information]\n\n12. ADDITIONAL NOTES\n[Additional Notes]""",
    "regulatory filing": """REGULATORY FILING\n\nThis Regulatory Filing (\"Filing\") is prepared by [Company Name] for submission to [Regulatory Authority].\n\nSUBJECT: [Filing Title]\n\n1. FILING OVERVIEW\n[Description of Filing]\n\n2. KEY DISCLOSURES\n[Key Disclosures]\n\n3. SUPPORTING DOCUMENTATION\n[Supporting Documents]\n\n4. RESPONSIBLE OFFICER\n[Responsible Officer]\n\n5. CERTIFICATION AND ATTESTATION\nThe Responsible Officer affirms the filing is true and complete.\n\n6. SUBMISSION STATUS\n[Submission Status]\n\n7. RECORD KEEPING\nA copy of this Filing and all supporting documentation must be retained.\n\n8. ADDITIONAL NOTES\n[Additional Notes]""",
    "risk register": """RISK REGISTER\n\nThis Risk Register (\"Register\") is prepared for [Company Name] within the [Department] for [Reporting Period].\n\n1. RISK MANAGEMENT OVERVIEW\nThis Register provides a structured approach to risk management.\n\n2. RISK CATEGORIES\n[Risk Categories]\n\n3. RISK REGISTER TABLE\n[Identified Risks]\n\n4. RISK IMPACT\n[Risk Impact]\n\n5. LIKELIHOOD\n[Likelihood]\n\n6. MITIGATION PLAN\n[Mitigation Plan]\n\n7. ACCOUNTABILITY\n[Risk Owner]\n\n8. STATUS\n[Status]\n\n9. RISK REVIEW AND ESCALATION\nHigh-risk items must be escalated to senior management.\n\n10. ADDITIONAL NOTES\n[Additional Notes]""",
    "incident form": """INCIDENT REPORT\n\nThis Incident Form (\"Report\") is completed for [Company Name] regarding [Incident Title].\n\n1. INCIDENT DETAILS\nDate: [Date of Incident]\nTime: [Time of Incident]\nLocation: [Location]\n\n2. REPORTED BY\n[Reported By]\n\n3. INCIDENT DESCRIPTION\n[Incident Description]\n\n4. INDIVIDUALS INVOLVED\n[Individuals Involved]\n\n5. IMMEDIATE ACTION TAKEN\n[Immediate Action Taken]\n\n6. SEVERITY LEVEL\n[Severity Level]\n\n7. FOLLOW-UP ACTIONS\n[Follow-Up Actions]\n\n8. INVESTIGATION AND RESOLUTION\nFindings and resolutions should be documented and reviewed.\n\n9. RECORD KEEPING AND CONFIDENTIALITY\nThis Report must be securely stored and handled according to company policies.\n\n10. ADDITIONAL NOTES\n[Additional Notes]""",
    "ethics policy": """ETHICS POLICY\n\nThis Ethics Policy (\"Policy\") is established by [Company Name] and is effective as of [Policy Effective Date].\n\n1. CORE VALUES\n[Core Values]\n\n2. CODE OF CONDUCT\n[Code of Conduct]\n\n3. CONFLICT OF INTEREST\n[Conflict of Interest Policy]\n\n4. REPORTING VIOLATIONS\n[Reporting Violations]\n\n5. DISCIPLINARY ACTIONS\n[Disciplinary Actions]\n\n6. COMPLIANCE RESPONSIBILITY\n[Compliance Responsibility]\n\n7. POLICY ENFORCEMENT AND REVIEW\nThis Policy will be enforced by designated personnel and reviewed periodically.\n\n8. ADDITIONAL NOTES\n[Additional Notes]""",
    "records index": """RECORDS INDEX\n\nThis Records Index (\"Index\") is maintained by [Company Name] for the [Department] as of [Index Date].\n\n1. RECORD MANAGEMENT OVERVIEW\nThis Index provides a structured listing of all records maintained within the organization.\n\n2. RECORD CATEGORIES\n[Record Categories]\n\n3. RECORDS INDEX TABLE\n[Record Name]\n\n4. STORAGE LOCATION\n[Storage Location]\n\n5. RETENTION POLICY\n[Retention Period]\n\n6. RESPONSIBILITY\n[Responsible Person]\n\n7. STATUS\n[Status]\n\n8. RECORD REVIEW AND AUDIT\nRecords must be reviewed periodically to ensure accuracy and compliance.\n\n9. ADDITIONAL NOTES\n[Additional Notes]""",
    "compliance report": """COMPLIANCE REPORT\n\nThis Compliance Report (\"Report\") is prepared for [Company Name] within the [Department] covering [Reporting Period].\n\n1. COMPLIANCE OVERVIEW\nThis Report provides a comprehensive review of compliance performance.\n\n2. COMPLIANCE AREAS\n[Compliance Areas]\n\n3. FINDINGS\n[Findings]\n\n4. VIOLATIONS IDENTIFIED\n[Violations Identified]\n\n5. CORRECTIVE ACTIONS\n[Corrective Actions]\n\n6. RESPONSIBILITY\n[Responsible Parties]\n\n7. STATUS\n[Status]\n\n8. REVIEW DATE\n[Review Date]\n\n9. CONTINUOUS IMPROVEMENT\nBased on findings and actions, ongoing improvements should be implemented.\n\n10. ADDITIONAL NOTES\n[Additional Notes]""",
}

def _base_content_for_document_type(doc_type_name, schema, category_name=None):
    name = doc_type_name.lower()
    required_fields = [field["name"] for field in schema if field.get("required")]
    optional_fields = [field["name"] for field in schema if not field.get("required")]

    if category_name == "Business Operations" and name in BUSINESS_OPERATION_BASE_CONTENT:
        base_content = {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
        }
        base_content.update(BUSINESS_OPERATION_BASE_CONTENT[name])
        return base_content

    if category_name == "Administration & Office" and name in ADMIN_OFFICE_BASE_CONTENT:
        base_content = {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
        }
        base_content.update(ADMIN_OFFICE_BASE_CONTENT[name])
        return base_content

    if category_name == "General Templates" and name in GENERAL_SCHEMAS:
        base_content = {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "output_logic": {"include_optional_sections_only_if_provided": True},
        }

        general_document_numbers = {
            "cover letter": 1,
            "meeting agenda": 2,
            "project plan": 3,
            "status report": 4,
            "checklist": 5,
            "to-do list": 6,
            "notes template": 7,
            "invoice": 8,
            "contract agreement": 9,
            "proposal": 10,
            "presentation outline": 11,
        }

        if name == "cover letter":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
                    "signature_configuration": {
                        "sender_signature": {"required": True, "fields": ["name", "date"]},
                    },
                }
            )
        elif name == "contract agreement":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
                    "signature_configuration": {
                        "company_signature": {"required": True, "fields": ["name", "date"]},
                        "client_signature": {"required": True, "fields": ["name", "date"]},
                    },
                }
            )
        elif name == "proposal":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
                    "signature_configuration": {
                        "company_signature": {"required": True, "fields": ["name", "date"]},
                        "client_signature": {"required": True, "fields": ["name", "date"]},
                    },
                }
            )

        base_content["document_number"] = general_document_numbers[name]
        return base_content

    if category_name == "Compliance & Records" and name in COMPLIANCE_SCHEMAS:
        base_content = {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "output_logic": {"include_optional_sections_only_if_provided": True},
        }

        compliance_document_numbers = {
            "compliance checklist": 1,
            "audit trail": 2,
            "data retention policy": 3,
            "gdpr policy": 4,
            "regulatory filing": 5,
            "risk register": 6,
            "incident form": 7,
            "ethics policy": 8,
            "records index": 9,
            "compliance report": 10,
        }

        if name == "risk register":
            base_content["output_logic"] = {
                "include_optional_sections_only_if_provided": True,
                "support_risk_score_guidance": True,
                "color_code_risk_score": True,
            }

        base_content["document_number"] = compliance_document_numbers[name]
        return base_content

    if category_name == "Legal Documents" and name in LEGAL_SCHEMAS:
        base_content = {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"include_optional_sections_only_if_provided": True},
        }

        legal_actions = {
            "non-disclosure agreement (freelancer nda)": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "employee non-disclosure agreement (employee nda)": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "service agreement": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "partnership agreement": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "consulting contract": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
            "terms of service": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "privacy policy": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "cease and desist letter": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "letter of intent (loi)": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "intellectual property assignment agreement": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
            "vendor contract": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
            "confidentiality agreement": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
            "independent contractor agreement": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
            "release of liability agreement": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
            "legal notice": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
        }

        base_content["actions"] = legal_actions[name]

        if name == "non-disclosure agreement (freelancer nda)":
            base_content.update({
                "signature_configuration": {
                    "disclosing_party_signature": {"required": True, "fields": ["name", "date"]},
                    "freelancer_signature": {"required": True, "fields": ["name", "date"]},
                },
                "output_logic": {"include_optional_sections_only_if_provided": True},
                "document_number": 1,
            })
        elif name == "employee non-disclosure agreement (employee nda)":
            base_content.update({
                "signature_configuration": {
                    "employer_signature": {"required": True, "fields": ["name", "date"]},
                    "employee_signature": {"required": True, "fields": ["name", "date"]},
                },
                "output_logic": {"include_optional_clauses_only_if_provided": True},
                "document_number": 2,
            })
        elif name == "service agreement":
            base_content.update({
                "signature_configuration": {
                    "company_signature": {"required": True, "fields": ["name", "date"]},
                    "client_signature": {"required": True, "fields": ["name", "date"]},
                },
                "output_logic": {"include_optional_sections_only_if_provided": True},
                "document_number": 3,
            })
        elif name == "partnership agreement":
            base_content.update({
                "signature_configuration": {
                    "all_partners_signature": {"required": True, "fields": ["name", "date"]},
                },
                "output_logic": {"support_multiple_partner_entries": True},
                "document_number": 4,
            })
        elif name == "consulting contract":
            base_content.update({
                "signature_configuration": {
                    "consultant_signature": {"required": True, "fields": ["name", "date"]},
                    "client_signature": {"required": True, "fields": ["name", "date"]},
                },
                "output_logic": {"include_optional_terms_only_if_provided": True},
                "document_number": 5,
            })
        elif name == "terms of service":
            base_content.update({
                "signature_configuration": {"required": False},
                "output_logic": {"always_display_full_structure": True},
                "document_number": 6,
            })
        elif name == "privacy policy":
            base_content.update({
                "signature_configuration": {"required": False},
                "output_logic": {"include_optional_sections_only_if_provided": True},
                "document_number": 7,
            })
        elif name == "cease and desist letter":
            base_content.update({
                "signature_configuration": {
                    "sender_signature": {"required": True, "fields": ["name", "date"]},
                },
                "output_logic": {"tone": "firm_and_direct", "include_optional_sections_only_if_provided": True},
                "document_number": 8,
            })
        elif name == "letter of intent (loi)":
            base_content.update({
                "signature_configuration": {
                    "sender_signature": {"required": True, "fields": ["name", "date"]},
                    "recipient_acknowledgment": {"required": False, "fields": ["name", "date"]},
                },
                "output_logic": {"include_optional_clauses_only_if_provided": True},
                "document_number": 9,
            })
        elif name == "intellectual property assignment agreement":
            base_content.update({
                "signature_configuration": {
                    "assignor_signature": {"required": True, "fields": ["name", "date"]},
                    "assignee_signature": {"required": True, "fields": ["name", "date"]},
                },
                "output_logic": {"include_optional_clauses_only_if_provided": True},
                "document_number": 10,
            })
        elif name == "vendor contract":
            base_content.update({
                "signature_configuration": {
                    "company_signature": {"required": True, "fields": ["name", "date"]},
                    "vendor_signature": {"required": True, "fields": ["name", "date"]},
                },
                "output_logic": {"include_optional_sections_only_if_provided": True},
                "document_number": 11,
            })
        elif name == "confidentiality agreement":
            base_content.update({
                "signature_configuration": {
                    "party_a_signature": {"required": True, "fields": ["name", "date"]},
                    "party_b_signature": {"required": True, "fields": ["name", "date"]},
                },
                "output_logic": {"include_optional_clauses_only_if_provided": True},
                "document_number": 12,
            })
        elif name == "independent contractor agreement":
            base_content.update({
                "signature_configuration": {
                    "company_signature": {"required": True, "fields": ["name", "date"]},
                    "contractor_signature": {"required": True, "fields": ["name", "date"]},
                },
                "output_logic": {"include_optional_clauses_only_if_provided": True},
                "document_number": 13,
            })
        elif name == "release of liability agreement":
            base_content.update({
                "signature_configuration": {
                    "releasing_party_signature": {"required": True, "fields": ["name", "date"]},
                },
                "output_logic": {"tone": "strong_and_clear_legal", "include_optional_sections_only_if_provided": True},
                "document_number": 14,
            })
        elif name == "legal notice":
            base_content.update({
                "signature_configuration": {"required": False},
                "output_logic": {"tone": "formal_and_clear", "include_optional_sections_only_if_provided": True},
                "document_number": 15,
            })

        return base_content

    if category_name == "Marketing & Communications" and name in MARKETING_SCHEMAS:
        base_content = {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "output_logic": {"include_optional_sections_only_if_provided": True},
        }

        if name == "press release":
            base_content.update({"document_number": 1})
        elif name == "campaign brief":
            base_content.update({"document_number": 2})
        elif name == "social media plan":
            base_content.update({"document_number": 3})
        elif name == "brand guidelines":
            base_content.update({"document_number": 4})
        elif name == "email newsletter":
            base_content.update({"document_number": 5})
        elif name == "ad copy":
            base_content.update({"document_number": 6})
        elif name == "content calendar":
            base_content.update({"document_number": 7})
        elif name == "influencer brief":
            base_content.update({"document_number": 8})
        elif name == "marketing report":
            base_content.update({"document_number": 9})
        elif name == "event proposal":
            base_content.update({"document_number": 10})

        return base_content

    if name in OPS_SCHEMAS:
        base_content = {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"show_optional_fields_only_if_provided": True},
        }

        ops_actions = {
            "shipping manifest": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "inventory log": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "delivery order": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "logistics plan": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "supply chain report": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "warehouse checklist": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
            "fleet report": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "vendor agreement": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "procurement request": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "goods receipt note (grn)": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
        }

        if name == "shipping manifest":
            base_content.update(
                {
                    "actions": ops_actions[name],
                    "signature_configuration": {
                        "dispatcher_signature": {"required": True, "fields": ["name", "date"]},
                        "receiver_signature": {"required": False, "fields": ["name", "date"]},
                    },
                    "document_number": 1,
                }
            )
        elif name == "inventory log":
            base_content.update(
                {
                    "actions": ops_actions[name],
                    "signature_configuration": {
                        "prepared_by_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "output_logic": {"support_multiple_item_rows": True},
                    "document_number": 2,
                }
            )
        elif name == "delivery order":
            base_content.update(
                {
                    "actions": ops_actions[name],
                    "signature_configuration": {
                        "dispatcher_signature": {"required": True, "fields": ["name", "date"]},
                        "receiver_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "output_logic": {"show_received_section_only_if_completed": True},
                    "document_number": 3,
                }
            )
        elif name == "logistics plan":
            base_content.update(
                {
                    "actions": ops_actions[name],
                    "signature_configuration": {
                        "prepared_by_signature": {"required": True, "fields": ["name", "date"]},
                        "approved_by_signature": {"required": False, "fields": ["name", "date"]},
                    },
                    "output_logic": {"show_optional_sections_only_if_provided": True},
                    "document_number": 4,
                }
            )
        elif name == "supply chain report":
            base_content.update(
                {
                    "actions": ops_actions[name],
                    "signature_configuration": {
                        "prepared_by_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "output_logic": {"show_optional_sections_only_if_provided": True},
                    "document_number": 5,
                }
            )
        elif name == "warehouse checklist":
            base_content.update(
                {
                    "actions": ops_actions[name],
                    "signature_configuration": {
                        "supervisor_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "output_logic": {"keep_checklist_structured_and_scannable": True},
                    "document_number": 6,
                }
            )
        elif name == "fleet report":
            base_content.update(
                {
                    "actions": ops_actions[name],
                    "signature_configuration": {
                        "prepared_by_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "output_logic": {
                        "support_multiple_vehicle_rows": True,
                        "show_optional_sections_only_if_provided": True,
                    },
                    "document_number": 7,
                }
            )
        elif name == "vendor agreement":
            base_content.update(
                {
                    "actions": ops_actions[name],
                    "signature_configuration": {
                        "company_representative_signature": {"required": True, "fields": ["name", "date"]},
                        "vendor_representative_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "output_logic": {"include_optional_clauses_only_if_provided": True},
                    "document_number": 8,
                }
            )
        elif name == "procurement request":
            base_content.update(
                {
                    "actions": ops_actions[name],
                    "signature_configuration": {
                        "requester_signature": {"required": True, "fields": ["name", "date"]},
                        "approver_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "output_logic": {"show_vendor_and_approval_only_if_provided": True},
                    "document_number": 9,
                }
            )
        elif name == "goods receipt note (grn)":
            base_content.update(
                {
                    "actions": ops_actions[name],
                    "signature_configuration": {
                        "receiver_signature": {"required": True, "fields": ["name", "date"]},
                        "inspector_signature": {"required": False, "fields": ["name", "date"]},
                    },
                    "output_logic": {"show_inspection_section_only_if_provided": True},
                    "document_number": 10,
                }
            )

        return base_content

    if name in FINANCE_SCHEMAS:
        base_content = {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"include_optional_sections_only_if_provided": True},
        }

        finance_actions = {
            "invoice": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "receipt": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "purchase order": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "expense report": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "budget proposal": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
            "payment terms": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "billing statement": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "financial summary": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "profit & loss statement": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "balance sheet": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "cash flow statement": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "break-even analysis": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "petty cash log": {"download_pdf": True, "send_via_email": False, "send_for_signature": False},
            "tax summary": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "credit note": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "debit note": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "audit report": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "loan agreement": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
            "reimbursement form": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
            "payroll summary": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "vendor payment": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
        }

        if name == "invoice":
            base_content.update(
                {
                    "actions": finance_actions[name],
                    "signature_configuration": {"required": False},
                    "document_number": 1,
                    "output_logic": {
                        "include_tax_section_only_if_provided": True,
                        "auto_calculate_subtotal": True,
                        "auto_calculate_total_amount": True,
                        "format_description_as_bullets": True,
                    },
                }
            )
        elif name == "receipt":
            base_content.update(
                {
                    "actions": finance_actions[name],
                    "signature_configuration": {
                        "received_by_signature": {"required": False, "fields": ["name", "date"]},
                    },
                    "document_number": 2,
                    "output_logic": {
                        "include_remaining_balance_only_if_provided": True,
                        "format_currency_fields": True,
                    },
                }
            )
        elif name == "purchase order":
            base_content.update(
                {
                    "actions": finance_actions[name],
                    "signature_configuration": {
                        "authorized_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 3,
                    "output_logic": {
                        "include_tax_section_only_if_provided": True,
                        "auto_calculate_subtotal": True,
                        "auto_calculate_total_amount": True,
                        "render_vendor_as_mailing_label": True,
                    },
                }
            )
        elif name == "expense report":
            base_content.update(
                {
                    "actions": finance_actions[name],
                    "signature_configuration": {
                        "employee_signature": {"required": True, "fields": ["name", "date"]},
                        "manager_approval": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 4,
                    "output_logic": {"include_optional_notes_only_if_provided": True},
                }
            )
        elif name == "budget proposal":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"prepared_by": {"required": True, "fields": ["name", "date"]}, "approved_by": {"required": True, "fields": ["name", "date"]}}, "document_number": 5, "output_logic": {"show_optional_sections_only_if_filled": True}})
        elif name == "payment terms":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"required": False}, "document_number": 6, "output_logic": {"show_optional_sections_only_if_filled": True}})
        elif name == "billing statement":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"required": False}, "document_number": 7, "output_logic": {"show_adjustments_only_if_provided": True}})
        elif name == "financial summary":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"prepared_by": {"required": True, "fields": ["name", "date"]}}, "document_number": 8, "output_logic": {"show_optional_sections_only_if_filled": True}})
        elif name == "profit & loss statement":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"prepared_by": {"required": True, "fields": ["name", "date"]}}, "document_number": 9, "output_logic": {"show_optional_sections_only_if_filled": True}})
        elif name == "balance sheet":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"prepared_by": {"required": True, "fields": ["name", "date"]}}, "document_number": 10, "output_logic": {"show_optional_sections_only_if_filled": True}})
        elif name == "cash flow statement":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"prepared_by": {"required": True, "fields": ["name", "date"]}}, "document_number": 11, "output_logic": {"show_optional_sections_only_if_filled": True}})
        elif name == "break-even analysis":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"prepared_by": {"required": True, "fields": ["name", "date"]}}, "document_number": 12, "output_logic": {"show_optional_notes_only_if_provided": True}})
        elif name == "petty cash log":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"custodian_signature": {"required": True, "fields": ["name", "date"]}}, "document_number": 13, "output_logic": {"transactions_displayed_in_structured_table": True}})
        elif name == "tax summary":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"prepared_by": {"required": True, "fields": ["name", "date"]}}, "document_number": 14, "output_logic": {"show_optional_values_only_if_provided": True}})
        elif name == "credit note":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"authorized_signature": {"required": True, "fields": ["name", "date"]}}, "document_number": 15, "output_logic": {"show_remaining_balance_only_if_provided": True, "split_tax_refund_from_base_amount": True}})
        elif name == "debit note":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"authorized_signature": {"required": True, "fields": ["name", "date"]}}, "document_number": 16, "output_logic": {"show_optional_balance_only_if_provided": True, "counterparty_toggle_customer_vendor": True}})
        elif name == "audit report":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"auditor_signature": {"required": True, "fields": ["name", "date"]}}, "document_number": 17, "output_logic": {"recommendations_shown_only_if_provided": True}})
        elif name == "loan agreement":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"lender_signature": {"required": True, "fields": ["name", "date"]}, "borrower_signature": {"required": True, "fields": ["name", "date"]}}, "document_number": 18, "output_logic": {"optional_terms_shown_only_if_provided": True, "auto_calculate_maturity_date": True}})
        elif name == "reimbursement form":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"employee_signature": {"required": True, "fields": ["name", "date"]}, "manager_approval": {"required": True, "fields": ["name", "date"]}}, "document_number": 19, "output_logic": {"show_optional_notes_only_if_provided": True}})
        elif name == "payroll summary":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"prepared_by": {"required": True, "fields": ["name", "date"]}}, "document_number": 20, "output_logic": {"support_multiple_employee_rows": True}})
        elif name == "vendor payment":
            base_content.update({"actions": finance_actions[name], "signature_configuration": {"authorized_signature": {"required": True, "fields": ["name", "date"]}}, "document_number": 21, "output_logic": {"show_optional_fields_only_if_provided": True}})

        return base_content

    if name in HR_SCHEMAS:
        base_content = {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"include_optional_sections_only_if_provided": True},
        }

        if name == "offer letter":
            base_content.update(
                {
                    "output_logic": {"include_optional_fields_only_if_provided": True},
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
                    "signature_configuration": {
                        "employer_signature": {"required": True, "fields": ["name", "date"]},
                        "candidate_acceptance": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 1,
                }
            )
        elif name == "employment contract":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
                    "signature_configuration": {
                        "employer_signature": {"required": True, "fields": ["name", "date"]},
                        "employee_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 2,
                }
            )
        elif name == "termination letter":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
                    "signature_configuration": {
                        "employer_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 3,
                }
            )
        elif name == "performance review":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
                    "signature_configuration": {
                        "reviewer_signature": {"required": True, "fields": ["name", "date"]},
                        "employee_acknowledgment": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 4,
                }
            )
        elif name == "job description":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
                    "signature_configuration": {"required": False},
                    "document_number": 5,
                }
            )
        elif name == "onboarding checklist":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
                    "signature_configuration": {"required": False},
                    "document_number": 6,
                }
            )
        elif name == "employee handbook":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
                    "signature_configuration": {
                        "employee_acknowledgment": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 7,
                }
            )
        elif name == "pip template":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
                    "signature_configuration": {
                        "manager_signature": {"required": True, "fields": ["name", "date"]},
                        "employee_acknowledgment": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 8,
                }
            )
        elif name == "warning letter":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
                    "signature_configuration": {
                        "manager_signature": {"required": True, "fields": ["name", "date"]},
                        "employee_acknowledgment": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 9,
                }
            )
        elif name == "reference letter":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
                    "signature_configuration": {
                        "authorized_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 10,
                }
            )
        elif name == "internal audit checklist":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
                    "signature_configuration": {
                        "auditor_signature": {"required": True, "fields": ["name", "date"]},
                        "manager_acknowledgment": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 11,
                }
            )
        elif name == "office incident report":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
                    "signature_configuration": {
                        "reporter_signature": {"required": True, "fields": ["name", "date"]},
                        "manager_review": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 12,
                }
            )
        elif name == "mail handling log":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": False, "send_for_signature": False},
                    "signature_configuration": {"required": False},
                    "document_number": 13,
                }
            )
        elif name == "office maintenance request":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
                    "signature_configuration": {
                        "manager_approval": {"required": False, "fields": ["name", "date"]},
                    },
                    "document_number": 14,
                }
            )
        elif name == "document control register":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
                    "signature_configuration": {
                        "controller_signature": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 15,
                }
            )
        elif name == "leave policy":
            base_content.update(
                {
                    "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": True},
                    "signature_configuration": {
                        "employee_acknowledgment": {"required": True, "fields": ["name", "date"]},
                    },
                    "document_number": 16,
                }
            )

        return base_content

    if name == "sales proposal":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {
                "include_additional_notes_only_if_provided": True,
                "include_acceptance_section": True,
            },
            "actions": {
                "download_pdf": True,
                "send_via_email": False,
                "send_for_signature": True,
            },
            "signature_configuration": {
                "company_representative_signature": {"required": True, "fields": ["name", "date"]},
                "client_signature": {"required": True, "fields": ["name", "date"]},
            },
            "document_number": 1,
        }

    if name == "client onboarding":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"include_additional_notes_only_if_provided": True},
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "document_number": 2,
        }

    if name == "follow-up email":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {
                "include_sender_position_only_if_provided": True,
                "include_contact_information_only_if_provided": True,
                "include_additional_notes_only_if_provided": True,
            },
            "actions": {"download_pdf": False, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "document_number": 3,
        }

    if name == "service agreement":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {
                "include_confidentiality_clause_only_if_provided": True,
                "include_additional_terms_only_if_provided": True,
                "include_acceptance_section": True,
            },
            "actions": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
            "signature_configuration": {
                "company_representative_signature": {"required": True, "fields": ["name", "date"]},
                "client_signature": {"required": True, "fields": ["name", "date"]},
            },
            "document_number": 4,
        }

    if name == "quote template":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {
                "include_taxes_fees_only_if_provided": True,
                "include_additional_notes_only_if_provided": True,
            },
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "document_number": 5,
        }

    if name == "meeting summary":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {
                "include_meeting_time_only_if_provided": True,
                "include_location_only_if_provided": True,
                "include_next_steps_only_if_provided": True,
                "include_additional_notes_only_if_provided": True,
            },
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "document_number": 6,
        }

    if name == "crm report":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"include_optional_sections_only_if_provided": True},
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "document_number": 7,
            "positioning": "Client relationship intelligence and account health focus.",
        }

    if name == "pitch deck outline":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"include_optional_sections_only_if_provided": True},
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "document_number": 8,
        }

    if name == "account plan":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"include_optional_sections_only_if_provided": True},
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "document_number": 10,
            "positioning": "Client-specific strategic planning and long-term growth.",
        }

    if name == "action plan":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"include_optional_sections_only_if_provided": True},
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "document_number": 11,
            "positioning": "Execution tracking with accountable owners and deadlines.",
        }

    if name == "sales report":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"include_optional_sections_only_if_provided": True},
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "document_number": 12,
            "positioning": "Revenue, quota, and sales KPI performance focus.",
        }

    if name == "win/loss analysis":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"include_optional_sections_only_if_provided": True},
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {"required": False},
            "document_number": 13,
        }

    if name == "partnership proposal":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {"include_optional_sections_only_if_provided": True},
            "actions": {"download_pdf": True, "send_via_email": False, "send_for_signature": True},
            "signature_configuration": {
                "company_representative_signature": {"required": True, "fields": ["name", "date"]},
                "partner_representative_signature": {"required": True, "fields": ["name", "date"]},
            },
            "document_number": 14,
        }

    if name == "client feedback form":
        return {
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "output_logic": {
                "include_optional_sections_only_if_provided": True,
                "include_acknowledgment_section_only_if_signature_provided": True,
            },
            "actions": {"download_pdf": True, "send_via_email": True, "send_for_signature": False},
            "signature_configuration": {
                "client_acknowledgment": {"required": False, "fields": ["name", "date"]},
            },
            "document_number": 15,
        }

    return {
        "required_fields": required_fields,
        "optional_fields": optional_fields,
    }


def _schema_for_document_type(doc_type_name, category_name=None):
    name = doc_type_name.lower()

    if category_name == "Business Operations" and name in BUSINESS_OPERATION_SCHEMAS:
        return BUSINESS_OPERATION_SCHEMAS[name]

    if category_name == "Administration & Office" and name in ADMIN_OFFICE_SCHEMAS:
        return ADMIN_OFFICE_SCHEMAS[name]

    if category_name == "General Templates" and name in GENERAL_SCHEMAS:
        return GENERAL_SCHEMAS[name]

    if category_name == "Compliance & Records" and name in COMPLIANCE_SCHEMAS:
        return COMPLIANCE_SCHEMAS[name]

    if category_name == "Legal Documents" and name in LEGAL_SCHEMAS:
        return LEGAL_SCHEMAS[name]
    if category_name == "Marketing & Communications" and name in MARKETING_SCHEMAS:
        return MARKETING_SCHEMAS[name]
    if category_name == "Operations & Logistics" and name in OPS_SCHEMAS:
        return OPS_SCHEMAS[name]
    if category_name == "Finance & Billing" and name in FINANCE_SCHEMAS:
        return FINANCE_SCHEMAS[name]
    if category_name == "Sales & Client Management" and name in SALES_CLIENT_SCHEMAS:
        return SALES_CLIENT_SCHEMAS[name]
    if category_name == "Human Resources" and name in HR_SCHEMAS:
        return HR_SCHEMAS[name]

    if name in OPS_SCHEMAS:
        return OPS_SCHEMAS[name]

    if name in FINANCE_SCHEMAS:
        return FINANCE_SCHEMAS[name]

    if name in SALES_CLIENT_SCHEMAS:
        return SALES_CLIENT_SCHEMAS[name]

    if name in HR_SCHEMAS:
        return HR_SCHEMAS[name]

    if name in MARKETING_SCHEMAS:
        return MARKETING_SCHEMAS[name]

    if name in GENERAL_SCHEMAS:
        return GENERAL_SCHEMAS[name]

    if name in COMPLIANCE_SCHEMAS:
        return COMPLIANCE_SCHEMAS[name]

    if name == "client proposal":
        return [
            _field("client_name", "Client Name", "text", 1),
            _field("project_name", "Project Name", "text", 2),
            _field("scope", "Scope of Work", "textarea", 3),
            _field("timeline", "Timeline", "text", 4, placeholder="Estimated delivery timeline"),
            _field("pricing", "Pricing", "currency", 5),
            _field("valid_until", "Valid Until", "date", 6, required=False),
        ]

    if name == "service agreement":
        return [
            _field("party_a", "Party A", "text", 1),
            _field("party_b", "Party B", "text", 2),
            _field("service_description", "Service Description", "textarea", 3),
            _field("start_date", "Start Date", "date", 4),
            _field("end_date", "End Date", "date", 5, required=False),
            _field("payment_terms", "Payment Terms", "text", 6, placeholder="Net 30, 50% advance, etc."),
            _field("signatory_name", "Signatory Name", "text", 7, required=False),
        ]

    if name == "offer letter":
        return [
            _field("candidate_name", "Candidate Name", "text", 1),
            _field("position_title", "Position Title", "text", 2),
            _field("start_date", "Start Date", "date", 3),
            _field("salary", "Salary", "currency", 4),
            _field("reporting_manager", "Reporting Manager", "text", 5, required=False),
            _field("acceptance_deadline", "Acceptance Deadline", "date", 6, required=False),
        ]

    if name == "office notice":
        return [
            _field("notice_title", "Notice Title", "text", 1),
            _field("audience", "Audience", "text", 2),
            _field("notice_date", "Notice Date", "date", 3),
            _field("effective_date", "Effective Date", "date", 4, required=False),
            _field("message", "Message", "textarea", 5),
        ]

    if name == "meeting minutes":
        return [
            _field("meeting_title", "Meeting Title", "text", 1),
            _field("meeting_date", "Meeting Date", "date", 2),
            _field("attendees", "Attendees", "textarea", 3),
            _field("agenda", "Agenda", "textarea", 4),
            _field("decisions", "Decisions", "textarea", 5),
            _field("action_items", "Action Items", "textarea", 6, required=False),
        ]

    if name == "policy circular":
        return [
            _field("policy_title", "Policy Title", "text", 1),
            _field("department", "Department", "text", 2, required=False),
            _field("effective_date", "Effective Date", "date", 3),
            _field("summary", "Summary", "textarea", 4),
            _field("details", "Details", "textarea", 5),
        ]

    if name == "job description":
        return [
            _field("role_title", "Role Title", "text", 1),
            _field("department", "Department", "text", 2),
            _field("reporting_to", "Reporting To", "text", 3, required=False),
            _field("responsibilities", "Responsibilities", "textarea", 4),
            _field("qualifications", "Qualifications", "textarea", 5),
        ]

    if name == "employee warning":
        return [
            _field("employee_name", "Employee Name", "text", 1),
            _field("incident_date", "Incident Date", "date", 2),
            _field("warning_reason", "Warning Reason", "textarea", 3),
            _field("corrective_action", "Corrective Action", "textarea", 4),
            _field("manager_name", "Manager Name", "text", 5, required=False),
        ]

    if name == "leave approval":
        return [
            _field("employee_name", "Employee Name", "text", 1),
            _field("leave_type", "Leave Type", "select", 2, options=["Annual Leave", "Sick Leave", "Emergency Leave", "Unpaid Leave"]),
            _field("start_date", "Start Date", "date", 3),
            _field("end_date", "End Date", "date", 4),
            _field("approver", "Approver", "text", 5),
            _field("remarks", "Remarks", "textarea", 6, required=False),
        ]

    if name == "invoice":
        return [
            _field("invoice_number", "Invoice Number", "text", 1),
            _field("bill_to", "Bill To", "textarea", 2),
            _field("invoice_date", "Invoice Date", "date", 3),
            _field("due_date", "Due Date", "date", 4, required=False),
            _field("line_items", "Line Items", "textarea", 5),
            _field("subtotal", "Subtotal", "currency", 6),
            _field("tax_amount", "Tax Amount", "currency", 7, required=False),
            _field("total_amount", "Total Amount", "currency", 8),
            _field("payment_method", "Payment Method", "text", 9, required=False),
        ]

    if name == "payment reminder":
        return [
            _field("recipient_name", "Recipient Name", "text", 1),
            _field("invoice_number", "Invoice Number", "text", 2, required=False),
            _field("outstanding_amount", "Outstanding Amount", "currency", 3),
            _field("due_date", "Due Date", "date", 4, required=False),
            _field("reminder_message", "Reminder Message", "textarea", 5),
        ]

    if name == "budget summary":
        return [
            _field("budget_period", "Budget Period", "text", 1),
            _field("department", "Department", "text", 2),
            _field("prepared_by", "Prepared By", "text", 3),
            _field("income", "Income", "currency", 4),
            _field("expenses", "Expenses", "currency", 5),
            _field("variance", "Variance", "currency", 6, required=False),
            _field("notes", "Notes", "textarea", 7, required=False),
        ]

    if name == "dispatch note":
        return [
            _field("dispatch_number", "Dispatch Number", "text", 1),
            _field("sender_name", "Sender Name", "text", 2),
            _field("recipient_name", "Recipient Name", "text", 3),
            _field("dispatch_date", "Dispatch Date", "date", 4),
            _field("items", "Items", "textarea", 5),
            _field("delivery_terms", "Delivery Terms", "textarea", 6, required=False),
        ]

    if name == "inventory checklist":
        return [
            _field("checklist_title", "Checklist Title", "text", 1),
            _field("location", "Location", "text", 2, required=False),
            _field("review_date", "Review Date", "date", 3),
            _field("items", "Items", "textarea", 4),
            _field("remarks", "Remarks", "textarea", 5, required=False),
        ]

    if name == "delivery confirmation":
        return [
            _field("delivery_number", "Delivery Number", "text", 1),
            _field("client_name", "Client Name", "text", 2),
            _field("delivery_date", "Delivery Date", "date", 3),
            _field("items", "Items Delivered", "textarea", 4),
            _field("received_by", "Received By", "text", 5),
            _field("condition", "Condition", "textarea", 6, required=False),
        ]

    if name == "nda":
        return [
            _field("party_a", "Party A", "text", 1),
            _field("party_b", "Party B", "text", 2),
            _field("effective_date", "Effective Date", "date", 3),
            _field("confidential_info", "Confidential Information", "textarea", 4),
            _field("term", "Term", "text", 5),
            _field("governing_law", "Governing Law", "text", 6, required=False),
        ]

    if name == "contract addendum":
        return [
            _field("original_contract", "Original Contract", "text", 1),
            _field("addendum_date", "Addendum Date", "date", 2),
            _field("changes", "Changes", "textarea", 3),
            _field("effective_date", "Effective Date", "date", 4, required=False),
        ]

    if name == "terms notice":
        return [
            _field("service_name", "Service Name", "text", 1),
            _field("effective_date", "Effective Date", "date", 2),
            _field("terms_summary", "Terms Summary", "textarea", 3),
            _field("contact_info", "Contact Information", "textarea", 4, required=False),
        ]

    if name == "press release":
        return [
            _field("headline", "Headline", "text", 1),
            _field("announcement_date", "Announcement Date", "date", 2),
            _field("company_name", "Company Name", "text", 3),
            _field("summary", "Summary", "textarea", 4),
            _field("quote", "Quote", "textarea", 5, required=False),
            _field("contact_info", "Contact Information", "textarea", 6, required=False),
        ]

    if name == "campaign brief":
        return [
            _field("campaign_name", "Campaign Name", "text", 1),
            _field("objective", "Objective", "textarea", 2),
            _field("target_audience", "Target Audience", "textarea", 3),
            _field("channels", "Channels", "textarea", 4),
            _field("budget", "Budget", "currency", 5, required=False),
            _field("timeline", "Timeline", "text", 6, required=False),
        ]

    if name == "social media plan":
        return [
            _field("brand_name", "Brand Name", "text", 1),
            _field("planning_period", "Planning Period", "text", 2),
            _field("platforms", "Platforms", "textarea", 3),
            _field("content_themes", "Content Themes", "textarea", 4),
            _field("posting_frequency", "Posting Frequency", "text", 5),
            _field("goals", "Goals", "textarea", 6, required=False),
        ]

    if name == "audit checklist":
        return [
            _field("audit_area", "Audit Area", "text", 1),
            _field("audit_date", "Audit Date", "date", 2),
            _field("auditor", "Auditor", "text", 3),
            _field("checklist_items", "Checklist Items", "textarea", 4),
            _field("findings", "Findings", "textarea", 5, required=False),
            _field("action_plan", "Action Plan", "textarea", 6, required=False),
        ]

    if name == "compliance notice":
        return [
            _field("compliance_topic", "Compliance Topic", "text", 1),
            _field("effective_date", "Effective Date", "date", 2),
            _field("departments", "Departments", "textarea", 3),
            _field("requirements", "Requirements", "textarea", 4),
            _field("deadline", "Deadline", "date", 5, required=False),
        ]

    if name == "risk report":
        return [
            _field("report_title", "Report Title", "text", 1),
            _field("assessment_date", "Assessment Date", "date", 2),
            _field("risk_items", "Risk Items", "textarea", 3),
            _field("mitigations", "Mitigations", "textarea", 4),
            _field("owner", "Owner", "text", 5, required=False),
        ]

    if name == "general notice":
        return [
            _field("notice_title", "Notice Title", "text", 1),
            _field("audience", "Audience", "text", 2),
            _field("notice_date", "Notice Date", "date", 3),
            _field("body", "Body", "textarea", 4),
            _field("contact_info", "Contact Information", "textarea", 5, required=False),
        ]

    if name == "simple agreement":
        return [
            _field("party_a", "Party A", "text", 1),
            _field("party_b", "Party B", "text", 2),
            _field("agreement_date", "Agreement Date", "date", 3),
            _field("key_terms", "Key Terms", "textarea", 4),
            _field("duration", "Duration", "text", 5, required=False),
        ]

    if name == "basic proposal":
        return [
            _field("client_name", "Client Name", "text", 1),
            _field("proposal_date", "Proposal Date", "date", 2),
            _field("objective", "Objective", "textarea", 3),
            _field("scope", "Scope", "textarea", 4),
            _field("pricing", "Pricing", "currency", 5, required=False),
            _field("next_steps", "Next Steps", "textarea", 6, required=False),
        ]

    return [
        _field("title", "Title", "text", 1),
        _field("date", "Date", "date", 2),
        _field("summary", "Summary", "textarea", 3),
        _field("details", "Details", "textarea", 4, required=False),
    ]


def _template_body_for_document_type(doc_type_name, variant, category_name=None):
    name = doc_type_name.lower()
    is_modern = variant.lower() == "modern"

    if category_name == "Business Operations" and name in BUSINESS_OPERATION_TEMPLATES:
        return BUSINESS_OPERATION_TEMPLATES[name]

    if category_name == "Administration & Office" and name in ADMIN_OFFICE_TEMPLATES:
        return ADMIN_OFFICE_TEMPLATES[name]

    if category_name == "General Templates" and name in GENERAL_TEMPLATES:
        return GENERAL_TEMPLATES[name]

    if category_name == "Compliance & Records" and name in COMPLIANCE_TEMPLATES:
        return COMPLIANCE_TEMPLATES[name]

    if category_name == "Legal Documents" and name in LEGAL_TEMPLATES:
        return LEGAL_TEMPLATES[name]
    if category_name == "Marketing & Communications" and name in MARKETING_TEMPLATES:
        return MARKETING_TEMPLATES[name]
    if category_name == "Operations & Logistics" and name in OPS_TEMPLATES:
        return OPS_TEMPLATES[name]
    if category_name == "Finance & Billing" and name in FINANCE_TEMPLATES:
        return FINANCE_TEMPLATES[name]
    if category_name == "Sales & Client Management" and name in SALES_CLIENT_TEMPLATES:
        return SALES_CLIENT_TEMPLATES[name]
    if category_name == "Human Resources" and name in HR_TEMPLATES:
        return HR_TEMPLATES[name]

    if name in OPS_TEMPLATES:
        return OPS_TEMPLATES[name]

    if name in FINANCE_TEMPLATES:
        return FINANCE_TEMPLATES[name]

    if name in SALES_CLIENT_TEMPLATES:
        return SALES_CLIENT_TEMPLATES[name]

    if name in HR_TEMPLATES:
        return HR_TEMPLATES[name]

    if name in MARKETING_TEMPLATES:
        return MARKETING_TEMPLATES[name]

    if name in GENERAL_TEMPLATES:
        return GENERAL_TEMPLATES[name]

    if name in COMPLIANCE_TEMPLATES:
        return COMPLIANCE_TEMPLATES[name]

    if name == "service agreement":
        return (
            "This Service Agreement is entered into by [Party A] and [Party B] on [Start Date].\n\n"
            "Services: [Service Description]\n"
            "Payment Terms: [Payment Terms]\n"
            "End Date: [End Date]"
        )
    if name == "invoice":
        return (
            "Invoice Number: [Invoice Number]\n"
            "Bill To: [Bill To]\n"
            "Invoice Date: [Invoice Date]\n\n"
            "Items:\n[Line Items]\n\n"
            "Subtotal: [Subtotal]\nTax: [Tax Amount]\nTotal: [Total Amount]"
        )
    if name == "offer letter":
        return (
            "Dear [Candidate Name],\n\n"
            "We are pleased to offer you the position of [Position Title], starting on [Start Date].\n"
            "Your salary will be [Salary].\n\n"
            "Please confirm acceptance by [Acceptance Deadline]."
        )
    if name == "nda":
        return (
            "This Non-Disclosure Agreement is entered into by [Party A] and [Party B] effective [Effective Date].\n\n"
            "Confidential Information: [Confidential Information]\n"
            "Term: [Term]\n"
            "Governing Law: [Governing Law]"
        )
    if name == "press release":
        return (
            "[Headline]\n\n"
            "Date: [Announcement Date]\n"
            "Company: [Company Name]\n\n"
            "Summary: [Summary]\n\n"
            "Quote: [Quote]"
        )
    if name == "audit checklist":
        return (
            "Audit Checklist for [Audit Area]\n\n"
            "Assessment Date: [Audit Date]\n"
            "Auditor: [Auditor]\n\n"
            "Checklist Items:\n[Checklist Items]\n\n"
            "Findings: [Findings]\n"
            "Action Plan: [Action Plan]"
        )
    if is_modern:
        return (
            "[Title]\n\n"
            "Date: [Date]\n\n"
            "Summary: [Summary]\n\n"
            "Details:\n[Details]"
        )
    return (
        "[Title]\n\n"
        "Date: [Date]\n\n"
        "Summary: [Summary]\n\n"
        "Details: [Details]"
    )


CATEGORIES = [
    ("Business Operations", "Standardized daily operations documents.", "business", 13, True, True),
    ("Sales & Client Management", "Documents to support sales and client relationships.", "sales", 14, True, True),
    ("Administration & Office", "Internal office and administrative documentation.", "office", 10, False, True),
    ("Human Resources", "Essential human resources templates.", "hr", 15, False, True),
    ("Finance & Billing", "Essential finance documents.", "finance", 21, True, True),
    ("Operations & Logistics", "Manage operations and logistics efficiently.", "operations", 10, False, True),
    ("Legal Documents", "Compliance-ready legal documentation.", "legal", 15, True, False),
    ("Marketing & Communications", "Documents for business communication.", "marketing", 10, False, False),
    ("Compliance & Records", "Compliance-ready templates and records.", "compliance", 10, False, True),
    ("General Templates", "Flexible forms for all business needs.", "general", 11, False, False),
]

DOC_TYPES = {
    "Business Operations": [
        "Internal Memo",
        "Company Policy Notice",
        "SOP Summary",
        "Incident Report",
        "Equipment Checklist",
        "Process Documentation",
        "Meeting Minutes",
        "Action Plan",
        "Operational Report",
        "Project Brief",
        "Work Log",
        "Task Assignment Sheet",
        "Risk Assessment",
    ],
    "Sales & Client Management": [
        "Sales Proposal",
        "Client Onboarding",
        "Follow-Up Email",
        "Service Agreement",
        "Quote Template",
        "Meeting Summary",
        "CRM Report",
        "Pitch Deck Outline",
        "Account Plan",
        "Action Plan",
        "Sales Report",
        "Win/Loss Analysis",
        "Partnership Proposal",
        "Client Feedback Form",
    ],
    "Administration & Office": [
        "Office Policy",
        "Visitor Log",
        "Office Supply Request",
        "Expense Claim",
        "Meeting Room Booking",
        "Staff Announcement",
        "Internal Notice",
        "Filing Guide",
        "Correspondence Log",
        "Delegation of Duties",
    ],
    "Human Resources": [
        "Offer Letter",
        "Employment Contract",
        "Termination Letter",
        "Performance Review",
        "Job Description",
        "Onboarding Checklist",
        "Employee Handbook",
        "PIP Template",
        "Warning Letter",
        "Reference Letter",
        "Internal Audit Checklist",
        "Office Incident Report",
        "Mail Handling Log",
        "Office Maintenance Request",
        "Document Control Register",
        "Leave Policy",
    ],
    "Finance & Billing": [
        "Invoice",
        "Receipt",
        "Purchase Order",
        "Expense Report",
        "Budget Proposal",
        "Payment Terms",
        "Billing Statement",
        "Financial Summary",
        "Profit & Loss Statement",
        "Balance Sheet",
        "Cash Flow Statement",
        "Break-Even Analysis",
        "Petty Cash Log",
        "Tax Summary",
        "Credit Note",
        "Debit Note",
        "Audit Report",
        "Loan Agreement",
        "Reimbursement Form",
        "Payroll Summary",
        "Vendor Payment",
    ],
    "Operations & Logistics": [
        "Shipping Manifest",
        "Inventory Log",
        "Delivery Order",
        "Logistics Plan",
        "Supply Chain Report",
        "Warehouse Checklist",
        "Fleet Report",
        "Vendor Agreement",
        "Procurement Request",
        "Goods Receipt Note (GRN)",
    ],
    "Legal Documents": [
        "Non-Disclosure Agreement (Freelancer NDA)",
        "Employee Non-Disclosure Agreement (Employee NDA)",
        "Service Agreement",
        "Partnership Agreement",
        "Consulting Contract",
        "Terms of Service",
        "Privacy Policy",
        "Cease and Desist Letter",
        "Letter of Intent (LOI)",
        "Intellectual Property Assignment Agreement",
        "Vendor Contract",
        "Confidentiality Agreement",
        "Independent Contractor Agreement",
        "Release of Liability Agreement",
        "Legal Notice",
    ],
    "Marketing & Communications": [
        "Press Release",
        "Campaign Brief",
        "Social Media Plan",
        "Brand Guidelines",
        "Email Newsletter",
        "Ad Copy",
        "Content Calendar",
        "Influencer Brief",
        "Marketing Report",
        "Event Proposal",
    ],
    "Compliance & Records": [
        "Compliance Checklist",
        "Audit Trail",
        "Data Retention Policy",
        "GDPR Policy",
        "Regulatory Filing",
        "Risk Register",
        "Incident Form",
        "Ethics Policy",
        "Records Index",
        "Compliance Report",
    ],
    "General Templates": [
        "Cover Letter",
        "Meeting Agenda",
        "Project Plan",
        "Status Report",
        "Checklist",
        "To-Do List",
        "Notes Template",
        "Invoice",
        "Contract Agreement",
        "Proposal",
        "Presentation Outline",
    ],
}

TEMPLATE_VARIANTS = [
    "Classic",
    "Modern",
]

HELP_ARTICLES = [
    ("getting_started", "How to generate your first document", "Step-by-step guide to create your first document.", True),
    ("getting_started", "How downloads work", "Understand credit deduction and downloads.", False),
    ("billing", "How to update payment method", "Update your saved card details from billing settings.", True),
    ("billing", "How to cancel subscription", "Cancel and manage renewal preferences.", False),
    ("templates", "How to choose templates", "Select the best template for your business use-case.", True),
    ("templates", "How to request a missing template", "Submit a request from help center.", False),
]


class Command(BaseCommand):
    help = "Seed dashboard categories, document types, templates, and help articles."

    def handle(self, *args, **options):
        category_map = {}

        for idx, row in enumerate(CATEGORIES, start=1):
            name, description, icon, count, recommended, popular = row
            category_slug = slugify(name)
            category, _ = TemplateCategory.objects.update_or_create(
                slug=category_slug,
                defaults={
                    "name": name,
                    "description": description,
                    "icon": icon,
                    "template_count": count,
                    "is_recommended": recommended,
                    "is_popular": popular,
                    "is_active": True,
                    "sort_order": idx,
                },
            )
            category_map[name] = category

        template_total = 0
        for category_name, doc_type_names in DOC_TYPES.items():
            category = category_map[category_name]
            DocumentType.objects.filter(category=category).exclude(name__in=doc_type_names).delete()
            for idx, doc_type_name in enumerate(doc_type_names, start=1):
                doc_type_slug = slugify(doc_type_name)
                doc_type, _ = DocumentType.objects.update_or_create(
                    category=category,
                    slug=doc_type_slug,
                    defaults={
                        "name": doc_type_name,
                        "description": f"{doc_type_name} documents for {category_name}.",
                        "schema_definition": _schema_for_document_type(doc_type_name, category_name=category_name),
                        "is_active": True,
                        "sort_order": idx,
                    },
                )

                for variant in TEMPLATE_VARIANTS:
                    template_name = f"{doc_type_name} {variant}"
                    template_slug = slugify(template_name)
                    schema = _schema_for_document_type(doc_type_name, category_name=category_name)
                    _, _created = DocumentTemplate.objects.update_or_create(
                        document_type=doc_type,
                        slug=template_slug,
                        defaults={
                            "name": template_name,
                            "description": f"{variant} style {doc_type_name} template.",
                            "is_active": True,
                            "content_template": _template_body_for_document_type(doc_type_name, variant, category_name=category_name),
                            "base_content": _base_content_for_document_type(doc_type_name, schema, category_name=category_name),
                        },
                    )
                    template_total += 1

        for idx, (section, title, short_desc, popular) in enumerate(HELP_ARTICLES, start=1):
            help_slug = slugify(f"{section}-{title}")
            HelpArticle.objects.update_or_create(
                section=section,
                title=title,
                defaults={
                    "slug": help_slug,
                    "short_description": short_desc,
                    "content": short_desc,
                    "is_popular": popular,
                    "is_active": True,
                    "sort_order": idx,
                },
            )

        self.stdout.write(self.style.SUCCESS("Dashboard seed complete."))
        self.stdout.write(self.style.SUCCESS(f"Categories: {TemplateCategory.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Document types: {DocumentType.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Templates: {DocumentTemplate.objects.count()}"))
        self.stdout.write(self.style.SUCCESS(f"Help articles: {HelpArticle.objects.count()}"))
