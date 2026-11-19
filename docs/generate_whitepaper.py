import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._element.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tcPr.append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=150, right=150):
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def create_document():
    doc = docx.Document()

    # Page setup: Standard Letter, 1 inch margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Styles & Colors
    # Primary: #141110 (Obsidian Ink)
    # Accent: #c28340 (Cognac Gold)
    # Sub: #5e4b45 (Warm Bronze)
    # Background light: #fdfaf6
    COLOR_INK = RGBColor(20, 17, 16)
    COLOR_GOLD = RGBColor(194, 131, 64)
    COLOR_SUB = RGBColor(94, 75, 69)
    COLOR_GREEN = RGBColor(40, 122, 76)
    COLOR_RED = RGBColor(179, 57, 39)

    # Set normal style font
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Arial'
    style_normal.font.size = Pt(10.5)
    style_normal.font.color.rgb = COLOR_INK
    style_normal.paragraph_format.line_spacing = 1.2
    style_normal.paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # Title Page / Cover Section
    # -------------------------------------------------------------
    p_pre = doc.add_paragraph()
    r_pre = p_pre.add_run("ENTERPRISE TECHNICAL SPECIFICATION & ARCHITECTURE WHITEPAPER")
    r_pre.font.size = Pt(9.5)
    r_pre.font.bold = True
    r_pre.font.color.rgb = COLOR_GOLD
    p_pre.paragraph_format.space_after = Pt(4)

    p_title = doc.add_paragraph()
    r_title = p_title.add_run("AutoPatch: Autonomous Verified Software Repair & Invariant Engineering Platform")
    r_title.font.size = Pt(24)
    r_title.font.bold = True
    r_title.font.color.rgb = COLOR_INK
    p_title.paragraph_format.space_after = Pt(8)
    p_title.paragraph_format.line_spacing = 1.15

    p_sub = doc.add_paragraph()
    r_sub = p_sub.add_run("A Unified Theoretical, Algorithmic, and Operational Architecture for Self-Healing Repositories, Spectrum-Based Fault Localization, Multi-Model Deliberation, and Zero-Regression MicroVM Verification")
    r_sub.font.size = Pt(12)
    r_sub.font.italic = True
    r_sub.font.color.rgb = COLOR_SUB
    p_sub.paragraph_format.space_after = Pt(18)

    # Meta Table
    tbl_meta = doc.add_table(rows=4, cols=2)
    tbl_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Platform Version:", "AutoPatch Enterprise Edition v2.4 (Lumina Glassmorphic Architecture)"),
        ("Classification:", "Confidential / Commercial Enterprise Architecture Blueprint"),
        ("Engineering Focus:", "Deterministic Fault Localization, 3D AST Digital Twins, Multi-Agent Consensus, BRT Sandbox"),
        ("Date of Publication:", "November 2026")
    ]
    for row_idx, (k, v) in enumerate(meta_data):
        c0 = tbl_meta.cell(row_idx, 0)
        c1 = tbl_meta.cell(row_idx, 1)
        c0.width = Inches(1.8)
        c1.width = Inches(4.7)
        c0.paragraphs[0].text = k
        c0.paragraphs[0].runs[0].font.bold = True
        c0.paragraphs[0].runs[0].font.size = Pt(9.5)
        c0.paragraphs[0].runs[0].font.color.rgb = COLOR_SUB
        c1.paragraphs[0].text = v
        c1.paragraphs[0].runs[0].font.size = Pt(9.5)
        c1.paragraphs[0].runs[0].font.color.rgb = COLOR_INK
        set_cell_background(c0, "F5EFE8")
        set_cell_background(c1, "FAF6F0")
        set_cell_margins(c0, 60, 60, 100, 100)
        set_cell_margins(c1, 60, 60, 100, 100)

    doc.add_paragraph().paragraph_format.space_after = Pt(14)
    doc.add_page_break()

    # Helper function for headings
    def add_sec_heading(title, level=1):
        h = doc.add_heading(level=level)
        r = h.add_run(title)
        r.font.name = 'Arial'
        if level == 1:
            r.font.size = Pt(16)
            r.font.bold = True
            r.font.color.rgb = COLOR_INK
            h.paragraph_format.space_before = Pt(16)
            h.paragraph_format.space_after = Pt(6)
        elif level == 2:
            r.font.size = Pt(13)
            r.font.bold = True
            r.font.color.rgb = COLOR_GOLD
            h.paragraph_format.space_before = Pt(12)
            h.paragraph_format.space_after = Pt(4)
        elif level == 3:
            r.font.size = Pt(11)
            r.font.bold = True
            r.font.color.rgb = COLOR_SUB
            h.paragraph_format.space_before = Pt(8)
            h.paragraph_format.space_after = Pt(2)
        return h

    # -------------------------------------------------------------
    # Section 1: Executive Summary & Mission
    # -------------------------------------------------------------
    add_sec_heading("1. Executive Summary & Core Mission", 1)
    
    p = doc.add_paragraph()
    p.add_run("Modern software development organizations face an escalating systemic crisis: the velocity of software creation outpaces the human capacity for verification, maintenance, and security hardening. Enterprises accumulate millions of lines of code, leaving critical repositories encumbered by technical debt, obscure regression bugs, unpatched Common Vulnerabilities and Exposures (CVEs), and fragile architectural coupling.")

    p2 = doc.add_paragraph()
    p2.add_run("First-generation Generative AI coding assistants (such as GitHub Copilot, Cursor, and raw foundation models) exacerbate this problem. While capable of generating rapid code completions, they operate on statistical token probability rather than semantic correctness. They hallucinate non-existent APIs, introduce subtle logical vulnerabilities, write code without understanding whole-repository invariants, and produce patches that pass superficial tests while silently breaking downstream consumers.")

    # Callout Box: The Core Philosophy
    tbl_callout = doc.add_table(rows=1, cols=1)
    tbl_callout.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = tbl_callout.cell(0, 0)
    c.width = Inches(6.5)
    set_cell_background(c, "F6ECE1")
    set_cell_margins(c, 100, 100, 140, 140)
    cp = c.paragraphs[0]
    cr_title = cp.add_run("THE AUTOPATCH ENGINEERING MANDATE\n")
    cr_title.font.bold = True
    cr_title.font.size = Pt(10)
    cr_title.font.color.rgb = COLOR_GOLD
    cr_body = cp.add_run('"Never apply a code patch without first mathematically proving the defect via an automated Bug Reproducer Test (BRT). Never deploy a repair without executing full-suite differential regression verification in an isolated sandbox. Never trust a single model when an adversarial multi-agent committee can deliberate and vote."')
    cr_body.font.italic = True
    cr_body.font.size = Pt(10.5)
    cr_body.font.color.rgb = COLOR_INK

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    p3 = doc.add_paragraph()
    p3.add_run("AutoPatch is an autonomous, self-healing software intelligence platform designed for mission-critical enterprise codebases. It combines Spectrum-Based Fault Localization (Ochiai SBFL), Abstract Syntax Tree (AST) Taint Analysis, 3D Dependency Digital Twins, Multi-Model Consensus Committees (Gemini 1.5 Pro and Claude 3.5 Sonnet ensemble), and MicroVM Sandbox Verifiers into an automated end-to-end repair pipeline.")

    # -------------------------------------------------------------
    # Section 2: How Everything Works (System Architecture)
    # -------------------------------------------------------------
    add_sec_heading("2. How Everything Works: System Architecture", 1)
    
    p = doc.add_paragraph()
    p.add_run("AutoPatch operates as a dual-engine architecture: a high-throughput, deterministic Python/FastAPI backend verification engine coupled with Lumina, a warm glassmorphic executive interface delivering live telemetry over Server-Sent Events (SSE).")

    add_sec_heading("2.1 High-Level Architectural Pipeline", 2)
    p_pipe = doc.add_paragraph()
    p_pipe.add_run("The platform executes an end-to-end 8-stage verification and remediation cycle:")

    stages = [
        ("Stage 1: Secure Ingestion & AST Extraction", "Remote Git repositories (via HTTPS/SSH or GitHub OAuth Portal) and local ZIP archives are ingested into isolated workspaces. The engine builds an Abstract Syntax Tree (AST) symbol table across all files, extracting classes, functions, routes, and call edges."),
        ("Stage 2: 3D Codebase Digital Twin Mapping", "The extracted AST is projected into an interactive 3D repository topology, categorizing components into Public Ingress APIs, Core Business Logic, Infrastructure Modules, and Verification Tests. Downstream blast radii are pre-computed using Breadth-First Search (BFS) graph traversal."),
        ("Stage 3: Fault Localization (Ochiai SBFL)", "Using Spectrum-Based Fault Localization and dynamic execution trace matrices, AutoPatch computes suspiciousness coefficients for every executed statement, localizing bugs to exact file lines without relying on guesswork."),
        ("Stage 4: Automated Bug Reproducer Test (BRT) Synthesis", "Before generating any fix, the platform synthesizes an independent reproducer test harness (BRT). This test executes against the unmodified codebase to confirm deterministically that the bug fails as expected."),
        ("Stage 5: AI Model Committee Deliberation", "A multi-LLM consensus committee (Security Analyst, Logic Specialist, and Performance Auditor) debates candidate patches, evaluates invariant safety, checks for edge-case regressions, and votes on consensus."),
        ("Stage 6: Minimal Edit Distance Patch Synthesis", "Candidate diffs are synthesized using AST node replacement and Levenshtein minimal edit constraints, ensuring patches remain tight, surgically scoped, and free of gratuitous refactoring."),
        ("Stage 7: MicroVM Sandbox Verification & Flakiness Guards", "The candidate patch is applied inside an isolated execution sandbox. The BRT is re-run (which must now pass), followed by the entire repository test suite to guarantee zero regressions. Flakiness filters detect and reject non-deterministic test results."),
        ("Stage 8: Automated Git Deployment & Long-Term Learning", "Human engineers review the patch in the Lumina interface. Upon approval, AutoPatch pushes remediation branches, opens formatted Pull Requests with verification evidence tables, or exports patched ZIP archives. The successful repair pattern is indexed into SQLite for persistent long-term learning.")
    ]

    for title, desc in stages:
        p_st = doc.add_paragraph(style='List Bullet')
        r_t = p_st.add_run(f"{title}: ")
        r_t.font.bold = True
        r_t.font.color.rgb = COLOR_INK
        r_d = p_st.add_run(desc)
        r_d.font.color.rgb = COLOR_SUB

    add_sec_heading("2.2 Multi-Tenant Security & Secret Redaction", 2)
    p_sec = doc.add_paragraph()
    p_sec.add_run("Security is enforced at every layer: all API endpoints require Bearer token or API key authentication (`get_current_user`). Multi-tenant workspace boundaries prevent cross-account access (`assert_project_ownership`). Crucially, the engine runs automated regular-expression and entropy-based secret scrubbers across all code snippets before sending data to LLMs or UI streams, ensuring API keys, database credentials, and internal tokens are never leaked.")

    # -------------------------------------------------------------
    # Section 3: Complete Feature List
    # -------------------------------------------------------------
    add_sec_heading("3. Comprehensive Feature Matrix", 1)

    features = [
        ("Codebase Digital Twin (3D)", "Tab 0", "Interactive 3D dependency graph displaying functions, APIs, modules, and tests. Provides real-time BFS blast radius simulation before applying any patch to visualize affected callers and exposed routes."),
        ("AI Model Committee", "Tab 1", "Multi-model adversarial debate and consensus engine. Gathers three specialized personas (Security, Logic, Performance) to review candidate diffs, vote on invariant safety, and produce consensus scores."),
        ("Predictive Bug Detection", "Tab 2", "Proactive static hazard radar scanning ASTs for structural failure patterns: mutable default arguments, unchecked null/None returns, unclosed file/socket descriptors, and dangerous broad exceptions."),
        ("Code Hotspot Detection", "Tab 3", "Correlates static cyclomatic complexity (McCabe metric) with live Git commit churn and author count to pinpoint fragile modules at high risk of impending regression."),
        ("Long-Term Repair Learning", "Tab 4", "Persistent SQLite Memory Bank tracking successfully verified repair patterns, CWE classifications, and reuse counters. Accelerates future patch synthesis through learned templates."),
        ("API Security Testing (OWASP Top 10)", "Tab 5", "Audits REST API endpoint signatures across FastAPI, Flask, and Express against OWASP API Top 10 vulnerabilities (Broken Object Level Auth, Missing Rate Limits, Mass Assignment)."),
        ("Bug Origin Detection (Git Blame)", "Tab 6", "Automated Git blame root-cause tracing that correlates defect lines to introducing commits, author identities, commit hashes, and commit messages."),
        ("Automatic Documentation Generation", "Tab 7", "Synthesizes production Architecture Decision Records (ADRs), Security Changelogs, and Executive Briefings directly from scan telemetry and patch diffs with 1-click Markdown copy and download."),
        ("Spectrum-Based Fault Localization (SBFL)", "Core Engine", "Ochiai ranking algorithm computing suspiciousness coefficients for statement-level fault localization using pass/fail test execution matrices."),
        ("Bug Reproducer Test (BRT) Harness", "Core Engine", "Autonomous test synthesizer that writes and validates deterministic failing test cases before patch generation, preventing phantom repairs."),
        ("Isolated MicroVM Sandbox Runner", "Core Engine", "Subprocess execution harness with strict timeouts, environment isolation, zero-network enforcement, and differential regression checks."),
        ("Automated Git Deployment Engine", "Delivery", "Automates remediation branch creation, remote pushes (with fork redirection on permission denial), and GitHub Pull Requests with evidence matrices."),
        ("Live SSE Telemetry Stream", "Observability", "Real-time Server-Sent Events stream feeding worker telemetry, AST analysis progress, and execution logs directly into the Lumina terminal console.")
    ]

    tbl_feat = doc.add_table(rows=len(features)+1, cols=3)
    tbl_feat.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Feature Module", "Subsystem", "Operational Capability & Technical Scope"]
    for col_idx, h in enumerate(headers):
        cell = tbl_feat.cell(0, col_idx)
        cell.paragraphs[0].text = h
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.size = Pt(9.5)
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "141110")
        set_cell_margins(cell, 80, 80, 100, 100)

    for idx, (f_name, f_sub, f_desc) in enumerate(features):
        row = idx + 1
        c0 = tbl_feat.cell(row, 0)
        c1 = tbl_feat.cell(row, 1)
        c2 = tbl_feat.cell(row, 2)
        c0.width = Inches(1.8)
        c1.width = Inches(1.2)
        c2.width = Inches(3.5)

        c0.paragraphs[0].text = f_name
        c0.paragraphs[0].runs[0].font.bold = True
        c0.paragraphs[0].runs[0].font.size = Pt(9)
        c0.paragraphs[0].runs[0].font.color.rgb = COLOR_INK

        c1.paragraphs[0].text = f_sub
        c1.paragraphs[0].runs[0].font.size = Pt(8.5)
        c1.paragraphs[0].runs[0].font.color.rgb = COLOR_GOLD

        c2.paragraphs[0].text = f_desc
        c2.paragraphs[0].runs[0].font.size = Pt(8.5)
        c2.paragraphs[0].runs[0].font.color.rgb = COLOR_SUB

        bg_color = "FDF8F3" if idx % 2 == 0 else "FFFFFF"
        set_cell_background(c0, bg_color)
        set_cell_background(c1, bg_color)
        set_cell_background(c2, bg_color)
        set_cell_margins(c0, 60, 60, 80, 80)
        set_cell_margins(c1, 60, 60, 80, 80)
        set_cell_margins(c2, 60, 60, 80, 80)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # Section 4: Unique Solution & Value Proposition
    # -------------------------------------------------------------
    add_sec_heading("4. Unique Solution: How AutoPatch Redefines Code Repair", 1)

    p_sol = doc.add_paragraph()
    p_sol.add_run("The central innovation of AutoPatch lies in bridging the gap between statistical AI generative models and rigorous formal software verification. Other tools generate code and hope it works; AutoPatch proves correctness before and after modification.")

    pillars = [
        ("1. The Reproducer-First Invariant", "Traditional code assistants attempt to repair bugs by directly generating code diffs. This frequently produces hallucinations where the model 'fixes' code that was never broken or masks defects with trivial workarounds. AutoPatch mandates that every candidate bug must first be captured by a synthesized Bug Reproducer Test (BRT). If the BRT cannot fail deterministically on the unpatched codebase, the finding is discarded."),
        ("2. Multi-Model Adversarial Deliberation", "Single LLM agents suffer from blind spots, prompt drift, and sycophantic self-reinforcement. AutoPatch introduces an AI Model Committee where independent personas (Security, Logic, Performance) evaluate the defect independently and debate the patch. The patch is only accepted if consensus agreement exceeds threshold metrics."),
        ("3. Pre-Patch Digital Twin Blast Radius", "Applying a patch to a shared utility or service module can cascade into unexpected outages across downstream callers. AutoPatch builds an in-memory 3D Digital Twin using AST symbol graphs. Before landing a fix, engineers and automated policies visualize exactly which functions, public endpoints, and test suites lie in the blast radius."),
        ("4. Deterministic MicroVM Sandbox Harness", "AutoPatch enforces strict execution sandboxing during verification. Test runs occur in microVM-isolated subprocesses with frozen dependencies, strict CPU/wall-clock timeouts, disabled external networking, and flakiness detection that runs tests multiple times to guard against non-deterministic race conditions."),
        ("5. Cumulative Memory Bank with Zero Re-Learning", "Standard AI tools treat every invocation as day zero. AutoPatch stores verified patch diffs, abstract syntax representations, and CWE mappings in a persistent SQLite repair bank. When a similar defect appears in other microservices or repos, the platform retrieves prior verified templates.")
    ]

    for p_title, p_body in pillars:
        add_sec_heading(p_title, 2)
        p_desc = doc.add_paragraph()
        p_desc.add_run(p_body)

    # -------------------------------------------------------------
    # Section 5: Competitor Comparison
    # -------------------------------------------------------------
    add_sec_heading("5. Competitor Comparison: Why AutoPatch Leads the Market", 1)

    p_comp = doc.add_paragraph()
    p_comp.add_run("The automated software engineering market is fragmented into static analyzers, dependency checkers, developer assistants, and unconstrained agents. AutoPatch is the only platform that provides end-to-end verified autonomous repair.")

    comp_data = [
        ("Capability / Vector", "AutoPatch", "Static Analysis (SonarQube)", "Dependency Bots (Snyk/Dependabot)", "Coding Assistants (Copilot/Cursor)", "Autonomous Agents (Devin/SWE-Agent)"),
        ("Autonomous Bug Repair", "Yes (Verified via Sandbox)", "No (Alerts only)", "Partial (Version bump only)", "No (Manual developer prompt)", "Yes (High failure rate)"),
        ("Bug Reproducer Synthesis", "Yes (Mandatory BRT)", "No", "No", "No", "Rare / Inconsistent"),
        ("Zero Regression Proof", "Yes (Full suite execution)", "No", "No", "No", "Flaky / Not guaranteed"),
        ("Multi-Model Consensus", "Yes (3-Model Debate)", "No", "No", "No", "No (Single model loop)"),
        ("3D Digital Twin Blast Radius", "Yes (AST caller graph)", "No", "No", "No", "No"),
        ("OWASP API Security Top 10", "Yes (AST route audit)", "Partial (Pattern-based)", "Dependencies only", "No", "No"),
        ("Predictive Hazard Radar", "Yes (Static AST analysis)", "Rule-based lint only", "No", "No", "No"),
        ("Long-Term Repair Memory", "Yes (SQLite WAL bank)", "No", "No", "No", "No"),
        ("Deterministic Cost & Speed", "Instant & Low Token Burn", "Fast but static", "Fast", "Interactive", "Extremely High Token Burn")
    ]

    tbl_comp = doc.add_table(rows=len(comp_data), cols=6)
    tbl_comp.alignment = WD_TABLE_ALIGNMENT.CENTER
    for col_idx in range(6):
        cell = tbl_comp.cell(0, col_idx)
        cell.paragraphs[0].text = comp_data[0][col_idx]
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.size = Pt(8)
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "141110")
        set_cell_margins(cell, 60, 60, 60, 60)

    for row_idx, row_vals in enumerate(comp_data[1:], start=1):
        for col_idx, val in enumerate(row_vals):
            cell = tbl_comp.cell(row_idx, col_idx)
            cell.paragraphs[0].text = val
            cell.paragraphs[0].runs[0].font.size = Pt(8)
            if col_idx == 1:
                cell.paragraphs[0].runs[0].font.bold = True
                cell.paragraphs[0].runs[0].font.color.rgb = COLOR_GREEN
            elif "No" in val:
                cell.paragraphs[0].runs[0].font.color.rgb = COLOR_RED
            else:
                cell.paragraphs[0].runs[0].font.color.rgb = COLOR_INK

            bg = "FAF6F0" if col_idx == 1 else ("FDF8F3" if row_idx % 2 == 0 else "FFFFFF")
            set_cell_background(cell, bg)
            set_cell_margins(cell, 50, 50, 60, 60)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # Section 6: Workflow & Operational Lifecycle
    # -------------------------------------------------------------
    add_sec_heading("6. Workflow & Operational Lifecycle", 1)

    p_wf = doc.add_paragraph()
    p_wf.add_run("The following flowchart outlines the operational lifecycle of an AutoPatch automated remediation run:")

    wf_steps = [
        ("Step 1: Workspace Ingestion", "Engine clones remote Git repository (HTTPS/SSH) or unpacks uploaded archive. Multi-tenant isolation creates unique workspace ID."),
        ("Step 2: AST Digital Twin Generation", "Python `ast` parser parses every source file, extracting function signatures, docstrings, classes, import dependencies, and REST endpoint routes. Generates JSON graph of nodes and call edges."),
        ("Step 3: Fault Localization (Ochiai SBFL)", "Executes existing test suite with trace profiling. Builds the spectrum execution matrix linking passing and failing tests to suspicious statements."),
        ("Step 4: BRT Harness Construction", "Generates a standalone reproducer test specifically exercising the fault condition. Verifies that the test exits with status code non-zero on the current commit."),
        ("Step 5: Deliberation & Minimal Diff Generation", "AI Model Committee inspects the failing trace, source AST, and repair bank templates. Synthesizes a unified diff scoped to minimal edit distance."),
        ("Step 6: Sandbox Execution & Regression Suite", "Patch applied in memory/worktree. The BRT is re-run (must pass). Full test suite executes in isolated microVM (must pass 100% with zero regressions)."),
        ("Step 7: Human Decision in Lumina Hub", "Engineers inspect the diff, 3D blast radius visualization, committee debate transcript, and test evidence in the Lumina web application."),
        ("Step 8: Automated Deployment & Knowledge Ingestion", "One-click deployment pushes remediation branch to origin (or user fork if write-denied), generates GitHub Pull Request, and stores the verified repair pattern in SQLite.")
    ]

    for s_title, s_desc in wf_steps:
        p_st = doc.add_paragraph(style='List Bullet')
        r_t = p_st.add_run(f"{s_title}: ")
        r_t.font.bold = True
        r_t.font.color.rgb = COLOR_INK
        r_d = p_st.add_run(s_desc)
        r_d.font.color.rgb = COLOR_SUB

    # -------------------------------------------------------------
    # Section 7: Tech Stack
    # -------------------------------------------------------------
    add_sec_heading("7. Complete Technology Stack", 1)

    stack_categories = [
        ("Core Backend Framework", "FastAPI, Uvicorn, Python 3.9+, Pydantic v2", "Asynchronous REST API, high-throughput request validation, Server-Sent Events (SSE) telemetry."),
        ("AST Parsing & Static Analysis", "Python `ast`, `symtable`, `tokenize`", "Abstract Syntax Tree extraction, symbol resolution, cyclomatic complexity calculation, taint tracking."),
        ("Fault Localization & Sandboxing", "Ochiai SBFL Engine, Pytest Runner, Subprocess Sandbox", "Spectrum-based execution profiling, isolated microVM sandbox execution, timeout and memory enforcement."),
        ("Persistence & Telemetry", "SQLite3 (WAL Mode), JSON Lines (JSONL), In-Memory Registry", "Durable repair memory bank, event ledgers, historical telemetry, and multi-tenant workspace registries."),
        ("LLM Ensemble & Deliberation", "Gemini 1.5 Pro, Claude 3.5 Sonnet, GPT-4o Abstraction", "Multi-model committee consensus, debate transcripts, minimal diff synthesis, and anti-hallucination scoring."),
        ("Lumina Frontend Interface", "HTML5, Vanilla ES6+ JavaScript, CSS3 Glassmorphism", "Bespoke executive luxury aesthetic, zero heavy frontend build dependencies, high rendering performance."),
        ("3D Visualizer & Projection", "HTML5 Canvas 2D/3D Isometric Engine, Three.js", "Tactile glass capsules, architectural tiers, particle flow animations, and interactive blast radius illumination."),
        ("Version Control & DevOps", "Git CLI Core, GitHub REST API v3, Docker, Docker Compose", "Autonomous branch generation, fork management, Pull Request creation, and containerized deployment.")
    ]

    tbl_stack = doc.add_table(rows=len(stack_categories)+1, cols=3)
    tbl_stack.alignment = WD_TABLE_ALIGNMENT.CENTER
    for col_idx, h in enumerate(["Subsystem", "Technologies & Libraries", "Architectural Role & Purpose"]):
        cell = tbl_stack.cell(0, col_idx)
        cell.paragraphs[0].text = h
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.size = Pt(9)
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "141110")
        set_cell_margins(cell, 60, 60, 80, 80)

    for idx, (cat, tech, purp) in enumerate(stack_categories, start=1):
        c0 = tbl_stack.cell(idx, 0)
        c1 = tbl_stack.cell(idx, 1)
        c2 = tbl_stack.cell(idx, 2)
        c0.width = Inches(1.8)
        c1.width = Inches(2.2)
        c2.width = Inches(2.5)

        c0.paragraphs[0].text = cat
        c0.paragraphs[0].runs[0].font.bold = True
        c0.paragraphs[0].runs[0].font.size = Pt(8.5)
        c0.paragraphs[0].runs[0].font.color.rgb = COLOR_INK

        c1.paragraphs[0].text = tech
        c1.paragraphs[0].runs[0].font.size = Pt(8.5)
        c1.paragraphs[0].runs[0].font.color.rgb = COLOR_GOLD

        c2.paragraphs[0].text = purp
        c2.paragraphs[0].runs[0].font.size = Pt(8.5)
        c2.paragraphs[0].runs[0].font.color.rgb = COLOR_SUB

        bg = "FDF8F3" if idx % 2 == 0 else "FFFFFF"
        set_cell_background(c0, bg)
        set_cell_background(c1, bg)
        set_cell_background(c2, bg)
        set_cell_margins(c0, 50, 50, 60, 60)
        set_cell_margins(c1, 50, 50, 60, 60)
        set_cell_margins(c2, 50, 50, 60, 60)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # Section 8: Algorithms & Mathematical Formulations
    # -------------------------------------------------------------
    add_sec_heading("8. Algorithms & Mathematical Formulations", 1)

    p_algo = doc.add_paragraph()
    p_algo.add_run("AutoPatch replaces heuristics with formal mathematical formulations for fault localization, blast radius computation, cyclomatic risk scoring, and consensus agreement.")

    add_sec_heading("8.1 Spectrum-Based Fault Localization (Ochiai SBFL Metric)", 2)
    p_ochiai = doc.add_paragraph()
    p_ochiai.add_run("To isolate candidate defect lines without human bias, AutoPatch employs the Ochiai similarity coefficient. For any statement s in the repository:")

    p_eq1 = doc.add_paragraph()
    r_eq1 = p_eq1.add_run("S(s) = failed(s) / sqrt( total_failed * ( failed(s) + passed(s) ) )")
    r_eq1.font.bold = True
    r_eq1.font.name = 'Courier New'
    r_eq1.font.size = Pt(10)
    p_eq1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_eq1.paragraph_format.space_before = Pt(4)
    p_eq1.paragraph_format.space_after = Pt(4)

    p_ochiai_desc = doc.add_paragraph()
    p_ochiai_desc.add_run("Where failed(s) is the count of failing test cases that traversed statement s, passed(s) is the count of passing test cases that traversed statement s, and total_failed is the total number of failing test cases in the test suite. Statements with S(s) >= 0.70 are tagged as primary defect candidates.")

    add_sec_heading("8.2 BFS Dependency Blast Radius Traversal", 2)
    p_bfs = doc.add_paragraph()
    p_bfs.add_run("To compute the downstream architectural impact of modifying component c, AutoPatch executes a Breadth-First Search across the directed call graph G = (V, E) where V represents functions, methods, and endpoints, and E represents invocation edges (u -> v):")

    p_bfs_code = doc.add_paragraph()
    r_bc = p_bfs_code.add_run(
        "Queue Q = [c]; Visited = {c}; Affected = []\n"
        "while Q is not empty:\n"
        "    current = Q.dequeue()\n"
        "    for each caller in IngressEdges(current):\n"
        "        if caller not in Visited:\n"
        "            Visited.add(caller)\n"
        "            Affected.append(caller)\n"
        "            Q.enqueue(caller)\n"
        "BlastRadiusPct = (|Affected| / |V|) * 100"
    )
    r_bc.font.name = 'Courier New'
    r_bc.font.size = Pt(8.5)
    p_bfs_code.paragraph_format.space_after = Pt(6)

    add_sec_heading("8.3 Cyclomatic Complexity & Code Hotspot Score", 2)
    p_cyc = doc.add_paragraph()
    p_cyc.add_run("The Hotspot Detection engine computes McCabe Cyclomatic Complexity M for every function AST node:")

    p_eq2 = doc.add_paragraph()
    r_eq2 = p_eq2.add_run("M = E - N + 2P")
    r_eq2.font.bold = True
    r_eq2.font.name = 'Courier New'
    r_eq2.font.size = Pt(10)
    p_eq2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_eq2.paragraph_format.space_before = Pt(4)
    p_eq2.paragraph_format.space_after = Pt(4)

    p_hotspot_comb = doc.add_paragraph()
    p_hotspot_comb.add_run("Where E is edges in the control-flow graph, N is nodes, and P is connected components. The Hotspot Risk Score H is then computed by normalizing complexity against commit churn and unique authors:")

    p_eq3 = doc.add_paragraph()
    r_eq3 = p_eq3.add_run("HotspotScore = min( 100, (0.40 * M_norm) + (0.35 * Churn_norm) + (0.25 * Authors_norm) )")
    r_eq3.font.bold = True
    r_eq3.font.name = 'Courier New'
    r_eq3.font.size = Pt(9.5)
    p_eq3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_eq3.paragraph_format.space_after = Pt(6)

    add_sec_heading("8.4 Consensus Agreement Index & Anti-Hallucination Guard", 2)
    p_agree = doc.add_paragraph()
    p_agree.add_run("During AI Model Committee deliberation, each model persona evaluates the patch across invariant safety, performance impact, and style compatibility. The Consensus Score C is defined as:")

    p_eq4 = doc.add_paragraph()
    r_eq4 = p_eq4.add_run("C = (Sum of Model Scores / 3) * AgreementMultiplier")
    r_eq4.font.bold = True
    r_eq4.font.name = 'Courier New'
    r_eq4.font.size = Pt(9.5)
    p_eq4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_eq4.paragraph_format.space_after = Pt(6)

    p_agree_desc = doc.add_paragraph()
    p_agree_desc.add_run("Where AgreementMultiplier is 1.0 for unanimous consensus, 0.70 for 2/3 majority, and 0.20 when any single model detects a security hazard (overriding majority vote).")

    # -------------------------------------------------------------
    # Section 9: Deployment & DevOps Guide
    # -------------------------------------------------------------
    add_sec_heading("9. Deployment Architecture & Production Operations", 1)

    p_dep = doc.add_paragraph()
    p_dep.add_run("AutoPatch is engineered for enterprise-grade deployment across on-premises air-gapped clusters, dedicated private clouds, or managed Kubernetes infrastructure.")

    add_sec_heading("9.1 Containerized Microservices Topology", 2)
    p_dock = doc.add_paragraph()
    p_dock.add_run("The platform is delivered as two coordinated container services orchestrated via Docker Compose or Kubernetes manifests:")

    docker_services = [
        ("autopatch-engine (Port 8000)", "FastAPI ASGI backend running Uvicorn workers. Houses the AST parser, Ochiai localization matrix, Sandbox test runner, SQLite repair memory bank, and multi-agent committee orchestrator."),
        ("lumina-frontend (Port 3000)", "High-performance static HTTP gateway delivering the Lumina luxury glassmorphic interface, 3D Canvas visualizer, and SSE client event listeners.")
    ]
    for s_name, s_role in docker_services:
        p_ds = doc.add_paragraph(style='List Bullet')
        r_sn = p_ds.add_run(f"{s_name}: ")
        r_sn.font.bold = True
        r_sn.font.color.rgb = COLOR_INK
        r_sr = p_ds.add_run(s_role)
        r_sr.font.color.rgb = COLOR_SUB

    add_sec_heading("9.2 Production Docker Compose Blueprint", 2)
    p_comp_yml = doc.add_paragraph()
    r_yml = p_comp_yml.add_run(
        "version: '3.8'\n"
        "services:\n"
        "  autopatch-engine:\n"
        "    build:\n"
        "      context: .\n"
        "      dockerfile: Dockerfile\n"
        "    ports:\n"
        "      - '8000:8000'\n"
        "    environment:\n"
        "      - AUTOPATCH_ENV=production\n"
        "      - AUTOPATCH_AUTH_TOKEN=${AUTOPATCH_AUTH_TOKEN:-dev_token_user_developer}\n"
        "      - GITHUB_TOKEN=${GITHUB_TOKEN}\n"
        "      - GEMINI_API_KEY=${GEMINI_API_KEY}\n"
        "      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}\n"
        "    volumes:\n"
        "      - autopatch-data:/var/lib/autopatch\n"
        "    restart: unless-stopped\n\n"
        "  lumina-web:\n"
        "    image: nginx:alpine\n"
        "    ports:\n"
        "      - '3000:80'\n"
        "    volumes:\n"
        "      - ./lumina:/usr/share/nginx/html:ro\n"
        "    depends_on:\n"
        "      - autopatch-engine\n"
        "    restart: unless-stopped\n\n"
        "volumes:\n"
        "  autopatch-data:\n"
        "    driver: local"
    )
    r_yml.font.name = 'Courier New'
    r_yml.font.size = Pt(8)
    p_comp_yml.paragraph_format.space_after = Pt(10)

    add_sec_heading("9.3 Enterprise Security & Compliance Hardening", 2)
    p_hard = doc.add_paragraph()
    p_hard.add_run("For regulated enterprise environments (Financial Services, Healthcare, Defense), AutoPatch enforces strict compliance standards:")

    comps = [
        ("Air-Gapped Operation", "AutoPatch can operate completely disconnected from external foundation model APIs by integrating local open-source LLMs (DeepSeek-Coder, Llama-3-Code) deployed within private VPC clusters."),
        ("Zero-Retention Code Privacy", "Workspaces are scrubbed immediately upon session completion or retention expiration. Code is never logged to persistent disks unencrypted and never used to train third-party models."),
        ("Comprehensive Audit Trails", "Every scan, AST traversal, BRT execution, committee vote, and human decision is immutably logged to SQLite audit tables for SOC2, HIPAA, and ISO 27001 compliance reviews.")
    ]
    for c_title, c_desc in comps:
        p_cp = doc.add_paragraph(style='List Bullet')
        r_ct = p_cp.add_run(f"{c_title}: ")
        r_ct.font.bold = True
        r_ct.font.color.rgb = COLOR_INK
        r_cd = p_cp.add_run(c_desc)
        r_cd.font.color.rgb = COLOR_SUB

    # Save DOCX file
    out_docx_path = "docs/AutoPatch_Enterprise_Architecture_and_Specification.docx"
    doc.save(out_docx_path)
    print(f"Successfully generated DOCX whitepaper at: {out_docx_path}")

create_document()
