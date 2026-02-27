---
name: teambition-prd-writer
description: A skill to help Teambition's internal teams (product, design, engineering) write PRDs for new features or feature optimizations. Use this skill to structure and generate a complete PRD based on Teambition's specific format and product context.
---

# Teambition PRD Writer

This skill helps you create a comprehensive Product Requirements Document (PRD) for Teambition. It's designed for internal use by product managers, designers, and engineers.

## How to Generate a PRD

Follow these steps to generate a complete PRD:

1.  **Understand the Goal:** Start by asking the user for the high-level goal of the new feature or optimization. What problem are they trying to solve?

2.  **Gather Detailed Information:** Use the questions below to collect all the necessary details for the PRD. You don't need to ask them all at once.

3.  **Consult Teambition's Product Context:** When filling out the PRD, refer to the `references/teambition_product_reference.md` file to ensure your descriptions are consistent with Teambition's existing features, terminology, and user base.

4.  **Fill out the PRD Template:** Use the `templates/prd_template.md` as the foundation for your PRD. Make sure to fill in every section with the information you've gathered.

5.  **Review and Refine:** Once the PRD is complete, review it for clarity, consistency, and completeness. Make sure it's ready for the engineering team to start working on.

## Questions to Ask the User

-   **Feature Name:** What is the name of this new feature or optimization?
-   **Background:** What is the problem you're trying to solve? Why is it important to solve it now?
-   **User Feedback:** Do you have any direct quotes, feedback, or meeting notes from customers or internal stakeholders?
-   **Competitive Landscape:** How do competitors like ClickUp, Asana, Monday.com, or JIRA handle this problem?
-   **Goals & Success Metrics:** What are the primary goals for this feature? How will you measure its success?
-   **Detailed Description:** Can you walk me through the user story? What are the key functional requirements? Are there any non-functional requirements (e.g., performance, security)?
-   **Out of Scope:** What is explicitly *not* part of this feature?

## Using the Bundled Resources

-   **`templates/prd_template.md`:** This is the master template for all Teambition PRDs. Always start with this file.
-   **`references/teambition_product_reference.md`:** This file contains key information about Teambition's product structure, core modules, and target audience. Use it to ensure your PRD is grounded in the product's reality.
