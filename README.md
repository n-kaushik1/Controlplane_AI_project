# ControlPlane AI

ControlPlane AI is a governance and safety layer for LLM-powered applications. It sits between an application and an LLM provider and evaluates requests and model responses before allowing them to proceed.

The prototype is designed to demonstrate how an AI system can apply **policy-driven governance, risk assessment, factuality verification, human oversight, auditability, and monitoring** around LLM usage.

---

## What the Project Does

ControlPlane AI provides a centralized control layer for LLM requests.

A typical request flows through the system as:

```text
User Request
     |
     v
Request Validation
     |
     v
Request Governance
(Bias / Cost / Privacy / Security)
     |
     v
Policy Evaluation
     |
     +---- BLOCK ----> Request stopped
     |
     +---- REVIEW ---> Human review queue
     |
     +---- ALLOW ----> LLM invocation
                         |
                         v
                 Response Governance
                 (Factuality / Bias /
                  Privacy / Security)
                         |
                         v
                 Final Policy Decision
                         |
              +----------+----------+
              |          |          |
            ALLOW      REVIEW      BLOCK
              |          |          |
              v          v          v
           Output    Human Review  Output blocked
```

The goal is not to replace an LLM. Instead, ControlPlane acts as a **governance control plane around the LLM**.

---

## Key Capabilities

### 1. Request Governance

Before an LLM is called, the request can be evaluated by multiple governance agents:

- **Security Agent** — detects potentially unsafe or suspicious request patterns.
- **Privacy Agent** — detects sensitive information and privacy-related signals.
- **Bias Agent** — checks for obvious group-based bias patterns.
- **Cost Agent** — estimates token usage and checks configured compute/cost limits.

The agents produce risk, status, confidence, reasons, and supporting signals.

---

### 2. Response Governance

After the model generates a response, ControlPlane evaluates the response before returning it to the user.

The response governance layer supports:

- Factuality verification
- Evidence-based verification
- Bias checks
- Privacy checks
- Security checks
- Policy evaluation
- Human review when required

This ensures that a request being safe does not automatically mean that the generated answer is safe to release.

---

### 3. Factuality and Evidence

The prototype includes a factuality pipeline for checking model-generated claims.

It can use:

- Local evidence
- Evidence retrieval
- Web evidence retrieval
- Claim extraction
- Evidence verification

The project contains an evidence store and an indexed evidence dataset under:

```text
data/
```

The factuality result can influence the final governance decision.

For example:

```text
Model Response
      |
      v
Claim Extraction
      |
      v
Evidence Retrieval
      |
      v
Claim Verification
      |
      v
Factuality Result
      |
      v
Response Policy
```

---

### 4. Risk Profiles

The project supports configurable risk profiles for different AI use cases.

Current profiles include:

#### Customer Support

Designed for customer-facing AI where safety, privacy, security, factuality, and responsive interaction are important.

```text
customer_support
```

#### Internal Copilot

Designed for employee-facing AI with stronger emphasis on grounded answers, enterprise data protection, source traceability, and productivity.

```text
internal_copilot
```

#### Regulated Decision

Designed for high-risk or regulated decision-support workflows with stricter thresholds and stronger human oversight.

```text
regulated_decision
```

Each profile can define controls such as:

- Maximum risk
- Maximum uncertainty
- Maximum cost
- Maximum latency
- Factuality requirement
- Human review requirement
- Privacy requirement
- Bias requirement
- Security threshold
- Consequential-action review
- Regulatory context
- Governance priorities
- Multi-turn support

---

## Policy Decisions

The policy engine can produce three primary outcomes:

### ALLOW

The request or response satisfies the configured governance requirements.

```text
ALLOW
```

### REVIEW

The request or response requires human oversight before it can proceed or be released.

```text
REVIEW
```

### BLOCK

The request or response violates a blocking condition or exceeds a critical policy threshold.

```text
BLOCK
```

The policy engine also returns:

- Aggregated risk
- Decision reason
- Triggered rules
- Policy name
- Uncertainty
- Verification status
- Agent count
- Risk thresholds
- Security threshold
- Human-review requirements
- Other policy metadata

---

## Human Review

ControlPlane includes a human-review workflow for cases that require additional oversight.

A review can contain information such as:

- Request
- Model response
- Governance decision
- Risk information
- Factuality information
- Evidence
- Review status
- Reviewer decision
- Resolution information
- Request ID

