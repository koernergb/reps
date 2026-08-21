# ADR 0005: Externally isolated Python execution

- Status: Proposed
- Date: 2026-08-20

## Recommendation

Start with Python 3.12 and its standard library. Use a purpose-built remote execution provider for private beta if it meets the threat model; otherwise operate a dedicated sandbox worker plane using hardened ephemeral microVMs. The API submits immutable jobs and receives normalized results. The browser never talks directly to the execution provider.

## Non-negotiable controls

- no execution in the web/API process;
- no provider credentials inside learner sandboxes;
- no outbound network;
- no host or cross-job mounts;
- ephemeral filesystem and unprivileged user;
- strict CPU, wall, memory, process, file, and output limits;
- protected hidden-test harness and aggregate-only failure feedback;
- rate/concurrency limits, audit metadata, and an emergency kill switch.

## Required before implementation

Compare E2B, Modal sandboxes, and a self-managed microVM design for isolation evidence, regions, cold-start latency, limits, observability, deletion, and cost. Human Gate 0 chooses the approach; Human Gate 3 must approve its deployed security behavior before public traffic.
