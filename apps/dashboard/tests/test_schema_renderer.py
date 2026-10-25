from django.test import TestCase
from rest_framework.test import APIClient
from apps.user.models import User
from apps.dashboard.models import DocumentType, DocumentTemplate, TemplateCategory, CreditWallet
from apps.dashboard.views import (
    _build_dynamic_fields_from_content,
    _format_schema_field_node,
    _missing_required_template_fields,
    _validate_repeater_min_max_items,
    _render_document_body,
    _evaluate_single_condition,
    _is_field_visible_recursive,
    _build_schema_parent_map,
)


class SchemaRendererUnitTests(TestCase):
    def test_schema_is_single_source_of_truth_with_nested_group_and_repeater(self):
        schema = [
            {
                "name": "personal_info",
                "label": "Personal Info",
                "type": "group",
                "section": "PERSONAL",
                "position": "top",
                "order": 1,
                "children": [
                    {
                        "name": "full_name",
                        "label": "Full Name",
                        "type": "text",
                        "required": True,
                        "order": 1,
                    },
                    {
                        "name": "profile_photo",
                        "label": "Profile Photo",
                        "type": "image",
                        "required": False,
                        "order": 2,
                    },
                ],
            },
            {
                "name": "employment_history",
                "label": "Employment History",
                "type": "repeater",
                "section": "WORK",
                "position": "middle",
                "order": 2,
                "min_items": 1,
                "max_items": 3,
                "children": [
                    {
                        "name": "company_name",
                        "label": "Company Name",
                        "type": "text",
                        "required": True,
                        "order": 1,
                    },
                    {
                        "name": "relieving_letter",
                        "label": "Relieving Letter",
                        "type": "file",
                        "required": False,
                        "order": 2,
                    },
                ],
            },
        ]

        dynamic_fields = _build_dynamic_fields_from_content("", schema_definition=schema)

        # 2 top level fields: group and repeater
        self.assertEqual(len(dynamic_fields), 2)
        
        group_node = dynamic_fields[0]
        self.assertEqual(group_node["name"], "personal_info")
        self.assertEqual(group_node["type"], "group")
        self.assertEqual(group_node["option"], "group")
        self.assertEqual(group_node["position"], "top")
        self.assertEqual(group_node["section"], "PERSONAL")
        self.assertEqual(len(group_node["children"]), 2)
        self.assertEqual(group_node["children"][1]["type"], "image")
        self.assertEqual(group_node["children"][1]["option"], "file")

        repeater_node = dynamic_fields[1]
        self.assertEqual(repeater_node["name"], "employment_history")
        self.assertEqual(repeater_node["type"], "repeater")
        self.assertEqual(repeater_node["option"], "repeater")
        self.assertEqual(repeater_node["min_items"], 1)
        self.assertEqual(repeater_node["max_items"], 3)
        self.assertEqual(len(repeater_node["children"]), 2)
        self.assertEqual(repeater_node["children"][1]["type"], "file")
        self.assertEqual(repeater_node["children"][1]["option"], "file")

    def test_nested_conditions_parent_hidden_hides_children(self):
        schema = [
            {
                "name": "employment_type",
                "label": "Employment Type",
                "type": "select",
                "options": ["Permanent", "Contractor"],
            },
            {
                "name": "contractor_group",
                "label": "Contractor Details",
                "type": "group",
                "conditions": [{"field": "employment_type", "operator": "eq", "value": "Contractor"}],
                "children": [
                    {
                        "name": "daily_rate",
                        "label": "Daily Rate",
                        "type": "number",
                        "required": True,
                    }
                ],
            },
        ]

        parent_map = _build_schema_parent_map(schema)

        # When employment_type is Permanent
        form_data_perm = {"employment_type": "Permanent", "daily_rate": ""}
        contractor_group = schema[1]
        daily_rate_field = schema[1]["children"][0]

        self.assertFalse(_is_field_visible_recursive(contractor_group, form_data_perm, parent_map))
        self.assertFalse(_is_field_visible_recursive(daily_rate_field, form_data_perm, parent_map))

        # When employment_type is Contractor
        form_data_contract = {"employment_type": "Contractor", "daily_rate": "500"}
        self.assertTrue(_is_field_visible_recursive(contractor_group, form_data_contract, parent_map))
        self.assertTrue(_is_field_visible_recursive(daily_rate_field, form_data_contract, parent_map))

    def test_conditional_fields_inactive_when_hidden(self):
        category = TemplateCategory.objects.create(name="General Cat 1")
        doc_type = DocumentType.objects.create(
            category=category,
            name="Conditional Test Type",
            schema_definition=[
                {
                    "name": "include_guarantor",
                    "label": "Include Guarantor",
                    "type": "checkbox",
                },
                {
                    "name": "guarantor_name",
                    "label": "Guarantor Name",
                    "type": "text",
                    "required": True,
                    "conditions": [{"field": "include_guarantor", "operator": "eq", "value": True}],
                },
                {
                    "name": "guarantor_sig",
                    "label": "Guarantor Signature",
                    "type": "signature",
                    "required": True,
                    "conditions": [{"field": "include_guarantor", "operator": "eq", "value": True}],
                },
            ],
        )
        template = DocumentTemplate.objects.create(
            document_type=doc_type,
            name="Conditional Test Template",
            content_template="Guarantor: [Guarantor Name]",
        )

        # When include_guarantor is False
        form_data_no_guarantor = {"include_guarantor": False, "guarantor_name": ""}
        missing = _missing_required_template_fields(template, form_data_no_guarantor)
        self.assertEqual(missing, [])

        body = _render_document_body(template, form_data_no_guarantor)
        self.assertNotIn("Guarantor Name", body)

        # When include_guarantor is True
        form_data_with_guarantor_empty = {"include_guarantor": True, "guarantor_name": ""}
        missing_with = _missing_required_template_fields(template, form_data_with_guarantor_empty)
        self.assertIn("Guarantor Name", missing_with)
        self.assertIn("Guarantor Signature", missing_with)

    def test_repeater_min_max_validation(self):
        category = TemplateCategory.objects.create(name="General Cat 2")
        doc_type = DocumentType.objects.create(
            category=category,
            name="Repeater Test Type",
            schema_definition=[
                {
                    "name": "items",
                    "label": "Items",
                    "type": "repeater",
                    "min_items": 2,
                    "max_items": 4,
                    "children": [
                        {"name": "item_name", "label": "Item Name", "type": "text"}
                    ],
                }
            ],
        )
        template = DocumentTemplate.objects.create(
            document_type=doc_type,
            name="Repeater Test Template",
            content_template="Items: [items]",
        )

        # 0 items / empty form data -> required error
        errors_empty = _validate_repeater_min_max_items(template, {})
        self.assertEqual(len(errors_empty), 1)
        self.assertIn("is required", errors_empty[0])
        self.assertIn("at least 2 item(s)", errors_empty[0])

        # Empty list -> required error
        errors_empty_list = _validate_repeater_min_max_items(template, {"items": []})
        self.assertEqual(len(errors_empty_list), 1)
        self.assertIn("is required", errors_empty_list[0])

        # Blank/empty dicts inside list -> counts as 0 valid items, so required error
        errors_blank_items = _validate_repeater_min_max_items(template, {"items": [{}, {"item_name": "   "}]})
        self.assertEqual(len(errors_blank_items), 1)
        self.assertIn("is required", errors_blank_items[0])

        # 1 item -> error (min is 2)
        errors_1 = _validate_repeater_min_max_items(template, {"items": [{"item_name": "A"}]})
        self.assertEqual(len(errors_1), 1)
        self.assertIn("at least 2 item(s)", errors_1[0])
        self.assertIn("You provided 1", errors_1[0])

        # 2 items -> valid
        errors_2 = _validate_repeater_min_max_items(template, {"items": [{"item_name": "A"}, {"item_name": "B"}]})
        self.assertEqual(errors_2, [])

        # 4 items -> valid
        errors_4 = _validate_repeater_min_max_items(template, {"items": [{"item_name": "A"}, {"item_name": "B"}, {"item_name": "C"}, {"item_name": "D"}]})
        self.assertEqual(errors_4, [])

        # 5 items -> exceeds max_items (4)
        errors_5 = _validate_repeater_min_max_items(template, {"items": [{"item_name": f"Item {i}"} for i in range(5)]})
        self.assertEqual(len(errors_5), 1)
        self.assertIn("allows at most 4 item(s)", errors_5[0])
        self.assertIn("You provided 5", errors_5[0])

        # Test repeater with is_required=True and no min_items specified defaults min to 1
        doc_type_req = DocumentType.objects.create(
            category=category,
            name="Repeater Required Type",
            schema_definition=[
                {
                    "name": "qualifications",
                    "label": "Qualifications",
                    "type": "repeater",
                    "is_required": True,
                    "max_items": 3,
                    "children": [{"name": "title", "label": "Title", "type": "text"}],
                }
            ],
        )
        template_req = DocumentTemplate.objects.create(
            document_type=doc_type_req,
            name="Repeater Required Template",
            content_template="Q: [qualifications]",
        )
        errors_req_empty = _validate_repeater_min_max_items(template_req, {})
        self.assertEqual(len(errors_req_empty), 1)
        self.assertIn("is required", errors_req_empty[0])
        self.assertIn("at least 1 item(s)", errors_req_empty[0])

        errors_req_valid = _validate_repeater_min_max_items(template_req, {"qualifications": [{"title": "BSc"}]})
        self.assertEqual(errors_req_valid, [])

    def test_repeated_switching_mutually_exclusive_branches(self):
        category = TemplateCategory.objects.create(name="General Cat 3")
        doc_type = DocumentType.objects.create(
            category=category,
            name="Branch Test Type",
            schema_definition=[
                {
                    "name": "mode",
                    "label": "Mode",
                    "type": "select",
                    "options": ["A", "B"],
                },
                {
                    "name": "field_a",
                    "label": "Field A",
                    "type": "text",
                    "required": True,
                    "conditions": [{"field": "mode", "operator": "eq", "value": "A"}],
                },
                {
                    "name": "field_b",
                    "label": "Field B",
                    "type": "text",
                    "required": True,
                    "conditions": [{"field": "mode", "operator": "eq", "value": "B"}],
                },
            ],
        )
        template = DocumentTemplate.objects.create(
            document_type=doc_type,
            name="Branch Test Template",
            content_template="A: [Field A]\nB: [Field B]",
        )

        # Step 1: Mode A, field_a filled
        form_data = {"mode": "A", "field_a": "ValA", "field_b": "StaleB"}
        self.assertEqual(_missing_required_template_fields(template, form_data), [])
        body_a = _render_document_body(template, form_data)
        self.assertIn("ValA", body_a)
        self.assertNotIn("StaleB", body_a)

        # Step 2: Switch to Mode B, field_b filled
        form_data = {"mode": "B", "field_a": "StaleA", "field_b": "ValB"}
        self.assertEqual(_missing_required_template_fields(template, form_data), [])
        body_b = _render_document_body(template, form_data)
        self.assertIn("ValB", body_b)
        self.assertNotIn("StaleA", body_b)

        # Step 3: Switch back to Mode A
        form_data = {"mode": "A", "field_a": "NewA", "field_b": "StaleB"}
        self.assertEqual(_missing_required_template_fields(template, form_data), [])
        body_a2 = _render_document_body(template, form_data)
        self.assertIn("NewA", body_a2)
        self.assertNotIn("StaleB", body_a2)

    def test_deeply_nested_stress_schema(self):
        category = TemplateCategory.objects.create(name="Stress Test Cat")
        schema = [
            {
                "name": "personal_details",
                "label": "Personal Details",
                "type": "group",
                "section": "IDENTITY",
                "position": "top",
                "order": 1,
                "required": False,
                "children": [
                    {"name": "full_name", "label": "Full Name", "type": "text", "required": True, "order": 1},
                    {"name": "dob", "label": "Date of Birth", "type": "date", "required": True, "order": 2},
                    {"name": "email", "label": "Email Address", "type": "email", "required": True, "order": 3},
                    {"name": "phone", "label": "Phone Number", "type": "phone", "required": True, "order": 4},
                    {"name": "profile_photo", "label": "Profile Photo", "type": "image", "required": False, "order": 5},
                    {"name": "has_middle_name", "label": "Do you have a middle name?", "type": "checkbox", "required": False, "order": 6},
                    {
                        "name": "middle_name",
                        "label": "Middle Name",
                        "type": "text",
                        "required": True,
                        "order": 7,
                        "conditions": [{"field": "has_middle_name", "operator": "eq", "value": True}],
                    },
                    {
                        "name": "address_details",
                        "label": "Address Details",
                        "type": "group",
                        "section": "IDENTITY",
                        "position": "full",
                        "order": 8,
                        "required": False,
                        "children": [
                            {"name": "street_address", "label": "Street Address", "type": "textarea", "required": True, "order": 1},
                            {"name": "city", "label": "City", "type": "text", "required": True, "order": 2},
                            {"name": "postal_code", "label": "Postal Code", "type": "number", "required": True, "order": 3},
                            {"name": "is_international_address", "label": "Is International Address?", "type": "checkbox", "required": False, "order": 4},
                            {
                                "name": "country_code",
                                "label": "Country Code",
                                "type": "text",
                                "required": True,
                                "order": 5,
                                "conditions": [{"field": "is_international_address", "operator": "eq", "value": True}],
                            },
                        ],
                    },
                ],
            },
            {
                "name": "educational_qualifications",
                "label": "Educational Qualifications",
                "type": "repeater",
                "section": "SCOPE",
                "position": "middle",
                "order": 2,
                "min_items": 1,
                "max_items": 5,
                "required": False,
                "children": [
                    {"name": "degree_name", "label": "Degree Name", "type": "text", "required": True, "order": 1},
                    {"name": "institution", "label": "Institution Name", "type": "text", "required": True, "order": 2},
                    {"name": "passing_year", "label": "Passing Year", "type": "number", "required": True, "order": 3},
                    {"name": "has_certificate", "label": "Certificate Available?", "type": "checkbox", "required": False, "order": 4},
                    {
                        "name": "certificate_file",
                        "label": "Certificate File",
                        "type": "file",
                        "required": False,
                        "order": 5,
                        "conditions": [{"field": "has_certificate", "operator": "eq", "value": True}],
                    },
                    {
                        "name": "institution_contact_group",
                        "label": "Institution Contact Details",
                        "type": "group",
                        "section": "SCOPE",
                        "position": "full",
                        "order": 6,
                        "required": False,
                        "children": [
                            {"name": "verifier_name", "label": "Verifier Contact Name", "type": "text", "required": False, "order": 1},
                            {"name": "verifier_email", "label": "Verifier Email", "type": "email", "required": False, "order": 2},
                        ],
                    },
                ],
            },
            {
                "name": "requires_guarantor",
                "label": "Is Guarantor Required?",
                "type": "select",
                "section": "EXECUTION",
                "position": "left",
                "order": 3,
                "required": True,
                "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
            },
            {
                "name": "guarantor_details",
                "label": "Guarantor Information",
                "type": "group",
                "section": "EXECUTION",
                "position": "full",
                "order": 4,
                "required": False,
                "conditions": [{"field": "requires_guarantor", "operator": "eq", "value": "Yes"}],
                "children": [
                    {"name": "guarantor_full_name", "label": "Guarantor Full Name", "type": "text", "required": True, "order": 1},
                    {"name": "guarantor_phone", "label": "Guarantor Phone Number", "type": "phone", "required": True, "order": 2},
                    {"name": "guarantor_id_doc", "label": "Guarantor ID Document", "type": "file", "required": False, "order": 3},
                    {
                        "name": "guarantor_signature",
                        "label": "Guarantor Signature",
                        "type": "signature",
                        "section": "EXECUTION",
                        "position": "signature_area",
                        "order": 4,
                        "required": True,
                        "conditions": [{"field": "requires_guarantor", "operator": "eq", "value": "Yes"}],
                    },
                ],
            },
            {
                "name": "applicant_signature",
                "label": "Applicant Signature",
                "type": "signature",
                "section": "EXECUTION",
                "position": "signature_area",
                "order": 5,
                "required": True,
            },
        ]

        doc_type = DocumentType.objects.create(
            category=category,
            name="Stress Test Type",
            schema_definition=schema,
        )
        template = DocumentTemplate.objects.create(
            document_type=doc_type,
            name="Stress Test Template",
            content_template="Name: [full_name]\nGuarantor: [guarantor_full_name]",
        )

        dynamic_fields = _build_dynamic_fields_from_content("", schema_definition=schema)
        self.assertEqual(len(dynamic_fields), 5)

        # Test required field validation when guarantor is NO
        form_data_no_guarantor = {
            "full_name": "John Doe",
            "dob": "1995-01-01",
            "email": "john@example.com",
            "phone": "1234567890",
            "has_middle_name": False,
            "street_address": "123 St",
            "city": "Dhaka",
            "postal_code": "1200",
            "is_international_address": False,
            "educational_qualifications": [
                {
                    "degree_name": "BSc CS",
                    "institution": "University A",
                    "passing_year": 2020,
                    "has_certificate": False,
                }
            ],
            "requires_guarantor": "No",
            "applicant_signature": "SigData",
        }

        missing_no_g = _missing_required_template_fields(template, form_data_no_guarantor)
        self.assertEqual(missing_no_g, [])

        # Test required field validation when guarantor is YES but guarantor details missing
        form_data_yes_g_missing = dict(form_data_no_guarantor)
        form_data_yes_g_missing["requires_guarantor"] = "Yes"
        missing_yes_g = _missing_required_template_fields(template, form_data_yes_g_missing)
        self.assertIn("Guarantor Full Name", missing_yes_g)
        self.assertIn("Guarantor Phone Number", missing_yes_g)
        self.assertIn("Guarantor Signature", missing_yes_g)

    def test_employee_onboarding_form_schema_rendering_and_validation(self):
        category = TemplateCategory.objects.create(name="Onboarding Category")
        schema = [
            {
                "name": "personal_details",
                "label": "Personal Details",
                "type": "group",
                "section": "PERSONAL_INFO",
                "position": "top",
                "order": 1,
                "children": [
                    {"name": "first_name", "label": "First Name", "type": "text", "required": True, "order": 1},
                    {"name": "last_name", "label": "Last Name", "type": "text", "required": True, "order": 2},
                    {"name": "dob", "label": "Date of Birth", "type": "date", "required": False, "order": 3},
                    {"name": "email", "label": "Email Address", "type": "email", "required": True, "order": 4},
                    {"name": "phone", "label": "Phone Number", "type": "phone", "required": False, "order": 5},
                    {"name": "employee_photo", "label": "Employee Photo", "type": "image", "required": True, "order": 6},
                    {
                        "name": "address_info",
                        "label": "Address Information",
                        "type": "group",
                        "order": 7,
                        "children": [
                            {
                                "name": "address_type",
                                "label": "Address Type",
                                "type": "select",
                                "required": True,
                                "order": 1,
                                "options": ["present", "permanent"]
                            },
                            {
                                "name": "present_address_group",
                                "label": "Present Address",
                                "type": "group",
                                "order": 2,
                                "conditions": [
                                    {
                                        "field": "personal_details.address_info.address_type",
                                        "operator": "eq",
                                        "value": "present"
                                    }
                                ],
                                "children": [
                                    {"name": "village", "label": "Village Name", "type": "text", "required": True, "order": 1},
                                    {"name": "district", "label": "District", "type": "text", "required": True, "order": 2},
                                    {"name": "thana", "label": "Thana", "type": "text", "required": False, "order": 3},
                                    {
                                        "name": "present_contact_info",
                                        "label": "Present Contact Information",
                                        "type": "group",
                                        "order": 4,
                                        "children": [
                                            {"name": "present_phone", "label": "Present Phone", "type": "phone", "required": False, "order": 1},
                                            {"name": "present_email", "label": "Present Email", "type": "email", "required": False, "order": 2}
                                        ]
                                    }
                                ]
                            },
                            {
                                "name": "permanent_address_group",
                                "label": "Permanent Address",
                                "type": "group",
                                "order": 3,
                                "conditions": [
                                    {
                                        "field": "personal_details.address_info.address_type",
                                        "operator": "eq",
                                        "value": "permanent"
                                    }
                                ],
                                "children": [
                                    {"name": "address_name", "label": "Address Name", "type": "text", "required": True, "order": 1},
                                    {"name": "district", "label": "District", "type": "text", "required": True, "order": 2},
                                    {"name": "upazila", "label": "Upazila", "type": "text", "required": False, "order": 3},
                                    {
                                        "name": "permanent_contact_info",
                                        "label": "Permanent Contact Information",
                                        "type": "group",
                                        "order": 4,
                                        "children": [
                                            {"name": "permanent_phone", "label": "Permanent Phone", "type": "phone", "required": False, "order": 1},
                                            {"name": "permanent_email", "label": "Permanent Email", "type": "email", "required": False, "order": 2}
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "name": "has_previous_experience",
                "label": "Previous Work Experience",
                "type": "checkbox",
                "section": "WORK_HISTORY",
                "position": "middle",
                "order": 2
            },
            {
                "name": "previous_company_name",
                "label": "Previous Company Name",
                "type": "text",
                "required": True,
                "section": "WORK_HISTORY",
                "position": "middle",
                "order": 3,
                "conditions": [
                    {
                        "field": "has_previous_experience",
                        "operator": "eq",
                        "value": True
                    }
                ]
            },
            {
                "name": "educational_qualifications",
                "label": "Educational Qualifications",
                "type": "repeater",
                "section": "EDUCATION",
                "position": "middle",
                "order": 4,
                "min_items": 1,
                "max_items": 5,
                "children": [
                    {"name": "degree_name", "label": "Degree Name", "type": "text", "required": True, "order": 1},
                    {"name": "institution_name", "label": "Institution Name", "type": "text", "required": True, "order": 2},
                    {"name": "completion_year", "label": "Year of Completion", "type": "number", "required": False, "order": 3},
                    {
                        "name": "additional_education_details",
                        "label": "Additional Education Details",
                        "type": "group",
                        "order": 4,
                        "children": [
                            {"name": "gpa", "label": "GPA / Grade", "type": "number", "required": False, "order": 1},
                            {"name": "has_honors", "label": "Graduated with Honors", "type": "checkbox", "required": False, "order": 2},
                            {
                                "name": "honors_certificate",
                                "label": "Honors Certificate Document",
                                "type": "file",
                                "required": True,
                                "order": 3,
                                "conditions": [
                                    {
                                        "field": "has_honors",
                                        "operator": "eq",
                                        "value": True
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                "name": "approval_document",
                "label": "Approval Document",
                "type": "file",
                "required": True,
                "section": "APPROVALS",
                "position": "bottom",
                "order": 5
            },
            {
                "name": "requires_manager_approval",
                "label": "Requires Manager Approval",
                "type": "checkbox",
                "section": "APPROVALS",
                "position": "bottom",
                "order": 6
            },
            {
                "name": "manager_approval_group",
                "label": "Manager Approval",
                "type": "group",
                "section": "APPROVALS",
                "position": "signature_area",
                "order": 7,
                "conditions": [
                    {
                        "field": "requires_manager_approval",
                        "operator": "eq",
                        "value": True
                    }
                ],
                "children": [
                    {"name": "manager_name", "label": "Manager Name", "type": "text", "required": True, "order": 1},
                    {"name": "manager_signature", "label": "Manager Signature", "type": "signature", "required": True, "order": 2}
                ]
            }
        ]

        doc_type = DocumentType.objects.create(
            category=category,
            name="Employee Onboarding Type",
            schema_definition=schema
        )
        template = DocumentTemplate.objects.create(
            document_type=doc_type,
            name="Employee Onboarding Template",
            content_template="Employee: [first_name] [last_name]"
        )

        # Test Present Address Branch
        present_form_data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "employee_photo": "photo_data.jpg",
            "personal_details": {
                "address_info": {
                    "address_type": "present",
                    "present_address_group": {
                        "village": "Green Valley",
                        "district": "Dhaka",
                    }
                }
            },
            "has_previous_experience": False,
            "educational_qualifications": [
                {
                    "degree_name": "BSc Software Engineering",
                    "institution_name": "Tech University",
                    "completion_year": 2022
                }
            ],
            "approval_document": "approval.pdf",
            "requires_manager_approval": False
        }

        # Present branch should pass without requiring permanent branch fields or manager fields
        missing_present = _missing_required_template_fields(template, present_form_data)
        self.assertEqual(missing_present, [])

        # Switch to Permanent Address Branch
        permanent_form_data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "employee_photo": "photo_data.jpg",
            "personal_details": {
                "address_info": {
                    "address_type": "permanent",
                    "permanent_address_group": {
                        "address_name": "House 42, Road 7",
                        "district": "Chittagong"
                    }
                }
            },
            "has_previous_experience": False,
            "educational_qualifications": [
                {
                    "degree_name": "BSc Software Engineering",
                    "institution_name": "Tech University",
                    "completion_year": 2022
                }
            ],
            "approval_document": "approval.pdf",
            "requires_manager_approval": False
        }

        # Permanent branch should pass without requiring present branch fields
        missing_permanent = _missing_required_template_fields(template, permanent_form_data)
        self.assertEqual(missing_permanent, [])

    def test_select_option_nested_children(self):
        from apps.dashboard.serializers import DocumentTypeSerializer, sanitize_schema_fields

        schema = [
            {
                "name": "requires_guarantor",
                "label": "Is Guarantor Required?",
                "type": "select",
                "is_required": False,
                "options": [
                    {
                        "label": "Yes",
                        "value": "Yes",
                        "children": [
                            {
                                "name": "guarantor_details",
                                "label": "Guarantor Details",
                                "type": "group",
                                "required": False,
                                "order": 2,
                                "children": [
                                    {
                                        "name": "guarantor_name",
                                        "label": "Guarantor Name",
                                        "type": "text",
                                        "required": False,
                                        "order": 1
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "label": "No",
                        "value": "No"
                    }
                ]
            }
        ]

        sanitized = sanitize_schema_fields(schema)
        yes_opt = sanitized[0]["options"][0]
        self.assertEqual(yes_opt["value"], "Yes")
        self.assertEqual(len(yes_opt["children"]), 1)
        g_details = yes_opt["children"][0]
        self.assertEqual(g_details["name"], "guarantor_details")
        self.assertNotIn("required", g_details)
        self.assertEqual(g_details["is_required"], False)
        self.assertEqual(g_details["is_visible"], True)
        self.assertEqual(g_details["children"][0]["is_required"], False)
        self.assertNotIn("required", g_details["children"][0])

        # Test dynamic fields formatter
        dynamic_fields = _build_dynamic_fields_from_content("", schema_definition=sanitized)
        self.assertEqual(len(dynamic_fields), 1)
        df_yes_opt = dynamic_fields[0]["options"][0]
        self.assertEqual(len(df_yes_opt["children"]), 1)
        self.assertEqual(df_yes_opt["children"][0]["name"], "guarantor_details")

    def test_repeater_min_max_document_generation_api(self):
        client = APIClient()
        user = User.objects.create_user(email="doc_gen_user@example.com", password="password123")
        client.force_authenticate(user=user)

        wallet, _ = CreditWallet.objects.get_or_create(user=user)
        wallet.credits_used = 0
        wallet.save()

        category = TemplateCategory.objects.create(name="Gen Cat API")
        doc_type = DocumentType.objects.create(
            category=category,
            name="API Doc Type",
            schema_definition=[
                {
                    "name": "educational_qualifications",
                    "label": "Educational Qualifications",
                    "type": "repeater",
                    "min_items": 1,
                    "max_items": 3,
                    "children": [
                        {"name": "degree", "label": "Degree", "type": "text", "is_required": True}
                    ],
                }
            ],
        )
        template = DocumentTemplate.objects.create(
            document_type=doc_type,
            name="API Test Template",
            content_template="Qualifications: [educational_qualifications]",
        )

        # 1. Missing repeater data (empty dict) -> 400 Bad Request with required error
        resp_empty = client.post(
            "/api/documents/generate/",
            {
                "template_id": template.id,
                "name": "Doc Empty",
                "form_data": {},
            },
            format="json",
        )
        self.assertEqual(resp_empty.status_code, 400)
        self.assertIn("is required", str(resp_empty.data))
        self.assertIn("at least 1 item(s)", str(resp_empty.data))

        # 2. Blank repeater row [{}] -> 400 Bad Request with required error
        resp_blank = client.post(
            "/api/documents/generate/",
            {
                "template_id": template.id,
                "name": "Doc Blank",
                "form_data": {"educational_qualifications": [{}]},
            },
            format="json",
        )
        self.assertEqual(resp_blank.status_code, 400)
        self.assertIn("is required", str(resp_blank.data))

        # 3. Over max_items (4 items when max is 3) -> 400 Bad Request with max error
        resp_over = client.post(
            "/api/documents/generate/",
            {
                "template_id": template.id,
                "name": "Doc Over",
                "form_data": {
                    "educational_qualifications": [
                        {"degree": "Item 1"},
                        {"degree": "Item 2"},
                        {"degree": "Item 3"},
                        {"degree": "Item 4"},
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(resp_over.status_code, 400)
        self.assertIn("allows at most 3 item(s)", str(resp_over.data))
        self.assertIn("You provided 4", str(resp_over.data))

        # 4. Valid repeater items (1 item within 1 to 3) -> 201 Created
        resp_valid = client.post(
            "/api/documents/generate/",
            {
                "template_id": template.id,
                "name": "Doc Valid",
                "form_data": {
                    "educational_qualifications": [{"degree": "BSc Computer Science"}]
                },
            },
            format="json",
        )
        self.assertEqual(resp_valid.status_code, 201)
        self.assertIn("rendered_content", resp_valid.data.get("data", {}))

    def test_proper_short_error_message_for_missing_required_fields(self):
        user = User.objects.create_user(
            email="msg_user@example.com",
            password="StrongPassword123!",
        )
        client = APIClient()
        client.force_authenticate(user=user)

        category = TemplateCategory.objects.create(name="Short Msg Cat")
        doc_type = DocumentType.objects.create(
            category=category,
            name="Short Msg Type",
            schema_definition=[
                {
                    "name": "educational_qualifications",
                    "label": "Educational Qualifications",
                    "type": "repeater",
                    "min_items": 1,
                    "max_items": 5,
                    "children": [
                        {"name": "degree_name", "label": "Degree Name", "type": "text", "is_required": True},
                        {"name": "institution_name", "label": "Institution Name", "type": "text", "is_required": True},
                    ],
                }
            ],
        )
        template = DocumentTemplate.objects.create(
            document_type=doc_type,
            name="Short Msg Template",
            content_template="Qualifications: [educational_qualifications]",
        )

        # User added 1 repeater entry but left Degree Name and Institution Name blank
        resp = client.post(
            "/api/documents/generate/",
            {
                "template_id": template.id,
                "name": "Short Msg Doc",
                "form_data": {
                    "educational_qualifications": [
                        {"degree_name": "", "institution_name": ""}
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        # Main message must be proper and short, pointing directly to the required problem
        self.assertEqual(resp.data.get("message"), "Degree Name is required.")
        self.assertNotEqual(resp.data.get("message"), "Missing required repeater data.")
        # Form data errors list must list the specific required missing fields
        errors = resp.data.get("errors", {}).get("form_data", [])
        self.assertIn("Degree Name is required.", errors)
        self.assertIn("Institution Name is required.", errors)

    def test_no_legacy_required_key_in_schema_response(self):
        from apps.dashboard.serializers import DocumentTemplateSerializer
        category = TemplateCategory.objects.create(name="Clean Schema Cat")
        doc_type = DocumentType.objects.create(
            category=category,
            name="Clean Schema Type",
            schema_definition=[
                {
                    "name": "test_field",
                    "label": "Test Field",
                    "type": "text",
                    "required": False,
                    "is_required": False,
                }
            ],
        )
        template = DocumentTemplate.objects.create(
            document_type=doc_type,
            name="Clean Schema Template",
            content_template="Field: [test_field]",
        )

        serializer = DocumentTemplateSerializer(template)
        data = serializer.data

        def assert_no_legacy_required(obj):
            if isinstance(obj, dict):
                self.assertNotIn("required", obj)
                for v in obj.values():
                    assert_no_legacy_required(v)
            elif isinstance(obj, list):
                for item in obj:
                    assert_no_legacy_required(item)

        assert_no_legacy_required(data)

    def test_richtext_field_schema_metadata(self):
        category = TemplateCategory.objects.create(name="Rich Schema Cat")
        doc_type = DocumentType.objects.create(
            category=category,
            name="Rich Schema Type",
            schema_definition=[
                {
                    "name": "project_scope",
                    "label": "Project Scope",
                    "type": "richtext",
                    "is_required": False,
                }
            ],
        )
        template = DocumentTemplate.objects.create(
            document_type=doc_type,
            name="Rich Schema Template",
            content_template="Scope: [project_scope]",
        )

        user = User.objects.create_user(
            email="rich_schema_user@example.com",
            password="StrongPassword123!",
        )
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.get(f"/api/templates/form-schema/?template_id={template.id}")
        self.assertEqual(resp.status_code, 200)
        fields = resp.data.get("data", {}).get("fields", [])
        self.assertEqual(len(fields), 1)
        rich_field = fields[0]
        self.assertEqual(rich_field["type"], "richtext")
        self.assertEqual(rich_field["option"], "richtext")
        self.assertIn("formatting_controls", rich_field)
        controls = rich_field["formatting_controls"]
        self.assertIn("bold", controls)
        self.assertIn("italic", controls)
        self.assertIn("underline", controls)

    def test_richtext_html_preserved_in_render_text_as_html(self):
        from apps.dashboard.serializers import render_text_as_html

        html_input = "<p>This is <b>bold</b>, <i>italic</i>, and <u>underlined</u> text.</p>"
        result = render_text_as_html(html_input)
        self.assertIn("<b>bold</b>", result)
        self.assertIn("<i>italic</i>", result)
        self.assertIn("<u>underlined</u>", result)
        self.assertNotIn("&lt;b&gt;", result)

        inline_input = "Paragraph with <strong>bold</strong> and <em>emphasis</em>."
        result_inline = render_text_as_html(inline_input)
        self.assertIn("<strong>bold</strong>", result_inline)
        self.assertIn("<em>emphasis</em>", result_inline)

    def test_richtext_document_generation_and_pdf(self):
        from apps.dashboard.models import GeneratedDocument
        user = User.objects.create_user(
            email="richtext_gen_user@example.com",
            password="StrongPassword123!",
        )
        client = APIClient()
        client.force_authenticate(user=user)

        wallet, _ = CreditWallet.objects.get_or_create(user=user)
        wallet.credits_used = 0
        wallet.save()

        category = TemplateCategory.objects.create(name="Rich Gen Cat")
        doc_type = DocumentType.objects.create(
            category=category,
            name="Rich Gen Type",
            schema_definition=[
                {
                    "name": "scope_details",
                    "label": "Scope Details",
                    "type": "richtext",
                    "is_required": False,
                }
            ],
        )
        template = DocumentTemplate.objects.create(
            document_type=doc_type,
            name="Rich Gen Template",
            content_template="Agreement Details:\n[scope_details]",
        )

        resp = client.post(
            "/api/documents/generate/",
            {
                "template_id": template.id,
                "name": "Rich Text Document",
                "form_data": {
                    "scope_details": "<p>Scope includes <b>full architecture</b> and <u>daily reports</u>.</p>"
                },
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        rendered = resp.data.get("data", {}).get("rendered_content", "")
        self.assertIn("<b>full architecture</b>", rendered)
        self.assertIn("<u>daily reports</u>", rendered)
        self.assertNotIn("&lt;b&gt;", rendered)

        # Verify PDF build succeeded
        doc_id = resp.data.get("data", {}).get("id")
        doc = GeneratedDocument.objects.get(id=doc_id)
        from apps.dashboard.pdf_service import build_pdf_for_document
        abs_path, rel_path = build_pdf_for_document(doc)
        import os
        self.assertTrue(os.path.exists(abs_path))

    def test_repeater_min_items_entry_fields_required(self):
        category = TemplateCategory.objects.create(name="Employment Category")
        schema = [
            {
                "name": "employment_history",
                "label": "Employment History",
                "type": "repeater",
                "min_items": 1,
                "max_items": 3,
                "is_required": False,  # Should be promoted because min_items >= 1
                "children": [
                    {"name": "company_name", "label": "Company Name", "type": "text"},
                    {"name": "job_title", "label": "Job Title", "type": "text"},
                    {"name": "employment_period", "label": "Employment Period", "type": "checkbox"},
                    {"name": "responsibilities", "label": "Responsibilities", "type": "textarea"},
                    {"name": "supervisor_contact", "label": "Supervisor Contact", "type": "checkbox"},
                ],
            }
        ]

        # 1. Test schema formatting for frontend:
        # Core fields must be is_required=True and is_visible=True, checkboxes must stay is_required=False
        formatted_node = _format_schema_field_node(schema[0])
        self.assertTrue(formatted_node["is_required"])
        self.assertEqual(formatted_node["min_items"], 1)
        ch_map = {ch["name"]: ch for ch in formatted_node["children"]}
        self.assertTrue(ch_map["company_name"]["is_required"])
        self.assertTrue(ch_map["company_name"]["is_visible"])
        self.assertTrue(ch_map["job_title"]["is_required"])
        self.assertTrue(ch_map["job_title"]["is_visible"])
        self.assertTrue(ch_map["responsibilities"]["is_required"])
        self.assertTrue(ch_map["responsibilities"]["is_visible"])
        self.assertFalse(ch_map["employment_period"]["is_required"])
        self.assertFalse(ch_map["supervisor_contact"]["is_required"])

        doc_type = DocumentType.objects.create(
            category=category,
            name="Employment Doc Type",
            schema_definition=schema,
        )
        template = DocumentTemplate.objects.create(
            document_type=doc_type,
            name="Employment History Template",
            content_template="Employment: [employment_history]",
        )

        # 2. Test partial Entry #1 (only company_name provided, missing job_title and responsibilities)
        partial_entry_1 = {
            "employment_history": [{"company_name": "Carrillo and Pearson Trading"}]
        }
        missing_1 = _missing_required_template_fields(template, partial_entry_1)
        self.assertIn("Job Title", missing_1)
        self.assertIn("Responsibilities", missing_1)
        self.assertNotIn("Company Name", missing_1)

        # 3. Test complete Entry #1 (all required fields provided)
        complete_entry_1 = {
            "employment_history": [
                {
                    "company_name": "Carrillo and Pearson Trading",
                    "job_title": "Developer",
                    "responsibilities": "Writing backend code",
                }
            ]
        }
        missing_complete_1 = _missing_required_template_fields(template, complete_entry_1)
        self.assertEqual(missing_complete_1, [])

        # 4. Test 2 entries where Entry #2 is empty / partially filled
        partial_entry_2 = {
            "employment_history": [
                {
                    "company_name": "Carrillo and Pearson Trading",
                    "job_title": "Developer",
                    "responsibilities": "Writing backend code",
                },
                {
                    "company_name": "",
                    "job_title": "",
                    "responsibilities": "",
                },
            ]
        }
        missing_2 = _missing_required_template_fields(template, partial_entry_2)
        self.assertIn("Company Name (Entry #2)", missing_2)
        self.assertIn("Job Title (Entry #2)", missing_2)
        self.assertIn("Responsibilities (Entry #2)", missing_2)
        self.assertNotIn("Company Name (Entry #1)", missing_2)

        # 5. Test 2 entries both complete
        complete_entry_2 = {
            "employment_history": [
                {
                    "company_name": "Carrillo and Pearson Trading",
                    "job_title": "Developer",
                    "responsibilities": "Writing backend code",
                },
                {
                    "company_name": "Acme Corporation",
                    "job_title": "Engineering Lead",
                    "responsibilities": "Leading team",
                },
            ]
        }
        missing_complete_2 = _missing_required_template_fields(template, complete_entry_2)
        self.assertEqual(missing_complete_2, [])

        # 6. Test sanitize_schema_fields promotes repeater children
        from apps.dashboard.serializers import sanitize_schema_fields
        sanitized = sanitize_schema_fields([dict(schema[0])])
        san_ch_map = {ch["name"]: ch for ch in sanitized[0]["children"]}
        self.assertTrue(sanitized[0]["is_required"])
        self.assertTrue(san_ch_map["company_name"]["is_required"])
        self.assertTrue(san_ch_map["job_title"]["is_required"])
        self.assertFalse(san_ch_map["employment_period"]["is_required"])

        # 7. Test validate_output promotes repeater children
        from apps.ai_document_assistant.services.validators import validate_output
        validated_data = {
            "schema_definition": [dict(schema[0])],
            "content_template": "Test: [employment_history]",
            "base_content": {},
        }
        validate_output(validated_data, action="generate")
        val_ch_map = {ch["name"]: ch for ch in validated_data["schema_definition"][0]["children"]}
        self.assertTrue(validated_data["schema_definition"][0]["is_required"])
        self.assertTrue(val_ch_map["company_name"]["is_required"])
        self.assertTrue(val_ch_map["job_title"]["is_required"])
        self.assertFalse(val_ch_map["employment_period"]["is_required"])

    def test_image_and_file_rendering_in_document_preview(self):
        category = TemplateCategory.objects.create(name="Image Cat")
        schema = [
            {
                "name": "personal_details",
                "label": "Personal Details",
                "type": "group",
                "children": [
                    {"name": "full_name", "label": "Full Name", "type": "text"},
                    {"name": "profile_photo", "label": "Profile Photo", "type": "image"},
                    {"name": "id_card", "label": "ID Card", "type": "file"},
                ],
            }
        ]
        doc_type = DocumentType.objects.create(
            name="Image Test Type",
            category=category,
            schema_definition=schema,
        )
        template = DocumentTemplate.objects.create(
            name="Image Test Template",
            document_type=doc_type,
            content_template="Name: [Full Name]\nPhoto: [Profile Photo]\nID: [ID Card]",
        )

        form_data = {
            "personal_details": {
                "full_name": "Al Amin Islam",
                "profile_photo": "/media/document_uploads/photo.jpg",
                "id_card": "/media/document_uploads/id.pdf",
            }
        }

        rendered = _render_document_body(template, form_data)

        # 1. Full name must be plain text and NOT a document link
        self.assertIn("Name: Al Amin Islam", rendered)
        self.assertNotIn('<a href="Al Amin Islam"', rendered)

        # 2. Profile photo must be rendered as an img tag
        self.assertIn('<img src="/media/document_uploads/photo.jpg"', rendered)

        # 3. ID Card must be rendered as a document link
        self.assertIn('<a href="/media/document_uploads/id.pdf"', rendered)
        self.assertIn('View Attached Document', rendered)

    def test_generate_document_api_with_file_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        user = User.objects.create_user(
            email="upload_test_user@example.com",
            password="StrongPassword123!",
        )
        wallet, _ = CreditWallet.objects.get_or_create(user=user)
        wallet.credits_used = 0
        wallet.save()

        category = TemplateCategory.objects.create(name="Upload Cat")
        schema = [
            {
                "name": "personal_details",
                "label": "Personal Details",
                "type": "group",
                "children": [
                    {"name": "full_name", "label": "Full Name", "type": "text", "is_required": True},
                    {"name": "profile_photo", "label": "Profile Photo", "type": "image", "is_required": False},
                ],
            }
        ]
        doc_type = DocumentType.objects.create(
            name="Upload Doc Type",
            category=category,
            schema_definition=schema,
        )
        template = DocumentTemplate.objects.create(
            name="Upload Doc Template",
            document_type=doc_type,
            content_template="Candidate: [Full Name]\nPicture: [Profile Photo]",
        )

        import io
        from PIL import Image
        img_buffer = io.BytesIO()
        test_img = Image.new("RGB", (20, 20), color="blue")
        test_img.save(img_buffer, format="PNG")
        uploaded_file = SimpleUploadedFile(
            "my_avatar.png",
            img_buffer.getvalue(),
            content_type="image/png"
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            "/api/documents/generate/",
            {
                "template_id": template.id,
                "name": "Test Upload Generation",
                "form_data": '{"personal_details": {"full_name": "Al Amin"}}',
                "profile_photo": uploaded_file,
            },
            format="multipart"
        )

        self.assertEqual(response.status_code, 201)
        resp_data = response.json()["data"]
        rendered_content = resp_data["rendered_content"]

        # Picture must contain <img> tag with the saved media path
        self.assertIn("<img", rendered_content)
        self.assertIn("/media/document_uploads/", rendered_content)
        self.assertIn("Candidate: Al Amin", rendered_content)

    def test_schema_placeholder_and_width_enforcement(self):
        """
        Verify that placeholder and width fields are properly generated and retained
        on parent containers (group/repeater) and child input fields.
        Also verify that if position is missing, it defaults to width='full'.
        """
        from apps.dashboard.serializers import sanitize_schema_fields
        from apps.dashboard.views import _format_schema_field_node
        from apps.ai_document_assistant.services.validators import validate_output

        raw_schema = [
            {
                "name": "personal_details",
                "label": "Personal Details",
                "type": "group",
                "section": "IDENTITY",
                "position": "top",
                "order": 1,
                "children": [
                    {
                        "name": "full_name",
                        "label": "Full Name",
                        "type": "text",
                        "order": 1,
                    },
                    {
                        "name": "email",
                        "label": "Email Address",
                        "type": "email",
                        "position": "left",
                        "order": 2,
                    },
                ],
            }
        ]

        # 1. Test sanitize_schema_fields adds placeholder and width
        sanitized = sanitize_schema_fields(raw_schema)
        parent = sanitized[0]
        self.assertIn("placeholder", parent)
        self.assertIn("personal and contact details", parent["placeholder"])
        self.assertEqual(parent["width"], "full")
        self.assertEqual(parent["position"], "top")

        child_full_name = parent["children"][0]
        self.assertIn("placeholder", child_full_name)
        self.assertEqual(child_full_name["placeholder"], "e.g., John Smith")
        # Position was not specified -> width defaults to full
        self.assertEqual(child_full_name["width"], "full")
        self.assertEqual(child_full_name["position"], "full")

        child_email = parent["children"][1]
        self.assertEqual(child_email["placeholder"], "e.g., john.smith@example.com")
        # Position was left -> width is half
        self.assertEqual(child_email["width"], "half")
        self.assertEqual(child_email["position"], "left")

        # 2. Test _format_schema_field_node formats placeholder and width
        formatted_parent = _format_schema_field_node(raw_schema[0])
        self.assertIn("placeholder", formatted_parent)
        self.assertEqual(formatted_parent["width"], "full")
        formatted_child = formatted_parent["children"][0]
        self.assertEqual(formatted_child["placeholder"], "e.g., John Smith")
        self.assertEqual(formatted_child["width"], "full")

        # 3. Test validate_output keeps and populates placeholder and width
        ai_data = {
            "schema_definition": raw_schema,
            "content_template": "Name: [Full Name], Email: [Email Address]",
            "base_content": {"document_type": "Test Doc", "required_fields": []},
        }
        validated = validate_output(ai_data)
        val_schema = validated["schema_definition"]
        self.assertIn("placeholder", val_schema[0])
        self.assertIn("width", val_schema[0])
        self.assertIn("placeholder", val_schema[0]["children"][0])
        self.assertIn("width", val_schema[0]["children"][0])