Human review decisions can resolve a pending governance case.

This is especially important for higher-risk workflows where fully automated decisions are not appropriate.

---

## Audit Logging

The prototype includes an audit logging system.

Important events in the lifecycle of a request can be recorded, including:

- Request received
- Input validation
- Governance execution
- Policy decision
- Model invocation
- Response governance
- Human review
- Final decision
- Errors

Audit information supports traceability and debugging.

Audit logs are written to:

```text
logs/
```

Generated runtime logs should generally not be committed to a public repository.

---

## Monitoring and Metrics

The project contains monitoring and metrics components for observing system behavior.

The monitoring layer can support analysis of areas such as:

- Governance decisions
- Risk
- Latency
- Token usage
- Cost
- Agent performance
- Model activity
- Review activity
- Operational behavior

The goal is to make governance measurable rather than treating it as an invisible middleware layer.

---

## Feedback

The prototype includes feedback and review components that can record feedback associated with governance decisions.

This provides a foundation for evaluating governance quality and improving the system over time.

Relevant components are located under:

```text
app/feedback/
```

---

# Project Architecture

The main application structure is:

```text
ControlPlane AI
│
├── API
│   └── routes.py
│
├── Gateway
│   ├── request_gateway.py
│   ├── model_gateway.py
│   └── review_gateway.py
│
├── Agents
│   ├── base.py
│   ├── orchestrator.py
│   ├── bias_agent.py
│   ├── cost_agent.py
│   ├── factuality_agent.py
│   ├── privacy_agent.py
│   └── security_agent.py
│
├── Policies
│   ├── engine.py
│   └── policies.py
│
├── Evidence
│   ├── claims.py
│   ├── retriever.py
│   ├── store.py
│   └── verifier.py
│
├── Core
│   ├── config.py
│   ├── evidence_retriever.py
│   ├── factuality_engine.py
│   └── web_evidence_retriever.py
│
├── Context
│   ├── request_context.py
│   └── risk_profiles.py
│
├── Feedback
│   ├── models.py
│   ├── review_queue.py
│   ├── service.py
│   └── store.py
│
├── Audit
│   └── logger.py
│
├── Monitoring
│   ├── aggregator.py
│   └── metrics.py
│
├── Actions
│   └── executor.py
│
├── Dashboard
│   ├── index.html
│   ├── app.js
│   └── style.css
│
├── Data
│   ├── evidence.json
│   └── evidence_index.npz
│
└── Tests
```

---

# Technology Stack

The prototype uses:

- Python
- FastAPI
- Uvicorn
- Pydantic
- HTTP-based LLM provider integration
- Evidence retrieval
- Web evidence retrieval
- JSON/JSONL persistence
- HTML/CSS/JavaScript dashboard
- Pytest

The exact package versions are maintained in:

```text
requirements.txt
```

---

# Requirements

Before running the project, make sure you have:

- Python 3.10+ recommended
- pip
- Internet access for external LLM/web evidence providers
- An LLM provider API key
- Tavily API key if web evidence retrieval is enabled

---

# Installation

## 1. Clone the repository

Clone this repository to your machine and enter the project directory.

Example:

```powershell
git clone <repository-url>
cd ControlPlane_ai_final_prototype
```

## 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, activate the environment using an appropriate Python/PowerShell configuration for your machine.

---

## 3. Install dependencies

```powershell
pip install -r requirements.txt
```

---

# Environment Variables

Create a local `.env` file in the project root.

Use `.env_example` as the template:

```text
.env_example
```

Do not commit your real `.env` file.

A typical setup contains the API credentials required by the configured model and evidence providers.

For example:

```env
OPENROUTER_API_KEY=your_openrouter_key
TAVILY_API_KEY=your_tavily_key
```

Use the variable names already defined by the project's `.env_example` and configuration code.

### Important

Never put real API keys in:

- GitHub
- README files
- Python source files
- JavaScript files
- screenshots
- test files

The `.gitignore` should exclude `.env`.

---

# Tavily API

Tavily is used by the web evidence retrieval component when web-based evidence is required.

If your configured workflow uses web evidence:

1. Create a Tavily API key.
2. Add it to your local `.env`.
3. Keep the key private.
4. Do not commit `.env`.

The local evidence functionality can still be used through the project's evidence data and retrieval components where applicable.

---

# Running the Application

From the project root, with the virtual environment activated:

```powershell
uvicorn app.main:app --reload
```

The FastAPI application will normally be available at:

