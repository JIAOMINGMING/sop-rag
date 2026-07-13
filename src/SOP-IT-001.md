---
doc_no: SOP-IT-001
title: Computerized System Validation and Data Integrity
version: "3.0"
effective_date: 2026-03-01
owner: IT Quality / CSV
company: Meridian Pharma K.K.
---

# 1. Purpose

This SOP defines the risk-based approach for validation of GxP computerized systems and the controls ensuring data integrity throughout the data lifecycle at Meridian Pharma K.K., in line with GAMP 5 (2nd Edition), EU Annex 11, and 21 CFR Part 11.

# 2. Scope

This SOP applies to all computerized systems used in GxP activities, including the safety database, eQMS, eDMS, laboratory systems, and validated spreadsheets. Non-GxP business systems are out of scope. Changes to validated systems follow SOP-QA-003 with the validation impact assessment defined herein.

# 3. Definitions

- **CSV**: Computerized System Validation.
- **GAMP category**: Software classification per GAMP 5: Category 1 (infrastructure), Category 3 (non-configured products), Category 4 (configured products), Category 5 (custom applications).
- **ALCOA+**: Data integrity principles — Attributable, Legible, Contemporaneous, Original, Accurate, plus Complete, Consistent, Enduring, Available.
- **Audit trail**: Secure, computer-generated, time-stamped record of the creation, modification, or deletion of electronic records.
- **Periodic review**: Documented evaluation confirming a validated system remains in a validated state.

# 4. Responsibilities

- **System Owner**: Accountable for the system's fitness for use and operational controls.
- **Business Process Owner**: Defines requirements and owns the data in the system.
- **CSV Lead**: Plans and executes validation deliverables; maintains the system inventory.
- **IT Quality**: Approves validation deliverables and periodic review reports.

# 5. Procedure

## 5.1 System Inventory and GxP Assessment

All computerized systems shall be recorded in the validated system inventory. Each new system shall receive a documented GxP determination and, if GxP, a GAMP category assignment and initial risk classification (high / medium / low) based on patient safety, product quality, and data integrity impact.

## 5.2 Risk-Based Validation Approach

- **Category 3** systems: leverage supplier documentation; verification may be limited to installation qualification and fitness-for-use testing.
- **Category 4** systems: validate configuration against documented requirements; risk-based functional testing of configured workflows.
- **Category 5** systems: full lifecycle validation including design specifications, code review where feasible, and comprehensive functional testing.

Supplier assessments shall be performed for Category 4 and 5 systems before selection; a supplier audit is required for high-risk Category 5 systems.

## 5.3 Validation Deliverables

At minimum: Validation Plan, Requirements Specification, Risk Assessment, Test Protocols and Reports, Traceability Matrix, and Validation Summary Report. Deliverables shall be approved by the System Owner, Business Process Owner, and IT Quality, and managed per WI-QA-004.

## 5.4 Data Integrity Controls

### 5.4.1 ALCOA+

All GxP data shall meet ALCOA+ principles across the data lifecycle (creation, processing, review, reporting, retention, destruction).

### 5.4.2 Access Management

Role-based access shall enforce segregation of duties. User access reviews shall be performed at least **every 6 months** for high-risk systems and annually for others. Shared accounts are prohibited for GxP data entry.

### 5.4.3 Audit Trail Review

Audit trails shall be enabled and shall not be disabled or modified by end users. Risk-based audit trail review shall be performed:

- High-risk systems (e.g., safety database, eQMS): at least **quarterly**;
- Medium-risk systems: at least annually;
- Additionally, targeted audit trail review shall be part of investigations per SOP-QA-001 where data integrity is in question.

## 5.5 Change Management and Validation Impact

All changes to validated systems shall follow SOP-QA-003. The CSV Lead shall document a validation impact assessment specifying the regression testing scope. Emergency changes (SOP-QA-003, Section 5.6) shall have the impact assessment completed retrospectively within 5 business days.

## 5.6 Periodic Review

Validated systems shall undergo periodic review at least **every 3 years**; high-risk systems **every 2 years**. The review shall cover change history, deviation history (SOP-QA-001), audit trail review status, access reviews, supplier status, and continued fitness for use. Findings requiring action shall be tracked via CAPA per SOP-QA-002.

## 5.7 System Retirement

Retirement shall be executed under change control (SOP-QA-003) with a data migration or archival plan ensuring records remain available and readable for the full retention period per WI-QA-004, Section 5.6.

# 6. Records

Validation deliverables, access review records, audit trail review logs, and periodic review reports shall be retained per WI-QA-004.

# 7. References

- SOP-QA-001 Deviation Management
- SOP-QA-002 CAPA Management
- SOP-QA-003 Change Control
- WI-QA-004 Document Control and Records Management
- GAMP 5 (2nd Edition), EU Annex 11, 21 CFR Part 11, PIC/S PI 041

# 8. Revision History

| Version | Effective Date | Description of Change |
|---------|---------------|----------------------|
| 2.0 | 2024-02-01 | Aligned to GAMP 5 2nd Edition critical thinking approach |
| 3.0 | 2026-03-01 | Audit trail review frequencies made risk-based; high-risk periodic review shortened to 2 years |
