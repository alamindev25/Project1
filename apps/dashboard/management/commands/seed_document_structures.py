"""
Management command to seed reusable document structures.
Creates base structures for Legal, Contract, and Financial documents.
"""
import json
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.dashboard.models import DocumentStructure, DocumentSchema


class Command(BaseCommand):
    help = 'Seed professional document structures for different document types'

    def create_structure(self, structure_data):
        """Create or update a document structure."""
        name = structure_data['name']
        structure_type = structure_data['structure_type']
        
        structure, created = DocumentStructure.objects.update_or_create(
            slug=slugify(f"{structure_type}-{name}"),
            defaults={
                'structure_type': structure_type,
                'name': name,
                'description': structure_data.get('description', ''),
                'has_header': structure_data.get('has_header', True),
                'has_footer': structure_data.get('has_footer', True),
                'has_page_numbers': structure_data.get('has_page_numbers', True),
                'has_signature_section': structure_data.get('has_signature_section', False),
                'has_date_field': structure_data.get('has_date_field', True),
                'header_height_mm': structure_data.get('header_height_mm', 30),
                'footer_height_mm': structure_data.get('footer_height_mm', 20),
                'left_margin_mm': structure_data.get('left_margin_mm', 20),
                'right_margin_mm': structure_data.get('right_margin_mm', 20),
                'top_margin_mm': structure_data.get('top_margin_mm', 20),
                'bottom_margin_mm': structure_data.get('bottom_margin_mm', 20),
                'line_spacing': structure_data.get('line_spacing', 1.15),
                'logo_width_mm': structure_data.get('logo_width_mm', 40),
                'logo_position': structure_data.get('logo_position', 'top_left'),
                'is_active': True,
            }
        )
        
        # Create or update schema if provided
        if 'schema' in structure_data:
            DocumentSchema.objects.update_or_create(
                structure=structure,
                defaults={'fields_definition': structure_data['schema']}
            )
        
        status = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"[OK] {status}: {structure_type.title()} - {name}"))
        return structure

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Seeding document structures...\n"))

        # Legal Agreements Structure
        legal_structure = {
            'structure_type': 'legal',
            'name': 'Legal Agreement Template',
            'description': 'Professional legal document structure with signature lines',
            'has_header': True,
            'has_footer': True,
            'has_page_numbers': True,
            'has_signature_section': True,
            'has_date_field': True,
            'header_height_mm': 40,
            'footer_height_mm': 25,
            'left_margin_mm': 25,
            'right_margin_mm': 25,
            'top_margin_mm': 25,
            'bottom_margin_mm': 25,
            'line_spacing': 1.5,
            'logo_width_mm': 50,
            'logo_position': 'top_left',
            'schema': [
                {
                    'name': 'parties',
                    'label': 'Parties Involved',
                    'type': 'textarea',
                    'required': True,
                    'order': 1,
                    'placeholder': 'Enter names of all parties to this agreement'
                },
                {
                    'name': 'agreement_date',
                    'label': 'Agreement Date',
                    'type': 'date',
                    'required': True,
                    'order': 2
                },
                {
                    'name': 'terms_summary',
                    'label': 'Terms Summary',
                    'type': 'textarea',
                    'required': True,
                    'order': 3,
                    'placeholder': 'Briefly summarize the key terms'
                },
                {
                    'name': 'effective_date',
                    'label': 'Effective Date',
                    'type': 'date',
                    'required': False,
                    'order': 4
                },
                {
                    'name': 'duration',
                    'label': 'Duration',
                    'type': 'text',
                    'required': False,
                    'order': 5,
                    'placeholder': 'e.g., 1 year, 2 years, ongoing'
                }
            ]
        }

        # Contracts Structure
        contract_structure = {
            'structure_type': 'contract',
            'name': 'Service Contract Template',
            'description': 'Professional contract document with pricing and terms',
            'has_header': True,
            'has_footer': True,
            'has_page_numbers': True,
            'has_signature_section': True,
            'has_date_field': True,
            'header_height_mm': 35,
            'footer_height_mm': 20,
            'left_margin_mm': 20,
            'right_margin_mm': 20,
            'top_margin_mm': 20,
            'bottom_margin_mm': 20,
            'line_spacing': 1.2,
            'logo_width_mm': 45,
            'logo_position': 'top_left',
            'schema': [
                {
                    'name': 'service_provider',
                    'label': 'Service Provider',
                    'type': 'text',
                    'required': True,
                    'order': 1
                },
                {
                    'name': 'client_name',
                    'label': 'Client Name',
                    'type': 'text',
                    'required': True,
                    'order': 2
                },
                {
                    'name': 'service_description',
                    'label': 'Service Description',
                    'type': 'textarea',
                    'required': True,
                    'order': 3
                },
                {
                    'name': 'contract_value',
                    'label': 'Contract Value',
                    'type': 'currency',
                    'required': True,
                    'order': 4
                },
                {
                    'name': 'payment_terms',
                    'label': 'Payment Terms',
                    'type': 'text',
                    'required': True,
                    'order': 5,
                    'placeholder': 'e.g., Net 30, 50% deposit + 50% on completion'
                },
                {
                    'name': 'start_date',
                    'label': 'Start Date',
                    'type': 'date',
                    'required': True,
                    'order': 6
                },
                {
                    'name': 'end_date',
                    'label': 'End Date',
                    'type': 'date',
                    'required': False,
                    'order': 7
                }
            ]
        }

        # Financial Documents Structure
        financial_structure = {
            'structure_type': 'financial',
            'name': 'Financial Document Template',
            'description': 'Invoice, receipt, and financial statement document structure',
            'has_header': True,
            'has_footer': True,
            'has_page_numbers': False,
            'has_signature_section': False,
            'has_date_field': True,
            'header_height_mm': 45,
            'footer_height_mm': 15,
            'left_margin_mm': 15,
            'right_margin_mm': 15,
            'top_margin_mm': 15,
            'bottom_margin_mm': 15,
            'line_spacing': 1.1,
            'logo_width_mm': 60,
            'logo_position': 'top_center',
            'schema': [
                {
                    'name': 'invoice_number',
                    'label': 'Invoice/Document Number',
                    'type': 'text',
                    'required': True,
                    'order': 1
                },
                {
                    'name': 'bill_to',
                    'label': 'Bill To',
                    'type': 'textarea',
                    'required': True,
                    'order': 2
                },
                {
                    'name': 'invoice_date',
                    'label': 'Date',
                    'type': 'date',
                    'required': True,
                    'order': 3
                },
                {
                    'name': 'due_date',
                    'label': 'Due Date',
                    'type': 'date',
                    'required': False,
                    'order': 4
                },
                {
                    'name': 'item_description',
                    'label': 'Item Details',
                    'type': 'textarea',
                    'required': True,
                    'order': 5,
                    'placeholder': 'List items/services provided'
                },
                {
                    'name': 'subtotal',
                    'label': 'Subtotal',
                    'type': 'currency',
                    'required': True,
                    'order': 6
                },
                {
                    'name': 'tax_amount',
                    'label': 'Tax',
                    'type': 'currency',
                    'required': False,
                    'order': 7
                },
                {
                    'name': 'total_amount',
                    'label': 'Total Amount Due',
                    'type': 'currency',
                    'required': True,
                    'order': 8
                },
                {
                    'name': 'payment_method',
                    'label': 'Payment Method',
                    'type': 'text',
                    'required': False,
                    'order': 9,
                    'placeholder': 'e.g., Bank Transfer, Credit Card'
                },
                {
                    'name': 'notes',
                    'label': 'Notes',
                    'type': 'textarea',
                    'required': False,
                    'order': 10
                }
            ]
        }

        # HR Documents Structure
        hr_structure = {
            'structure_type': 'hr',
            'name': 'HR Document Template',
            'description': 'HR documents including offer letters, verification letters',
            'has_header': True,
            'has_footer': True,
            'has_page_numbers': True,
            'has_signature_section': True,
            'has_date_field': True,
            'header_height_mm': 40,
            'footer_height_mm': 20,
            'left_margin_mm': 22,
            'right_margin_mm': 22,
            'top_margin_mm': 22,
            'bottom_margin_mm': 22,
            'line_spacing': 1.3,
            'logo_width_mm': 50,
            'logo_position': 'top_center',
            'schema': [
                {
                    'name': 'employee_name',
                    'label': 'Employee Name',
                    'type': 'text',
                    'required': True,
                    'order': 1
                },
                {
                    'name': 'employee_id',
                    'label': 'Employee ID',
                    'type': 'text',
                    'required': False,
                    'order': 2
                },
                {
                    'name': 'position',
                    'label': 'Position',
                    'type': 'text',
                    'required': True,
                    'order': 3
                },
                {
                    'name': 'department',
                    'label': 'Department',
                    'type': 'text',
                    'required': False,
                    'order': 4
                },
                {
                    'name': 'start_date',
                    'label': 'Start Date',
                    'type': 'date',
                    'required': True,
                    'order': 5
                },
                {
                    'name': 'salary',
                    'label': 'Salary',
                    'type': 'currency',
                    'required': False,
                    'order': 6
                },
                {
                    'name': 'document_type',
                    'label': 'Document Type',
                    'type': 'select',
                    'required': True,
                    'order': 7,
                    'options': ['Offer Letter', 'Employment Agreement', 'Verification Letter', 'Experience Certificate']
                },
                {
                    'name': 'terms',
                    'label': 'Key Terms',
                    'type': 'textarea',
                    'required': False,
                    'order': 8
                }
            ]
        }

        # Create structures
        self.create_structure(legal_structure)
        self.stdout.write("")
        self.create_structure(contract_structure)
        self.stdout.write("")
        self.create_structure(financial_structure)
        self.stdout.write("")
        self.create_structure(hr_structure)

        self.stdout.write(self.style.SUCCESS("\n✅ All document structures seeded successfully!"))
        self.stdout.write(self.style.WARNING("\nDocuments are now using reusable structures instead of per-type templates."))
        self.stdout.write(self.style.WARNING("All structures share consistent professional styling and layout."))