```text
http://127.0.0.1:8000
```

FastAPI's interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

---

# Running the Dashboard

The dashboard is located under:

```text
dashboard/
```

The dashboard consists of:

```text
dashboard/index.html
dashboard/app.js
dashboard/style.css
```

The dashboard communicates with the backend API.

Start the backend first:

```powershell
uvicorn app.main:app --reload
```

Then open the dashboard using the project's configured frontend serving method.

If opening the HTML file directly does not work correctly because of browser/API restrictions, serve the dashboard directory using a simple local HTTP server.

For example:

```powershell
python -m http.server 5500 --directory dashboard
```

Then open:

```text
http://127.0.0.1:5500
```

---

# Running Tests

The project includes a comprehensive automated test suite.

Run all tests:

```powershell
python -m pytest -q
```

The current validated project state contains:

```text
104 passed, 1 warning
```

The warning is related to the Starlette/httpx test-client compatibility message and does not represent a failing project test.

---

# Important Test Areas

The repository contains tests covering areas including:

```text
tests/test_actions.py
tests/test_agents.py
tests/test_audit.py
tests/test_context.py
tests/test_controlplane_e2e.py
tests/test_evidence.py
tests/test_factuality_gateway_integration.py
tests/test_factuality_review_e2e.py
tests/test_feedback.py
tests/test_gateway.py
tests/test_metrics_api.py
tests/test_monitoring.py
tests/test_observability.py
tests/test_policy.py
tests/test_review_integration.py
```

These tests cover the main governance, evidence, factuality, policy, review, monitoring, and end-to-end behavior of the prototype.

---

# Example Governance Scenarios

The system is designed to distinguish between different types of requests and responses.

## Low-risk request

Example:

```text
What is the capital of India?
```

A normal request can pass request governance and continue to model invocation, subject to response governance and factuality verification.

---

## Request requiring review

A request that crosses a configured review threshold can produce:

```text
REVIEW
```

and enter the human-review workflow.

---

## High-risk request

A request that violates a blocking condition or exceeds a critical threshold can produce:

```text
BLOCK
```

without allowing unsafe processing to continue.

---

## Factuality failure

A model response containing an unsupported or insufficiently verified claim can trigger response governance.

Depending on the active policy, the response may be:

```text
ALLOW
```

```text
REVIEW
```

or

```text
BLOCK
```

---

# Risk Profile Examples

The policy engine can be inspected directly from Python.

Example:

```python
from app.policies.engine import PolicyEngine

result = PolicyEngine("customer_support").evaluate(
    [{"agent": "bias", "risk": 0.40, "status": "PASS"}],
    verification_status="VERIFIED",
)

print(result)
```

For a stricter profile:

```python
from app.policies.engine import PolicyEngine

result = PolicyEngine("regulated_decision").evaluate(
    [{"agent": "bias", "risk": 0.40, "status": "PASS"}],
    verification_status="VERIFIED",
)

print(result)
```

The regulated profile intentionally applies stricter governance thresholds and may require review for situations that are allowed by less restrictive profiles.

---

# API and Backend Components

The primary backend entry points are:

```text
app/main.py
app/api/routes.py
```

The gateway layer coordinates the request lifecycle:

```text
app/gateway/request_gateway.py
app/gateway/model_gateway.py
app/gateway/review_gateway.py
```

Governance agents are coordinated through:

```text
app/agents/orchestrator.py
```

Policy decisions are handled through:

```text
app/policies/engine.py
```

---

# Data and Evidence

The repository contains the project's local evidence resources:

```text
data/evidence.json
data/evidence_index.npz
```

These support the evidence retrieval and factuality workflow.

If the application generates additional runtime data, logs, or caches during execution, those should be treated separately from the static project evidence.

---

# Audit and Runtime Files

The application may create runtime files such as:

```text
logs/audit.jsonl
logs/feedback.jsonl
```

These files can become large because they contain runtime activity.

For a public repository, generated runtime logs should not normally be committed.

The source code and configuration required to generate logs should be committed instead.

---

# Security Considerations

This prototype is intended for demonstration and evaluation.

Before deploying it in a production environment, additional security controls would be required.

Important considerations include:

- Secure secret management
- Authentication
- Authorization
- Rate limiting
- Provider failure handling
- Production database storage
- Encryption
- Secure audit-log storage
- Access control for human reviewers
- Stronger threat modeling
- Provider-specific reliability handling
- Monitoring and alerting
- Production-grade observability
- Data retention policies
- Privacy and compliance review

The governance layer should not itself be considered a guarantee that every possible unsafe or incorrect model output will be detected.

---

# Project Limitations

This repository represents a prototype.

Some components are intentionally simplified for demonstration purposes.

In particular:

- Governance agents use configurable rule/risk logic.
- Factuality depends on the available evidence and retrieval quality.
- Web evidence depends on external services.
- LLM availability depends on the configured provider.
- Human review is implemented as a prototype workflow rather than a complete enterprise review platform.
- Runtime persistence is lightweight and can be replaced with production databases.
- Production authentication and authorization are outside the prototype scope.

---

# Design Philosophy

The main design principle is:

> **AI generation should be surrounded by explicit governance controls rather than treated as an uncontrolled model call.**

The prototype separates:

1. Request governance
2. Policy evaluation
3. Model invocation
4. Response governance
5. Factuality verification
6. Human review
7. Audit logging
8. Monitoring
9. Feedback

This separation makes the system easier to test, inspect, and extend.

---

# End-to-End Lifecycle

A complete request can follow this lifecycle:

```text
1. User submits prompt
        |
2. Request context created
        |
3. Request governance agents execute
        |
4. Request policy evaluated
        |
5. BLOCK / REVIEW / ALLOW
        |
        +---- BLOCK
        |
        +---- REVIEW -> human review
        |
        +---- ALLOW
                |
6. LLM invocation
                |
7. Model response received
                |
8. Response governance agents execute
                |
9. Factuality / evidence verification
                |
10. Response policy evaluated
                |
11. BLOCK / REVIEW / ALLOW
                |
12. Final response or review workflow
                |
13. Audit event recorded
                |
14. Metrics / monitoring updated
```

---

# Repository Structure

```text
.
├── app/
│   ├── actions/
│   ├── agents/
│   ├── api/
│   ├── audit/
│   ├── context/
│   ├── core/
│   ├── evidence/
│   ├── feedback/
│   ├── gateway/
│   ├── models/
│   ├── monitoring/
│   ├── policies/
│   └── main.py
│
├── dashboard/
│   ├── app.js
│   ├── index.html
│   └── style.css
│
├── data/
│   ├── evidence.json
│   └── evidence_index.npz
│
├── tests/
│   └── test_*.py
│
├── .env_example
├── .gitignore
├── requirements.txt
└── README.md
```

---

# Quick Start

For someone evaluating the repository, the shortest path is:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.env` from `.env_example` and configure the required provider keys.

Then run:

```powershell
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Run the tests:

```powershell
python -m pytest -q
```

Then launch/open the dashboard from:

```text
dashboard/
```

---

# Prototype Validation

The current prototype has been validated with the automated test suite:

```text
104 passed, 1 warning
```

End-to-end factuality and governance behavior has also been exercised through the project's test suite and UI workflows.

The prototype has been tested across different governance profiles and scenarios involving:

- Normal requests
- Governance checks
- Policy decisions
- Factuality
- Human review
- Risk-profile differences
- ALLOW / REVIEW / BLOCK outcomes

---

# Future Extensions

Potential future improvements include:

- Persistent production database
- Enterprise identity and access management
- More sophisticated policy authoring
- Policy versioning
- Model/provider routing
- Advanced factuality scoring
- More evidence sources
- Automated policy regression testing
- Reviewer assignment and escalation
- Compliance reporting
- Governance analytics
- Distributed monitoring
- Production-grade secrets management
- More advanced anomaly detection
- Model-specific risk calibration

---

# License

Add the license appropriate for the intended distribution of this repository.

If this is an academic or prototype submission, the repository owner should specify the applicable project/submission terms.

---

# Summary

ControlPlane AI demonstrates a governance-first architecture for LLM applications.

Instead of:

```text
User -> LLM -> Answer
```

the prototype introduces a controlled lifecycle:

```text
User
  |
  v
Request Governance
  |
  v
Policy Engine
  |
  v
LLM
  |
  v
Response Governance
  |
  v
Factuality / Evidence
  |
  v
Policy Engine
  |
  +--> ALLOW
  +--> REVIEW
  +--> BLOCK
  |
  v
Audit + Monitoring
```

This provides a foundation for building AI applications where **risk, factuality, privacy, security, human oversight, policy enforcement, and auditability are explicit parts of the system rather than afterthoughts.**
